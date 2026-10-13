"""Native CLI. fixture는 실제 학습을 호출하지 않는다."""
import argparse
import json
from pathlib import Path
from .contracts import ConfigError, InputError, ModelError, validate_run_config
from .runner import preflight, run_training, load_fixture_bundle, training_worker


def main():
    parser = argparse.ArgumentParser(description='judgment 무다운로드 검증 CLI')
    parser.add_argument('command',choices=('preflight','train','evaluate','_train-worker'))
    parser.add_argument('--config',type=Path,required=True)
    args = parser.parse_args()
    try:
        if args.command == '_train-worker':
            training_worker(args.config); return 0
        payload = json.loads(args.config.read_text(encoding='utf-8'))
        config = validate_run_config(payload,real=payload.get('mode') == 'real')
        if args.command == 'preflight': result = preflight(config).values
        elif config.values['mode'] == 'fixture':
            result = run_training(config,load_fixture_bundle()).values
            if args.command == 'evaluate': result.update(status='fixture_contract_only',real_evaluation=False)
        else:
            # 실데이터 mapping·정책 sidecar·독립 평가 파일 계약은 G1에서 확인한다.
            preflight(config)
            raise ConfigError('g1_real_mapping_and_policy_required')
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
    except (ConfigError,InputError,ModelError) as e:
        print(json.dumps({'status':'blocked','code':e.code},ensure_ascii=False)); return 2
    except (OSError,ValueError,KeyError,TypeError):
        print(json.dumps({'status':'blocked','code':'invalid_local_config'},ensure_ascii=False)); return 2


if __name__ == '__main__': raise SystemExit(main())
