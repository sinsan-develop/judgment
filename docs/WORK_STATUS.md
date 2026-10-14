# judgment 작업현황

## 2026-10-14 학습 전 선택 평가 최소 메모리 보완·피크 측정 / 담당 어울

- 직접승인:before_training_selection배치/추론/결과보관진단·자료/입력/점수계산유지·최소보완후학습전평가만피크측정·실측+여유로A/B제안. GPU6GiB·타프로그램임의종료금지/final-test0/실제학습0.
- 고정upstream c73908d calibration_records 기본16·@torch.no_grad/model.eval/ampFalse, logits매batch.cpu().numpy()→recordsCPU, GPU결과누적아님. batch16일시activation/caching이자체reserved4.008GiB에기여한경로확인. upstream파일수정0.
- 최소보완:원래16collate/padding/후보·입력토큰·target유지하고동일_forward를GPU1행씩실행, CPU에서cat. 평가함수호출동안만_forwardhook/예외finally복구/학습_forward는원본, 전후평가동일경로. TDD미구현RED→기본2PASS/실제meta list구조RED→tensor/list행slice보완2PASS.
- 자원계획:preselection-memory-20261014-01 ownCIMproducer+container(기존image/networknone/RAM4+총RAMswap8/GPU6·총1800초guard). fresh3GPU≤3GiB시작, 초기모델로드+선택374평가만/optimizer·train·final-test0. 원래16패딩텐서로GPU2행기준 vs 1행16개점수수치1e-5·top대조후전체평가, payload/scores/meta는private현지보존/역복사0. 실제피크와현재baseline으로안전여유있는시작조건·A/B제안만, 자원은이번것만정리.

## 2026-10-14 공동 검증 여유 기준 A/B 1회 승인 / 담당 어울

- 종료판정:source17b79ff88707c23715718f36e8ef6d0b8029a89b/fresh3GPU표본모두2.5528946GiB≤4후승인실제1회실행. A75.971초vram_limit/hostpeak7383695360bytes(6.877GiB)>6/workerexit3/B미시작/비교미산출/자동재시도0. 마지막before_training_selection·완료optimizer0/not_started/recordage2.649초/정확종료수미확인.
- 기여근거:평가enter reserved1367343104→첫heartbeat3212836864→마지막4303355904bytes(4.008GiB),peakallocated3004742656bytes(2.798GiB). 모델로드공동검증1.242GiB기준은실제다음선택평가피크를포함하지않음. 프로세스추측원인·한도/설정변경0. fatal독립로그0/일반model_load대기지연경고1개는비치명으로계속,이번중단원인아님.
- 보존:parent+workerRAM표본peak2494324736bytes/worker마지막RSS2094268416bytes/disk17974205756bytes<30GiB,adapter적용827392/2392064/7380475904bytes. 원본8파일·초기가중치hash불변/final-test내용·hash열기0/비교calibration·selection측정미실행. owncontainer/producerPID12278잔류0/producerexit0/private현지보존/역복사0. 공개보고docs/AB_COMPARISON_RESULT.md갱신/승인1회소진/다음은안전기록checkpoint·근거보고/추가수정·학습0.
- 직접승인:정상공동검증의시작2.311GiB/피크3.640GiB/추가상한관측약1.329GiB·reserved1.242GiB를근거로fresh3표본≤4GiB(최소2GiB여유)확인후A/B1회,부족시미시작. 기존6GiB·총1800초·설정·697노출88optimizer·동일초기·A정상완료후B·calibration/selection평가·final-test0·실패자동재시도0.
- trial approved-headroom-ab-20261014-01. own judgment-ab-headroom-20261014-01 container+CIMproducer/검증된기존image/networknone/RAM4GiB+총RAMswap8GiB/기존GPU연결. 이전실패/private원본입력·순서·가중치보존,코드·설정변경/모델단독시험반복0. 안전checkpoint→PCWSLGit exactSHA→3표본여유검사→승인실제1회→이번자원만정리/보존/보고. 다른프로그램·서비스중지/한도변경/역복사0.

## 2026-10-14 GPU 기여 대조·모델 로드80기록 공동 검증 / 담당 어울

- 최종PASS:source9936e85d4105759040435c48bade6c688391ea93/probe gpu-headroom-joint-20261014-01/3fresh기준모두2.3109436GiB≤4→105.791초exit0/실제model_load exit·지정반복state80개1~80전수일치·sequence정상·fatal/delay로그각0bytes. 자체allocated1307824640/reserved1333788672bytes(1.218/1.242GiB),hostGPUpeak3908644864bytes(3.640GiB)<6. 초기모델hash불변/producerPID11396·owncontainer잔류0/private현지보존/역복사0/optimizer·학습·평가·final-test열기0.
- 원인정리:최초capstop allocator미초기화에도전체증가/기여프로그램중단시점자료없어확정불가,최종capstop은기존5.778GiB높은점유에model_load장치초기화/이동750MiB자체증가겹침. 현재CIM응용이름Chrome/Steamwebhelper/Whale는과거원인으로확정하지않음·프로그램종료0. 공동검증미완료해소/실제A-B학습697·88/reload/비교는미실행. 공개보고 docs/GPU_ATTRIBUTION_JOINT_VERIFICATION.md작성,별도지시전A-B보류.
- 직접승인:기존동시점allocator/adapter대조·다른작업이면프로그램식별/자체증가면단계보고·서비스추측종료/상한완화금지·GPU여유확인후모델로드80기록만/A-B보류/final-test0.
- 로그대조:첫capstop(snapshot/worker차0.043초)실험allocator not_initialized/host6.164GiB,주adaptercommitted2.746→6.134GiB. 최종capstop(차0.050초)baseline5.778GiB/host6.267GiB/실험model_load allocated=reserved786432000bytes(750MiB),직전초기화/장치이동확인. allocator와전체resident·committed범위달라직접차감하지않음. 중단시점process PID계수없어프로그램확정불가.
- 현재read-only CIM adapter계수약2.34GiB/응용GPU process Chrome·Steamwebhelper·Whale등확인,명령행·원문조회0. dwm process Dedicated값이전체adapter Dedicated보다커process합산으로과거원인단정0/프로그램종료0.
- 자원계획:gpu-headroom-joint-20261014-01 owncontainer+CIMproducer/검증된기존image·학습설정불변·networknone/RAM4+총RAMswap8/GPU6GiB·총1800초감시. 정상모델로드allocator약1.24GiB관측을근거로시작host≤4GiB의3개연속fresh표본에서최소2GiB여유확인후모델로드+80회기록1회만,optimizer·학습·평가0. 해당자원만정리/private현지기록/역복사0/통과전A-B0.

