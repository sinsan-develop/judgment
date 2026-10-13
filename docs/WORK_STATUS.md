# judgment 작업현황

## 2026-10-13 G0 / 담당 어울

- 신산님이 설계·계획·Native 실행·작업 branch commit/push 승인.
- Task 1–4와 Task 5 fixture 코드부터 진행. 실제 데이터·모델 준비·설치·학습은 G1, 품질은 G2, 데이터/모델 공개·배포는 G3.
- branch `work/native-synthetic`. 원격 ref 0에서 최초 목적 branch 생성. main 생성·병합 없음. 별도 복제본/임시 자원 없음.
- Task 1: complete. RED(미구현 import)→GREEN 4/4. 가변 후보·원문 비노출 오류·예약 ID·무ML import 검사. 실제 모델 미검증.
- Pre-flight: 계약→어댑터→점수→정책→평가, 정규화→그룹 split→runner 자료형 유지. split role 검사 및 미확정값 null 유지.
- 운영 정보는 로컬 환경 문서에만 기록한다. 자동 승인 검토가 인프라 정보 포함 문서 push를 거절해 업로드 대상에서 제외했다. 코드·합성 시험·인프라 없는 설명만 동기화한다.
- 초기 sandbox Git/SSH/CIM 제약은 native OpenSSH 및 읽기 전용 escalation으로 해소. 인증 설정 변경 없음. Python 경로 경고 발생, 테스트 exit 0. 실제 패키지 호환성 미검증.
- 다음: Task 2–5 fixture와 독립 리뷰. 실제 학습·품질 결과는 미완료.
- Task 2: complete. RED→GREEN 7/7. 실제 소스 심볼 읽기 확인, fixture token 손실·충돌·맥락·revision·local-only 경계 확인. 실 tokenizer/학습 의존성 미검증. tempfile cleanup 제한 1회: 임시 생성이 필요 없는 누락 경로 fixture로 변경; 잔여 경로 없음 확인.
- Task 3: complete. RED→GREEN 9/9. 전이 연결 그룹 분리·재현성·미래 발화 제외·gold 위치 변경·manifest 원문 제외. 실제 AI Hub 스키마는 미구현/미확인, 합성 mapping만 검증.
- Task 4: complete. RED→GREEN 정책 7/7·평가 4/4. calibration/selection/test 역할 차단, 명시 기권·동률·비정상 점수·미지원 bucket, 손계산 NLL/Brier/ECE·macro-F1, coverage 0의 risk=null, 그룹 bootstrap 확인. 합성 기준 숫자는 실제 G2 기준이 아니다.
- Task 5 fixture: complete. RED→GREEN runner 7/7、CLI preflight/train 合成実行 확인. 실제 optimizer 호출 0, trained=false. G1 이전 실제 데이터 mapping·학습 CLI·reload·optimizer 관측·AMP dtype 확인은 미완료. 실제 어댑터 테스트는 G1 조건부 SKIP.
