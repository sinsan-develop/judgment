# A 저장 상태·감시 보완·재학습 없는 후속 범위 검토

2026-10-14 / 담당 어울 / **A 재학습·모델 로드·평가·B 실행은 하지 않음**

## A의 저장 상태

중단 trial `approved-unified-worker-ab-20261014-01`, source `610a8b414421ae39e6b30505c3ce8d0b2100eb34`. A run의 저장 산출물과 승인 설정·완료 이벤트를 현지에서 읽었다. 실행 설정은 trial A의 승인 설정과 정확히 같다. 원본 학습 입력과 선택 입력도 존재한다.

| 확인 항목 | 판정 |
|---|---|
| optimizer 완료 exit 이벤트 | **88개**, 마지막 completed/expected88 |
| 입력 노출 위치 | **697** |
| `train_model` exit | **있음**, 88갱신 완료 뒤 후속 평가 진입 |
| epoch 종료 checkpoint | **있음**, `output/checkpoint_latest` |
| 가중치 파일 | **643,835,524bytes / 170 tensor** |
| 가중치 SHA256 | `ecb8e425645ad42755841e9d960f0c03e9ea361a1bb960912d2c8d8a0b2f1339` |
| safetensors 헤더·offset | 전부 payload 범위 이내 |
| CPU 전체 payload 검사 | **구간 연속·shape별 byte 수 일치·NaN/Inf0개** |
| 초기 대비 tensor 이름·shape | **일치** |
| encoder tensor 변경 | **0개** |
| head tensor 변경 | **32개** |
| checkpoint dtype | **F16** |
| checkpoint 모델 설정 | 초기 모델 설정과 차이 없음 |
| encoder config·tokenizer·tokenizer 설정 | 저장돼 있음 |
| 최종 output 모델·최종 모델 설정 | **없음** |
| `train_report.json`·`questions.json`·worker `summary.json` | **없음** |
| checkpoint의 `judgment_provenance.json` | **없음**, 복구 실행 때 검증된 참조 필요 |

고정 upstream의 `train_model`은 epoch 끝 callback에서 checkpoint를 저장한다. 기록은 callback을 포함한 train_model 반환 후 후속 평가로 진입했다. 따라서 **88갱신 학습을 마친 epoch checkpoint와 승인 설정·완료 기록이 보존된 것**은 확인된다. 다만 전체 finetune 종료·최종 모델·최종 평가 보고서가 완성된 것으로 승격하지 않는다.

가중치 구조와 tensor별 byte hash, 전체F16 payload의 NaN/Inf0개·구간 연속성·shape별 byte 수를 CPU로 검사했고 모델/torch를 로드하지 않았다. 실제 엄격한 state_dict 로드와 모델 추론은 아직 확인하지 않았다. 후속 실행의 첫 단계로 이 검사를 해야 한다. SHA256은 이후 원본 checkpoint 불변 검증 기준이다.

특히 upstream `save_checkpoint`는 **fp32 live tensor를 `.half().cpu()`로 저장**한다. 저장 checkpoint로 A 평가를 복구할 수 있지만, 중단 당시 live fp32의 평가를 bit 단위로 그대로 이어갈 수는 없다. 학습 재개가 아니라 **완료된 A의 저장 모델 기준 후속 평가**로 다뤄야 한다. optimizer state도 없으며 A의 추가 갱신을 수행하지 않는다.

## snapshot 실패의 직접 근거와 최소 보완

기존 producer 독립 로그는 snapshot 작업 **1.000330초 timeout / stop_seen=false**를 남겼다. serialize/open/write/flush/fsync(skip)/close는 계측 완료됐고 replace 계측은 완료되지 않았다. `atomic_json`의 `os.replace` 구간에서 완료를 기다리다 상한을 넘긴 것으로 좁혀진다. 물리 rename 지연과 스케줄링·GIL 재개 기여는 나눠 확정할 수 없다. 이후 오래된 표본이15초를 넘겨 global guard가 `resource_monitor_unavailable`로 중단했다. 당시 전체 GPU 표본 피크5.748GiB이며 6GiB 초과 중단은 아니다.

감시용 일시 snapshot만 **두 고정 슬롯에 번갈아 쓰고 flush**하도록 바꿨다. 공통 reader는 기본 파일과 두 슬롯의 JSON을 읽어 완성되고15초 이내인 값 중 최신을 선택한다. 한 슬롯 쓰기 중 JSON이 미완성이면 다른 슬롯을 사용하고, 모두 없거나 stale이면 기존 실패로 종료한다. writer는 더 이상 파일 교체·fsync를 하지 않는다. 원본 primary를 읽는 호환은 유지하고 baseline·각arm 시작 조건·독립 guard도 같은 reader를 사용한다. 실제 쓰기 예외·작업1초 timeout·15초 stale·6GiB·시간·해당 worker만 종료하는 기존 정책은 유지한다. 일반 진행·optimizer·중단 기록의 durable 방식은 바꾸지 않았다.

새 producer source `da0c512`의 모델 없는 검증:

