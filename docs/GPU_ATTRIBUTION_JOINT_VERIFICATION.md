# GPU 기여 대조·모델 로드80회 기록 공동 검증

2026-10-14 / 담당 어울 / **공동 검증 PASS, A/B 학습 보류 유지**

## 기존 중단의 기여 대조

동일 중단 파일의 `trigger.gpu_snapshot`과 저장된 worker progress를 대조했다. allocator는 PyTorch 할당 영역이고, adapter는 전체 host의 resident/committed를 포함한 보수적 계수이므로 직접 차감하거나 allocated+reserved를 합산하지 않는다.

| 기존 시도 | 시작 전체 GiB | 중단 전체 GiB | 중단 직전 자체 allocated/reserved | 단계·시간 대응 |
|---|---:|---:|---|---|
| atomic-timing-after | 2.775 | 6.164 | `not_initialized`, 값 없음 | `model_load`; snapshot/progress 약0.043초 차이 |
| atomic-timing-final | 5.778 | 6.267 | 각각786,432,000bytes = **750MiB** | `model_load`; 약0.050초 차이 |

첫 시도에서는 기록된 PyTorch allocator 증가가 없이 전체 사용량이 상승했다. **다른 작업 또는 allocator에 포함되지 않는 native/driver 영역의 기여를 의심할 근거**이며, 모든 상승이 외부 프로그램 때문이라고 확정하는 증거는 아니다. 중단 당시 프로그램별 PID 계수는 저장하지 않아 기여 프로그램을 소급 확정할 수 없다.

최종 시도는 모델이 GPU로 올라가기 전부터 전체5.778GiB로 여유가 작았다. 직전 약1초의 heartbeat에서 미초기화→observed/750MiB 전환이 확인돼 **`model_load`의 장치 초기화·모델 장치 이동 구간**이 실험 자체 증가가 관측된 단계다. 높은 기존 점유에 이 증가가 겹쳐 전체6GiB를 넘겼다. baseline과 stop의 전체 차이0.489GiB를 자체750MiB와 동일한 수치로 해석하지 않는다.

중단 snapshot의 adapter별 적용값은 `max(DedicatedUsage+SharedUsage, TotalCommitted)`다. 아래는 bytes이며 세 계수행을 세 물리 GPU라고 간주하지 않는다.

| adapter 계수행 | 첫 중단 | 최종 중단 |
|---|---:|---:|
| 1 | 835,584 | 835,584 |
| 2 | 30,343,168 | 30,343,168 |
| 3 | 6,586,839,040 | 6,697,725,952 |
| 합계 | 6,618,017,792 | 6,728,904,704 |

## 현재 프로그램 확인과 GPU 여유

모델을 띄우지 않는 Windows/CIM 조회로 adapter 전체와 GPU process PID의 **프로그램 이름·메모리 숫자만** 확인했다. 명령행·창 제목·원문·Secret은 읽지 않았다. 조회 시 전체는 약2.34GiB였으며 중단 당시 점유와 다른 현재 관측이다.

현재 확인된 응용 프로그램의 committed 예시는 Chrome PID9700 약300MiB, Steamwebhelper PID17872 약290MiB, Whale PID21092 약172MiB다. **과거 초과의 원인 프로그램으로 확정되지 않았으므로 종료 대상으로 지정하지 않았다.** dwm의 process Dedicated 값은10,239,565,824bytes로 같은 조회의 adapter Dedicated1,394,614,272bytes보다 커, 개별 process 값을 그대로 합산해 전체 점유나 원인으로 단정하지 않았다. 시스템 process나 다른 서비스를 종료하지 않았다.

공동 검증 시작 전에 새 producer의 서로 다른 시각 snapshot3개를 확인했고 모두 **2.3109436GiB**였다. 이전 정상 모델 로드의 reserved 약1.242GiB를 고려해 시작 기준을 전체≤4GiB로 보수적으로 확인했다. 이는 최소2GiB 여유를 확인하는 시작 gate이며, 실제 **중단 한도6GiB를 변경하지 않았다.**

## 공동 검증 결과

소스 `9936e85d4105759040435c48bade6c688391ea93`, probe `gpu-headroom-joint-20261014-01`, 기존 PCWSL 전용 image/runtime/GPU 연결·network none/RAM4GiB/총RAM+swap8GiB 조건에서 수행했다. 코드·학습 설정은 바꾸지 않았다.

| 항목 | 결과 |
|---|---|
| 실제 모델 로드·반복 기록 | **정상 완료**, exit0 |
| 전체 경과 | **105.791초**, 기존1800초 이내 |
| 지정 반복 기록 | **80개**, `repeated_progress` state의 위치1~80 전수 일치 |
| 모델 로드 완료 | `model_load` exit 확인 |
| 기록 순서 | sequence 순서 정상 |
| 독립 fatal / delay 로그 | 각각 **0bytes** |
| optimizer·학습·평가 | **0회** |
| final-test 내용/hash 접근 | **0회** |
| 자체 allocated / reserved | 1,307,824,640 /1,333,788,672bytes, 약1.218/1.242GiB |
| 전체 host GPU 표본 피크 | **3,908,644,864bytes = 약3.640GiB**, 6GiB 이내 |

새 피크 snapshot의 adapter 적용값은827,392 /2,363,392 /3,905,454,080bytes다. 실험 자체 allocator와 전체 host 계수를 각각 기록했다. 모델 해제·정상 기록 종료 뒤 producer PID11396와 해당 container 잔류0, 초기 가중치 hash 불변을 확인했다.

private 결과·계수·시작 여유3표본·80회 기록·가중치 보존 요약은 PCWSL `.work/model_load_probe/gpu-headroom-joint-20261014-01`과 `.work/pcwsl-runtime/gpu-headroom-joint-20261014-01`에 보존했다. Windows 역복사나 비공개 자료 Git 업로드는 없다.

**모델 로드·반복 기록 공동 검증의 미완료 조건을 해소했다.** 실제 A/B의 dry_run·학습697노출/88갱신·reload·calibration/selection 비교는 이번 범위에서 실행하지 않았으며 완료를 주장하지 않는다. A/B 재실행은 별도 지시 전까지 보류한다.
