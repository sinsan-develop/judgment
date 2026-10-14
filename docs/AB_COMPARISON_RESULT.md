# 승인된 A/B 비교 실행 기록 — A 중단·B 미시작

2026-10-14 / 담당 어울 / **최신 승인 시도: A 학습 전 선택 평가에서 GPU 상한 중단/exit3, B 미시작, 비교 결과 미산출**

## 최신 판정 — 공동 검증 여유 기준 승인 A/B 1회

시도 `approved-headroom-ab-20261014-01`, 실행 소스 `17b79ff88707c23715718f36e8ef6d0b8029a89b`. 공동 검증의 시작2.311GiB/추가 관측 약1.329GiB/reserved1.242GiB를 근거로 시작≤4GiB gate를 사용했다. 새 시각 GPU 표본3개가 모두 **2.5528946GiB**로 최소2GiB 여유 조건을 충족한 뒤 승인된 실제1회만 시작했다. 기존 초기 가중치·학습 설정·697노출/88갱신 계획·GPU6GiB·총1800초를 유지했다.

**A가 parent 관측75.971초에 host GPU6.877GiB 초과로 중단됐고, B는 시작하지 않았다.** 실제 A/B 결과는 없으며 자동 재시도0회다. worker 종료 코드3, 사유 `vram_limit`이다. 마지막 저장 optimizer 완료는 **0회**, `not_started`; 저장 기록 age 약2.649초로 정확한 종료 순간 횟수는 미확인이다.

이번 실행은 모델 로드·입력 검사·dry_run·probe 해제·finetune 모델 로드를 지나 **`before_training_selection`**, 즉 학습 전 선택 자료 평가 단계에서 실험 자체 GPU 사용량 증가가 관측됐다.

| 저장된 시점 | 자체 allocated bytes | reserved bytes | peak allocated bytes |
|---|---:|---:|---:|
| 학습 전 선택 평가 enter | 1,341,379,072 | 1,367,343,104 | 1,341,379,072 |
| 다음 heartbeat | 1,341,379,584 | 3,212,836,864 | 2,712,117,760 |
| 마지막 heartbeat | 1,341,379,584 | **4,303,355,904** | **3,004,742,656** |

reserved 최대는 **4.008GiB**, peak allocated는 **2.798GiB**다. allocated와 reserved를 합산하지 않는다. 모델 로드 공동 검증의 reserved1.242GiB는 뒤 단계의 이 피크를 포함하지 않았다. 따라서 이번 시작 여유 기준은 모델 로드에는 충분했으나 실제 A의 다음 경로 사용량까지 보장하지 못했다. 기존 점유와 실험 자체 증가가 함께 전체 한도에 기여했으며, 특정 다른 프로그램을 이번 초과의 원인으로 단정하지 않는다.

| 중단 자원 표본 | 값 |
|---|---:|
| host GPU 피크·중단 계수 | **7,383,695,360bytes ≈6.877GiB**, 승인6GiB 초과 |
| 마지막 worker 자체 RSS | 2,094,268,416bytes |
| parent+worker RAM 표본 피크 | 2,494,324,736bytes |
| 저장 표본 | 17,974,205,756bytes, 30GiB 이내 |
| adapter 계수행1/2/3 적용값 | 827,392 /2,392,064 /7,380,475,904bytes |

adapter 적용값은 각 `max(DedicatedUsage+SharedUsage, TotalCommitted)`로 전체 host를 포함하고, 자체 allocator와 같은 범위가 아니다. 메모리 조회 실패는 없다. 독립 fatal 로그는0행이다. 일반 `submit.wait_timeout` 지연1건은 `model_load`에서 경고로 남고 실행은 계속됐다. 이 기록 지연이 이번 중단 사유는 아니다.

원본8파일·초기 가중치 hash 불변을 확인했다. 검증·시험 자료를 optimizer에 넣지 않았고 final-test 내용/hash는 다시 열지 않았다. 비교용 calibration/selection 측정은 도달하지 못했고, 진행 중인 upstream의 학습 전 selection 평가는 A의 정상 완료 또는 비교 결과로 승격하지 않았다. 선별280건·잠정 정답49건·반복 노출의 합친 효과는 미측정이다.

