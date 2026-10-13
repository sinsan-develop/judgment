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
- Task 5 fixture: complete. RED→GREEN runner 7/7, CLI preflight/train 합성 실행 확인. 실제 optimizer 호출 0, trained=false. G1 이전 실제 데이터 mapping·학습 CLI·reload·optimizer 관측·AMP dtype 확인은 미완료. 실제 어댑터 테스트는 G1 조건부 SKIP.

## 합성 단계 최종 검증·인수 checkpoint

- Task 6 합성 범위: 공개 제외 검사·MODEL_CARD·측정 계약·CLI 합성 평가 연결 완료. 실제 기본/학습 모델 독립 비교는 미완료.
- Native 최종 검사: `python -m unittest discover -s tests -t . -v` → 53 실행 / 52 PASS / 실제 모델 1 SKIP. `compileall` exit 0. CLI preflight·train·evaluate 실행 확인.
- evaluate는 사전 작성 합성 logits와 독립 역할 split을 사용한다. 최종 test는 합성 1행이며 실제 모델 성능·품질 합격을 의미하지 않는다. `quality_status=not_decided`, `trained=false`, 실제 optimizer 0.
- 독립 리뷰 1회: Critical 0, Important 3, Minor 2. worker gate/scope·dirty 코드·공개 점검 fail-open을 수정했다. fixture 평가 연결과 종료 후 디스크 검사도 해결했다. worker 자원 감시와 canonical import 검사를 추가했다. 새 리뷰를 반복하지 않았다.
- 회귀: worker 미승인, 파일 누락/외부 경로, fixture 지표, 종료 디스크 상한은 실패→통과를 확인했다. dirty 코드 거절 시험 통과. upstream question encoder list 반환형 오류는 실패→통과를 확인했다. 실제 finetune boundary에 soft-ce/shuffle/calib=0/eval_data=selection 전달을 mock 호출로 확인했다.
- Python sandbox shim 경고·realpath 이상은 Native 검사에서 재현하지 않았다. 공개 파일 점검은 lexical 절대경로 경계도 검사해 fail-open을 방지했다.
- 완료: Task 1–4, Task 5 fixture, Task 6 안전한 합성 검증·카드·독립 리뷰.
- 미완료/미검증: G1 데이터 조건·실제 mapping/수량·의존성 설치·실제 tokenizer/모델·실제 학습·가중치 reload·optimizer 횟수·실제 하드웨어 측정, G2 품질 판정, G3 모델/데이터 공개·배포. 실제 모드 CLI는 필요한 mapping·policy 확인 전 차단한다.
- 실행 판단: 최초 원격 branch가 없어 main 기준 격리가 불가했으며 계획의 최초 목적 branch 조항을 적용했다. 비용은 main 기준 인수 이력이 아직 없다는 점이다. 실제 AMP precision 자동 선택을 검증하기 전 fp32만 허용하고 나머지는 명시 차단한다. 비용은 혼합 정밀도 실행이 G1 후검증까지 지연된다는 점이다.
- 미룬 review finding 없음. 실제 환경/패키지 호환성은 승인 경계의 미검증으로 유지한다.
- 마지막 원격 checkpoint: `f369ceb10bfa227d5145293be49b6e278d84cb4e`. 최종 보존 commit은 이 기록 및 최종 diff를 포함해 push 후 직접 SHA를 대조한다.
- 안전한 upload 대상은 코드·자체 합성 시험·인프라 없는 문서뿐이다. 환경/승인 원문/G1 인프라 승인안은 로컬 보존. 기존 파일·원격 경로·credential 변경 없음. 임시 process·port·container·모델 cache·실데이터 생성 없음.
- rollback: 작업 branch의 Task별 기존 commit으로 복구 가능. main 병합·배포 없음.
- 다음 조치: 로컬 G1 승인안의 장비·설정·비용·디스크 한도를 신산님과 확정하고 AI Hub 확보 상태를 확인해 실제 mapping·수량·고정 설치 목록을 채운다. G1 승인 전 다운로드·학습을 실행하지 않는다.

## 2026-10-14 데이터 보유 확인 / 담당 어울

