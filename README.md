# judgment

한국어 발화·맥락·가변 후보를 입력받아 후보 선택 또는 기권을 검증하는 Python 파이프라인이다. 승인된 최초 헤드-only 1 epoch의 실제 갱신·reload·독립 비교를 확인했다. test 정확도 향상은 없었으며 품질 합격은 미결정이다. 결과는 `MODEL_CARD.md`에 기록한다.

## 실행 환경

합성 계약은 기존 Python 3.14와 표준 라이브러리로 검사한다. 실제 optimizer/model 시험은 명시된 전용 환경·설정이 있을 때만 실행한다. 아래 fixture 명령은 모델/데이터 다운로드와 실제 학습을 하지 않는다.

```powershell
python -m unittest discover -s tests -t . -v
$env:PYTHONPATH = 'src'
python -m judgment preflight --config configs/experiment.example.json
python -m judgment train --config configs/experiment.example.json
python -m judgment evaluate --config configs/experiment.example.json
```

코드·합성 시험·원문 없는 기록은 지정 작업 branch에 보존한다. 실제 데이터·모델·설정·출처 mapping은 로컬 ignored 영역에만 유지하며 배포하지 않는다.

작업현황은 `docs/WORK_STATUS.md`다. 승인 설계·계획 원문과 인프라 정보가 있는 환경 문서는 로컬 전용으로 보존한다.

G1은 실제 데이터 이용 조건·mapping·분리 수량, canonical checkout, 장비, 고정 모델 revision, 설치 목록, 다운로드량·저장 경로·자원 한도·학습 설정의 묶음 승인이다. G2 품질 기준과 G3 데이터/모델 공개·배포는 별도다. main 병합·force push를 하지 않는다.

`train`의 fixture 모드는 optimizer를 호출하지 않고 데이터 계약만 검사한다. `evaluate`는 사전에 직접 작성한 합성 logits를 calibration/selection/test 역할로 나눠 보정·기권·지표 계산을 연결한다. 점수는 모델 출력이 아니며 평가 수치가 한국어 모델의 성능을 의미하지 않는다. split과 온도·임계값은 합성 시험 전용이며 G1/G2 실제 설정으로 승격하지 않는다.

실제 `train`은 승인 scope·clean SHA·명시 mapping·file digest·분할 독립성·토큰·upstream 누락·실제 optimizer 횟수·자원 상한을 검사한다. 성공에는 head tensor 갱신·encoder 불변·전체 tensor reload가 필요하며, 실패/불완전은 nonzero exit다. 실제 CLI `evaluate`의 정책 판정은 G2 기준 확정 전 차단한다. G1 독립 비교는 사전 온도 grid와 명시 기권만으로 측정했으며 정책을 선택하거나 품질 합격을 선언하지 않았다.

고정 설치 후보는 `docs/requirements.g1.txt`다. 승인된 전용 Windows 환경에서 실제 설치·CUDA·tokenizer·학습을 확인했지만 다른 장비/환경의 호환성을 보장하지 않는다. 공개 점검의 경로·일부 secret pattern 검사는 수동 diff 검토를 대체하지 않는다.