이번 container와 producer PID12278 잔류0/producer exit0을 확인했고 다른 프로그램·서비스·driver·6GiB·학습 설정은 변경하지 않았다. PCWSL trial에 고정 입력·설정·worker 단계/중단/종료/독립 로그·`interrupted.summary.private.json`을 보존했다. Windows 비공개 역복사와 비공개 자료 Git 업로드는 없다. 승인1회는 소진됐으며 추가 수정·학습·자동 재시도를 하지 않는다.

## 이전 시도 — 독립 오류 로그 적용 승인 A/B 1회

시도 `approved-independent-log-ab-20261014-01`, 소스 `acabafb8b31e51d6d4639d25b295d91f844d0a35`. 기존 검증된 코드를 바꾸거나 모델 로드 시험을 반복하지 않고 승인된 실제 비교1회만 실행했다. 시작 전체 GPU **0.8296GiB≤6GiB**, 동일 초기 가중치·학습 설정·각697노출/88갱신 계획·총1800초를 유지했다. **A parent 관측69.858초에 실패, B 미시작, 비교 결과 없음, 자동 재시도0**이다.

독립 최소 오류 로그는 최초 실패를 다음과 같이 보존했다.

| 항목 | 저장 값 |
|---|---|
| 실패 호출·코드 | `submit.wait_timeout` — `Telemetry._submit()`의 완료 event 대기 |
| 오류 분류 | `TimeoutError`; 실제 caller에는 `ConfigError(telemetry_unavailable)`로 전달 |
| 당시 writer 진행 호출 | `writer.atomic_json` |
| 단계 | `model_load` |
| 저장 완료 optimizer | **0회** |
| OS errno/예외 호출 stack | 없음; OS 예외가 아니라 1초 완료 대기 초과로 직접 분류 |

정확히 확인된 직접 원인은 **기록 요청의 완료 event가 기존1초 제한 안에 설정되지 않은 것**이다. 당시 writer가 `atomic_json()`을 처리 중이었다. 이 함수의 JSON 직렬화·flush·fsync·replace 중 어느 작업이 지연됐는지, 저장 장치/스케줄링/모델 import 중 어느 요인이 기여했는지는 기록되지 않아 미확인이다. 디스크 오류나 GPU 오류로 단정하지 않는다. `TimeoutError`는 최소 로그의 진단 분류이며 실제 OS가 던진 예외를 발견했다는 의미가 아니다.

worker의 독립 guard가 `telemetry_unavailable`을 감지해 **종료 코드3**으로 스스로 중단했다. parent 종료 요청은 `false`이고 결과의 `worker_failed`는 이 worker 종료의 요약이다. 이번 `/proc` 실패는 없었다. worker guard 경과65.981초, 마지막 단계 `model_load`, optimizer `not_started`, 마지막 progress age 약2.495초다. **정확한 종료 순간 optimizer 횟수는 미확인**이며 저장 완료0회와 구분한다. 모델 로드 완료 기록·학습·reload·평가는 없다.

| 자원 | 관측 |
|---|---:|
| 전체 host GPU 표본 피크 | **891,256,832bytes ≈0.830GiB**, 6GiB 이하 |
| parent+worker RAM 표본 피크 | 1,452,101,632bytes |
| 마지막 worker 자체 RSS | 1,084,428,288bytes |
| 마지막 worker GPU allocator | `not_initialized`, allocated/reserved 값 없음 |
| 저장 표본 | 17,968,241,111bytes, 30GiB 이하 |

마지막 유효 snapshot의 adapter 계수행별 적용값은831,488 /30,343,168 /859,549,696bytes다. 각 `max(DedicatedUsage+SharedUsage, TotalCommitted)`이며 다른 작업/committed도 포함한다. 실험 자체 VRAM이나 마지막 snapshot을 표본 피크와 동일한 값으로 해석하지 않는다.

원본8파일·초기 가중치 hash 불변, final-test 내용/hash 비접근을 확인했다. calibration/selection 평가까지 도달하지 못했으므로 자료 선별·잠정 정답 수정·반복 노출의 합친 효과를 측정하지 못했다. 해당 container와 producer PID8338 잔류0/producer exit0을 확인했다. 다른 서비스·driver·한도·학습 설정 변경, Windows 비공개 역복사는 없다. PCWSL trial에 `interrupted.summary.private.json`과 연결 worker의 독립 오류 로그·종료/단계 기록을 보존했다. 승인 학습1회는 소진됐으며 중단 후 추가 수정·학습은 수행하지 않는다.