- 신산님 검토: Windows 로컬 GPU 준비, Python 3.14 선제 교체 없음. 헤드-only·1 epoch·최대 2,000행은 최초 실행 검증 범위. 저장 30 GiB/RAM 24 GiB/VRAM 6 GiB/30분 상한은 실제 사용량으로 확인. 실제 학습 승인은 데이터 확인 이후.
- 프로젝트 파일과 사용자 다운로드 폴더의 관련 파일명 확인 결과, AI Hub 116 실파일을 찾지 못했다. 다른 저장 위치와 계정 신청·승인 상태는 미확인이다. 확인 범위 밖 전체 디스크 탐색 없음.
- PyTorch 공식 Windows 안내의 Python 3.10–3.14 지원 범위를 확인했다. 실제 Laya 포함 의존성·CUDA 호환성은 미검증으로 유지한다.
- 변경: 로컬 G1 승인안과 이 기록. 코드 변경·데이터/모델 다운로드·패키지 설치·학습 없음. 문서 변경만으로 테스트를 반복하지 않았다. 오류 0회.
- 다음: 기존 확보 자료의 다른 경로가 있는지 확인한다. 없으면 AI Hub 116 신규 확보·조건/스키마 확인부터 진행하고 실제 학습 승인안을 완성한다.

## 2026-10-14 AI Hub 116 신규 확보 조사 / 담당 어울

- 요청 범위: 신청·이용 동의 등 사용자 단계와 다운로드 전 필수 파일·용량의 읽기 전용 조사.
- 공식 데이터 페이지·FAQ·Shell 가이드·공개 파일 목록 메타데이터 확인. 현재 대상 ZIP 1개: 한국어대화_new_260226.zip, filekey 562173, 7,353,351 bytes(7.01 MiB). 데이터 설명서는 fileSn 8018, 크기 HEAD 조회 403으로 미확인.
- 필요 조치: 신산님 계정의 신청·이용 조건 확인/동의·제출·승인 상태 확인. 어울은 승인 후 개별 파일 확보·스키마·그룹/split 수량·해제 공간을 점검하고 학습 승인을 별도로 받는다.
- 검증/변경: DATA_AND_LICENSES와 이 기록. 코드 변경 없음. 기존 tests 반복 없음. 데이터/모델/설명서 본문 다운로드, 설치, API key 발급, 신청 제출, 학습 없음.
- 오류: 비표시 브라우저 탭 생성 timeout 1회·탭 미생성 확인. 공식 공개 HTTP 조회로 파일 목록 확인. 설명서 HEAD 접근 제한 1회, 우회/반복 다운로드 없음.
- 미검증: 로그인 후 신청 폼의 정확한 항목·개별 이용 동의 내용·사용자 승인 상태·ZIP 내부·압축해제량. 3배 공간 산술값 약 21.04 MiB는 실제 해제량 보장이 아니다.
- 다음: 신산님의 AI Hub 116 신청·승인 상태 확인 후 다운로드 대상으로 562173을 재확인한다. 전체 프로젝트 자원 상한 및 실제 학습 별도 승인 유지.

## 2026-10-14 사용자 제공 데이터 확인 / 담당 어울

- 신산님이 원본 ZIP 보유 위치를 지정했다. 해당 파일의 크기·CRC·압축 구성·XLSX 헤더/행 수·누락/중복 여부를 읽기 전용 확인했다. 원문과 개별 식별자를 출력하지 않았다. 상세 집계와 원본 식별 digest는 로컬 G1 문서에만 기록한다.
- 확인: 파일 크기는 공식 목록과 일치, CRC 통과, XLSX 13개. 두 종류의 schema와 행/문장 중복·일부 필드 누락을 확인했다. 기존 합성 mapping을 실제 스키마에 그대로 적용하지 않는다.
- 조치: 사용자 지정 원본 ZIP을 정확한 .gitignore 규칙으로 제외했다. 원본은 추출·복사·수정·삭제하지 않았다. 개발 패키지 설치·실제 모델 준비·학습 없음.
- 검증: Git ignore/추적 여부 및 문서 diff 확인. 코드 변경 없음, 기존 테스트 반복 없음. bundled openpyxl의 기본 style 누락 경고 1회는 read-only 데이터 판독에 영향 없음을 확인했다.
- 미검증: 데이터별 이용 동의·명시 mapping/대화 연결·후보 라벨·고객/민원인 필터 이후 수량·개인정보 전체 검사·최종 split·실제 CUDA/dependency 호환성. 실제 학습은 데이터 확인 후 별도 승인 원칙 유지.
- 다음: 두 schema의 변환 규칙과 원본/대화/중복 연결 의미를 확인해 G1의 실제 학습 입력·수량을 확정한다.

