# snapshot 진단·임시 학습 피크·최종 시작 조건

2026-10-14 / 담당 어울 / A/B 미실행

## 오류 판정과 최소 보완

이전 평가 전용 시험의 stop 파일 생성은 1791954980.627690, producer 오류 로그 갱신은 1791954980.825690이었다. 기존 루프는 CIM 조회 이후 stop을 다시 확인하지 않아 정상 종료 요청과 새 저장이 겹칠 수 있었다. 다만 당시 `bounded_call`은 예외와 대기 초과를 모두 False로 축약했다. **이전 오류 자체가 종료 순서 때문인지 실제 저장 실패인지 소급 확정할 기록은 없다.**

최소 보완은 조회 직후 stop 재검사, 저장 예외 종류·errno와 timeout 분리, atomic 구간 계측, 별도 0600 최소 오류 로그다. 원문·오류 메시지·비밀값을 담지 않는다. 최소 로그도 독립 daemon과 소유 dup FD로 최대20ms만 기다린다. 종료 요청이 있어도 이미 발생한 실제 저장 실패는 숨기지 않는다.

보완 코드 `9ef7a57d081972c4dd6178357dabc4996a3f077b`의 임시 학습 시험에서 오류가 재현됐다. **stop_seen=false인 snapshot 저장의 1.000367초 대기 초과**였으며 serialize/open/write/flush 계측은 완료되고 fsync/close/replace는 미완료였다. 이번 재현은 정상 종료 요청 때문이 아니라 **fsync 구간의 저장 대기 실패**다. 물리 I/O 지연과 스케줄링 지연의 기여는 나누어 확정할 수 없다.

최종 보완 코드 `d7512ee`는 일시적인 GPU 최신 snapshot만 flush+atomic replace, GPU 이력은 flush로 기록한다. 이 계수는 실행 중 fresh 값으로만 소비하고 재부팅 후 복구자료로 사용하지 않으므로 매 표본의 fsync를 안전 감시 전제에서 제외했다. 일반 진행·단계·optimizer 기록과 중단 packet의 기본 fsync는 유지했다. 저장1초 제한은 늘리지 않았다. 실제 쓰기 예외/대기 초과는 계속 producer 실패이며 기존 stale15초 거절·독립 메모리 감시·6GiB 중단은 유지했다.

## 실제 임시 모델 검증

1차 진단 probe는 `training-memory-20261014-01`/source `9ef7a57d081972c4dd6178357dabc4996a3f077b`다. 최종 공동 probe는 `training-memory-final-20261014-01`/source **`d7512ee02c0d503990556665cffa46bbc6127e64`**다. 각각 서로 다른 fresh GPU 표본3개가 모두 **2.514442GiB**였으므로 시작했다. 기존 immutable image·offline/network none·RAM4GiB/총RAM+swap8GiB·GPU6GiB/1800초를 유지했다.

초기 원본 가중치를 별도 새 모델 인스턴스로 로드하고 보완된 학습 전 선택 평가374건을 수행했다. 이어 기존 원본 학습697건·seed13·원래 `train_model`·fp32·freeze_encoder·soft-CE·micro_batch1·grad_accum8·기존 LR/clip을 사용했다. scheduler 예산도 전체697건 기준88을 유지했다. 16번째 학습 입력의 backward와 두 번째 optimizer/scheduler/zero_grad를 마친 뒤 다음 forward 직전에 probe 전용 예외로 함수만 빠져나왔다. A/B의 고정 반복 입력을 전부 시험한 것은 아니며 전체88회 학습·저장/reload는 미검증이다.

| 항목 | 최종 공동 실측 |
|---|---:|
| 임시 모델 worker | **60.099초, exit0** |
| 준비·종료 포함 전체 | **78.236초**, producer exit0 |
| 선택 평가 | **374건** |
| 실제 학습 forward/backward | **각16회**, enter/exit 기록 전수 확인 |
| AdamW 갱신 | **2회**, enter/exit 기록 전수 확인 |
| 변경된 head tensor | **31개** |
| 자체 peak allocated | **1,870,781,952bytes / 1.742301GiB** |
| 자체 peak reserved | **2,027,945,984bytes / 1.888672GiB** |
| adapter 전체 표본 피크 | **5,113,245,696bytes / 4.762081GiB** |
| 시작 대비 전체 추가 사용량 | **2.247639GiB** |
| 자체 allocated 피크 최초 기록 단계 | **training_backward exit** |
| worker RAM 표본 피크 | **2,480,369,664bytes** |
| 독립 worker fatal 로그 | **0행** |
| 일반 진행 기록 지연 | **1건**, 비치명 경고 후 계속 |
| 원본 학습/선택 입력·초기 가중치 hash | **전후 불변** |
| 임시 가중치 저장/A-B 재사용 | **0회**, 모델 해제 |
| final-test 내용/hash 열기 | **0회** |

