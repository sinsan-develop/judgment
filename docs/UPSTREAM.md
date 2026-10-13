# upstream 실행 계약

소스 고정: v0.4.6 / `c73908d96ff73c0062c340a11bf7c54ec7d8bc4d`. 모델은 `convaiinnovations/laya-multilingual`의 별도 immutable revision을 G1에서 정한다. 소스 SHA를 모델 SHA로 대체하지 않는다.

읽기 전용 확인 출처: [train.py](https://github.com/NandhaKishorM/laya/blob/c73908d96ff73c0062c340a11bf7c54ec7d8bc4d/laya/train.py), [common.py](https://github.com/NandhaKishorM/laya/blob/c73908d96ff73c0062c340a11bf7c54ec7d8bc4d/laya/common.py), [agent.py](https://github.com/NandhaKishorM/laya/blob/c73908d96ff73c0062c340a11bf7c54ec7d8bc4d/laya/agent.py).

`TrainConfig`와 `finetune(data, model_dir, output_dir, config, device)`를 지연 import한다. 선택형 질문은 type/instructions/criteria, gold는 질문 ID별 probabilities다. soft-ce, shuffle_options=('choice',), calib_frac=0, calib_max=0, eval_data=selection을 명시한다. 외부 calibration·test를 upstream에 전달하지 않는다.

`common.build_head`, `build_sequence`, `Agent._to_internal`을 그대로 사용한다. head/total budget뿐 아니라 개별 후보 48 token 제한과 질문 잘림도 원형 token span과 비교한다. mask·special token 정리로 원문이 바뀔 수 있는 입력은 거절한다. raw logits만 반환하며 confidence·upstream 보정을 결과 확률로 재사용하지 않는다.

실제 로딩은 로컬 encoder/tokenizer/model/config와 모델 provenance를 요구한다. upstream checkout의 HEAD와 tracked dirty 상태를 검사한다. wheel만 있고 source 증거가 없으면 실행을 차단한다. HF/Transformers offline과 local_files_only를 사용한다.

현재 fake tokenizer/backend 시험만 수행했다. 실제 tokenizer·raw logit shape·PyTorch 호환성은 G1 이후 검사 전까지 미검증이다. upstream 소스·가중치 자체는 이 저장소에 복제하지 않는다.
