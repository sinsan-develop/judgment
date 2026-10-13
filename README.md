# judgment

한국어 발화·맥락·가변 후보를 입력받아 후보 선택 또는 기권을 검증하는 Python 파이프라인이다. 현재는 합성 데이터 검증 단계이며 실제 한국어 모델 학습이나 품질 향상을 주장하지 않는다.

## 실행 환경

Windows 기존 Python 3.14.3과 표준 라이브러리만 사용한다. 설치·모델/데이터 다운로드 없이 저장소 루트에서 다음 명령을 실행한다.

```powershell
python -m unittest discover -s tests -t . -v
$env:PYTHONPATH = 'src'
python -m judgment preflight --config configs/experiment.example.json
```

원격 동기화·배포는 실행하지 않는다. 실제 의존성 호환성과 학습 자원은 G1에서 확정한다.

작업현황은 `docs/WORK_STATUS.md`다. 승인 설계·계획 원문과 인프라 정보가 있는 환경 문서는 로컬 전용으로 보존한다.

G1은 실제 데이터 이용 조건·mapping·분리 수량, canonical checkout, 장비, 고정 모델 revision, 설치 목록, 다운로드량·저장 경로·자원 한도·학습 설정의 묶음 승인이다. G2 품질 기준과 G3 데이터/모델 공개·배포는 별도다. main 병합·force push를 하지 않는다.
