# A/B 공통 worker 환경 사전검사와 1회 실행 승인안

2026-10-14 / 담당 어울 / **동일 child의 모델 로드 사전검사 PASS, A/B 추가 실행0**

## 실행 환경 대조와 통일

| 구분 | 인터프리터 | 작업 경로 | 모듈 경로 |
|---|---|---|---|
| 앞선 통과 임시 모델 시험 | `/opt/venv/bin/python` | `/workspace` | `/workspace/src:/workspace/.work/upstream/laya` |
| 실패한 A/B 부모 launcher | 위와 같음 | 위와 같음 | 위와 같음 |
| 실패한 A/B child worker | 위와 같음 | 위와 같음 | `/workspace/src`만 전달 |
| 보완 후 실제 A/B child와 사전검사 | 위와 같음 | 위와 같음 | **src+고정 upstream 두 경로** |

고정 이미지 `sha256:55a6560f149bf076a44d4b6ee3f22c5e3092e52ffd337f0466c3f008fa2ef7bf`, PCWSL 정본 `/home/daon/deploy/judgment`를 `/workspace`로 연결하는 기존 GPU·ROCm read-only 연결/network none/RAM4GiB·총RAM+swap8GiB를 재사용했다. 글로벌 설치·새 venv·다른 모델/라이브러리 위치를 만들지 않았다.

`runner.worker_invocation`이 현재 launcher의 `sys.executable`, canonical cwd, 승인된 두 PYTHONPATH를 함께 구성한다. 실제 A/B의 `run_training`과 사전검사가 이 함수를 그대로 사용한다. child 명령은 둘 다 `같은 Python -m judgment _train-worker --config ...`이며 사전검사만 `--precheck-only`를 추가한다. 입력 검증·감시·동일 `LayaAdapter.from_local` 모델 로드를 거친 뒤 optimizer 앞에서 반환한다. 기록도 실제 A/B가 사용하는 기존 `.work/runs/run-*` 구조다. 검증 전용 loader/root/module 경로를 사용하지 않았다.

실제 outer launcher도 검증과 A/B 모두 위 고정 이미지 안에서 `/opt/venv/bin/python docs/run_ab_comparison.py ... --root /workspace`를 사용한다. 사전검사는 `precheck`, A/B는 `run --trial-id <새 승인1회 ID>`만 다르며 Python·cwd·환경·mount·GPU·자원 제한은 동일하게 유지한다. 별도 인터프리터 자동 탐색이나 글로벌 설치로 대체하지 않는다.

## 실제 사전검사 결과

실행 source **`f50e0210091847691ac2e66b3614d5f78377793b`**, runtime `worker-launcher-precheck-20261014-01`. 실제 실행 명령은 A/B launcher의 `precheck`다.

| 항목 | 결과 |
|---|---|
| fresh 시작 표본3개 | 모두 **2.724380GiB≤2.75GiB** |
| child 인터프리터/cwd | `/opt/venv/bin/python` / `/workspace` |
| child PYTHONPATH | `/workspace/src:/workspace/.work/upstream/laya` |
| Python / Laya 버전 | **3.12.3 / 0.4.6** |
| import된 Laya 소스 | `/workspace/.work/upstream/laya/laya/__init__.py` |
| Laya 고정 Git 소스 | **`c73908d96ff73c0062c340a11bf7c54ec7d8bc4d`**, clean |
| 모델 로드 | **PASS**, 고정 source 위치 검사와 기존 checkpoint provenance 검증 |
| worker / parent / 생산자 종료 | **모두0** |
| child 관측 / 준비·정리 포함 전체 | **60.514초 / 84.040초** |
| 마지막 저장 단계 | **worker_precheck_complete** |
| 자체 allocated / reserved 피크 | **1,307,833,856 / 1,333,788,672bytes** |
| host GPU 표본 피크 | **4,353,105,920bytes / 4.054146GiB**, 6GiB 이내 |
| host 기록 | **64표본**, 최대간격4.821초, producer 실패0 |
| 독립 fatal / 일반 기록 지연 | **0행 / 1건 비치명 경고**, 정상 완료 |
| optimizer / 학습 / A/B | **0회** |
| 원본8파일·고정 초기가중치 hash | **보존** |
| final-test 내용/hash 접근 | **0회** |