## 2026-10-14 데이터 변환·그룹 판정과 G1 승인안 / 담당 어울

- 요청 범위 완료: 두 schema 변환 규칙·누락/상충/중복 처리·대화/출처 연결 기준·실제 수량·4분할 검증·구체적인 로컬 G1 승인안. 신산님이 본인 계정 다운로드 승인·이용 동의 완료를 직접 확인했다. 계정에 접속해 독립 확인한 것은 아니다.
- 변경: AIHUB116_CONVERSION, 재현 Python/출력 없는 notebook, hash 고정 설치 후보 requirements.g1, DATA_AND_LICENSES, 이 기록. 장비/로컬 경로/승인 원문은 Git 제외 G1 문서에 보존한다.
- 원본 95,955행 → 역할 제외 43,632 / 발화 누락 37 / 의도 누락 102 / 불연속 블록 8,761 / 동일 입력 gold 상충 248 → 유지 43,175행 → 완전 중복 초과 260 제거 → 42,915입력 사례. 서로 다른 현재 발화 39,366, 도메인별 의도 2,677(MAIN 문자열 2,537), 연결 그룹 3,042.
- 고객 QA=A는 사용자 응답으로 유지한다. gold 누락을 기권 gold로 만들지 않는다. 공공민원은 비식별 필드만 쓰며 명시 대화 ID가 없어 파일 단위 분할 금지/맥락 없음. 소상공인 복구 블록·완전 중복·같은 현재 발화의 전이 연결 성분을 쪼개지 않는다.
- 전체 train/calibration/selection/test 30,040/4,292/4,292/4,291사례. 6쌍의 입력·현재 발화·출처 블록 교집합 모두 0. 공식 검증 대화 ID·의미 paraphrase 누출 전부를 입증한 것은 아니다.
- 최초 후보 250개 완전 소상공인 연결 그룹, 양성 1,600, 의도 585. 정답 제외 파생 400개는 계획만 존재한다. 합계 최대 2,000, split 계획 1,400/200/200/200. 실제 후보 목록/JSONL/파생 사례/토큰 캐시 미생성.
- 로컬 G1 승인안: 고정 소스/모델·38개 hash 고정 Windows Python 3.14 의존성 후보·헤드-only 1 epoch·토큰/최소 표본 gate·다운로드/저장/RAM/VRAM/시간 상한·실측·중단/보존 조건을 구체화했다. wheel metadata/파일 크기는 준비 근거이며 실제 pip/CUDA/Laya 호환성 증거는 아니다.
- 오류/조치: 초기 metadata 조사에서 value_shapes가 원문 일부를 tool 출력에 포함한 오류 1회. 바로 인정하고 이후 모든 출력은 집계로 제한했다. Git 파일/원격에 원문을 저장하지 않았다. QA=A 제외 초안은 실제 역할 cross count로 교정했다. metadata resolver의 legacy version 파싱 실패 1회는 InvalidVersion 필터 후 해결했다. style 경고는 read-only 판독에 영향 없는 기존 유형이다. 미해결 실행 오류 0.
- 검증 PASS: 실제 ZIP CRC·상호 배타 제외 합계·입력 합계·43,175 원본 행 mapping/42,915 대표 행·그룹 closure·split 교집합·동일 seed 반복 요약 완전 일치·Python 컴파일·notebook 출력 없음/코드 컴파일·Git 제외/diff. Native 공개 파일 audit 6개 safe=true/findings=0, 수동 내용 확인. 기존 제품 코드 변경이 없어 합성 전체 tests는 반복하지 않는다; 앞선 52 PASS/실제 모델 1 SKIP는 현재 실제 데이터/모델 성공 증거로 확대하지 않는다.
- 미검증/미완료: 실제 tokenizer 최종 통과 수·개인정보 전체 검사·pip 설치·모델 준비·CUDA 실행·학습/가중치 갱신/reload·관측 optimizer 횟수·자원 peak·G2 품질 판정. 실제 학습/다운로드/설치 없음.
- 보존: 안전한 집계·코드·규칙만 work/native-synthetic에 commit/push. 사용자 ZIP·출처 매핑·로컬 요약·G1 승인 원문·장비/운영 문서는 제외. 원격 SHA는 push 뒤 조회해 최종 보고한다. main 병합·배포 없음.
- 다음: 신산님이 G1의 장비·설치/모델 준비·학습 설정·비용/저장/자원 상한을 묶어 승인한 뒤 해당 범위만 실행한다. 동의 완료 확인만으로 실제 학습 승인으로 해석하지 않는다.