## 2026-10-14 atomic_json 지연 계측·최소 보완 / 담당 어울

- 최종판정:현지 ea17e36 모델없는안전5시험2.085초전부PASS/실제worker종료·unrelated생존확인. 일반delay경고뒤계속하다실제hostGPU6.267GiB에서중단,모델로드+지정80회공동검증미완료. 계속A/B보류/추가모델시도0,가용GPU여유에서공동재검증필요. 원본초기가중치hash불변/producer9362·9818·10248잔류0/owncontainer잔류0/private현지보존. 공개보고 docs/ATOMIC_WRITER_DIAGNOSIS.md에계측전후·한계·미검증기록.
- 보완후시험:6994eba 첫모델전용시험writermax0.2606초/atomic0.2605/lock0.019ms,delay/failure로그없음이나37.716초hostGPU6.164GiB로exit3. 8409aab 최종시험model_load중63.103초hostGPU6.267GiB로exit3,일반1초초과delay로그1행을남기고계속한뒤실제vram_limit중단확인. 학습/optimizer0/모델로드+80반복완료미검증,상한완화·서비스중지0. 현지안전시험실제mem조회실패·6GiB+1byte owned종료/unrelated생존PASS,FD시험은30ms인위지연상한을종료에도써서close검사실패→시험만지연주입30ms/종료1초분리. product1초유지.
- 독립review1회Critical0/Important0/Minor1(FD latewriter 재사용경합)→dupFD를note thread가소유/close,TDD RED→GREEN5PASS/재리뷰없음. Windows최종전체116중112PASS/4조건skip(이번test-only보완전),모델없는추가현지시험으로최종확인. 코드계측결과는스케줄링/GIL·외부부하포함이라단순전후성능비교아님.
- 재현결과:sourcee586331 모델로드중exit3/독립submit.wait_timeout writer.atomic_json/완료0,52완료계측. writer전체max1.6336초/atomic max0.6505초/serialize max0.103ms/fsync중앙100.280ms·max221.113ms/lock max260.011ms/queue max0.280ms. 각구간벽시계는스케줄링·GIL재개도포함,물리디스크장애확정0. 완료대기에는append+atomic 2회durable fsync가누적되며state lock을유지한I/O대기가확인됨.
- 최소보완:TDD일반기록지연비치명/대기중잠금해제2RED→구현. heartbeat history만flush(최신snapshot durable fsync유지),phase/optimizer history durable유지. queue삽입·순서는lock내/1초wait는lock외. 1초내done미완료는독립delay로그·delayed flag로분리,한도연장0. 실제writer예외·queuefull·메모리/6GiB·stale 감시중단은기존failed/독립guard그대로. 정상close에writer미완료면완료로승격하지않음.
- 직접승인:A/B보류/경로·serialize·lock·write·flush/fsync·replace분리계측/1초상한단순연장금지/일반기록지연과안전감시구분/GPU6GiB·중단유지/모델로드+반복기록검증.
- 실제경로PCWSL /home/daon/deploy/judgment/.work/runs는 /dev/sdd ext4/WSL내부,symlink없음/Windows공유경로아님. Docker /workspace는해당WSL정본bind. 원인판정전에선택적JUDGMENT_TELEMETRY_TIMING=1로atomic의9계측과queue/lock/writer총시간분리,JSON직렬화와stream쓰기구분. 정상1초대기/감시중단정책아직변경0.
- 계획자원:own atomic-timing-before-20261014-01 container+CIMproducer/기존image·GPU/RAM4g+총RAMswap8g/networknone. 실제모델로드+80회0.5초반복기록만,학습·optimizer·eval·final-test0. 진단private timing은fsync없는소형FD에기록,source안전commit→Git exactSHA→계측→근거기반최소보완→합성실패경계+같은모델반복시험. 이번자원만정리/서비스변경·역복사0.

## 2026-10-14 독립 오류 로그 적용 A/B 비교1회 승인 / 담당 어울

- 종료판정:sourceacabafb8b31e51d6d4639d25b295d91f844d0a35/A parent69.858초실패/B미시작/비교미산출/자동재시도0. 독립최초오류 submit.wait_timeout/진단TimeoutError/단계model_load/완료optimizer0/inflight writer.atomic_json. 정상기록기존1초대기내done미설정확인,atomic내부지연작업·기여원인미확인. worker guard65.981초 telemetry_unavailable→자체exit3,parent termination_requestedfalse/proc오류0. 마지막progressage2.495초/not_started/정확최종optimizer수미확인.
- 자원/보존:baseline0.8296GiB/hostGPUpeak891256832bytes(0.830GiB)<6,parent+workerRAMpeak1452101632bytes/workerRSS1084428288bytes/자체GPU미초기화,disk17968241111bytes<30GiB. 원본8파일·초기가중치hash불변/final-test내용·hash열기0/평가미실행. owncontainer·producerPID8338잔류0/producer exit0/다른서비스변경0/역복사0. 현지trial interrupted.summary.private.json·독립오류/종료/단계보존,공개보고 docs/AB_COMPARISON_RESULT.md갱신. 승인1회소진/추가수정·학습0,다음은공개기록checkpoint후실패원인및미확인보고.
- 직접승인:기존설정/동일초기가중치/GPU6GiB/전체1800초/A정상완료후B/calibration·selection평가/final-test비접근/실패자동재시도0. trial approved-independent-log-ab-20261014-01,이전실패 namespace보존/고정697노출·88optimizer/선별280·잠정정답49유지.
- 검증된코드a0dd121의독립최소로그/감시·중단을그대로사용,코드·설정수정0. 모델로드단독및합성시험반복0. 이번기록checkpoint exactSHA를PCWSLGit으로동기화/원본입력·가중치고정검사/시작GPU≤6→승인실제1회.
- 계획자원:judgment-ab-independent-log-20261014-01 owncontainer1개(기존immutable image/networknone/RAM4GiB+총RAMswap8GiB/GPU연결)와ownCIMproducer1개. 전체1800초독립guard/기존RAM24·disk30GiB/GPU6유지. 이번자원만종료/기존서비스변경0/private로그현지보존/역복사0. 실패시독립오류로그·마지막단계·저장optimizer수·종료코드·자원집계보고.