## 이전 시도 — 수정 감시 코드 승인 재실행 1회

시도 `approved-monitor-retry-20261014-01`, 실행 소스 `d0d5b876ed2c714d985c7668e1adb13948a10420`. 현지 사전 시험은 최초 dummy 종료 타이밍 때문에 의도한 조회 경합이 발생하지 않아 1개 실패했다. 실제 학습은 시작하지 않은 상태에서 시험을 release 파일·실제 wait로 동기화했다. 이후 현지 4개 시험 PASS/장시간 시험1개 skip 확인 후 승인된 실제 A/B 1회를 실행했다. 이전 180초 검증을 반복하거나 학습을 자동 재시도하지 않았다.

시작 GPU 기준값은 **0.8677GiB≤6GiB**였다. A parent 관측 경과 **3.735초**, worker 자체 guard 경과 **1.762초**에 worker가 `telemetry_unavailable`을 감지해 **exit3**으로 스스로 중단했다. parent 결과의 `worker_failed`는 이 종료의 요약이다. parent의 `termination_requested=false`, 종료 코드3 기록을 확인했다. **A 완료 조건 미충족으로 B 미시작, A/B 결과 미산출, 자동 재시도0회**다.

| 항목 | 마지막 기록/표본 |
|---|---:|
| 마지막 worker 단계 | `model_load` |
| 마지막 저장 완료 optimizer | **0회**, `not_started` |
| 종료 순간 정확한 optimizer 완료 수 | 미확인; 저장 기록 age 약1.228초 |
| worker 자체 RSS | 38,576,128bytes |
| worker 자체 GPU allocator | `not_initialized`; allocated/reserved 값 없음 |
| parent+worker RAM 피크 | 82,612,224bytes |
| 전체 host GPU 피크 | **930,045,952bytes ≈0.866GiB**, 6GiB 이하 |
| 저장 표본 | 17,962,839,642bytes, 30GiB 이하 |

마지막 유효 snapshot의 adapter 계수행1/2/3 적용값은 각각831,488 /30,343,168 /898,871,296bytes다. 적용값은 각 행 `max(DedicatedUsage+SharedUsage, TotalCommitted)`이며 실험 자체 VRAM이 아니다. 원문 없는 전체 계수는 위 GPU 피크로 합산했다.

이번에는 `/proc` 조회 오류와 그에 따른 `monitor_observation`이 **발생하지 않았다**. 따라서 worker가 먼저 사라져 조회가 실패한 사례가 아니라 **worker의 독립 감시가 기록 실패 flag를 확인해 스스로 중단한 사례**다. 코드상 해당 flag는 기록 쓰기 예외, queue 부족, bounded 기록 대기 실패, sampler 예외에서 설정될 수 있다. 어느 하위 조건이 발생했는지는 구분 기록이 없어 미확인이다. 마지막 `model_load` heartbeat 이후 기록이 멈춘 사실만으로 fsync 시간 초과·권한·디스크 오류·모델/driver 문제를 확정하지 않는다. host GPU producer는 exit0/오류 로그0bytes였다. 이번 실행 이후 추가 수정·학습 재시도는 하지 않았다.

원본8파일과 초기 가중치 hash 불변을 확인했다. final-test는 내용/hash를 다시 열지 않았고 calibration/selection 평가도 도달하지 못했다. 선별280건/잠정 정답49건·동일 초기·697노출/88 optimizer 계획·1800초·6GiB·학습 설정을 유지했으나 실제 완료 조건은 충족하지 못했다. 선별·정답 수정·반복 노출의 합친 효과는 미측정이다.

이번 producer PID6972와 컨테이너 잔류0을 확인했고, 기존 서비스·driver 변경과 Windows 비공개 역복사는 없다. PCWSL trial에 `interrupted.summary.private.json`, worker 종료/중단/단계 기록과 고정 입력을 보존했다. 원문 출력 가능성이 있던 첫 진단 명령은 자동 승인 검토가 거절하여 실행되지 않았고, 이후 오류 코드·숫자·안전 메타데이터만 현지에서 집계했다. 승인 학습1회는 소진됐으며 새 학습은 시작하지 않는다.