## 2026-10-14 G1 승인·분할 상속·준비 ABI 검사 / 담당 어울

- 신산님 직접 승인: Windows 로컬 전용 준비·자원 상한 내 헤드-only 1 epoch 시험. 추가 조건은 확정 전체 분할에서 같은 250그룹을 상속 추출하고 그룹별 기록 저장·검증 후 학습, 재무작위 분할 금지. 현재 단계는 1단계 로컬 개발 검증이며 운영/배포/G2 품질 합격이 아니다.
- 변경 사유와 전후: 기존 pilot의 balanced_parts 재분할 → 확정 전체 group_map 로드·그룹/대표 행 구조 대조·split 상속. 실제 G1 경로는 전체 splitter도 호출하지 않는다. 이전 후보 계획 138/37/37/38그룹 → 상속된 67/66/54/63그룹; 양성 574/369/300/357, 정답 없음 파생 계획 144/92/75/89, 합계 계획 718/461/375/446. 250그룹/1,600양성/585의도 선정은 유지했다.
- 로컬 보존: 전체 기준 mapping을 다시 쓰지 않고 읽기 전용 유지. pilot 그룹별 full_split/split·양성 수와 원본/그룹 기록 digest를 로컬 inheritance manifest로 저장했다. 43,175 원본 행의 기존/재현 그룹 배정 대조 및 250그룹의 원본/상속 배정 일치, 대표 양성 1,600, 이동 0 확인. 원문/매핑/manifest는 원격 제외.
- 검증: RED(상속 인자 미구현·splitter 차단)→GREEN 상속 3/3. 분할 누락·다중 배정 거절, 비율 불균형 그대로 상속, 재분할 함수를 호출하면 실패하는 검증. 기존 데이터 경계 9개도 PASS. 제품 전체 합성 suite를 같은 단계에서 반복하지 않는다.
- 준비: 기존 Native Python 3.14 전용 venv 생성. ensurepip 제공 pip는 25.3으로 관측됐으며 기존 글로벌 pip를 바꾸지 않았다. 공식 wheel 38개 다운로드 2,932,975,749 bytes, 전체 hash/size 검증 완료. 실제 .work+원본 ZIP 점유 2,956,427,501 bytes 관측. 신규 설치·CUDA·모델 준비·학습은 아직 없음.
- 오류 1: 준비 잠금 목록 작성 시 일반 cp314와 free-threaded cp314t ABI를 혼동해 hf-xet/tokenizers 두 wheel을 잘못 선택했다. Native 지원 tag 대조에서 두 개만 비호환 확인. 동일 버전의 공식 hf-xet cp38-abi3/tokenizers cp310-abi3 파일·hash를 확인하고 requirements.g1에 수정안을 제시했다. 추가 두 파일 합계 6,694,745 bytes; 버전/학습 범위/자원 상한 변화 없음. 원본 lock 승인안의 파일/hash 불일치 중단 조건에 따라 설치·학습 중단 및 신산님 확인 질문을 보냈다. 자동 최신/downgrade 없음.
- 영향을 받지 않는 분할 기록·검증은 완료했다. package 설치·import/CUDA·토큰·최소 표본·원본/파생 쌍 처리·실학습·가중치 갱신/reload·optimizer 관측·독립 test/자원 peak는 미검증이다. 파생 400개는 아직 계획이다.
- 변경 파일: aihub116_review.py/notebook, test_pilot_inheritance, AIHUB116_CONVERSION, requirements.g1 수정안, 이 기록. G1 승인 원문·환경·준비 영수증은 로컬 제외 문서에 기록한다. 공개 파일 검사 후 work/native-synthetic checkpoint를 non-force push하고 원격 SHA를 직접 대조한다.
- 다음: ABI 수정안 실행 확인 후 동일 버전/고정 hash로 준비를 계속하고, CUDA·토큰·최소 표본 검사를 통과해야 승인된 첫 파이프라인 시험을 실행한다. 본 단계 결과를 학습 성공으로 표시하지 않는다.
- 독립 리뷰 1회: Critical 0/Important 1/Minor 0. 기존 summary/pilot 파일 순차 덮어쓰기는 저장 실패 시 기존 증거를 훼손할 수 있다는 finding. RED→GREEN 기존 기록 비교 전용·내용 변경 시 거절·덮어쓰기 없음으로 1회 수정했고, 쓰기 불가 fixture에서 기존 bytes 보존을 확인했다. 다시 리뷰하지 않았다.
- 수정 후 전체 suite: 57 실행/56 PASS/실제 로컬 모델 1 SKIP. 실제 모델 시험의 경로가 없어 skip된 것이며 G1 승인 자체가 없는 것은 아니다. 실제 ZIP 재실행도 성공, 원래 전체 group_map의 digest 보존 및 재분할 호출 없음 확인. 이 suite는 준비/상속 코드 회귀 증거이며 실제 학습 성공 증거가 아니다.