## 2026-10-14 telemetry 실패 원인·모델 로드 전용 재현 / 담당 어울

- 검증판정:source8a29cae exactSHA/모델로드전용probe model-load-probe-20261014-01 정상60.111초 exit0/최종model_load_verified/optimizer0. 초기화전GPU not_initialized·RSS745525248bytes,로드후allocated1307824640/reserved1333788672·RSS1696055296bytes;해제후allocator0. 최소실패로그0행/기존실패재현안됨으로정확한이전호출·예외미확인,근본해결확정0. 실제학습·평가·final-test열기0.
- 최종보존:producer49표본/hostGPUpeak2336632832bytes(2.176GiB)<6/기준0.866GiB,producerPID7581및owncontainer잔류0/최소로그0600/초기가중치hash불변. verified.summary.private.json 현지보존,역복사0.
- 시험/오류:독립로그2RED→보완뒤writer PermissionError/errno13·submit timeout 분류확인. 최초보완FD회수누락으로Windows정리오류3개→기록후close/최대20ms완료대기로해결,영향20PASS/1skip·전체112중108PASS/4조건skip,현지2PASS. 이번probe container/producer종료/비공개현지기록유지·초기가중치보존검사. 공개보고 docs/TELEMETRY_MODEL_LOAD_VERIFICATION.md. 정상로드·기록확인뒤동일조건A/B1회제안만하며별도승인전학습0.
- 직접승인:A/B보류/정확한기록실패호출진단/독립최소로그/실제모델로드까지만재현/GPU6GiB·기존시간·중단유지. 기존로그하위원인없어소급확정불가,새instrumented재현으로확인.
- TDD:독립writer예외/대기시간초과진단2시험RED→보완. telemetry.fail은실패flag먼저설정,별도preopen0600FD에원문없이operation/type/errno/stage/inflight/완료수1행,기존queue·fsync·atomic경로미사용/daemon최대20ms대기/쓰기불가시best-effort. writer append/atomic·submit대기/queue·sampler/event memory/drain/close지점분리. 기본1초정상기록상한변경0.
- 자원계획:PCWSL model-load-probe-20261014-01 owncontainer1개/ownCIMproducer1개,기존image/networknone/RAM4g+총RAMswap8g/GPUreadonly연결. ignored .work/model_load_probe/승인probe namespace에private기록,학습자료·optimizer·평가·final-test읽기0. 동일초기가중치로드후해제/해당자원만정리. source안전commit→Git exactSHA→합성gate→모델로드전용재현→원인별최소보완이필요하면별도검증,정상완료뒤에만A/B제안.

## 2026-10-14 수정 감시 코드 A/B 재실행1회 승인 / 담당 어울

- 종료판정:source d0d5b876ed2c714d985c7668e1adb13948a10420 현지gate4PASS/장시간1skip뒤승인학습1회실행. baseline0.8677GiB≤6. A parent3.735초/workerguard1.762초 telemetry_unavailable로worker자체exit3,parent termination_requestedfalse/요약worker_failed. /proc오류0/상태분류packet발생없음. 마지막model_load/완료optimizer0/not_started/recordage1.228초/정확한종료수미확인. B미시작/평가미실행/비교미산출/자동재시도0.
- 자원/보존:hostGPUpeak930045952bytes(0.866GiB)<6; parent+workerRAMpeak82612224bytes; 자체RSS38576128bytes/GPUallocator not_initialized. adapter적용bytes831488/30343168/898871296,disk17962839642bytes<30GiB. 원본8파일·초기가중치hash불변/final-test내용·hash열기0. owncontainer/producerPID6972잔류0,다른서비스·driver변경0/역복사0. 현지trial interrupted.summary.private.json·실패/종료기록보존.
- 미확인:telemetry.failed flag를설정한쓰기예외/queue/대기/sampler중정확한하위원인미기록,추정확정0. 원문마지막줄출력가능한진단명령자동승인거절1회→원문없는오류코드·숫자현지집계로완료,거절명령실행0. 공개결과 docs/AB_COMPARISON_RESULT.md 갱신. 승인1회소진/추가수정·학습재시도0. 다음은공개기록checkpoint·원인및미검증보고.
- 현지사전gate1오류:dummy exit가parent poll보다빨라의도한/proc경합미발생,monitor_observation없어시험KeyError. 실제학습Popen0/trial미생성/승인학습1회미소진. 시험release파일+실제worker.wait로경합명시동기화,production변경0. 해당사전container/producer종료확인후gate다시검증,학습자동재시도아님.
- 직접승인:기존GPU6GiB/전체1800초/설정유지,A정상88완료·저장·reload·평가후에만B,재시도0/final-test열기0. 승인1회 trial approved-monitor-retry-20261014-01,기존실패보존.
- /proc실패시종료여부분류를독립private packet·exit파일·결과에명시하는최소추가. worker poll값을종료요청전에저장하며 exited/running은해당검사시점관측이고실패이전정확한시간순서를추정하지않음. failedPID/errno/State와최종returncode함께보존. TDD2개미기록RED후구현,모델없는영향시험만수행.
- 계획자원:PCWSL judgment-ab-approved-monitor-retry-20261014-01 container1개/networknone/RAM4g+총RAMswap8g/기존immutable image/GPU연결과ownCIMmonitor1개. 해당자원만종료,로그원문가림·private보존/역복사0/기타서비스변경0. 순서는안전SHA→현지짧은분류시험→baseline≤6→1회A/B→증거·원본보존·정리·보고.

