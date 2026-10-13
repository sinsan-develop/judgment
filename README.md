# judgment

한국어 발화·맥락·가변 후보를 입력받아 후보 선택 또는 기권을 검증하는 Python 파이프라인이다. 현재는 합성 데이터 검증 단계이며 실제 한국어 모델 학습이나 품질 향상을 주장하지 않는다.

## 실행 환경

Windows 기존 Python 3.14.3과 표준 라이브러리만 사용한다. 설치·모델/데이터 다운로드 없이 저장소 루트에서 다음 명령을 실행한다.

```powershell
python -m unittest discover -s tests -t . -v
$env:PYTHONPATH = 'src'
python -m judgment preflight --config configs/experiment.example.json
python -m judgment train --config configs/experiment.example.json
python -m judgment evaluate --config configs/experiment.example.json
```

원격 동기화·배포는 실행하지 않는다. 실제 의존성 호환성과 학습 자원은 G1에서 확정한다.

작업현황은 `docs/WORK_STATUS.md`다. 승인 설계·계획 원문과 인프라 정보가 있는 환경 문서는 로컬 전용으로 보존한다.

G1은 실제 데이터 이용 조건·mapping·분리 수량, canonical checkout, 장비, 고정 모델 revision, 설치 목록, 다운로드량·저장 경로·자원 한도·학습 설정의 묶음 승인이다. G2 품질 기준과 G3 데이터/모델 공개·배포는 별도다. main 병합·force push를 하지 않는다.

`train`의 fixture 모드는 optimizer를 호출하지 않고 데이터 계약만 검사한다. `evaluate`는 사전에 직접 작성한 합성 logits를 calibration/selection/test 역할로 나눠 보정·기권·지표 계산을 연결한다. 점수는 모델 출력이 아니며 평가 수치가 한국어 모델의 성능을 의미하지 않는다. split과 온도·임계값은 합성 시험 전용이며 G1/G2 실제 설정으로 승격하지 않는다.

실제 모드의 CLI는 G1 실제 mapping·정책 sidecar 확인 전 차단된다. backend 학습 호출의 tensor 갱신 검사·자원 감시는 작성했지만, 실제 reload·optimizer update 관측·학습 실패 회복과 CUDA/패키지 호환성은 아직 미검증이다. 현재 공개 점검은 파일 경로·금지 산출물·일부 secret pattern을 검사하며 stage diff의 원문·비공개 내용 검토를 대체하지 않는다.
