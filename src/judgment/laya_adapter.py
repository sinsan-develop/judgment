"""고정 Laya 경계. 실모델 생성은 G1 이후의 로컬 자산만 허용한다."""
from pathlib import Path
import json
import os
import re
import subprocess
from contextlib import contextmanager
from .contracts import SOURCE_COMMIT, ABSTAIN_ID, TokenAudit, Scores, InputError, ConfigError, ModelError

ABSTAIN_DESCRIPTION = '해당 없음 또는 주어진 맥락만으로 판단할 수 없음'


@contextmanager
def offline():
    keys = ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE')
    old = {k: os.environ.get(k) for k in keys}
    for k in keys: os.environ[k] = '1'
    try: yield
    finally:
        for k, v in old.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v


class LayaAdapter:
    def __init__(self, backend): self.backend = backend

    @classmethod
    def from_backend(cls, backend):
        if backend.source_commit != SOURCE_COMMIT: raise ConfigError('source_revision')
        return cls(backend)

    @classmethod
    def from_local(cls, model_dir: Path, *, source_commit: str, model_revision: str, device: str):
        if source_commit != SOURCE_COMMIT: raise ConfigError('source_revision')
        if model_revision == source_commit: raise ConfigError('distinct_revisions_required')
        if not isinstance(model_revision, str) or not re.fullmatch('[0-9a-f]{40}', model_revision): raise ConfigError('immutable_model_revision')
        model_dir = model_dir.resolve()
        required = ('rl_agent_config.json', 'model.safetensors', 'tokenizer', 'encoder', 'judgment_provenance.json')
        if any(not (model_dir / p).exists() for p in required): raise ConfigError('missing_local_checkpoint')
        provenance = json.loads((model_dir / 'judgment_provenance.json').read_text(encoding='utf-8'))
        if provenance.get('model_id') != 'convaiinnovations/laya-multilingual' or provenance.get('model_revision') != model_revision:
            raise ConfigError('model_provenance')
        if device not in ('cpu', 'cuda', 'mps'): raise ConfigError('explicit_device_required')
        with offline():
            return cls(_LocalBackend(model_dir, source_commit, model_revision, device))

    def render(self, request):
        criteria = {c.id: c.description for c in request.candidates}
        if ABSTAIN_ID in criteria or len(criteria) != len(request.candidates): raise InputError('invalid_ids')
        criteria[ABSTAIN_ID] = ABSTAIN_DESCRIPTION
        state = json.dumps({'past_dialogue': [dict(role=t.role, content=t.content) for t in request.context],
                            'current_utterance': request.utterance}, ensure_ascii=False)
        return {'state': state, 'question': {'type': 'choice', 'instructions': request.question, 'criteria': criteria}}

    def _prepare(self, request):
        p = self.backend.prepare(self.render(request))
        original, actual = p['original_options'], p['actual_options']
        if len(actual) != len(original): raise InputError('token_budget')
        if len(set(map(tuple, actual))) != len(actual): raise InputError('option_collision')
        if (original != actual or p['original_head'] != p['actual_head'] or p['original_state'] != p['actual_state']
                or p['head_tokens'] > self.backend.head_limit or p['total_tokens'] > self.backend.total_limit):
            raise InputError('token_budget')
        audit = TokenAudit(p['head_tokens'], p['total_tokens'], self.backend.head_limit, self.backend.total_limit,
                           len(request.candidates), len(original), True)
        return p, audit

    def audit(self, request): return self._prepare(request)[1]

    def score(self, request):
        p, audit = self._prepare(request)
        logits = tuple(self.backend.raw_logits(p))
        ids = tuple(c.id for c in request.candidates) + (ABSTAIN_ID,)
        if len(logits) != len(ids): raise ModelError('score_shape')
        return Scores(ids, logits, self.backend.model_revision, audit)

    def finetune(self, train_path, selection_path, output_dir, *, config):
        from .contracts import validate_run_config
        c = validate_run_config(config.values, real=True).values
        if not isinstance(self.backend, _LocalBackend): raise ConfigError('real_backend_required')
        if str(train_path.resolve()) == str(selection_path.resolve()): raise ConfigError('split_overlap')
        with offline():
            from laya.train import TrainConfig, finetune
            t = c['training']
            cfg = TrainConfig(epochs=t['epochs'], micro_batch=t['micro_batch'], grad_accum=t['grad_accum'],
                              encoder_lr=t['encoder_lr'], head_lr=t['head_lr'], freeze_encoder=t['freeze_encoder'],
                              seed=c['seed'], amp=t['precision'] != 'fp32', loss='soft-ce', shuffle_options=('choice',),
                              calib_frac=0, calib_max=0, eval_data=str(selection_path))
            return finetune(str(train_path), str(self.backend.model_dir), str(output_dir), config=cfg, device=c['device'])