## 이전 시도 — 기록 보완 후 승인된 PCWSL 재실행 1회

시도 `approved-retry-20261014-01`, 실행 소스 `262cfada722a1c7166ac4850c8d9ea4d7307e039`. 시작 직전 기록된 전체 GPU 기준값은 **0.7083GiB**로 6GiB 이하였다. A worker 실행 약 **94.02초**에 `memory_monitor_unavailable`로 중단됐다. **A 정상 완료 조건을 충족하지 못해 B는 실행하지 않았고 자동 재시도는 0회다.** 모델 로드·입력 검사·초기 tensor 검사를 지난 뒤 마지막 저장 단계는 학습 전 `dry_run`이었다. 평가까지 도달하지 않아 A/B 비교 결과와 품질 판정은 없다.

| 중단 기록 | 관측 |
|---|---:|
| 마지막 저장 optimizer 완료 수 | **0회**, 상태 `not_started` |
| 정확한 종료 순간 optimizer 완료 수 | **미확인**; 마지막 worker 기록은 중단 약5.35초 전 |
| 실험 worker 자체 RAM RSS, 마지막 기록 | 1.873GiB |
| 실험 자체 GPU allocated / reserved, 마지막 기록 | 1.249 / 1.277GiB |
| 실험 자체 GPU peak allocated / reserved | 1.258 / 1.277GiB |
| 전체 host GPU 계수 표본 피크 | **2.289GiB**, 6GiB 이하 |
| parent+worker RAM 표본 피크 | 2.520GiB |
| 프로젝트 저장 표본 | 17,957,499,832bytes; 승인30GiB 이내 |

자체 GPU 수치는 PyTorch allocator 관측치이며 allocated와 reserved를 합산하지 않는다. 전체 resident VRAM으로 간주하지 않는다. 아래는 마지막 유효 host snapshot의 adapter 계수행별 전체 사용량이다. 각 행의 적용값은 `max(dedicated+shared, committed)`이고 총합은 **2,344.410MiB = 2.289GiB**다. 다른 작업과 committed memory가 포함될 수 있으며 세 계수행을 세 물리 GPU라고 해석하지 않는다.

| adapter 계수행 | Dedicated MiB | Shared MiB | Committed MiB | 적용값 MiB |
|---|---:|---:|---:|---:|
| 1 | 0.285 | 0.500 | 0.793 | 0.793 |
| 2 | 0.000 | 0.008 | 28.906 | 28.906 |
| 3 | 1,540.258 | 208.496 | 2,314.711 | 2,314.711 |

중단 파일의 자원 snapshot은 감시 실패 직전의 **마지막 유효 측정**이다. 이를 6GiB 초과를 발생시킨 측정으로 해석하지 않는다. 감시가 worker 메모리를 계속 읽지 못한 사실은 확인되지만, worker 소멸의 근본 원인은 미확인이다. 이번 컨테이너에 한정한 Docker 이벤트에는 OOM 이벤트가 없었다. 이는 OOM을 배제하는 증거가 아니며, 컨테이너의 exit1은 parent 종료 값이다. worker OS 종료 코드는 저장되지 않았다. 비공개 worker 출력의 원문을 가린 기록만으로 드라이버 오류·OOM·외부 종료를 단정하지 않는다.

원본 train/calibration/selection의 examples·JSONL6파일과 선별 제안·검토2파일의 전후 hash가 같고 초기 가중치 hash도 이전 승인 전송 기록과 같다. 기존 실패 폴더를 덮어쓰지 않고 새 시도 폴더에 고정 입력·순서·원본 ID/그룹 추적을 보존했다. A/B의 동일 초기 가중치·학습 설정·각697노출/88갱신 계획 및 B280건/잠정 정답49건 조건을 유지했으나 실제 완료 조건은 충족하지 못했다. 검증·시험 자료를 학습에 넣지 않았고 final-test는 다시 열지 않았다. calibration/selection 평가도 이번에는 미실행이다. 따라서 자료 선별·정답 수정·반복 노출의 합친 효과를 아직 측정하지 못했다.

