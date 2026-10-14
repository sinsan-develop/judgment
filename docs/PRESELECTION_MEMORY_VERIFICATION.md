# 학습 전 선택 평가 메모리 보완·실측·A/B 제안

2026-10-14 / 담당 어울 / **선택374건 학습 전 평가 PASS, 실제 학습·A/B는 미실행**

## 진단과 최소 보완

고정 upstream `c73908d96ff73c0062c340a11bf7c54ec7d8bc4d`의 `calibration_records`는 기본 batch16, `@torch.no_grad()`, `model.eval()`, `_forward(..., amp=False, detach_encoder=False)`다. 각 배치 logits를 `.cpu().numpy()`로 옮겨 CPU records에 보관하므로 **GPU에 결과를 계속 쌓는 구조는 아니다.** 이전 `before_training_selection`의 일시적 allocated 피크와 reserved 증가가 batch16 forward 구간에서 관측됐다.

`bounded_evaluation_forward`를 평가 호출 동안만 적용했다. 원래16건 collate의 token IDs·attention/marker mask·padding 길이·순서·target·메타데이터를 유지하고, GPU forward만1행씩 같은 원래 `_forward`로 수행한다. 출력은 즉시 CPU로 옮겨 CPU에서 cat하고 기존 `calibration_records`와 `evaluate_records`에 전달한다. eval/no_grad/fp32와 점수 함수는 그대로다. 예외에도 원래 `_forward`를 복구하며 학습 forward·optimizer·학습 batch/LR/seed에는 적용하지 않는다. 전후 평가의 메모리 경로를 동일하게 제한했다. upstream 원본 Git clean도 확인했다.

## 검증 결과

실행 소스 `fc0eb0e59c1719b4a08055260d26af58de1d532a`, PCWSL probe `preselection-memory-20261014-01`. 기존 이미지·전용 runtime·network none/RAM4GiB/총RAM+swap8GiB/GPU6GiB·1800초 guard를 유지했다. 새GPU3표본 모두 **2.525337GiB**로 확인한 뒤 실행했다. 선택 자료374건의 기존 JSONL·입력 변환·`label_smoothing=0`·checkpoint를 사용했고, 원본 입력/초기 가중치 hash 불변을 확인했다.

| 항목 | 결과 |
|---|---:|
| 전체 probe | **70.185초, exit0** |
| 실제 학습 전 선택 평가 구간 | **13.220초**, 374건 완료 |
| 평가 순서/skip | 기존 순서/skip0 |
| GPU 점수 동등성 표본 | 동일16건 padding, 원래2행 forward 대 보완1행 |
| 표본 logits 최대 절대 오차 | **0.0**; rtol/atol1e-5 검사 PASS |
| 표본 최상위 후보 | 전부 동일 |
| 결과 보관 | CPU, 374건 점수 finite |
| optimizer·학습·A/B | **0회** |
| final-test 내용/hash 접근 | **0회** |

기존 batch16 전체 GPU 출력을 다시 실행해 비교한 것은 아니다. 같은 원래 점수 함수를 사용했고 실제 GPU2행/1행 표본 및 입력 보존을 검증한 범위다. 이 결과를 품질 향상이나 새로운 holdout 평가로 해석하지 않는다.

| 메모리 | 이전 중단 기록 | 보완 평가 실측 |
|---|---:|---:|
| 자체 peak allocated | 3,004,742,656bytes /2.798GiB | **1,479,220,224bytes /1.378GiB** |
| 자체 peak reserved | 4,303,355,904bytes /4.008GiB | **1,614,807,040bytes /1.504GiB** |
| 전체 host GPU 표본 피크 | 6.877GiB, 중단 | **4.322601GiB**, 6GiB 이내 |
| 이번 시작 대비 host 추가량 | 해당 없음 | **1.797264GiB** |

allocated/reserved는 합산하지 않는다. 이전 전체 A 경로와 이번 평가 전용 probe의 주변 상태가 같지는 않으므로 엄밀한 성능 A/B 수치로 표현하지 않는다. 이번 host 추가량은 모델 로드·동등성 표본·평가를 포함한 probe 최대 계수의 시작 대비 차이이며 자체 resident VRAM과 같은 범위가 아니다.

합성 TDD의 미구현 RED와 실제 meta list 구조 RED를 보완해 CPU 입력·padding·점수·예외 복구2시험 PASS다. 전체118개 중114 PASS/조건부4 skip, 읽기 전용 리뷰1회 Critical0/Important0/Minor0이다. 실제 GPU 평가 동안9개 host snapshot이 관측됐으며 마지막 snapshot은 평가 exit보다1.287초 뒤다. worker fatal/delay 로그는0행이다.

## 종료 뒤 snapshot 생산자 오류

컨테이너 probe는 정상 종료했으나 producer 종료 값은1이었다. 현지 허용 오류 코드 조회로 **`snapshot_recording_failed`**를 확인했다. 평가 exit 시각1791954975.467, summary 생성1791954976.358, 마지막 history snapshot1791954976.754, producer 오류 로그 갱신1791954980.826이다. **평가 종료 이후 정리 구간의 snapshot 기록 실패**이며 평가 도중 host 관측이 먼저 끊긴 사례는 아니다.

이 코드는 snapshot의 bounded 기록1초가 성공하지 못했음을 의미하고, 실제 write 예외인지 대기 초과인지까지는 producer가 구분하지 않는다. 해당 정리 오류를 정상 종료로 숨기지 않는다. stale15초 거절·GPU6GiB·worker 중단 guard는 변경하지 않았다. 추가 모델/학습 시험이나 별도 producer 코드 보완은 이번 측정 뒤 수행하지 않았다. producer PID13429와 이번 container 잔류0, 고정 upstream clean을 확인했다.

## 실측 근거의 시작 조건·A/B 제안

이번 최대 추가량1.797264GiB와 자체 reserved1.503906GiB 중 큰 **1.797264GiB**를 기준으로 잡고, **1GiB 추가 여유**를 둔다. `6 - 1.797264 - 1 = 3.202736GiB`이므로 시작 기준을 보수적으로 내림해 **전체 GPU≤3.0GiB, 서로 다른 시각의 fresh3표본 연속 확인**을 제안한다. 계수는 기존 adapter별 `max(dedicated+shared, committed)` 합계이고 중단6GiB는 그대로다.

제안은 A 원본697건/B 선별280건·잠정 정답49건·고정 반복순서/ID/그룹 추적, 같은 초기 가중치·기존 학습 설정·각697노출/88optimizer, **총1800초**에서 A 정상 완료 후 B를 진행하는1회다. 평가 자료·입력·점수 함수는 그대로이고 eval GPU forward만1행으로 제한한다. calibration/selection만 비교, final-test 비접근, 실패 자동 재시도0을 유지한다. 효과는 선별·정답 수정·반복 노출의 합친 효과로 보고한다.

이번 실측은 학습 전 평가의 근거이며 실제 학습·reload·전체 후속 단계 피크와 완료는 미검증이다. 시작 조건이 미래 전체 peak를 보장하는 것은 아니므로 기존 독립 감시가 계속6GiB를 강제한다. producer 정리 오류도 다음 실행에서 별도로 관찰·보고해야 한다. **A/B는 제안만 했으며 별도 승인 전 실행하지 않는다.**

비공개 점수·측정·headroom·검증 요약은 PCWSL `.work/preselection_probe/preselection-memory-20261014-01`과 해당 runtime 폴더에 보존했다. 원문/점수/가중치 Git 업로드·Windows 역복사·다른 프로그램/서비스 종료·한도 완화는 없다.