## 2026-10-14 memory_monitor_unavailable 직접 원인·감시 단독 검증 / 담당 어울

- 검증결과:source1322fec exactSHA/Windows합성110개중106PASS·조건부4skip/PCWSL모델없는5시험전부PASS(182.723초). dummy정상180.320초 exit0,baseline0.707GiB/peak822820864bytes(0.766GiB)<6, RAMpeak36687872bytes. producer138표본/관측210.647초/exit0/오류로그0bytes. RAMfailure주입5초이내ownworker종료·unrelated생존·failure/errno/반환코드저장,정상0/비정상7/종료경합7확인. owncontainer잔류0/producer정상종료. 모델·torch·GPUcontext·학습·final-test열기0.
- 오류/조치:새시험Telemetry.event추가인자불일치1회→기존state+event API사용. Windows전체시험임시폴더삭제/fsync handle경합1회→testcleanup만최대2초대기후전체106PASS. 제품중단write상한증가0/같은원인3연속0. 공개보고 docs/MEMORY_MONITOR_DIAGNOSIS.md. 정확한기존/proc실패하위원인과모델단계해소는미검증. 감시단독범위재실행준비됨/추가A-B승인없어재학습0. 다음은공개문서checkpoint·신산님보고.
- 직접 승인:추가학습0/기존로그·코드진단/최소수정/모델없는94초초과감시/감시실패시own실험만종료검증. GPU감시유지/6GiB유지/다른서비스변경0/final-test열기0.
- 조사:PCWSL RAM감시는명령이아닌/proc/status직접읽기. 읽기OS오류·VmRSS누락을동일ConfigError로축약했고숫자해석오류는ValueError로별도노출되는기존경로. 이번코드는ConfigError기록이므로감시명령실패·timeout·숫자해석오류증거없음. GPUproducer로그0bytes/실험중단뒤계수이력계속. 읽기실패와항목누락중정확한하위원인은기록없어미확인. worker.wait반환값을결과/파일에저장하지않은누락확인.
- 최소수정:TDD종료코드/감시failure상세미기록2실패→코드수정. 원문없이failure_kind/errno/PID/안전State기록,worker종료코드별도bounded파일+evidence,종료직후/proc조회경합은poll로분리. 종료전기록은기존best-effort유지,쓰기때문에중단지연없음. 변경src/judgment/runner.py/tests/test_memory_monitor.py.
- 계획자원:PCWSL .work/pcwsl-runtime/monitor-diagnostic-20261014-01의호스트CIMproducer1개/180초dummyworker1개/실패시험dummy와unrelated대조sleep. 기존immutable이미지의judgment-monitor-diagnostic-20261014-01 owncontainer1개(networknone/RAM4g+총RAMswap8g/사용자UID)에서/usr/bin/python3표준라이브러리만사용,GPUdevice전달0/모델·torch·GPUcontext·port·다운로드없음. 현지합성임시폴더·private로그만저장,시험후이번producer/container/child만종료잔류확인. canonicalsource는안전commit/push→PCWSL exactSHA로전달. 기존학습자원상한/조건변경없음. 다음은영향시험→현지180초+분류/종료격리시험→보고이며재학습없음.

## 2026-10-14 기존 조건 A/B 재실행1회 승인 / 담당 어울

- 최종판정:승인1회소진/A실패/B미시작/비교미산출. 실행SHA262cfada722a1c7166ac4850c8d9ea4d7307e039, trial approved-retry-20261014-01. 직전baseline0.7083GiB<6GiB로시작,worker 약94.02초 memory_monitor_unavailable. 마지막durable단계dry_run/완료optimizer0/not_started,기록age5.35초로정확한종료순간갱신수미확인. 자동재시도0.
- 관측:worker자체RSS1.873GiB/GPUallocator allocated1.249/reserved1.277GiB(peak1.258/1.277); parent+worker RAMpeak2.520GiB; hostGPUpeak2.289GiB<6; 마지막adapter적용MiB0.793/28.906/2314.711. 직전유효snapshot은GPU초과trigger가아님. container한정events OOM없음/worker종료코드미저장으로소멸원인미확인,OOM배제·driver원인주장0. 실행오류1회,같은원인재시도0.
- 보존/종료:원본8파일hash/초기가중치hash불변,final-test내용/hash열기0/평가미실행/Bfolder없음. 이번monitorPID3517잔류없음/container제거확인,다른서비스·driver변경0/Windows비공개역복사0. PCWSL trial에sources.after-interruption.private.json/interrupted.summary.private.json 및worker중단증거보존. 공개보고 docs/AB_COMPARISON_RESULT.md 갱신. 미검증은worker근본종료원인/정확한최종optimizer수/697실소비/88완료/reload/평가/A-B효과. 다음은공개기록checkpoint/push후신산님보고,새학습없음.
- 직접승인:시작기준GPU>6GiB면미시작,기존학습설정/6GiB유지, A정상완료(88관측/저장/reload/기존자료평가)때만B,중단시자동재시도0/마지막단계·저장완료수·자체allocator/RSS·adapter전체계수보고. final-test열기0,평가는calibration/selection만.
- 기존실패 namespace .work/ab_comparison 보존. 승인1회용 .work/ab_trials/approved-retry-20261014-01에검증된입력2/manifest2/preparation/sourcebefore의6파일만동일hash로복사. 새namespace 재사용거절,원본/초기가중치복제·정답수정·순서변경0. 이필수보존경로와baseline즉시거절검사만최소추가,TDD2 RED→GREEN/영향26PASS.
- 시작검사:전체trial직전/worker준비직전/실제Popen직전의fresh adapter snapshot을기록하고6GiB초과면ConfigError로worker미시작. 이후기존독립guard유지. 기존학습697노출/88optimizer/head-only/fp32/seed13/gradaccum8/정답49이번실험전용과1800초/RAM24/disk30GiB그대로.
- 자원:PCWSL own GPU감시1개와 judgment-ab-approved-retry-20261014-01 container1개만새로생성,networknone/RAM4g+총RAMswap8g/기존immutable image. 종료시이번monitor/container만정리하고source/input/weight/로그보존. 다른서비스/driver변경·비공개역복사없음. 다음은안전SHA/remote일치→CIM기준검사→승인1회시도→중단/결과보고.