이번 monitor와 컨테이너만 종료·제거했고 다른 서비스·driver·6GiB 한도·학습 설정은 변경하지 않았다. 비공개 로그·중단 기록·원본 보존 확인과 `interrupted.summary.private.json`은 PCWSL의 `.work/ab_trials/approved-retry-20261014-01` 및 연결 worker 폴더에 보존했다. Windows 역복사·원문/모델 Git 업로드는 없다. 승인된 재실행 1회는 소진됐으며 새 학습은 수행하지 않는다. 향후 원인 확인에 필요한 미기록 항목은 worker 종료 코드와 종료 직전 process 상태다.

## 이전 시도 — 기록 보완 전 승인된 PCWSL 시도

비공개 18파일 이전을 신산님이 명시 승인한 후 PCWSL에서 A/B를 시도했다. **A 시작 약15.7초에 전체 호스트 GPU 상한 계수6.30GiB가 승인 상한6GiB를 넘어 자동 중단됐고, B는 시작하지 않았다.** A의 최종 모델·697회 실제 소비·optimizer88회·reload·평가가 완료되지 않아 A/B 비교 수치는 없다. A의 실제 optimizer 횟수는 미확인이다. Windows 실패 증거는 덮어쓰지 않았다.

| 항목 | PCWSL 관측 | 승인 한도/조건 |
|---|---:|---:|
| A 경과 | 15.68초 | 전체 A/B·평가1800초 |
| parent+worker RAM 표본 피크 | 2.06GiB | 24GiB |
| 전체 GPU 보수적 상한 표본 피크 | **6.30GiB** | **6GiB** |
| 프로젝트 저장 표본 | 16.72GiB | 30GiB |
| A 실제 optimizer 갱신 | 미확인 | 88회 |
| B 실행 | 미시작 | 697노출·88회 |

GPU 계수는 각 Windows adapter의 `max(DedicatedUsage+SharedUsage, TotalCommitted)`를 합산한 값이다. 감시를 위해 GPU context를 만들지 않고 stale/형식/승인 binding 오류를 차단한다. 다른 process의 사용과 committed memory도 포함하므로 **판단 엔진 단독의 실제 resident VRAM**으로 표현하지 않는다. 별도의 종료 후 adapter 이름 조회에서는 그 조회 시점의 `_Total` 행이 없었다. 중단 순간 adapter 이름·resident/committed 내역이 저장되지 않아 피크 집계의 중복 여부와 어느 모델 단계가 상승에 기여했는지는 미확인이다.

실행 코드 checkpoint는 `49b0060dcffed35b43e94fb099e3fee529e5588a`다. Windows와 PCWSL의 exact SHA·tracked clean을 대조했다. PCWSL 전용 Python3.12.3/PyTorch2.13.0+rocm7.2 환경에서 Linux 고정37패키지 공식 hash/size, Laya exact upstream, pip check, 영향39시험과 실제 GPU 모델/tokenizer 경계1시험을 통과했다. 첫 모델 gate의 GPU 라이브러리 연결 오류는 목적경로를 수정하여 해결했고 실패 로그를 보존했다. 이후 학습 시도의 자원 상한 실패는 별개의 결과다. 기존 서비스·driver·권한을 변경하지 않았다.

자료 정리 전697건 중 명확한 정답216건/정말 후보 없음64건을 선별했다. 복수264건·불명확153건, 합계417건은 Windows 원본/검토표에 별도 보존한다. 잠정 gold49건은 원본에 반영하지 않고 B 실험 제안본에만 적용했다. A697고유×1회, B280고유(143×2회+137×3회)의 양쪽697노출·업무558/없음139·88예상 갱신 조건을 검증했다. Windows/PCWSL 준비 순서표의 정규 JSON digest도 동일하며 실제 소비 관측은 중단으로 미완료다.