## 2026-10-14 G1 실제 준비·토큰 gate 완료 / 담당 어울

- 신산님이 동일 버전 abi3 wheel/hash 수정과 준비/시험 계속을 직접 승인했다. actual metadata와 lock을 맞추고 추가 6,694,745 bytes만 확보. 고정 38개 패키지 설치와 pip check PASS, Laya editable import의 exact source SHA/clean 확인. 글로벌 Python/패키지/드라이버 변경 없음.
- 모델 고정 revision의 7개 파일을 LFS SHA-256/Git blob hash로 검증해 단일 로컬 cache에 준비했다. wheel+모델 신규 파일 수신 3,617,881,614 bytes, source Git object 저장 9,848,673 bytes(전송량 추정 기준, protocol overhead 제외), 5 GiB 한도 아래. 원본·변환 자료·가중치 외부 업로드 없음.
- 실제 Python 3.14/PyTorch 2.10.0+cu128/Transformers 5.19.0/Laya import, CUDA device capability 12.0의 finite 행렬 연산 PASS. 실제 CPU 모델/tokenizer 구성·정상 5+기권·긴 후보·긴 맥락·실제 mask special token·동일 긴 접두부 충돌 거절 PASS. 실제 CPU 학습 없음.
- 실제 WDDM process VRAM은 N/A였다. 6 GiB 제한을 완화하지 않고 전체 device 사용량 합계로 보수적 상한 감시하며 scope를 기록한다. parent+training worker RAM을 합산, 전체 .work+ZIP 실측 disk를 감시, 상한/감시 실패 시 해당 실행의 자식만 중단한다.
- 실데이터 변환: 저장된 분할 anchor·원본/전체 mapping/pilot 기록 digest를 대조하고 동일 250그룹을 상속했다. 정상 gold 제외 파생 400개를 같은 출처/split에 생성. 토큰/주소 패턴 거절은 원본과 파생 쌍에 함께 적용. 21 원본 묶음/26 입력 제외(주소 패턴 15, token budget 11, 이유 중복 5) 후 1,974 입력 유지.
- 실제 최종 split: train 697(양성558/기권139)/67그룹, calibration 457(365/92)/66, selection 374(299/75)/54, test 446(357/89)/63. 최소 사례·그룹·각 정답 유형·학습 MAIN 264종 gate PASS. 재분할/그룹 이동/추가 재추출 0. 개인정보 검사는 모든 retained request 필드의 명시 식별자 패턴 검사이며 모든 이름·의미상 개인정보의 완전한 증명이 아니다.
- upstream dry-run PASS: train697/selection374 실제 item 수 일치, skipped/eval_skipped 0, 내부 calibration0, 예상 optimizer88. 실제 optimizer는 아직 시작하지 않았다.
- 변경: 실제 변환 경계, actual train CLI/독립 파일 비접근 loader, worker JSONL digest, 실제 optimizer hook·인코더 tensor 불변·전체 저장 tensor reload 확인·완료 증거. fixture RED→GREEN 확인. Native suite 65 실행/64 PASS/actual config 없는 모델 1 SKIP; 실제 token 경계는 별도로 실제 모델에서 확인했다.
- 독립 리뷰 1회: Critical0/Important2/Minor1. 최종 실측 disk 검사·upstream 행/optimizer 부분 실행 차단·CLI 실패 exit를 한 번 수정했다. 각 RED→GREEN 확인, 재리뷰 없음. 수정 후 전체 suite와 공개 파일 audit를 거쳐 clean code checkpoint를 먼저 보존한 뒤 단일 GPU 시험을 실행한다.
- 오류/조치: 패키지 설치가 진행 중인 상태에서 source pip check를 먼저 실행해 일시 누락 1회, 설치 종료 후 정상 확인. Windows 기본 cp949로 UTF-8 로컬 요약 읽기 실패 1회, 명시 UTF-8로 수정 후 데이터 검사 완료. WDDM 감시 불가 1회는 위 보수적 device 상한으로 해결. 미해결 실행 오류 없음.
- 다음: clean SHA/승인 scope·필수 gate를 대조하고 최대30분 전체 GPU trial에서 기본 모델 측정→헤드-only697행1epoch(88 optimizer 예상)→reload→같은 독립 test446행 비교. 온도는 calibration의 사전 grid만 사용, G2 임계값 선택/품질 합격 없음. 원문·출처/score/run/config/weight 증거는 ignored 로컬에만 보존한다.

