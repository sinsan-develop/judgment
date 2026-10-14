# atomic_json 지연 계측·최소 보완 검증

2026-10-14 / 담당 어울 / **코드·안전 경계 검증 완료, 모델 로드+80회 반복 기록 공동 검증은 GPU 상한 중단으로 미완료**

## 경로와 재현

실제 `/home/daon/deploy/judgment/.work/runs` 및 부모 경로는 symlink가 없고 WSL 내부 `/dev/sdd`, ext4에 있다. Windows 공유 경로가 아니다. 컨테이너 `/workspace`는 이 WSL 프로젝트를 bind한다.

기존 전체1초 대기를 유지한 계측 소스 `e5863316d7debad19f606d7497e91d17e6af6952`, probe `atomic-timing-before-20261014-01`에서 모델 로드 중 `submit.wait_timeout`/exit3을 재현했다. 완료된 writer52개를 측정했다. writer 전체 최대1.634초, atomic 자체 최대0.651초였다. 완료 대기는 앞선 이벤트 append와 atomic을 모두 포함하므로 `writer.atomic_json`이라는 진행 호출 표지만으로 해당 함수 내부에서1초가 소요됐다고 해석할 수 없다.

기존 각 heartbeat는 이벤트 history fsync와 최신 snapshot fsync를 모두 수행했다. state lock도 완료 I/O를 기다리는 동안 유지했다. 이것이 코드에서 확인한 중복 I/O와 잠금 유지 지점이다. 각 측정은 벽시계 시간이며 syscall 외에 스케줄링·GIL 재개 지연도 포함한다. 저장장치 장애나 특정 syscall의 kernel 내부 원인까지 확정하지 않는다.

## 분리 측정

JSON 직렬화와 실제 stream 쓰기를 분리하고 open·write·flush·fsync·close·replace·cleanup, queue/lock 대기, writer 총시간을 측정했다. `JUDGMENT_TELEMETRY_TIMING=1`에서만 원문 없는 계측을 0600 private 파일에 남긴다.

아래는 보완 전52개와 최종 보완 모델 전용 시험79개 완료 기록의 **최대값(ms)**이다. 실행 시 host GPU 기준값도 달랐으므로 통제된 성능 A/B 결과가 아니다.

| 구간 | 보완 전 | 최종 시험 |
|---|---:|---:|
| 직렬화 | 0.103 | 0.094 |
| open | 27.372 | 10.259 |
| write | 524.451 | 0.463 |
| flush | 69.514 | 7.609 |
| fsync | 221.113 | 867.433 |
| close | 0.171 | 203.460 |
| 파일 교체 | 27.786 | 549.852 |
| cleanup | 43.043 | 74.418 |
| atomic 전체 | 650.501 | 1,695.292 |
| state 잠금 대기 | 260.011 | 0.008 |
| queue 대기 | 0.280 | 89.278 |
| writer 전체 | 1,633.593 | 1,695.686 |

writer 전체 중앙값은215.299→119.991ms, fsync 중앙값은100.280→109.310ms다. 잠금 대기를 줄였지만 fsync·파일 교체의 일시적 지연은 남아 있다. 기록1초 제한을 늘려 지연을 가린 보완이 아니다.

## 최소 변경과 안전 경계

- heartbeat history는 flush만 하고 최신 snapshot의 durable fsync는 유지한다. 단계·optimizer 이벤트 history는 기존 fsync를 유지한다.
- state 갱신과 enqueue는 같은 lock 안에서 순서를 보존한다. 기존1초 완료 대기는 lock 밖으로 옮겼다.
- 일반 기록의 완료 대기 초과는 `delayed`와 독립 `telemetry.delay.min.private.jsonl`로 표시한다. 일반 지연이 메모리 감시 실패로 분류되지 않는다.
- 실제 writer 예외, queue 포화, 종료 시 미완료는 여전히 fatal이다. 정상 종료에서 writer drain이 끝나지 않으면 기록 정상 완료로 판정하지 않는다.
- 메모리 조회·host GPU 계수·6GiB 초과·stale snapshot 및 시간/디스크 안전 guard는 변경하지 않았다. 독립 오류 로그와 소유 worker 종료도 유지한다.

읽기 전용 리뷰1회 Critical0/Important0/Minor1이었다. 지연 로그 daemon의 FD 종료 경합은 복제 FD를 daemon이 소유하고 닫도록 TDD RED→GREEN으로 수정했다. 재리뷰는 하지 않았다.

## 검증과 제한

일반 지연 비치명·lock 밖 대기2개 실패를 먼저 확인하고 구현했다. 초기 영향 시험의 보완 오류는 새 delay FD 초기 실패 경로 회수 누락2개와 기존 시험 wrapper의 반환값 누락1개였고 수정 후23 PASS/1 skip이었다. 최종 제품 코드 기준 Windows 전체116개 중112 PASS/조건부4 skip이다.

현지 시험용30ms 지연 주입을 정상 종료 drain에도 적용해서 FD 시험과 일반 지연 시험이 각각 실패한 문제는 테스트에서만 지연 주입과 정상 종료1초를 분리해 수정했다. 최종 현지 **5개 전부 PASS**이며 실제 프로세스로 6GiB+1byte 중단, 메모리 조회 실패 중단, owned worker 종료/무관한 대조 process 생존을 확인했다. 제품1초 제한은 그대로다.

모델 전용 시험은 기존 immutable image `sha256:55a6560f149bf076a44d4b6ee3f22c5e3092e52ffd337f0466c3f008fa2ef7bf`, network none/RAM4GiB/총RAM+swap8GiB/GPU6GiB 감시에서 수행했다.

| 시도 | 결과 |
|---|---|
| 계측·기존 정책, e586331 | 모델 로드 중 일반 기록 완료 대기1초 초과/exit3 |
| 첫 보완, 6994eba | writer 최대0.261초·지연/오류 없음,37.716초 host GPU6.164GiB 초과로 안전 중단 |
| 최종 제품 보완, 8409aab | 모델 로드 중 일반1초 지연은 경고 후 계속,63.103초 host GPU6.267GiB 초과로 안전 중단 |

최종 시도의 독립 fatal 기록은 없고 지연 로그에 `progress_delay / submit.wait_timeout / model_load / writer.atomic_json`이 남았다. 실제 중단 사유는 **vram_limit**, 표본6,728,904,704bytes다. 일반 지연을 안전 실패로 오인하지 않고 실제6GiB 초과를 중단한 경로를 확인했다. 마지막 모델 단계는 `model_load`, optimizer0이다. 모델 로드 완료 및 이후 지정80회 반복 기록은 미완료이며, 실제 가용 GPU 여유에서 공동 재검증이 필요하다.

원본 초기 가중치 hash 불변, 이번 producer PID9362/9818/10248 및 own 컨테이너 잔류0을 확인했다. 비공개 계측·중단·지연 로그는 PCWSL `.work/model_load_probe/atomic-timing-{before,after,final}-20261014-01`에 보존했다. A/B 학습·optimizer·평가·final-test 접근·다른 서비스/driver 변경·Windows 비공개 역복사는 없다. **공동 검증이 미완료이므로 A/B 재실행은 제안하거나 시작하지 않는다.**
