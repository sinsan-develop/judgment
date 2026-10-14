# PCWSL 실패 진단과 최소 기록 보완안

2026-10-14 / 어울 / 현지 읽기 전용 진단, 구현·재학습 미실행

## 확인된 사실

실행 SHA는 `49b0060dcffed35b43e94fb099e3fee529e5588a`, 현지 현재 HEAD는 `854b5648363d93d4fbf87859776ac243ae392a72`다. 두 SHA 사이 runner·GPU 감시·A/B 실행 코드 변경이 없고 tracked checkout이 clean임을 확인했다. 고정 upstream SHA도 일치하고 clean이다.

| 항목 | 현지 증거로 확인한 결과 |
|---|---|
| 마지막 상위 단계 | A의 training 호출 진입·입력 검증 완료 |
| worker 시작 | 실행 입력/config와 parent worker 감시 증거 존재 |
| 종료 | exit3, `vram_limit`, arm 감시 경과15.6826초 |
| GPU 상한 계수 | 6,762,946,560bytes, 약6.30GiB > 6GiB |
| 완료 optimizer 횟수 | null / unverified. 0회라고 판단할 수 없음 |
| 실제697회 소비 | 미확인. replay_verified의697은 검증된 입력 계획 |
| 최종 산출 | worker summary/output/checkpoint 없음, B 미시작 |
| 실험 자체 GPU 사용량 | 중단 시 allocator/process 기록 없음 |

읽은 증거는 현지 A/B 로그·exit, A/limit_failure, worker/evidence, GPU 생산자 로그·마지막 snapshot 및 실행 코드다. 원문 입력·final-test·가중치 내용은 진단에서 열지 않았다. 비공개 파일의 Windows 역복사도 하지 않았다.

## 중단 단계의 한계

상위 로그의 `stage=training`은 worker 내부의 실제 optimizer 진입을 뜻하지 않는다. worker 내부에는 모델 로드 → 토큰 검사 → 첫 기준 추론 → tensor 검사/dry-run → 모델 해제 → finetune이 있지만 중간 기록이 없다. 고정 upstream finetune도 모델을 다시 로드하고 **학습 전 selection 기준 측정**을 수행한 뒤 train_model/AdamW.step으로 들어간다. 이들은 중단 가능한 후보 단계일 뿐, 당시 도달했다는 증거가 아니다.

upstream checkpoint는 epoch 종료 후 생성되므로 output이 없다는 사실로 optimizer 0회를 증명할 수 없다. worker stdout/stderr는 DEVNULL로 버리고, optimizer hook의 카운터는 메모리에만 있다가 학습·reload 완료 후 summary에 저장된다. 별도 감시는 os._exit로 종료하므로 finally에만 둔 기록은 보장되지 않는다. 이번 실패의 정확한 내부 단계·성공 optimizer 횟수·메모리 상승 원인은 미확인으로 유지한다.

## GPU 집계 방식

호스트 생산자가 Windows CIM의 GPUAdapterMemory를 읽는다. 각 행의 `max(DedicatedUsage + SharedUsage, TotalCommitted)`를 합산하고 최근 snapshot의 합계값을 읽는다. GPU context를 만들지 않으며 snapshot 나이가15초를 넘거나 형식/승인binding이 잘못되면 실패한다. parent의 worker 감시는0.2초 간격, 별도 상한 감시는1초 간격이며 생산자는 CIM 조회 완료 후0.5초 쉰다. 동일 snapshot을 여러 감시가 읽으므로 이를 독립적인 GPU 측정으로 세지 않는다.

GPU는 host 전체 adapter의 보수적 상한이다. pid 인수가 있어도 snapshot 경로에서는 해당 pid별 GPU 사용량을 측정하지 않는다. 실제 resident 사용량과 committed 값 중 큰 값을 쓰며 다른 작업도 포함한다. RAM의 parent+worker scope와 GPU scope는 다르다.

snapshot은 매번 교체되고 adapter 이름/원래 계수/시계열을 보존하지 않는다. 남은 약0.64GiB snapshot은 중단 후의 값으로6.30GiB 피크의 구성에 사용하면 안 된다. 이번 진단만으로 중단 순간의 adapter 중복 여부나 다른 서비스 기여를 재구성할 수 없다. 앞선 종료 후 이름 조회는 당시 중복 `_Total` 행이 없었다는 별도 관측에 한정된다.

## 최소 보완 제안 — 아직 구현하지 않음

1. **단계 기록:** worker 진입과 모델 로드/입력 검사/첫 추론/dry-run/finetune 모델 로드/학습 전 selection 측정/train_model/저장·reload/A-B 측정의 시작·종료를 남긴다. arm/run/PID/단조시각·UTC/입력 순번과 기존 manifest 참조만 기록하고 원문은 넣지 않는다. worker 오류는 예외 종류·안전한 코드·호출 위치만 저장하고 원문이 들어갈 수 있는 메시지/locals는 저장하지 않는다. upstream은 수정하지 않고 기존 어댑터·관측 hook에 연결하며 종료 시 복구한다.
2. **완료 갱신 기록:** 새 worker 진입에서0과 `not_started`를 저장하고, 기존 AdamW post-step hook의 정상 반환마다 완료 수를 증가시켜 즉시 저장한다. 예상88과 관측값을 분리한다. 갱신 시작/완료 상태도 표시해 중단 중인 다음 갱신을 확정 완료로 세지 않는다. 마지막 파일이 없거나 오래됐으면 미확인으로 남긴다.
3. **자체 메모리와 host 상한 분리:** 이미 GPU context를 가진 해당 실험 process에서만 PyTorch allocated/reserved와 각 peak, RSS를 단계·갱신 완료 시 및 기존 주기의 heartbeat에 기록한다. reserved에 allocated가 포함되므로 둘을 더하지 않는다. parent/worker별로 기록하고 초기화 전에는 null+이유를 표시한다. allocator 수치는 context·일부 라이브러리 등 process 전체 resident VRAM을 포함하지 못하므로 정확한 전체 자체 VRAM으로 부르지 않는다. host 생산자는 adapter Name/원래3계수/합계/시각을 원문 없는 짧은 시계열로 보존한다. 자체 수치나 시작 대비 차이로 기존 host6GiB 상한을 대체하지 않는다.
4. **중단 전 보존:** 단계/완료 갱신 기록은 임시파일 write→flush/fsync→atomic replace로 저장한다. 상한 감시는 trigger 계수·시각과 이미 저장된 worker 상태를 먼저 stop 기록에 저장한 뒤 이번 실험의 process만 종료한다. 새 GPU 작업이나 다음 optimizer 갱신을 기다리지 않는다. 강제 종료가 갱신/파일 저장 도중이면 최근 증명된 완료 수와 다음 갱신 미확인을 함께 보고하며 최종 정확한 횟수를 보장했다고 표시하지 않는다.

최소 변경 대상은 runner의 단계·post-step·중단 기록, 기존 replay 관측 연결, host GPU 생산자의 시계열, A/B 측정 단계 연결이다. 학습 설정·노출/순서·모델·검증/시험 경계·6GiB 상한은 바꾸지 않는다. 구현 후에는 합성 단계 이벤트·성공/실패 optimizer·가짜 GPU 계수·강제 중단으로 저장된 상태와 원문 비노출을 검증하면 된다. 해당 검증은 실제 재학습을 필요로 하지 않는다.

이번 조치는 진단과 제안까지만이다. 다른 서비스 종료·한도 변경·GPU 모델 재실행·패키지 설치·비공개 역복사·보완 코드 구현은 수행하지 않았다. 진단에 Windows 역복사는 필요하지 않았다.