## 2026-10-14 기록·중단 보완 승인 구현 / 담당 어울

- 직접승인:4개기록·중단보완,실행직전adapter별GPU기준값,원문/비밀없는비공개worker출력,정상/강제중단작은모의시험. A/B재실행은결과확인뒤. 실행기준d75c09c/work-native-synthetic기존체크아웃,실데이터/모델/서비스/한도/학습조건변경0.
- 순차TDD:새 telemetry 시험 RED(import미구현)→기본9시험PASS. 정상상태/완료갱신·갱신중미확인/출력허용숫자와나머지가림/기존context만allocator관측/atomic 이전자료보존/쓰기실패·멈춤/기준값/실제subprocess강제exit와owned 종료검증. Windows sandbox기본temp권한오류1회는프로젝트 .work/tmp로범위를명확히해해결.
- 연결:worker단계/CPU·기존GPUallocator heartbeat·AdamW pre/post hook/고정upstream모델로드·학습전selection·train_model관측및복원,private출력pipe가림,hostadapter계수시계열·학습전baseline,stop의최대50ms best-effort기록후finally owned종료. 정상기록은atomic+fsync/최대200ms 대기,실패시완료를주장하지않고중단. 모의/코드점검중 nullcontext 로컬import shadow오류1회수정,후속43 영향PASS. 변경구현은ML수학/순서/6GiB설정에관여하지않는다.
- 다음:추가pipeline 모의시험·필수영향검사·최종독립review1회→보완1회→안전checkpoint와PCWSL동일SHA의네트워크차단CPU/모의검증. own일회성시험container만생성/종료,학습/실GPUcontext/자료열기/역복사0. 실행환경준비를다시설치하거나수동자료검토를반복하지않는다.
- 독립review1회 Critical0/Important2/Minor0:SIGTERM무시worker가남을수있음/실제trigger snapshot 연결부족. 각각RED확인후owned terminate+kill,판정에사용한thread-local snapshot/current RAM·GPU·disk·elapsed/한도/판정시각그대로기록으로1회수정. 기록실패·hang여전히최대50ms best-effort뒤finally 종료. 재리뷰없음. Windows영향49실행/48PASS/POSIX1SKIP,추가producer시계열+baseline1시험PASS. POSIX skip는PCWSL에서실제SIGTERM무시child·무관child보존으로확인할예정.
- PCWSL최초모의50시험:45PASS/4ERROR/1FAIL. 실제I/O의 append/atomic fsync각약60~90ms와writer경합이초기200ms대기를초과,stop의fsync도50ms를초과해정상packet공개전강제exit. 권한/자료/모델문제아님. 합성6회I/O probe로원인확인후전용임시파일제거. 정상기록최대1초로제한하고독립guard는그기록을기다리지않는다. stop packet만atomic공개후sync를시도하며최대50ms뒤owned kill,stop동기화는best_effort로표시. 완료step/단계의정상기록은여전히fsync후atomic. 6GiB/학습/1800초변경0.
- PCWSL2차모의50시험:49PASS/1FAIL. 정상close가진행중sampler를100ms만기다린뒤살아있다고판정하는경합. 합성sampler완료지연으로RED재현→정상close의최대1초join으로GREEN. 상한중단경로는normalclose를호출하지않고50ms best_effort/owned강제종료유지,관련3시험PASS. 실학습실패/재실행으로계산하지않는모의구현오류이며각실패로그는별도파일로보존.
- 최종PCWSL checkpointfb79e66에서51시험/31.375초 ALL PASS(정상2회·강제최근완료1회/진행중·쓰기실패/hang·SIGTERM무시owned kill/무관child생존·6GiB경계·동일trigger snapshot·baseline·원문가림·함수복구). Windows추가import계약4PASS,정상sampler 경합시험/관련강제시험3PASS. 결과 docs/PCWSL_TELEMETRY_VERIFICATION.md. GPUdevice/네트워크없이CPU전용일회성container사용,실자료/모델/기존실패원문/final-test열기0,역복사0,A/B재실행0. 학습설정·한도·다른서비스변경0. 다음은검증보고/신산님실험재실행지시대기.

## 2026-10-14 PCWSL 실패 현지 진단·최소 기록안 / 담당 어울

- 신산님 직접지시:현지실패로그읽기/중단단계·GPU집계확인/미확인명시/기록보완안제시만. 재학습·서비스종료·6GiB변경없음,Windows역복사는필수일때만별도묶음승인.
- 현지HEAD854b564 clean,실행49b0060과관련실행코드차이0,고정upstream clean. A호출/worker기동/입력검증은확인,15.68초host상한6.30GiB로exit3/B미시작. worker optimizer null/unverified·summary/output없음. 내부모델load/기준추론/학습전selection/optimizer중정확한단계는기록없어미확인,checkpoint부재로0회추론금지.
- GPU는adapter별 max(dedicated+shared,committed)의host합계이며pid별자체VRAM아님. 마지막snapshot은중단후값,adapter별피크내역/시계열없음. worker출력DEVNULL/optimizer메모리카운터완료후저장/os._exit로중간증거유실확인. 제안 docs/PCWSL_FAILURE_DIAGNOSIS_PLAN.md에단계전후·성공step즉시atomic저장·자체allocator/RSS와host시계열분리·종료전stop기록및미확인경계정리. 구현/시험/학습미실행,진단에역복사불필요. 현지검색rg미설치1회는grep읽기로대체.

## 2026-10-14 PCWSL 비공개 전송 승인·실제 A/B 착수 / 담당 어울

