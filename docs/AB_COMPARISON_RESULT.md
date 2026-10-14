# 승인된 A/B 비교 실행 기록 — 자원 상한 중단

2026-10-14 / 담당 어울 / **Windows·PCWSL 모두 RESOURCE_LIMIT_STOP, 비교 결과 미산출**

## 최신 판정 — 승인된 PCWSL 시도

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
