# 승인된 A 저장 모델 평가·B 1회 후속 실행: 시작 조건 미충족

2026-10-14 / 담당 어울 / **A 평가·B 학습 미시작, 비교 결과 없음**

승인 범위에 맞춰 기존 A/B launcher에 `followup` 분기를 구현했다. A는재학습없이보존checkpoint를복사·파생provenance연결·F16구조/finite·실제strict state_dict/전수값digest검사후평가하고,B만기존학습함수를1회호출한다. 두arm의평가는같은함수·자료·F16저장/재로드로수행한다. 정상평가child종료후activeworker와parentallocated/reserved0을기록하고새fresh표본3개로B조건을재검사한다. 공통1230초deadline과6GiB·final-test봉인·실패자동재시도0을유지했다.

실행 source `1592749`, namespace `approved-checkpoint-followup-20261014-01`. 사전시작확인30초 동안20개 fresh GPU 표본을 받았으나 **최소5.244770GiB/최대5.262836GiB**로 전부 시작기준2.75GiB를 넘었다. 기준이하 표본0개로 연속3개 조건을 충족하지 못했다.

| 항목 | 결과 |
|---|---|
| 시작 확인·정리 시간 | **30.552초** |
| 중단/미시작 사유 | `headroom_unavailable` |
| launcher·모델 컨테이너 시작 | **0회**, parent_exit=null |
| A strict 모델 로드·평가 | **0회** |
| A 재학습 | **0회**, 기존88갱신checkpoint 보존 |
| B 학습·평가 | **0회** |
| 비교 결과 | **없음** |
| 감시 producer | **exit0**, 실패0 |
| A 원본 checkpoint hash | **기준SHA와 동일** |
| 후속 trial 폴더 | **미생성** |
| producer23676·이번컨테이너 | **잔류0** |
| final-test 내용/hash 접근 | **0회** |
| 자동 재시도·타프로그램 종료 | **0회** |

전체사용량은6GiB 미만이지만 **시작조건2.75GiB를충족하지않아모델실행전에멈췄다.** 엄격한로드검사실패나B학습실패로표현하지않는다. 승인된모델실행은아직시작하지않았으며,조건이부족한상태에서자동으로재실행하지않았다. 현재다른프로그램의점유를특정하거나임의로종료하지않는다.

구현검증은F16파일finite/구조불일치거절과공통1230초deadline2시험RED→PASS/startgate2PASS/전체132개중128PASS·조건부4skip이다. 실제strict모델로드·A저장모델평가·B완료·공통재로드비교는**미검증**이다.

현지runtime에전체20표본과`not-started.summary.private.json`·`runtime.summary.private.json`을보존했다. 이시작확인의30.552초도승인된합산1230초에포함해,같은승인으로다음재개할수있는예산은**최대1199.448초**다. Acheckpoint 원본은변경하지않았다. Windows역복사·자료/가중치Git업로드·6GiB상한변경은없다. 다음실행은GPU여유가확보된뒤직접재개지시에따라같은경로·조건으로진행해야한다.