## 2026-10-14 G1 최초 실제 학습 파이프라인 검증 완료 / 담당 어울

- 실행 SHA `78068da517cd28adcdf9d26631e60372f4b296fc`를 push/원격 일치·clean 확인 후 승인 scope에 결합했다. Windows local-only 단일 GPU trial에서 기준 모델 측정→697행 헤드-only1epoch→tensor/reload→동일 test446개 비교, 정상 exit0. 250그룹은 원래 전체 분할을 상속했고 실제 모든 사례의 원본 주소·group/split·입력 digest를 재대조해 이동0 확인했다.
- 실제 증거 PASS: train697/selection374/upstream skip0, 내부 calibration0, AdamW 예상88/관측88, 변경 tensor32/encoder변경0, 전체 저장 tensor와 reload tensor 일치·reload score 확인, epoch mean loss1.89582656. 실제 기본/학습 후 파일 SHA를 직접 재계산해 기록과 대조했다. 데이터·가중치·source 식별 digest 상세는 로컬 전용 증거에만 기록한다.
- 측정: test446/63연결 그룹 top-1 21.30%→21.30%, 정답 포함 후보 선택5.04%→5.88%, 보정 NLL1.80770→1.78165, ECE0.08401→0.02745, coverage14.13%→16.82%, 선택 응답 오류71.43%→72.00%. 확률 지표 일부 개선을 한국어 정확도/운영 품질 합격으로 표시하지 않는다. G2 기준과 임계값 선택 미결정, explicit-only 측정이다. 빈 태그 slice는 MODEL_CARD에 명시했다.
- 자원: 전체 trial 최종 phase elapsed256.38초, RAM(parent+worker 샘플)2.05GiB, 전체 device VRAM 상한 샘플5.36GiB, CUDA 할당/예약 피크2.81/5.02GiB, 정리 전 disk9.26GiB. 시간1800초/RAM24/VRAM6/disk30GiB 상한 내 관측·최종 검사 PASS. process VRAM N/A는 device 전체 상한으로 보수적으로 측정한 범위임을 명시했다. 외부 유료 자원 없음.
- 검증: 최종 수정 Native suite68 실행/67 PASS/실모델1 SKIP 뒤 그 실제 모델 시험1개를 처음 실행하여 PASS(2+기권 shape, 긴/접두부/맥락/special 거절). 저장된 상속 manifest·입력4파일·source/reloaded weight·tensor 변경·optimizer 관측·한도를 독립 대조 PASS. 학습 실패 없음. 리뷰 finding은 1회 수정으로 해결, 재리뷰 없음.
- 기본 표준 라이브러리 경로 회귀를 보존하기 위해 XLSX import를 실제 ingest 시점으로 늦추고 실제 optimizer 시험은 torch 있는 환경에서만 실행하게 했다. 기본 Native68 중66 PASS/선택 의존성2 SKIP, 전용 환경의 상속/hook7 PASS 확인. 실제 학습을 재실행하지 않았다.
- 정리: 최신 중간 checkpoint7개 파일이 최종본과 모두 동일한 hash임을 검증하고 절대 target 경계를 확인한 뒤 중복 latest만 제거했다. 이번 준비의 비호환 wheel2개도 제거. 원본 ZIP·최종 모델1개·base cache1곳·고정 source·모든 실행/분할/측정/자원 증거 보존. 정리 후 disk8.62GiB, 종료 후 GPU점유0 확인.
- 보존 문서: MODEL_CARD 실제 결과로 갱신, README/UPSTREAM 현재 실행 계약 반영, 환경/G1 원문에 비공개 상세 추가. 코드/집계 문서만 최종 checkpoint push하고 실제 원격 SHA를 보고한다. 모델/데이터 공개·main 병합·force push·WSL/Oracle 배포 없음.
- 완료: 승인된 Windows 준비, exact 의존성/모델, 전체 분할 상속·그룹별 기록, 실제 토큰/표본 gate, 최초1epoch헤드 학습·갱신·reload·독립측정·자원검증·중복 정리. 미완료: G2 정책/품질 판정, 추가 한국어 학습·인코더 학습·정밀한 한국어 유형/후보10·20/공공민원 평가, 의미/개인정보 전체 증명, 다른 환경·운영·G3 공개/배포.
- 다음: 결과를 신산님께 보고한다. 추가 학습을 자동 실행하지 않으며 이미 노출된 test를 향후 튜닝 후 새 미사용 검증으로 재사용하지 않는다. 추가 범위/품질 기준은 별도 승인 후 진행한다.