- 신산님이18파일약684MB의PCWSL전용 .work 전송을명시승인. 승인allowlist만SSH전송/전용권한해제압축,17payload파일의hash·크기전부일치(683,964,215bytes),final-test·과거시험점수·credential·원본ZIP전송0. 송수신임시tar만삭제,사용자원본/입력/모델/증거보존.
- 실제GPU모델gate: 첫연결은libdxcore 목적경로차이로GPU인식실패1회,수정후같은이미지/전용환경에서실제모델/tokenizer 경계1시험PASS(11.71초, RAM2.26GiB/GPU상한2.15GiB/disk16.71GiB). 실패증거보존·optimizer실행0,기존서비스/driver변경0. 최적화attention experimental 옵션은켜지않고양쪽동일기본연산경로유지.
- 반복입력gate PASS: A697고유/67그룹×1회, B280고유/62그룹(143×2+137×3), 양쪽노출697/업무558/없음139/예상optimizer88. 원본/출처/group/정답수정49/실효shuffle순서 추적고정·기존Windows 준비manifest와대조. calibration457/selection374만별도진단,final-test guard설치.
- 실행자원: 판단전용일회성ROCm container와context없는host GPU감시,전체trial1800초/RAM24/GPU6/disk30GiB. 공유host보호를위해 owncontainer RAM4GiB+총RAM/swap8GiB로더좁게제한. port/network/타프로젝트volume없음,시험종료후이번container/감시만제거. sharedruntimeimage도projectdisk에포함. 실입력/최종weights/추적/평가증거는ignored .work에보존.
- 다음: 안전checkpoint/원격exactSHA·clean확인 후 A→B순차1회실행,실697소비·88관측·인코더불변·동일초기·reload·자원한도·원본보존대조. 결과는선별/잠정정답수정/반복의합친효과이며품질판정not_decided. 상한/검증실패면해당실행만중단하고성공으로표시하지않는다.
- 실제실행: checkpoint49b0060 clean/원격일치에서A시작,15.68초에전체host GPU상한6,762,946,560bytes(6.30GiB)>6GiB로exit3자동중단. B시작0,A최종model/697실소비/88관측/reload/측정미완료,optimizer실제횟수미확인. parent+worker RAM2.06GiB/projectdisk16.72GiB관측,sharedimage포함. AMD adapterresident/committed 합산의보수상한이며단독VRAM으로표시하지않는다. `_Total`중복행없음직접확인,상승단계/타작업기여미확인. 같은학습자동재시도0.
- 사후대조:원본6파일+선별/검토2파일 및초기weight hash불변,PCWSL final-test없음/열기0. 이번container/감시종료·제거,기존음성서비스/DB/driver변경0. PCWSL중단증거보존;Windows역복사는구체적승인부족자동검토거절로수행하지않고원문없는집계만보고. 새결과 docs/AB_COMPARISON_RESULT.md에미완료로기록. 자원실패1회(Windows실패와별도),중단집계경로를arm폴더로찾아수정한읽기오류1회;실학습재실행0. 다음은이예외보고이며GPU6GiB내사용량축소검증없이성공/효과를주장하지않는다.

## 2026-10-14 PCWSL 이전 착수 / 담당 어울

- 직접 지시 '그럼 그기서 작업해'에 따라 PCWSL을 새 개발·A/B 실행 대상으로 승인. 기존 사용자 원본과 Windows 실패 증거는 보존하며 작업branch exactSHA를 Git으로 원격checkout한다. Windows 소스 archive 복사는 하지 않는다.
- 확인: SSH/WSL2/Python3.12/AMD RX7800XT 호스트/ROCm7.2.4 경로 및 /dev/dxg. 기존이미지 Torch2.13.0+rocm7.2/Transformers4.57.6/safetensors0.8.0. judgment 호환성과GPU연산은미검증. legacy rocm-smi 실패만으로GPU불가로단정하지않는다.
- 자원: 기존 fish-speech RAM18GiB,host가용약1.6GiB. 공유서비스중지/변경0. 우리별도container에서기존immutable ROCm이미지를재사용하고프로젝트만mount한다. GPU장치와ROCDXG/dxcore라이브러리읽기전용연결,타프로젝트모델/volume/port공유없음. container는준비·시험후삭제,프로젝트입력/모델/증거는ignored .work에단일보존.
- 이전payload: 원본train697/선별280/검토표·고정A/B 순서·calibration457/selection374·고정무학습모델/필요승인metadata만PCWSL사용자전용프로젝트로이전. raw ZIP/final-test/과거mixed scores/Windows venv·wheel·credential/이전학습모델전송0. 소스는Git exactSHA,데이터/모델Git업로드0.
- 조건유지: A/B 동일초기·동일Linux환경/설정·697/88·fp32·final-test비접근·원본보존. 전체1800초/RAM24/GPU6/projectdisk30GiB,준비5GiB상한. 큰런타임이미지신규다운로드없이읽기전용재사용. Linux의존성/저장범위/GPU감시검증후학습. 다음은checkout·전용환경·GPUgate.
- GPU 최소 fp32 연산 PASS. HIP free-memory는 다른process 점유를 안정적으로 반영하지 못해 전체 감시로 채택하지 않았다. GPU context를 만들지 않는 Windows adapter의 resident/committed 중 큰 값을 adapter별 합산해 보수적 상한을 읽고, stale/형식/경로/승인binding 실패 시 중단한다.
- 독립 portability 리뷰1회 Critical0/Important2/Minor1: 승인config와환경변수 양방향binding, 전용venv/Python/Torch 버전 사전검증, 공유runtime이미지 점유량의 음수/bool/비정수 거절을 1회 보완. 새 경계 RED→GREEN 및 영향회귀38 PASS, 재리뷰 없음. suite 순서상 optimizer 시험이 먼저torch를 import하여 import-only 시험1회 실패했고 import 시험을 먼저실행해 실제 회귀없음 확인. 실제 A/B 미실행.
- 전송은 자동승인검토에서 구체적 payload/destination 명시승인 부족으로거절. 18파일/684MB allowlist 묶음은 Windows ignored 로컬에준비했으나 PCWSL userdata/model 전송0. exactSHA 원격source/upstream, 전용venv·패키지준비·context없는GPU감시는 계속하며 원본/시험 자료는 열지않는다. 사용자에게 정확한 묶음/경로/목적/보존범위 승인을 요청해야 학습진행가능.
- 준비오류: 이미지Torch는 basePython이아닌 /opt/venv에있어 projectvenv 상속실패1회. 읽기전용 site-packages 경로를 ownvenv .pth에연결해해결. setuptools wheel의vendored METADATA까지세어무결성검사가거절1회, wheel최상위distribution metadata만사용하도록 RED→GREEN2 PASS. 고정버전/hash검증은유지하며 글로벌패키지변경0.
- PCWSL 준비결과: source checkpoint483a222/upstream고정SHA/clean, Linux37패키지 공식hash·size검증/신규수신53,161,061bytes(5GiB이내), Torch2.13.0+rocm7.2 유지, Python3.12.3, Laya editable/pipcheck PASS. projectvenv의 네트워크차단 합성·경계·optimizerhook 영향39시험 PASS. 실제모델호환/학습/697실소비/88갱신/A-B수치 미검증.
- 현재예외: 전송승인만미충족. PCWSL train/test/baseweight 파일없음확인, 자료전송/학습0. 이번probe·설치·합성검증container와GPUsnapshot process 모두종료/제거. 기존음성서비스·DB·driver 변경0. 사용자에게18파일약684MB의 PCWSL전용 .work 이전범위 승인을 요청하고 승인후 hash대조·모델gate·같은상한 A/B 실행한다.

