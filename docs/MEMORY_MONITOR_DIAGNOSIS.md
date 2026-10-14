# memory_monitor_unavailable 진단·감시 단독 검증

2026-10-14 / 담당 어울 / 추가 학습 0회 / 감시·GPU6GiB 유지

## 판정

승인된 이전 재실행의 직접 실패 경로는 **PCWSL의 RAM `/proc/<pid>/status` 조회**다. 외부 감시 명령 실행 실패나 시간 초과 경로가 아니다. 당시 GPU 계수 생산자 로그는 0bytes이고 계수 이력은 실험 중단 뒤에도 이어졌다. 정확한 하위 원인인 **OS 파일 읽기 실패와 `VmRSS` 누락 중 어느 쪽인지는 기존 기록으로 구별할 수 없다.** 모델 없는 감시는 보완 후 180.32초 정상 수행했다. 모델 실행 중 발생한 근본 원인 해결과 A/B 완료는 여전히 미검증이다.

## 기존 로그와 코드의 대응

대상은 `approved-retry-20261014-01`, worker `run-482133f3db154a59a1f03655a052e3ec`, 실행 소스 `262cfada722a1c7166ac4850c8d9ea4d7307e039`다. 원문·시험 자료를 다시 열지 않고 PCWSL 현지 운영 로그의 오류 유형과 숫자, 코드만 대조했다.

| 가능한 실패 | 기존 코드·기록 판정 |
|---|---|
| 외부 감시 명령의 실패 | RAM `_memory()`는 subprocess를 호출하지 않는다. 이번 오류의 직접 경로가 아니다. |
| 감시 명령 시간 초과 | RAM에는 명령·timeout 자체가 없다. GPU 생산자 로그에도 TimeoutExpired 기록이 없다. |
| 숫자 출력 해석 오류 | 기존 `VmRSS` 숫자 변환 오류는 ValueError 경로이며 이번에 저장된 ConfigError 사유와 다르다. |
| `/proc` 읽기 OS 오류 | `OSError`를 동일한 `memory_monitor_unavailable`로 축약했다. errno·대상 PID를 저장하지 않아 해당 여부 미확인. |
| `/proc`에 `VmRSS` 없음 | 파일을 읽었어도 해당 항목이 없으면 같은 사유를 냈다. process State를 저장하지 않아 해당 여부 미확인. |

parent는 worker RAM과 자신의 RAM을 순서대로 조회한다. 당시 어느 PID의 조회가 실패했는지도 저장하지 않았다. 따라서 worker 소멸·zombie·권한·OOM·드라이버 문제 중 하나로 확정하지 않는다. worker 마지막 기록은 `dry_run`, 완료 optimizer 0회이며 중단 약5.35초 전 기록이다. 기존 중단의 정확한 종료 코드나 종료 순간 갱신 수를 소급해서 채우지 않는다.

worker 종료 코드는 parent가 `poll()/wait()`로 받지만 `evidence.json` 결과에는 넣지 않았다. 종료 전 `limit_failure.json`만 저장했으므로 이후 반환 코드가 그 파일에 남을 수도 없었다. Docker의 parent exit1을 worker 종료 코드로 대체하지 않는다.

## 최소 수정 전후

| 변경 위치 | 변경 전 | 변경 후 |
|---|---|---|
| `src/judgment/runner.py::_memory` | 읽기 실패·항목 누락을 같은 코드로만 표시 | 원문 없이 `proc_read_error`/`rss_missing`/`rss_parse_error`, PID·errno·안전 State 기록 |
| `_training_process` | 종료 반환 코드 미저장 | `wait()` 후 `worker.exit.private.json`과 결과에 반환 코드 저장 |
| parent 중단 기록 | 감시 하위 실패 정보 없음 | `monitor_failure`와 종료 요청 전 반환 코드 기록 |
| poll→RAM 조회 종료 경합 | 반환 코드 미보존 | 종료를 다시 확인하고 이미 종료한 worker의 코드를 보존; 실행 중 감시 실패는 계속 중단 |
| `_worker_limits` | 포괄 감시 실패만 기록 | 안전한 실패 종류·예외형 정보 보존 |