승인된 allowlist 18파일의 payload683,964,215bytes를 SSH로 사용자 전용 프로젝트에 이전하고 hash/크기 전부 일치 확인했다. 원본ZIP·final-test·과거 test 혼합 점수·credential·기존 학습 모델은 옮기지 않았다. final-test가 PCWSL에 없음을 확인했으며 내용/hash를 다시 열지 않았다. 비교의 평가 대상은 calibration457/selection374로 고정했지만 이번에는 평가까지 도달하지 못했다. 검증·시험 자료는 optimizer 입력에 들어가지 않는다.

중단 후 원본 train/calibration/selection examples+JSONL6파일과 선별 제안/검토표2파일, 초기 모델 가중치가 준비/전송 전 hash와 일치했다. 이번 container·GPU 감시 process는 종료/제거했고, 전송용 tar만 송수신 양쪽에서 제거했다. 실입력·순서표·승인 설정·미완료 worker·상한 실패·보존 증거는 PCWSL ignored `.work`에 보존했다. 비공개 증거의 Windows 역복사는 자동승인검토에서 구체적 reverse-egress 승인 부족으로거절돼 수행하지 않았다. 원문 없는 집계는 이 문서에 기록한다. 상한 완화·기존 서비스 중지·학습 자동 재시도는 하지 않았다.

현재 판정은 **자료/환경/반복 입력 준비 완료, A/B 비교 미완료**다. 같은 GPU6GiB 한도를 유지하려면 메모리가 상승하는 실제 단계와 단독/다른 작업 기여를 확인하고 사용량을 줄이는 실행 경로를 먼저 검증해야 한다. 이 보고는 선별·잠정 정답 수정·반복 노출의 합친 효과를 측정한 결과가 아니며, G2 품질 판정은 `not_decided`다.

## 이전 시도 — Windows

## 판정

A 실행 약45.2초 시점에 전체 GPU 점유7.42GiB가 승인 상한6GiB를 넘어 parent/worker 안전 감시가 실행을 중단했다. B는 시작하지 않았다. A의 최종 모델·697노출 완료·optimizer88회 관측·reload 증거가 없으므로 실제 학습 완료나 A/B 효과를 주장하지 않는다. 실제 optimizer가 몇 회 실행됐는지도 확인되지 않았다.

신산님 승인에 따라 B의 선별280건과 잠정 정답49건은 이번 실험용 입력 제안에만 사용했다. 원본·기존 모델을 대체하지 않았다. 준비된 두 입력과 재개에 필요한 추적/실패 증거는 로컬에 보존했다. 자동 재시도·VRAM 상한 완화·CPU 장시간 전환·VM 종료는 하지 않았다.

## 준비와 검증

| 조건 | A 원본 | B 선별·잠정 정답 |
|---|---:|---:|
| 고유 사례 | 697 | 280 |
| 연결그룹 | 67 | 62 |
| 고정 노출 계획 | 697 | 697 |
| 업무 정답/없음 노출 | 558/139 | 558/139 |
| 사례별 반복 | 각1회 | 143건×2회, 137건×3회 |
| optimizer 계획 | 88회 | 88회 |
| 실제 optimizer 완료 관측 | 미확인 | 미실행 |

실행 코드 checkpoint는 `3531f1458f6ddbb704844a81cc6146f715d14741`이며 작업 branch 원격 일치·clean 상태를 확인한 뒤 사용했다. head-only/encoder 동결/soft-CE/1epoch/fp32/micro-batch1/gradient accumulation8/head LR1e-4/seed13 등 학습 조건은 동일하게 고정했다. 같은 무학습 모델 경로·revision을 두 arm에 결합했으나 B가 미실행이므로 실제 두 시작 tensor의 일치 관측은 아직 없다.

반복 대상·JSONL 순서·원본 ID·출처·그룹·정답·반복 횟수를 저장했다. upstream의 epoch shuffle까지 반영한 실제 예상 순서와 후보 순서·optimizer 묶음·실제 반복 occurrence를 별도로 고정하고, worker가 실제 소비 순서를 대조하도록 구현했다. 실제697회 소비 관측은 중단으로 미완료다.

새 입력 경계·순서·변조·외부ID·gold·global deadline·final-test 접근 차단 시험을 실패→통과로 확인했고, 수정 후 영향 범위31시험 PASS다. 독립 코드 리뷰1회(Critical0/Important2/Minor0)의 순서 기록과 전역 시간상한 finding을 한 번 수정했으며 다시 리뷰하지 않았다. 신규 소스 AST·공개파일 경로/Secret 패턴·수동 diff·Git diff 검사도 통과했다. 전체 제품 suite·과거 학습·수동 의미 검토는 반복하지 않았다.

