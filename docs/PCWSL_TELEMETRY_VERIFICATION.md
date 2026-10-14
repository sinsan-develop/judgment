# PCWSL 기록·중단 보완 검증 결과

2026-10-14 / 담당 어울 / **승인 보완 구현·모의 검증 완료, A/B 재실행 미수행**

## 결과

PCWSL 실행 checkpoint `fb79e66d29afab5083a6cfa94306e73193671608`에서 관련51시험이31.375초에 모두 통과했다. GPU 장치와 네트워크를 연결하지 않은 프로젝트 전용 CPU 시험 container에서 수행했다. 실제 학습자료·모델·final-test는 열지 않았고, scalar optimizer 시험은 합성 CPU parameter만 사용했다. 별도 Windows import 계약4시험도 통과했다.

| 확인 항목 | 결과 |
|---|---|
| 정상 worker 종료 | 단계·완료2회·비공개 가림 출력 보존 |
| 갱신 중 강제 중단 | 마지막 완료1회·다음 갱신 in_progress 보존, 최종 정확 횟수 미확인 표시 |
| 기존6GiB 경계 | 같은6GiB는 정상, 1byte 초과는 exit3 |
| 기록 I/O 실패·20초 멈춤 모의 | 종료는 기다리지 않고 진행, owned 종료 확인 |
| SIGTERM 무시 child | owned child 강제 종료 확인, 무관한 모의 child 생존 확인 |
| 실행 직전 기준값 | adapter 이름·전용/공유/committed·합계·시각을 같은 snapshot에서 저장 |
| 중단 trigger | 판정에 실제 사용한 snapshot/계수/한도/UTC·단조시각 보존. 이후 snapshot 재조회로 대체하지 않음 |
| 자체 메모리 | 기존 CUDA context만 allocator 관측, 미초기화는 null, RSS/allocated/reserved 분리 |
| 관측 wrapper | 학습 전 selection과 train_model 단계 기록, 예외에도 원래 upstream 함수 복구 |
| 비공개 출력 | 허용된 전체 숫자 진행문만 구조화, 원문·비밀 marker·임의 메시지는 가림 |

## 구현된 범위

- worker와 측정 parent의 단계 시작/종료, AdamW 시작/정상 반환 후 완료 수,0.5초 heartbeat를 기록한다. 입력 인코딩 순번을 완료 optimizer 횟수와 구분한다.
- 정상 단계·완료 수는 로컬 비공개 JSONL과 atomic 최신 상태에 기록한다. fsync 후 atomic replace가 완료되어야 정상 기록으로 인정한다. 실패/timeout이면 성공으로 표시하지 않는다.
- GPU host 생산자는 adapter 이름·원래3계수와 기존 보수적 합계 시계열을 저장한다. trial 직전과 worker launch 직전 기준 snapshot을 별도 저장한다. 자체 allocator 수치나 기준값 대비 차이로 **전체 host6GiB guard를 대체하지 않는다.**
- worker stdout/stderr는 pipe를 비공개 출력 로그로 보존한다. 전체 문장 numeric allowlist에 맞는 진행 정보만 남기며 그 밖의 출력은 가림 표시한다. 원문 출력 전체를 보존하는 기능은 아니다. 파일은 POSIX0600, 프로젝트 .work는 기존 사용자 전용 권한이다.
- 독립 상한 감시는 기록 I/O를 기다리는 정상 경로와 분리돼 있다. 중단 packet 보존은 최대50ms의 best-effort이며, 예외/멈춤 여부와 관계없이 등록된 이번 worker에 terminate+kill을 요청한 뒤 종료한다. 다른 서비스/임의 PID를 대상으로 하지 않는다.

## 발견·수정한 오류

독립 리뷰1회에서 Critical0/Important2/Minor0: owned worker에 terminate만 보낼 경우 잔류 가능성과 중단 trigger snapshot 연결 부족을 지적했다. 각각 실패시험을 확인한 뒤 강제 종료와 판정에 사용한 동일 snapshot 저장으로1회 수정했다. 다시 리뷰하지 않았다.

PCWSL 첫 모의 실행은50시험 중45통과/4오류/1실패였다. 소형 JSON append·atomic fsync 각각 약60~90ms를 관측해200ms 정상 대기가 writer 경합에서 부족함을 확인했다. 정상 기록은 최대1초 대기로 보완했다. 중단 packet은 먼저 atomic 공개한 뒤 sync를 시도하고 최대50ms 후 종료한다. 이에 따라 중단 packet의 전원 장애 durability는 보장하지 않으며 best-effort 표식을 남긴다. 정상 완료 수의 fsync 계약은 유지한다.

두 번째 모의 실행은49통과/1실패였다. 정상 종료 시 진행 중인 sampler를100ms만 기다린 뒤 실패로 판정하는 경합을 합성 시험으로 재현하고, 정상 종료의 bounded join을1초로 수정했다. 상한 중단은 정상 close를 호출하지 않는다. 최종51시험은 모두 통과했다. 각 실패/최종 시험 로그와 exit는 PCWSL ignored 실행 경로에 따로 보존했다. 기존 A/B 실패 증거를 덮어쓰지 않았다.

## 한계와 다음 단계

자체 GPU 수치는 해당 process의 PyTorch allocator 관측이며 context·일부 라이브러리의 전체 resident VRAM을 증명하지 않는다. 강제 종료가 optimizer 실행/기록 도중이거나 저장장치가 멈추면 최근 증명된 완료 수와 진행 중/미확인 상태만 보고한다. 중단 기록 실패 때문에 종료를 지연시키지 않는다.

이번 결과는 CPU·합성 계수·합성 process의 기록/종료 검증이다. 실제 GPU 재학습에서의 메모리 상승 단계, 실제697노출/88갱신 완료, A/B 효과나 품질 판정의 증거가 아니다. **6GiB·1800초·기존 학습 설정은 유지했고, 다른 서비스 종료·설치·driver 변경·Windows 역복사·A/B 재실행은 하지 않았다.** 신산님이 이 검증 결과를 확인한 뒤 별도의 A/B 실행을 진행한다.