- replace 실패 주입에도 live 저장 성공, 미완성 슬롯 우회, stale 거절,6GiB+1byte 값 그대로 전달, 쓰기 예외와 timeout 구분·정상 종료 요청 처리: **6시험 PASS**, PCWSL6 PASS.
- 기존 GPU snapshot6/start gate2/telemetry19 중18PASS1skip. 전체 Windows **130개 중126PASS/조건부4skip**.
- PCWSL 실제 CIM producer와 공통 reader는 **600.523초 / producer exit0**,486표본·2967정상읽기·읽기실패0·오류로그0bytes·최대표본나이5.054초·최대표본간격5.083초로 확인했다. 이전 약534초 중단보다 길다. 모델·torch·GPU context·학습은 생성하지 않았다. 감시 기록은 현지 `snapshot-slots-600-20261014-01`에 보존했다.
- 실제 슬롯의6GiB+1byte와 미완성 다른 슬롯으로 독립 guard를 검증했다. owned dummy worker는exit3/vram_limit로 종료됐고 무관 대조 dummy는 생존했다. 실제 서비스는 조작하지 않았다. 모델없는 장시간 검증이므로 모델 학습 부하 아래의 새 슬롯 방식은 아직 미검증이다.

## 재학습 없이 이어갈 수 있는 범위

**조건부 가능**하다. A의 저장 checkpoint로 평가를 수행하고 B를 원래 초기 가중치에서 한 번 학습하면 저장 모델끼리 비교할 수 있다. 원래 live 모델 후속 평가의 완전한 재개나 기존 final completion 증거와 동일하다고 표현할 수는 없다. 원래 run의 미완료 산출물을 덮어쓰지 않고 별도 후속 결과로 provenance·원본 checkpoint hash·완료88 이벤트·수정 소스 SHA를 연결해야 한다.

현재 엄격한 adapter는checkpoint에없는provenance파일을요구한다. 승인 후 원본checkpoint를보존한복구용산출물에초기모델참조·파생checkpoint hash·승인설정/완료88·원래run/source를명시해검증가능한provenance를붙이는최소준비가필요하다. 공식초기모델그자체나기존완료모델로오인시키지않는다. 후속 실행기에는남은1230초 단일deadline과 A검사/저장모델평가→자원해제→조건재확인→B만 실행하는 분기가 필요하며, 기존 `run`을 그대로 호출해 A를 재학습해서는 안 된다. 이 후속 실행기는 이번 요청에서 구현·실행하지 않았다.

승인 시 필요한 범위:

1. 같은 검증된 image/interpreter/cwd/module/child 경로에서 fresh GPU3표본≤2.75GiB 확인, A checkpoint hash·170tensor strict 로드·finite/encoder불변 검증. 기존 체크포인트는 read-only 보존한다.
2. A 추가 학습/optimizer0. 저장 checkpoint의 원시 점수로 calibration/selection 후속 평가를 수행하고 calibration에서만 기존 방식의 보정을 맞춘다. 누락된 train report나 당시 live 평가 값을 만들어 완료로 표시하지 않는다.
3. A 모델 해제·active worker0·allocated/reserved0을 확인하고 **새 fresh3표본≤2.75GiB**에서만 B를 같은 고정 초기 가중치로 시작한다. B는 기존280선별·49잠정 정답 수정·고정 반복/ID/그룹/순서·697노출88optimizer·동일학습설정이다.
4. B도 저장/reload 모델 기준 calibration/selection로 비교한다. A/B 저장 정밀도를 대칭으로 유지하고, 결과는 선별·정답 수정·반복 노출의 합친 효과로 해석한다. final-test 내용/hash는 계속 열지 않는다.
5. 실패하면 자동 재시도 없이 단계·완료 갱신 수·정확한 최종수 확인 여부·traceback/독립 오류·allocator/adapter 메모리를 보존한다. 타서비스·프로그램은 종료하지 않고6GiB를 올리지 않는다.

## 추가 실행 시간 제안

기존 A/B 승인의1800초는 A+B 전체 한도다. 첫 실행의 준비·정리를 포함한 소비 시간은568.763초였으므로 남은 보수적 예산은 **1231.237초**다. 추가 실행 상한을 **1230초**로 제안해 누적1798.763초 이내로 제한한다. 모델 없는 이번 진단/감시 검증은 학습 재실행이 아니며 이 후속 학습 예산을 리셋하는 근거로 사용하지 않는다.

1230초는 checkpoint 검사·A 평가·자원 해제/조건 재확인·B 학습/평가·최종 비교를 합친 하나의 deadline이다. 계획상 A 검사·평가에 최대300초, B 학습·저장/평가에 최대900초, 조건 재확인·정리에30초를 배분할 수 있지만 이는 성공 ETA가 아니다. B 시작 전 전체 남은 시간과 여유를 다시 확인하고 부족하면 B를 시작하지 않는다. 초과 시 기존 guard로 중단한다. 전체 성공에 시간이 부족하다면 한도를 자동 연장하지 않고 별도 승인으로 처리해야 한다.

**현재는 조사·감시 보완·모델 없는 검증·범위/시간 제안까지다. 후속 A 평가나 B를 자동 실행하지 않는다.**
