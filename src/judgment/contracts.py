"""입출력 계약과 원문을 포함하지 않는 오류."""
from dataclasses import dataclass
from typing import Literal
import math
import re

JSON = dict[str, object]
Split = Literal['train', 'calibration', 'selection', 'test']
ABSTAIN_ID = '__judgment_abstain__'
SOURCE_COMMIT = 'c73908d96ff73c0062c340a11bf7c54ec7d8bc4d'


class InputError(ValueError):
    def __init__(self, code): self.code = code; super().__init__(code)


class ConfigError(ValueError):
    def __init__(self, code): self.code = code; super().__init__(code)


class ModelError(ValueError):
    def __init__(self, code): self.code = code; super().__init__(code)


@dataclass(frozen=True)
class Candidate:
    id: str
    description: str


@dataclass(frozen=True)
class Turn:
    role: str
    content: str


@dataclass(frozen=True)
class Request:
    utterance: str
    question: str
    candidates: tuple[Candidate, ...]
    context: tuple[Turn, ...] = ()


@dataclass(frozen=True)
class TokenAudit:
    head_tokens: int
    total_tokens: int
    head_limit: int
    total_limit: int
    business_count: int
    model_count: int
    complete: bool


@dataclass(frozen=True)
class Scores:
    ids: tuple[str, ...]
    logits: tuple[float, ...]
    model_revision: str
    audit: TokenAudit


@dataclass(frozen=True)
class Decision:
    status: Literal['selected', 'abstained']
    selected_id: str | None
    probabilities: dict[str, float]
    abstain_probability: float
    reason: str | None
    policy_version: str
    model_revision: str
    audit: TokenAudit


@dataclass(frozen=True)
class Example:
    example_id: str
    source_id: str
    conversation_id: str
    duplicate_group: str
    request: Request
    gold_id: str | None
    tags: tuple[str, ...]


@dataclass(frozen=True)
class ScoredExample:
    example: Example
    scores: Scores
    split: Split


@dataclass(frozen=True)
class SplitBundle:
    parts: dict[Split, tuple[Example, ...]]
    manifest: JSON


@dataclass(frozen=True)
class Policy:
    version: str
    temperature_by_count: dict[int, float]
    thresholds_by_count: dict[int, tuple[float, float]]
    calibration_digest: str
    selection_digest: str


@dataclass(frozen=True)
class RunConfig:
    values: JSON


@dataclass(frozen=True)
class RunEvidence:
    values: JSON


@dataclass(frozen=True)
class Report:
    values: JSON


def text(value, code):
    if not isinstance(value, str) or not value.strip(): raise InputError(code)
    return value


def validate_request(payload: JSON) -> Request:
    if not isinstance(payload, dict): raise InputError('invalid_request')
    utterance = text(payload.get('utterance'), 'empty_utterance')
    question = text(payload.get('question'), 'empty_question')
    cs = payload.get('candidates')
    if not isinstance(cs, list): raise InputError('invalid_candidates')
    if not cs: raise InputError('empty_candidates')
    candidates, ids = [], set()
    for c in cs:
        if not isinstance(c, dict): raise InputError('invalid_candidate')
        cid = text(c.get('id'), 'empty_id')
        description = text(c.get('description'), 'empty_description')
        if cid == ABSTAIN_ID: raise InputError('reserved_id')
        if cid in ids: raise InputError('duplicate_id')
        ids.add(cid); candidates.append(Candidate(cid, description))
    context = payload.get('context', [])
    if not isinstance(context, list): raise InputError('invalid_context')
    turns = []
    for turn in context:
        if not isinstance(turn, dict): raise InputError('invalid_context')
        role = turn.get('role')
        if role not in ('user', 'assistant', 'system'): raise InputError('invalid_role')
        turns.append(Turn(role, text(turn.get('content'), 'empty_context')))
    return Request(utterance, question, tuple(candidates), tuple(turns))


def positive(value, code, *, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ConfigError(code)
    if integer and not isinstance(value, int): raise ConfigError(code)
    return value


def validate_run_config(payload: JSON, *, real: bool) -> RunConfig:
    if not isinstance(payload, dict) or payload.get('mode') not in ('fixture', 'real'):
        raise ConfigError('invalid_mode')
    if real:
        if payload['mode'] != 'real': raise ConfigError('real_required')
        required = ('approval', 'canonical_checkout', 'model_dir', 'model_revision', 'source_commit',
                    'device', 'work_dir', 'resources', 'training', 'data_manifest', 'split_paths', 'seed', 'code_revision')
        if any(payload.get(k) is None for k in required): raise ConfigError('missing_real_config')
        if payload['source_commit'] != SOURCE_COMMIT: raise ConfigError('source_revision')
        if not isinstance(payload['model_revision'], str) or not re.fullmatch(r'[0-9a-f]{40}', payload['model_revision']):
            raise ConfigError('immutable_model_revision')
        if payload['model_revision'] == SOURCE_COMMIT: raise ConfigError('distinct_revisions_required')
        if payload['device'] not in ('cpu', 'cuda', 'mps'): raise ConfigError('explicit_device_required')
        if isinstance(payload['seed'], bool) or not isinstance(payload['seed'], int): raise ConfigError('seed')
        if not isinstance(payload['approval'], dict) or payload['approval'].get('gate') != 'G1' or not payload['approval'].get('confirmed'):
            raise ConfigError('g1_required')
        if not isinstance(payload['resources'], dict): raise ConfigError('resources')
        if 'shared_runtime_image_bytes' in payload['resources']:
            image_bytes = payload['resources']['shared_runtime_image_bytes']
            if isinstance(image_bytes, bool) or not isinstance(image_bytes, int) or image_bytes < 0:
                raise ConfigError('shared_runtime_image_bytes')
        for key in ('disk_limit_bytes', 'estimated_disk_bytes', 'ram_limit_bytes', 'time_limit_seconds', 'checkpoint_bytes'):
            positive(payload['resources'].get(key), key)
        if payload['device'] == 'cuda': positive(payload['resources'].get('vram_limit_bytes'), 'vram_limit_bytes')
        training = payload['training']
        if not isinstance(training, dict): raise ConfigError('training')
        for key in ('epochs', 'micro_batch', 'grad_accum'): positive(training.get(key), key, integer=True)
        for key in ('encoder_lr', 'head_lr'): positive(training.get(key), key)
        if not isinstance(training.get('freeze_encoder'), bool) or training.get('precision') not in ('fp32', 'fp16', 'bf16'):
            raise ConfigError('training_scope_precision')
        if not isinstance(payload['split_paths'], dict) or set(payload['split_paths']) != {'train', 'calibration', 'selection', 'test'}:
            raise ConfigError('split_paths')
    return RunConfig(dict(payload))
