"""Native CLI. fixture는 실제 학습을 호출하지 않는다."""
import argparse
import json
from pathlib import Path
from .contracts import ConfigError, InputError, ModelError, validate_run_config
from .runner import preflight, run_training, load_fixture_bundle, training_worker, run_fixture_evaluation
from .data import load_real_bundle


def main():
    parser = argparse.ArgumentParser(description='judgment 무다운로드 검증 CLI')
    parser.add_argument('command',choices=('preflight','train','evaluate','_train-worker'))
    parser.add_argument('--config',type=Path,required=True)
    args = parser.parse_args()
    try:
        if args.command == '_train-worker':
            result=training_worker(args.config);return 0 if result.get('trained') else 2
        payload = json.loads(args.config.read_text(encoding='utf-8'))
        config = validate_run_config(payload,real=payload.get('mode') == 'real')
        if args.command == 'preflight': result = preflight(config).values
        elif config.values['mode'] == 'fixture':
            bundle = load_fixture_bundle()
            result = (run_fixture_evaluation(bundle) if args.command == 'evaluate' else run_training(config,bundle)).values
        else:
            preflight(config)
            if args.command=='train':
                result=run_training(config,load_real_bundle(config,roles=('train','selection'))).values
            else:
                raise ConfigError('g2_policy_required_for_cli_evaluation')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if config.values['mode']=='real' and args.command=='train' and not result.get('trained') else 0
    except (ConfigError,InputError,ModelError) as e:
        print(json.dumps({'status':'blocked','code':e.code},ensure_ascii=False)); return 2
    except (OSError,ValueError,KeyError,TypeError):
        print(json.dumps({'status':'blocked','code':'invalid_local_config'},ensure_ascii=False)); return 2


if __name__ == '__main__': raise SystemExit(main())
