# 기록 실패 진단 보완·실제 모델 로드 검증

2026-10-14 / 담당 어울 / A/B 학습 보류 유지

## 판정

**실제 모델 로드와 기록이 함께 정상 완료됐다.** 실행 소스 `8a29cae687170ddc6f0d6d38febfa72accb99f30`, probe `model-load-probe-20261014-01`, PCWSL 기존 격리 이미지·전용 환경에서 60.111초/exit0이다. optimizer·학습·평가·final-test 접근은 0회다. 이번에는 `telemetry_unavailable`이 재현되지 않았으므로 **이전 실패의 정확한 호출·예외는 여전히 미확인**이며, 근본 원인이 해결됐다고 단정하지 않는다.

## 실패 진단 보완

이전 코드는 writer 예외·submit 대기 초과·queue 부족·sampler 예외를 모두 `failed` flag로만 축약했다. 이전 `model_load` heartbeat 뒤 어떤 호출이 실패했는지는 기존 기록으로 소급 복원할 수 없다.

수정 후 최초 실패를 `telemetry.failure.min.private.jsonl`에 별도로 남긴다. 시작 시 0600 FD를 열고, 일반 queue·append/fsync·atomic_json 경로를 거치지 않는 작은 `os.write` 한 행을 사용한다. 실패 flag를 먼저 설정하며 daemon 기록을 최대20ms만 기다린다. 단, 저장 장치 자체가 쓰기 불가능하면 최소 로그 역시 best-effort이며 완전한 보존을 보장하지 않는다.

| 실패 위치 | 저장 정보 |
|---|---|
| writer의 append/atomic 호출 | 호출 구분, 예외 종류, errno, 예외 호출 함수명 |
| submit 대기 시간 초과 | `submit.wait_timeout`, 당시 writer 진행 호출, 단계 |
| queue·sampler·memory·drain·close | 구체적 실패 지점과 예외 종류 |

모든 행에 단계·시각·PID·완료 optimizer 수를 포함한다. 원문·Secret·예외 message·locals·원본 경로는 저장하지 않는다. 최초 원인을 보존하고 파생 오류가 이를 덮어쓰지 않는다. 정상 기록의 기존1초 대기, 6GiB 감시와 자원 중단 기능은 유지했다.

변경 전에는 같은 `telemetry_unavailable`만 있었고, 변경 후에는 `writer.append_json`의 PermissionError/errno13과 `submit.wait_timeout`을 구분한다. 별도 최소 로그를 못 남기는 두 시험의 RED를 확인한 뒤 구현했다. 최초 보완 시험에서 Windows FD 회수 누락으로 정리 오류3개가 발생했고, 최소 로그 기록 후 FD 회수 및 최대20ms 완료 대기로 고쳐 영향20개 PASS/1개 skip을 확인했다. 전체 합성 시험은 **112개 중108개 PASS/조건부4개 skip**이다. PCWSL 최소 로그 경계 시험2개도 PASS다. 합성 CPU optimizer 시험은 실제 모델 학습이 아니다.

## 실제 모델 로드 시험

`docs/probe_model_load.py`는 framework import → 장치 초기화 전 관측 → 승인된 기존 모델의 GPU 로드 → 장치 초기화 후 관측 → 기록 유지 확인 → 모델 해제까지만 수행한다. train/selection/calibration 사례를 읽거나 optimizer·추론·평가를 호출하지 않는다. final-test guard를 적용했다. 이번 시험은 framework import와 모델 로드를 별도 단계로 구분하므로 이전 전체 A/B 경로와 동일한 실행이라고 표현하지 않는다.

| 관측 | 초기화 전 | 모델 로드 후 |
|---|---:|---:|
| worker RAM RSS bytes | 745,525,248 | 1,696,055,296 |
| GPU allocator 상태 | `not_initialized` | `observed` |
| GPU allocated bytes | 미초기화·값 없음 | 1,307,824,640 |
| GPU reserved bytes | 미초기화·값 없음 | 1,333,788,672 |

미초기화 상태를 사용량0이나 조회 실패로 바꾸지 않고 별도 표시했다. 모델 해제 후 allocated/reserved0 기록도 확인했다. 마지막 단계 `model_load_verified`, optimizer 완료0, 최소 실패 로그0행이다.

기존 immutable image `sha256:55a6560f149bf076a44d4b6ee3f22c5e3092e52ffd337f0466c3f008fa2ef7bf`, network none/RAM4GiB/총RAM+swap8GiB, GPU 연결·읽기전용 라이브러리 설정을 유지했다. 신규 설치·다운로드·학습 설정 변경·다른 서비스/driver 변경은 없다. 전체 GPU 기준값 약0.866GiB, producer49표본 피크2,336,632,832bytes(약2.176GiB)로 6GiB 이내였다. 시험 producer PID7581과 container 잔류0, 최소 로그 권한0600과 초기 가중치 hash 불변을 확인했다. 비공개 결과·계수 이력·최소 로그는 PCWSL `.work/model_load_probe/model-load-probe-20261014-01`과 해당 runtime 폴더에 보존하며 Windows 역복사는 없다.

## 다음 실행 제안

모델 로드·기록의 정상 완료를 확인했으므로 **같은 초기 가중치·학습 설정·697노출/88 optimizer·GPU6GiB·전체1800초의 A/B 1회**를 제안한다. 시작 기준 초과 시 미실행, A 정상 완료 뒤 B, 자동 재시도0, 평가 calibration/selection만, final-test 비접근을 유지한다. 다시 기록이 실패하면 독립 최소 로그의 최초 호출·예외·단계와 worker 종료 코드를 함께 보고한다. 이번 검증은 A/B 재실행 승인이 아니므로 새 학습은 수행하지 않는다.