allocated/reserved는 합산하지 않는다. host 계수는 기존 adapter별 max(dedicated+shared, committed) 합계이며 표본 피크다. 원래 학습 forward/backward/optimizer의 동작은 변경하지 않았고 평가에만 기존 GPU1행 보완을 적용했다. encoder는 원래 함수의 freeze 설정을 적용했으며 head 갱신과 초기 디스크 가중치 보존을 확인했다.

1차 worker는98.124초 exit0/자체 피크는 위와 동일했으나 host 표본 피크는4.429058GiB였고 producer는 snapshot timeout으로 exit1이었다. 마지막 host 표본 뒤 약8초의 관측 공백이 있었고 그 뒤 자체 allocated 피크가 기록됐으므로 공동 PASS로 표시하지 않는다. 감시 단독 검증만으로 마무리하려던 계획을 수정해 최종 코드로 새 임시 인스턴스의 같은 짧은 검증을 한 번 더 수행했다. A/B 자동 재시도가 아니다.

**최종 공동 시험은 worker·producer 모두 exit0**이다. GPU55표본/최대간격4.888초/생산자 실패0, forward·backward 각16회 enter/exit와 optimizer2회 enter/exit를 전수 확인했다. 마지막 모델 해제 기록1791957110.335, summary1791957110.950, 마지막 host 표본1791957114.300으로 **모델 종료 뒤까지 관측**했다. worker의 일반 기록 대기 경고1건은 비치명이며 독립 fatal 로그0행/최종 기록 완료를 확인했다.

## 보완 검증과 종료

- 종료 요청 중 조회 완료 시 새 저장 금지, 실제 저장 오류의 stop 후 은폐 금지, 예외/errno와 timeout 구분, 느린 fsync 주입 시 감시 snapshot 기록 유지: 최종4시험 PASS. PCWSL에서도4시험 PASS.
- Windows GPU snapshot6시험 PASS, telemetry19시험 중18 PASS/조건부1 skip. 일반 durable 동작을 유지한 회귀 범위다.
- 최종 보완 후 모델 없는 PCWSL 감시120초 요청/전체134.620초·실제 표본 관측133.189초/100표본/최대간격4.870초/오류0·producer exit0. 이어 위 최종 모델 공동 시험도 PASS다.

이번 컨테이너만 종료·삭제하고 producer만 요청 종료했다. 다른 서비스·프로그램·driver 중단이나 한도 변경, private 로그 역복사, 원본 자료/가중치 Git 업로드는 없다. 현지 비공개 기록은 해당 probe와 runtime 폴더에 보존했다.

## 최종 시작 조건 제안

최종 실측 추가량 **2.247639GiB**가 자체 reserved1.888672GiB보다 크므로 이를 기준으로 **1GiB 여유**를 더한다. `6 - 2.247639 - 1 = 2.752361GiB`를 보수적으로 내림해 **전체 GPU≤2.75GiB인 서로 다른 fresh 표본3개 연속 확인**을 최종 시작 조건으로 제안한다. 평가 전용의3.0GiB 제안을 갱신했다. 최종 공동 시험은 시작2.514442GiB로 이 새 조건도 만족했다. host 추가량에는 실험 외 변화와 allocator 밖 GPU 비용도 포함될 수 있어 순수 모델 resident 크기로 단정하지 않는다.

실행한다면 동일 초기 가중치·기존 학습 설정, A 원본697/B 선별280·잠정 정답49·고정 반복순서 및 ID/그룹 추적, 각697노출/88optimizer, 총1800초에서 A 정상 완료 후 B만 진행한다. 임시 검증 가중치는 사용하지 않는다. calibration/selection만 비교하고 final-test는 열지 않으며 실패 자동 재시도 없이 마지막 단계·완료 optimizer·자체 allocated/reserved·adapter 계수를 보고한다. 효과는 선별·정답 수정·반복 노출의 합친 효과로 해석한다.

짧은16노출이 전체 학습의 모든 입력/최대 후보 수·전체88갱신·저장/reload 피크를 보장하지 않는다. 최종 생산자와 임시 모델의 공동 기록·종료는 확인했지만 전체 학습은 미검증이다. **이 시작 조건과 기존 감시를 적용한 A/B 1회를 제안하며, A/B 실행은 하지 않았다.**