사전검사 결과는 기존 `.work/ab_comparison/worker-precheck.latest.private.json`에, 실제 child 환경은 해당 표준 run의 `worker.runtime.private.json`에 보존했다. worker 반환 결과의 status는 `worker_precheck_verified`, trained=false, optimizer_updates_observed=0이다. 이번 owncontainer와 producer17251 잔류0을 확인했고 타프로그램·서비스·driver·상한은 변경하지 않았다. Windows 역복사는 없다.

## traceback와 비밀값 처리

실제 worker CLI의 예외는 표준 stderr traceback으로 parent에 전달한다. 실제 parent의 보존 모드에서는 기존 `worker.output.private.jsonl`에 traceback 줄·예외 종류·메시지·소스 위치를 유지하고 환경 credential 값, API key/token/password, Bearer/Basic, HTTP 인증 URL 값만 가린다. 파일은0600이며 비공개 현지 기록이다. 공개 보고서에는 원문 로그를 복사하지 않는다. 모르는 예외 종류를 `redacted_exception`으로 통째로 지우지 않는다. 긴 traceback 줄도 보존 모드에서 기존4096바이트 생략을 적용하지 않는다.

원래 표준 출력의 전체 생략 모드는 fixture 등 기본 시험에 유지하고 실제 worker parent에만 보존 모드를 사용했다. 출력 transcript는 flush로 기록하며, 단계·완료 optimizer·중단 packet의 기존 durable 기록과6GiB·stale15초·시간 중단은 유지했다. 예외·traceback·secret 마스킹·공통 명령·CLI 전파4시험 RED→PASS, PCWSL4시험 PASS. 최종 Windows 전체 **128개 중124 PASS/조건부4 skip**다. 이번 실제 사전검사는 성공했으므로 실제 모델 오류 traceback은 발생하지 않았으며, 오류 보존 확인은 합성 시험 범위다.

## 승인 요청 범위: 같은 경로의 A/B 1회

사전검사를 통과한 위 interpreter/cwd/module/image 경로로만 **새 A/B 비교1회**를 제안한다. 현재는 승인안 보고까지이며 추가 A/B를 실행하지 않았다. 이전 실패 namespace와 로그는 보존한다.

1. 시작 직전 서로 다른 시각의 fresh GPU 표본3개가 연속 **전체≤2.75GiB**일 때만 A를 시작한다. 부족하거나 감시가 불가하면 시작하지 않는다.
2. 기존6GiB 감시·총1800초·기존 학습 설정을 유지한다. A 원본697건, B 선별280건·잠정 정답 수정49건·고정 반복순서/원본ID/그룹 추적, 각697노출·88optimizer 계획이다. 학습은 head-only/frozen encoder/fp32/micro_batch1/grad_accum8/기존LR·seed13·epoch1이다.
3. A가 학습88갱신·기존 검증과 보정/선택 측정을 정상 완료한 경우에만 자원을 해제한다. active_training_worker0·allocated/reserved0을 기록하고 B 직전 **fresh3표본≤2.75GiB를 새로 확인**한다. 조건 미충족이면 B를 시작하지 않는다.
4. B는 A나 임시 검증 가중치를 사용하지 않고 **같은 고정 초기 가중치**에서 시작한다. 두 arm의 initial tensor 증거와 원본/초기 hash 불변을 확인한다.
5. calibration/selection만 비교하고 final-test 내용/hash는 열지 않는다. 결과는 자료 선별·잠정 정답 수정·반복 노출의 **합친 효과**로 보고한다.
6. 실패·중단 시 자동 재시도 없이 마지막 단계·저장 완료 갱신 수와 정확한 최종수의 확인 여부·종료 코드·secret-masked traceback·독립 오류 로그·자체 allocated/reserved·adapter 전체 계수를 보고한다. 이번 자원만 정리하고 원본과 실패 증거는 보존한다.

이번 사전검사는 child import와 모델 로드까지다. 앞선 임시 학습에서 backward/optimizer2회와 실제평가를 검증했지만 **이번 통일된 child 경로에서 전체697노출·88갱신·저장/reload·A/B 완료는 미검증**이다. 모델 로드의4.054GiB만으로 시작 기준을 완화하지 않고 기존 실제 학습 실측에 근거한2.75GiB 조건을 유지한다.