최신 직접 지시로 final-test 재평가를 제외했다. loader와 parent/worker 파일 open guard로 final-test 및 과거 test 혼합 점수파일 접근을 차단했고 이번 준비·실행·진단에서 열지 않았다. calibration/selection만 평가하도록 구현했으나 이번 실행은 그 측정 단계까지 완료하지 못했다. 검증·시험 사례를 반복 입력에 넣지 않았다.

## 중단 근거와 읽기 전용 진단

| 관측 | 사용량 | 상한 |
|---|---:|---:|
| 전체 비교 중단 시 경과 | 약45.2초 | 전체1800초 |
| worker RAM 표본 피크 | 약2.18GiB | 24GiB |
| 전체 device GPU 표본 피크 | **7.42GiB** | **6GiB** |
| 프로젝트 저장 표본 | 약8.65GiB | 30GiB |

시간은 앞선 제안의 arm별30분/합계60분보다 보수적으로 전체 비교1800초 한도와 남은 arm/worker 예산으로 강제했다. 중단 사유는 시간·RAM·저장이 아니라 GPU 상한이다. WDDM의 전체 device 점유는 다른 process의 사용도 포함하므로 이 수치를 실험 단독 VRAM으로 표현하지 않는다.

종료 뒤 이 실험의 Python process가 남지 않음을 Native 조회로 확인했다. 전체 device 사용2325MiB는 계속 관측됐고 Windows GPU 집계에서 `vmwp`의 dedicated 사용 합계 약2.27GiB가 확인됐다. 개별 process 식별자는 로컬 증거에만 보존한다. 해당 VM 이름은 사용 가능한 조회 경로로 확인하지 못했다. **이 VM과 이번 실험의 관계, GPU 작업 내용 및 중단 순간의 기여는 미확인**이다. 확인 없이 다른 작업이나 드라이버 문제로 단정하지 않는다.

CPU tokenizer로 첫 검증 입력을 대조했을 때 A159/B319/기존 첫 입력164token이었다. GPU 모델 호출 없이 확인했으며 A의 첫 입력이 길어져 생긴 문제라는 가설은 뒷받침하지 못했다. 어느 worker 단계에서 단독 메모리가 증가했는지는 완료/phase 증거가 없어 미확인이다. 같은 실행을 원인 확인 없이 반복하지 않았다.

원본 train/calibration/selection의 examples·JSONL6파일과 선별 제안/검토표2파일은 중단 후에도 준비 전 hash와 동일했다. 원본 raw ZIP·기존 최종 모델을 수정·삭제하는 코드는 실행하지 않았다. final-test는 보존 hash 확인을 이유로도 다시 열지 않았다.

## 보존과 재개 조건

로컬 `.work/ab_comparison/`에 A/B 입력·원본 순서표·승인 설정·실행 로그·상한 실패 기록·중단 집계·원본 보존 증거를 유지했다. A worker의 미완료 실행 폴더도 보존했고, 완료 모델로 승격하지 않았다. `.work` 자료·원문·정답·모델은 Git 제외다. 공개 보존 대상은 검증 코드·합성 시험·원문 없는 집계 문서뿐이다.

재개에는 **전체 GPU6GiB 상한을 지킬 가용 상태와 잔류 VM 점유의 관계 확인**이 필요하다. VM 종료·다른 GPU 작업 중단·드라이버/환경 변경·VRAM 상한 변경은 이번 A/B 승인 범위로 추정하지 않는다. 신산님의 다음 지시 전 새 학습을 시작하지 않는다. 재개 시 실패 기록을 덮어쓰지 않고 승인된 같은 A/B 조건의 별도 시도로 구별한다.

향후 완료된 비교는 자료 선별·잠정 정답 수정·반복 노출이 합쳐진 효과로만 보고한다. 이번 중단에서 효과나 정확도 수치를 만들어내지 않으며, G2 품질 합격·일반화·운영 적합·배포 완료는 미확정이다.
