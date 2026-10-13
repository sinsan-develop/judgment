# 데이터·라이선스 경계

현재 데이터는 tests/fixtures의 자체 작성 합성 한국어 예제뿐이다. AI Hub 실제 파일 스키마·이용 조건·품질은 미확인이다. 실제 ingest 전 명시 mapping, 출처·버전·조건 링크·개인정보·라벨 누락·분포 검사와 그룹 수를 G1에서 확인한다.

원본·대화·변형 그룹의 전이 연결 성분을 한 split에 배정한다. train/calibration/selection/test를 분리하고 test는 학습·보정·정책 선택에 사용하지 않는다. manifest 공개본에는 원문·원문 해시·행/그룹 식별자 목록을 넣지 않는다. 실제 JSONL·캐시·questions.json·train_report·가중치·원문 로그는 로컬 전용이다.

Laya 모델·소스 Apache-2.0, mmBERT 백본 MIT 표기는 승인 설계의 참고 정보다. 실제 포함 파일의 LICENSE/NOTICE·수정 표시 및 데이터별 조건은 G1/G3에서 확인한다. upstream 소스/모델은 현재 배포물에 포함하지 않는다. 자체 코드와 최종 모델 공개 라이선스는 미결정이며 임의 LICENSE를 부여하지 않았다.

Aidot 비공개 자료·계정·원문은 사용하지 않았다. 지정 개발 Git의 코드·합성 예제 동기화는 데이터·모델 공개 승인을 의미하지 않는다.