## 2026-10-14 승인된 A/B 동일 노출 비교 / 담당 어울

- 직접 승인: B 선별280건/잠정정답49건을 이번 실험에 한해 사용, 원본 보존. A/B 동일 무학습 가중치·설정·697회 노출·AdamW88회. 순서/반복/원본ID/그룹 추적 고정. 검증·시험 자료 optimizer 비입력, final-test 다시 열지 않음. 효과는 선별·정답수정·반복노출의 합친 효과로 보고.
- 현재 1단계 Windows 로컬, branch work/native-synthetic / 시작 SHA c79183a, clean 확인. 기존 branch와 승인된 Native 실행을 이어가며 새 branch·자료/모델 복제본을 만들지 않는다.
- 실행 순서: 반복 입력/수정 범위/원본 추적/누출·final-test 접근차단 실패시험→최소 구현→필수 영향 회귀와 독립 리뷰1회→안전코드 checkpoint→A/B 순차 실제시험→calibration/selection 비교·보존·보고. 이미 완료된 수동검토와 과거 학습을 준비 검증으로 반복하지 않는다.
- 계획 자원: ignored `.work/ab_comparison/`의 원본ID 순서표·arm별697입력·승인config·평가 집계, 기존 `.work/runs/`의 새 arm별 최종 모델·worker 증거. A/B 동시 학습0, arm별30분/RAM24GiB/전체GPU6GiB/전체 프로젝트disk30GiB, 전체최대60분. 수명은 이번 비교 동안, 최종 모델/추적/측정 증거는 보존하고 새 중복checkpoint만 동일hash 확인 후 정리. 기존 원본/모델/증거 변경0, 신규설치/다운로드/외부자원0.
- 판단: 최신 직접 지시가 앞선 실험안의 test446 재평가를 대체한다. 평가 대상은 calibration457/selection374만, final-test는 loader 및 파일open guard로 차단. 과거 test 결과도 이번 비교에 새 결과로 인용하지 않는다.
- 상태: 반복 입력 검증 구현 시작, 실제 학습 미실행. 새 오류0. 다음은 새 실패시험과 결정된 반복 목록 검증.
- 반복 준비: A697고유×1회/67그룹, B280고유/62그룹(143개×2회+137개×3회). 양쪽697노출·업무558/없음139·예상88갱신. 원본ID/출처/그룹·JSONL순서·순환 횟수 고정, 원본과 선별 제안본 hash 보존. final-test/과거 mixed scores 열기0.
- 새 TDD: 반복/입력변조/외부ID/gold범위/final-test 차단6개 RED→GREEN. 영향 회귀28개 PASS(러너·그룹경계·실제optimizer hook 포함), 마지막 failed JSON은 CLI 실패fixture의 예상출력이며 실제 학습실패가 아니다.
- 독립 코드리뷰1회: Critical0/Important2/Minor0. upstream epoch shuffle로 JSONL 순서와 optimizer 소비순서가 다름을 발견하여 effective_schedule과 후보 순서·optimizer window·원본 occurrence를 추가, 실제 encode 소비를 관측/검증하는 hook을 연결했다. 전역deadline도 추가. 수정 후 신규9개 RED→GREEN, 재리뷰 없음. upstream 소스 변경0.
- 시간 판정: 앞선 제안은 arm별30분/최대60분이었으나 최신 직접 지시의 '기존 자원 상한'을 보수적으로 적용해 전체 A/B·평가·집계에 단일1800초 deadline을 설정. 각 arm/worker에는 남은 시간만 전달한다. 학습 설정과697/88 조건은 변경하지 않는다.
- 현재 변경: src/judgment/replay.py 신규, data.py의A/B test role 차단, runner.py의입력·실소비검증/접근guard, docs/run_ab_comparison.py, tests/test_replay.py, 이 기록. 원본/기존 모델/데이터·설치/credential 변화0. 다음은 수정 영향검사·안전checkpoint 뒤 실제 A/B 실행.
- 실행 전 gate: 수정 후 영향회귀31 PASS, 새Python파일 AST 문법 PASS, 공개경로/Secret패턴6파일 safe=true/findings0 및수동content/diff검토 PASS, git diff --check PASS. 실제 GPU시험은 아직 미실행. 동일근본오류0, TDD 미구현 import 실패는 계획된RED와 구별한다. 새checkpoint에 데이터/모델/검토원문을 stage하지 않는다.
- 실제 시도: 실행SHA3531f1458f6ddbb704844a81cc6146f715d14741의 clean/원격일치 확인 후 A/B 실행. A약45.2초에서 parent/worker 모두 전체device VRAM7.42GiB>6GiB를 감지해 exit3. B시작0. A완료모델/optimizer88/실제노출697/reload/평가 증거 없음, 실제optimizer 횟수도미확인. 상태 RESOURCE_LIMIT_STOP. 실패1회, 같은설정 자동재시도0, 상한완화/CPU장시간전환0.
- 진단: 이실험 Native Python잔류0, device2325MiB 지속. Windows GPU dedicated 집계 vmwp 합계약2.27GiB(개별PID는로컬증거에만기록), VM이름/실험과의관계/작업내용/중단시점 기여는미확인. CPUtokenizer A첫159/B첫319/기존첫164token 확인으로 긴첫입력 가설은근거없음; GPU모델 재호출0. VM/driver/다른GPU작업 변경0.
- 보존: 원본 train/calibration/selection examples+JSONL6파일 및선별제안/검토2파일 hash변화0. final-test는검증/hash명목으로도열지않음. 원본ZIP·기존모델 삭제/수정0. 고정replay/실효순서/승인config/worker미완료자료/상한로그/중단집계 보존. 공개결과 docs/AB_COMPARISON_RESULT.md 작성, 실제효과·품질수치 미산출을명시.
- 다음: 전체GPU6GiB를지킬 가용상태와VM점유 관계 확인 필요. VM종료/다른GPU작업중단/driver·환경/상한변경은승인범위외이므로 수행하지않고 신산님 다음지시대기. 실패증거를덮어쓰거나 A를완료로표시하지않는다. 원문없는실행중단기록만작업branch에보존한다.