## 2026-10-14 추가 학습 전 저장 점수 진단 / 담당 어울

- 직접 지시: calibration·selection의 업무 후보5개 정확도·정답 순위·정답 유무별 기권을 전후 비교하고 대표 입력/정답/후보 연결을 확인한다. 새 모델 호출·추가 학습·final-test로 설정 조정하지 않는다.
- 완료: calibration457(정답365/없음92)의 두 저장 점수를 정확한 example/candidate ID 순서로 결합, 유한값/동률/누락/중복 확인. 업무5 정확도86/365(23.56%)→91/365(24.93%), 순위 histogram86·81·68·67·63→91·75·65·68·66, 평균순위2.8356→2.8438. 정답 포함 기권299/365→289/365, 정답 없음80/92→78/92. 업무정답1위인데 기권64→65건. 개선순위24/악화23/동일318건.
- 제한: selection374(정답299/없음75)는 upstream train_report 집계만 저장됐다. 기존 6개 전체 정확도22.46%→23.26% 등은 확인 가능하지만 요청한 후보별 순위·업무5정확도·기권 분해는 기록 부재로 미검증이다. 집계에서 역산하지 않았으며 모델을 재호출하지 않았다.
- 연결: 두 분할831개 원본 ZIP의 발화/과거맥락/MAIN·도메인 후보ID·설명/문자열 유사도 후보집합/정답제외 파생/확정 전체 group·split과 대조, 불일치0·중복0·그룹교집합0. 원문·개별logit 사례는 ignored 로컬에만 기록했다. 원본/증거8파일 조사 전후 hash 일치.
- 의미 검토: 대표 selection 파생에서 원래 이용 가격 문의를 제외해도 이용 금액 문의 후보가 남아 의미상 기권 정답이 모호했다. 후보 설명은 도메인/MAIN 문자열이며 충분한 업무 정의가 아니다. 전체 의미상 정답 검증이나 인과관계 확정으로 확대하지 않았다.
- 변경 파일: docs/score_diagnosis.py, 출력 없는 동반 notebook, G1_SCORE_DIAGNOSIS.md, 이 기록. 모델 라이브러리 import0/호출0, 추가학습0, 설정변경0, final-test 계산·사례선정0. 같은 score JSON의 test 배열은 파일 decode 시 함께 메모리에 들어오지만 계산에서 참조하지 않는다.
- 검증: 실제 offline script 및 notebook 코드셀 순차 실행 PASS, 별도 정렬 기반 계산으로 순위histogram/정답선택/두기권분모 재대조 PASS. 엔진 코드를 바꾸지 않아 GPU/model 시험 및 전체 회귀를 반복하지 않았다.
- 오류: 첫 대표 사례 화면 출력의 Python 기본 인코딩 불일치1회는 UTF-8 명시로 해결. upstream 조사 경로 오지정1회는 실제 파일 목록으로 수정. 분석 계산/연결 오류0, 미해결실행오류0. 새 모형·추가 의존성 다운로드 없음.
- 다음: 진단 집계와 selection 기록 부재를 보고한다. 추가 학습 전에 후보 정의·동의 라벨·파생 기권 의미를 검토하도록 권장한다. 데이터 계약 변경·selection 점수 추가 생성·학습은 이번 단계에서 실행하지 않는다. 안전 코드·집계 문서만 작업 branch checkpoint로 commit/push하고 원격 SHA를 확인한다.