중단 전·후 추가 기록은 기존 bounded best-effort 방식이다. 기록 지연/실패가 종료를 막지 않으며 감시를 끄거나 자원 한도를 완화하지 않는다. allocated/reserved·단계·성공한 optimizer 완료 수의 기존 의미도 바꾸지 않았다.

## 검증 결과

검증 소스는 `1322fec1dabd97348e9ccc51092e64f1fbbdfaab`다. Windows 코드 checkpoint를 비강제 push한 뒤 PCWSL에서 Git exact SHA로 가져왔다. 기존 이미지 `sha256:55a6560f149bf076a44d4b6ee3f22c5e3092e52ffd337f0466c3f008fa2ef7bf`를 재사용했다. 시험 컨테이너는 network none, RAM4GiB/총 RAM+swap8GiB, 사용자 UID, GPU device 미전달, `/usr/bin/python3` 표준 라이브러리 환경이다. 모델·torch·GPU context·신규 설치·다운로드·학습·평가·final-test 접근은 없다.

- TDD: 종료 코드·감시 하위 기록 누락 2개 실패를 확인한 후 최소 수정했다.
- Windows 전체 합성 시험: **110개 중106개 PASS, 조건부4개 skip**. 실제 모델 시험과 현지 전용 시험은 로컬에서 실행하지 않았다. CPU scalar optimizer 시험은 합성 hook 검증이며 모델 학습이 아니다.
- PCWSL 현지 감시 시험: **5개 전부 PASS**, 전체182.723초. 정상 dummy worker가 **180.320초**, exit0으로 끝나 이전94초를 충분히 넘겼다.
- 정상 감시 시작 전체 GPU 기준값 **0.707GiB**, 시험 peak **822,820,864bytes = 약0.766GiB**, parent+worker RAM peak36,687,872bytes. GPU 상한 **6GiB** 유지.
- Windows/CIM producer는 138개 snapshot을 기록했고 첫·마지막 관측 간격210.647초, exit0, 오류 로그0bytes였다.
- `/proc` 읽기 permission 오류(errno13), `VmRSS` 누락/숫자 오류를 구분했고 원문이 실패 정보에 들어가지 않음을 확인했다.
- RAM 감시 실패 주입 시 **5초 이내 해당 worker 종료**, 반환 코드·failure 종류·errno 저장, 별도로 띄운 대조 sleep process 생존, active worker 목록 잔류0을 확인했다. 이는 이번 실험 ownership 경계의 검증이며 실제 다른 서비스 전체의 상태 재검증으로 확대하지 않는다.
- 정상 exit0, 비정상 exit7, RAM 조회 중 종료 경합의 exit7 보존을 실제 subprocess로 확인했다.

검증 중 새 시험 코드의 `Telemetry.event()` 인자 불일치 1회는 기존 API의 state+event 방식으로 바로잡았다. Windows 전체 시험 첫 실행은 비동기 fsync handle과 임시폴더 삭제가 겹쳐 정리 오류1회였고, 시험 cleanup에만 최대2초 대기를 두어 해결했다. 제품 중단 기다림은 늘리지 않았다. 최종 코드·문서 diff와 공개파일 원문/Secret 점검을 수행했다.

현지 `.work/pcwsl-runtime/monitor-diagnostic-20261014-01`에 producer history·로그·비공개 요약을 보존한다. 시험 컨테이너 제거와 producer 정상 종료를 확인했다. 기존 서비스·driver·데이터·초기 가중치 변경 및 Windows 비공개 역복사는 없다.

## 재실행 가능 여부

**감시 경로·종료 코드 기록은 모델 없는 시험 범위에서 재실행 준비가 됐다.** 다만 이전 모델 실행 중 `/proc` 실패의 하위 원인은 미확인이고 모델 단계에서 문제가 해소됐다는 증거는 없다. 새 A/B를 실행하면 같은 초기 가중치·학습 설정·6GiB·fresh 시작 기준 검사·A 정상 완료 시에만 B·재시도0·calibration/selection 평가·final-test 금지를 그대로 적용해야 한다. 이번 지시는 학습 재시도 승인이 아니므로 추가 학습을 시작하지 않는다.