class _LocalBackend:
    def __init__(self, model_dir, source_commit, model_revision, device):
        import laya
        root = Path(laya.__file__).resolve().parents[1]
        try:
            actual_commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
            dirty = subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=no'], text=True)
        except (OSError, subprocess.CalledProcessError): raise ConfigError('unverified_upstream_source') from None
        if actual_commit != source_commit or dirty: raise ConfigError('source_revision')
        from laya import common
        from laya.agent import Agent
        from transformers import AutoTokenizer
        from safetensors.torch import load_file
        import torch
        self.common, self.Agent, self.torch = common, Agent, torch
        self.model_dir, self.source_commit, self.model_revision, self.device = model_dir, source_commit, model_revision, device
        self.cfg = json.loads((model_dir / 'rl_agent_config.json').read_text(encoding='utf-8'))
        if self.cfg.get('option_layout', 'sequential') != 'sequential': raise ConfigError('unsupported_layout')
        self.head_limit, self.total_limit = self.cfg['head_max_len'], self.cfg['max_len']
        self.tok = AutoTokenizer.from_pretrained(str(model_dir / 'tokenizer'), local_files_only=True)
        self.model = common.build_model(self.cfg, encoder_dir=str(model_dir / 'encoder'), pretrained=False)
        self.model.load_state_dict(load_file(str(model_dir / 'model.safetensors')), strict=True)
        self.model.to(device).eval()  # OOM을 CPU 자동 전환으로 숨기지 않는다.

    def prepare(self, rendered):
        c, tok = self.common, self.tok
        q = self.Agent._to_internal(rendered['question'])
        texts = [rendered['question']['instructions'], rendered['state']] + c.render_options(q)
        if any(s and any(token in s for token in tok.all_special_tokens) for s in texts):
            raise InputError('special_token_loss')
        full_options = [tuple(c._encode_question_text(tok, ' ' + s, add_special_tokens=False)['input_ids']) for s in c.render_options(q)]
        full_head = tuple(c._encode_question_text(tok, 'choice question: ' + q['ins'], add_special_tokens=False)['input_ids'])
        head, hm, _ = c.build_head(tok, q, self.head_limit)
        actual_options = [tuple(head[a+1:b]) for a, b in zip(hm, hm[1:] + [len(head)-1])]
        actual_head = tuple(head[1:hm[0]-1])
        full_state = tuple(c.encode_text(tok, c.serialize_state(rendered['state']), add_special_tokens=False)['input_ids'])
        ids, markers, stats, trunc = c.build_sequence(tok, rendered['state'], q, self.total_limit, self.head_limit,
                                                     return_stats=True, return_truncation_stats=True)
        return dict(original_options=full_options, actual_options=actual_options, original_head=full_head,
                    actual_head=actual_head, original_state=full_state, actual_state=tuple(ids[len(head):-1]),
                    head_tokens=len(head), total_tokens=len(ids), ids=ids, markers=markers)

    def raw_logits(self, p):
        torch = self.torch
        ids = torch.tensor([p['ids']], dtype=torch.long, device=self.device)
        markers = torch.tensor([p['markers']], dtype=torch.long, device=self.device)
        with torch.no_grad():
            out = self.model(ids, torch.ones_like(ids), markers, torch.ones_like(markers, dtype=torch.bool),
                             torch.zeros(1, dtype=torch.long, device=self.device))
        return tuple(out[0][0, :len(p['markers'])].float().cpu().tolist())