## 2026-10-14 calibration92쌍 의미 검토·별도 재집계 / 담당 어울

- 신산님 지시대로 calibration의 정답 제외92개와 대응 원본92개(총184개/51연결그룹)를 저장된 과거맥락 전체와 함께 수동 검토했다. 원본양성365개 전체 검토나 공식 정답 변경으로 확대하지 않았다. 모델 score를 결합하기 전에 수동 검토 판단표를 작성하고 digest를 고정했다.
- 분류: 원본92는 유일46/복수29/맞는후보없음7/문맥부족10, 파생92는 유일14/복수14/맞는후보없음51/문맥부족13. 문맥부족에는 입력부족과 후보구분정의부족이 포함되며 근거에서 구별한다. 타당ID/미확정ID/부적합ID·기준·근거를 별도 로컬 검토표에 기록했다. 기존gold77타당/9현재의도불일치/6미확정은 라벨 정정이 아니라 어울 검토v1이다.
- 의도기준: 원본은 XLSX13개이고 공식 taxonomy 정의서 없음. 확정train 원본 MAIN/SUB의 라벨별 최대5개 사용례를 대조해 시간당요금/누적금액, 포장음식가격/별도포장비, 첫음료옵션/추가메뉴, 판매문의/구매명령, 새음식/남은음식포장 등을 구별했다. 공백/오타/일반·세부 라벨은 이름만으로 병합하지 않았으며 공식 기준이 없는 항목은 미확정으로 남겼다.
- 파생 재집계: 타당후보 남은28건 기권23→23(82.14%), 실제타당응답3→3, 업무5타당선택13→11. 정말후보없음51건 기권45→43(88.24%→84.31%). 문맥부족13건 기권12→12이며 정답 지표에서는 제외. 원본의 유형별 accuracy/rank/기권 및 복수 미확정후보 상하한은 별도 보고서에 기록했다.
- 보존·검증: 기존 원본/분할/입력/점수/보고서와 검토 입력13파일 조사 전후 hash 일치. 파생전체92↔원본92 연결/원래gold/후보순서/입력·맥락/유한값/최상위동률 검사PASS, 별도 정렬 방식으로 모든 유형의 기권·업무선택·순위분포 재계산PASS. 기존92개 기권80→78은 그대로 대조했다.
- 변경파일: docs/semantic_score_review.py, 출력없는 동반notebook, CALIBRATION_SEMANTIC_REVIEW.md, 이 기록. 개인원문·후보ID·score·검토표·구분근거 사용례·해시는 ignored .work/semantic_review에만 저장했다. 기존 G1_SCORE_DIAGNOSIS·MODEL_CARD·기존 평가 지표 수정0. 새모델호출0/학습0/설정변경0/final-test계산0.
- 오류: 분석·검증실패0. 원본사용례 준비 명령의 첫 출력이 비어 1회 출력확인이 누락됐다. 생성파일 완료·내용 확인 후 정상 인수했고 작업을 재실행하지 않았다. 미해결실행오류0.
- 완료:184개 별도 수동검토표·유형별 저장score 진단·재현코드·보존검증. 미확정: 공식 의도 정의/배타경계·도메인 담당 인수·문맥부족 사례, 전체corpus 의미정답 검증. 다음: 결과보고·안전한 코드/집계문서만 작업branch checkpoint push 및 원격SHA 확인. 별도 승인 없는 taxonomy/원본 gold 변경·학습은 수행하지 않는다.