## 2026-10-14 학습 697건 의미 선별·동일 조건 실험안 / 담당 어울

- 신산님 직접 요청: 기존 학습 697건만 검토해 명확한 정답/정말 후보 없음 선별, 복수·애매 사례는 삭제 없이 별도 보존, 정리 전후 수량과 원본/정리 학습 비교 실험안을 먼저 보고. 추가 학습은 보고 확인 이후.
- 범위: train 양성558/정답제외139/67연결그룹. 원본 train 및 calibration/selection/test 8파일의 조사 전 digest를 ignored 로컬에 기록. 기존 실행·검증·calibration 의미 검토 반복 없음.
- 담당: Main 통합/보존/실험안, 독립 검토자3명이 겹치지 않는 양성186건씩과 대응 파생을 검토. 각자 현재 발화·저장된 과거맥락 전체·업무후보를 확인하고 잠정 타당/미확정 ID와 근거를 남긴다. 모델 score와 검증·시험 자료는 판단 입력에 사용하지 않는다.
- 로컬 산출물: `.work/train_semantic_review/`에 입력 묶음·검토표·선별 후보·복수/불명확 보존본·원본 보존 digest. 원문/ID/검토 상세는 Git 제외. 새 임시 process·GPU·port·container·모델 cache 없음.
- 착수 checkpoint: 검토 진행 중으로 시작. 엔진 코드/설정·원본 gold·분할 수정0, 모델 호출/학습/설치/다운로드0. Python 시작 시 기존 경로 경고는 실행 exit0와 구별해 기록했다.
- 종료 checkpoint: 697건 전수 검토. unique216/none64/multiple264/uncertain153. 선별 제안280건/62그룹, 복수·불충분 보존417건/66그룹. 원본697건 삭제0. 기존 gold 변경 제안49건(업무→없음14/다른업무7/없음→업무28)은 원본 수정이 아니라 승인 전 별도 제안본에만 반영. 원래 gold를 유지하는 보수안231건도 수량을 구별했다.
- Main 표본 감사: 타당 후보 누락으로 파생1건 unique→multiple 교정, 후보합집합 근거와 실제 제시 후보의 범위 불일치 문장 정리. 최초281/416 집계는 preaudit로 보존하고 최종 results-v1의280/417로 대체. 전체 전문가 의미 재판정으로 확대하지 않는다.
- 새 검증: 각 검토자 전담 ID와 원본697개 전수 대응·누락/중복0·타당/미확정 후보 membership·유형정의·원래 gold/입력 보존·139쌍 공통 후보일관성·선별군과 calibration/selection/test ID/그룹 교집합0·원본8파일 조사 전후 digest 일치. 검토표 digest를 최종 집계에 결합. 새 집계 코드 문법 및 실제 집계 PASS. 과거 제품 전체 suite·실모델 시험·학습 반복0.
- 오류/조치: 상대 root를 전달한 집계 첫 시도에서 Native 경로 해석이 judgment/judgment로 중복되어 파일누락1회, 명시 절대 root로 해결. 후보 이름 출력 인코딩 불일치1회는 -X utf8로 해결. 3번 검토자 수동기록 연결 개행 누락1회는 helper만 수정 후186 unit coverage 확인. 미해결 실행오류0, 같은 근본원인3회 없음. source/input 검증실패0.
- 변경 파일: docs/train_semantic_selection.py, docs/TRAIN_SEMANTIC_SELECTION_EXPERIMENT.md, 이 기록. 원문·ID·근거·잠정정답·선별/보류자료는 ignored 로컬에만 보존. 제품 src·실제 학습설정 변경0.
- 최종 보존 검사: 독립 계산으로697=280+417·원본 source_example 전수동일·선별 request/그룹불변·정답제안49건·최종 검토표 digest 결합 확인 PASS. 원문/비밀 수동 내용검토 및 공개파일 경로/Secret 패턴 검사3파일 safe=true/findings0, git diff --check PASS. 실제 원격 기존 checkpoint70935a7과 일치 확인 후 해당3파일만 보존한다.
- 실험 제안: 동일 무학습 가중치에서 A 원본697건/B 선별280건 각각 시작. B는 선별 업무216/없음64를 각2~3회 반복하여 입력697회·업무558/없음139·AdamW 예상88회를 A와 맞춘다. 자연1epoch이면 B는35갱신이므로 같은 학습량이라고 하지 않는다. 동일 split·seed·head-only·학습률·batch·precision, arm별30분/전체최대60분·RAM24/VRAM6/전체disk30GiB. 실제 replay 생성/실험코드/추가학습 미실행.
- 다음: 신산님께 수량·49건 잠정정답 제안·동일조건 실험안을 보고한다. 보고 확인 전 추가학습0 유지. 미확정은 공식 의도 정의/전문가 인수·G2 품질기준·새 미사용 holdout이며, 기존 test를 새 검증으로 재사용하지 않는다. 안전한 코드·집계 보고만 작업branch에 보존하고 원문/모델/데이터 업로드·main병합·배포는 하지 않는다.

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
