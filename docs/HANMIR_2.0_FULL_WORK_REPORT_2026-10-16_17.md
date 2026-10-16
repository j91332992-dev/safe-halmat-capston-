# HANMIR 2.0 — 2026년 10월 16일 오후~17일 전체 작업·실측·인수인계

> **현재 잘되는 설정 유지.** 마지막 STT 호출어 힌트 복구 후 실제 투투스 3건·배터리 질문 1건이 처리됐고 사용자가 정상 청취를 확인했다.
> 본문은 최신 통합 상태, 부록 31개는 각 단계 당시 상세 기록이다. 부록의 ‘최종/현재/대기’는 그 문서 작성 시점 표현이다. 충돌하는 경우 본문을 우선한다.

## 문서 범위와 읽는 방법

- 기간: 2026-10-16 오후부터 2026-10-17 작성 시점, 한국시간 KST.
- 카메라·보호구·음성·AI·UWB·방향·대피·양방향 통화·메모리·트래픽·배포 상태를 함께 정리했다.
- 실제 장치 로그, 서버 JSONL/요약 JSON, 이전 단계 MD 및 사용자 청취 답변을 구분했다.
- 이번 요청은 문서화이며 운영 설정 변경·펌웨어 업로드·새 부하 시험·GitHub push는 하지 않았다.
- 원본 로그 UTC에 9시간을 더하면 KST다. 10/16 19:13 UTC는 10/17 04:13 KST다.
- 수치만 먼저 보려면 1·6·7장, 유지 설정은 8장, 다음 작업은 9장, 모든 시행착오는 부록을 읽는다.

## 1. 현재 어디까지 되었는가

| 기능 | 확인된 상태 | 남은 문제 |
|---|---|---|
| 영상 수신 | 최종 통화 시험 평균16.053FPS | 장시간·다른AP 환경 보장 아님 |
| 전체 YOLO | 평균11.087FPS | 최저5초창8.595FPS, 항상10FPS는 아님 |
| 상세 PPE | 평균3.657FPS | 5FPS 고정 아님, 장갑 오탐 남음 |
| 보호구 박스 | 종류별 구분 박스, 상세 화면 갱신 경량화 | 상세 박스를 전체11FPS로 추적하는 기능은 없음 |
| 투투스·배터리 | 마지막 실제 호출3건/질문1건 처리, 사용자 정상 확인 | STT 의존, 0.5초 종단 응답 미보장 |
| TTS | 문장 출력·버퍼 재생 복구, 사용자 깨짐 개선 확인 | 통화 RX큐 폐기는 별도 잔존 |
| UWB | 4앵커 측량,100ms 프로파일/WS/정지필터/보간 | 서버 간격 변동, 절대 정확도 미실측 |
| 방향 | BNO 방향 갱신·지도 보정값 활용 | 절대각 오차·보행방향 차이 미검증 |
| 통화 | 최종197.16초 양방향,재부팅/재연결0 | P4 RX큐 약2.8% 폐기, 장시간 검증 필요 |
| 통화 중 AI | 현재 설계상 호출/STT 중지 | 네 기능을 동시에 모두 실행하는 상태 아님 |
| 대피 | 지도/UWB/방향으로 상대방향·경계보정 구현 | 출구까지 실제 모의보행 완료 검증 남음 |
| 배터리 | 조회·음성 응답 확인 | SOC 계측 정확도/사용시간 미측정 |
| 앱 | 웹·모바일 공유 소스 변경 | 최신 APK/IPA 재배포·양 OS 실기 종합검증 미완료 |

시작 시점의 저속 분석·반복 통화 끊김에서 크게 개선됐지만, 모든 상황 무병목/무오탐/재난안전 검증 완료를 의미하지 않는다.

## 2. 어제 오후부터 진행한 작업 순서

1. GitHub 최신 UWB 안정화 변경을 기존 P4·모바일 통합판에 선별 반영. 수동지도와 기존 AV 구조 유지.
2. 최종 PRD의 데이터 최신성·상태 계약 기반 추가. 초기 회귀시험205 passed/2 skipped는 당시 결과이며 현재 전체 변경을 재시험한 수치가 아니다.
3. 과거 AP/서버IP 때문에 접속 실패하던 P4·태그 설정을 현재 환경에 맞춤. USB 포트 소실도 관찰했으나 그 전원/호스트 문제의 최종 원인은 미확정.
4. 마이크 좌우 슬롯·원시PCM·WAV·STT 원문 진단, TTS403 복구, 외부 NS OFF 비교 후 실제 음성 응답 확인.
5. VAD 종료시간 단축·안내 PCM 내장·unknown 장문 억제. 투투스 로컬모델용 녹음/라벨/학습/shadow 시험.
6. YOLO fast/detail 분리, ROI 확대, OpenVINO GPU 활용, 밝기/색감 조절, 상세 GPU960, 조끼 임계값 비교 및 박스/지표 표시.
7. UWB 정지 흔들림 필터,100ms 측량, HTTP 병목 비교 후 WS 전송, 시간창 정지 판단·화면 보간.
8. 화재 음성·A* 실제 경로·상대방향 단문·책상 경계 보정 구현. 실제 모의대피 시연은 남음.
9. 통화 스택 panic·송신 지연·서버 큐 정체·카메라 정체를 단계별 수정. 실패 후보도 기록 보존.
10. Wi-Fi 절전 해제 후 약3분 양방향 부하 시험. 이후 호출 저하를 발견해 기존 STT 힌트를 복구하고 사용자 성공 확인.

## 3. 카메라·YOLO·보호구·화면

### 3.1 초기 병목과 구조 변경

초기 전체640+상세640/960 직렬 대기에서46.42초 측정 수신10.49FPS/분석2.13FPS, 처리 중앙371.63ms/P95 577.71ms. 320 축소 시험은5.49FPS였지만 보호구 검출이 감소해 채택하지 않았다.
전체640 fast와 상세 PPE를 별도 프로세스로 분리하고 최신 프레임만 처리한다. 상세는 사람·머리·몸통 ROI를 확대해 추가 추론한다. 오래된 결과/상세 미실행을 즉시 미착용으로 누적하지 않고 UNKNOWN 및 결과 나이를 구분한다.
Torch predictor 재생성 때 스레드 제한이 바뀌던 문제를 확인했다. Intel Arc iGPU OpenVINO FP32를 적용했다. 같은8장 PyTorch 중앙109.59ms→GPU25.02ms. CUDA 미지원은 iGPU 사용 불가와 다르다.
상세960 CPU 패스를 GPU로 전환하고 제출 간격0.20초를 유지한다. 음성 중1FPS 제한을 제거했고 상세도 음성 중 수행한다.

### 3.2 밝기와 표시

현재 유지: 분석 gamma1.35, 표시 gamma1.75, red gain1.08/blue gain0.96, sharpen0.2. 분석과 표시 전용 보정을 구분해야 하며 센서 수동노출값이 아니다.
사용자 참고 사진과 비교했고 현재 밝기에 대한 개선 확인을 받았다. 이후 통화/UWB 작업에서는 밝기를 바꾸지 않았다.
사람·안전모·조끼·장갑 구분 박스와 FPS/ms 지표를 반영했다. ms는 해당 API 필드 의미에 따라 해석하며 무조건 네트워크 ping은 아니다.
‘최근 분석 화면’은 상세 분석 영상이다. 전체11FPS여도 상세 박스 갱신은 약3~4FPS다. 별도 추적 없이 옛 상세 박스를 새 전체 영상에 붙여 정확한11FPS 박스처럼 표시하지 않는다.
웹 확인 주기1초→200ms, 새 frame_id만 다운로드, 3초 정체 표시. 경량 metadata 한 표본5016→106바이트. 요청이 겹치지 않도록 완료 후 다음 요청을 예약한다.

### 3.3 실제 인식 비교

| 자료/단계 | 결과 | 제한 |
|---|---|---|
|초기 머리 ROI 전/후 착용8장|안전모0/8→3/8|이후 추가 개선 전 단계|
|GPU960 고정 착용20장|3종 각각20/20,CPU와 동일|같은 표본 결과|
|맨손16장|장갑 오탐11/16,CPU/GPU 동일|미해결 과제|
|조끼 임계값 .40/.35/.30/.25|같은 착용20장6/9/15/19개|.25 채택|
|조끼 미착용19장|후보 모두0/19 오탐|다른 옷 일반화 불가|
|새 연속 상세20개|안전모20,조끼19,장갑20,동시19|해당18/20 요구 충족|

새20개 양성 점수: 안전모 .456–.726, 조끼 .250–.616, 장갑 .666–.839. 장갑은 색상 보조 규칙을 포함하므로 전부 순수 glove 모델 확률이 아니다. 검출 점수와 정확도/재현율은 다르다.

| 라이브 단계 | 수신FPS | 전체FPS | 상세FPS | 음성 활성 구간 전체FPS |
|---|---:|---:|---:|---:|
|GPU960 최종간격|14.26|11.46|3.71|11.38|
|조끼·메타데이터 최종56.13초|14.66|11.17|3.58|11.04|
|최종 통화197.16초|16.053|11.087|3.657|통화 중 AI는 중지|

GPU960 단계는29개 구간 중1개6.42FPS, 조끼 최종은 약2초 표본21개 모두10 이상/최저10.14였다. 서로 다른 시험이므로 모든 순간10FPS 보장값으로 합치지 않는다.

## 4. 마이크·AI 호출·TTS와 마지막 복구

### 4.1 현재 실제 방식

INMP441 → P4 AFE VAD/프리롤 → WAV 전송 → gpt-4o-mini-transcribe(ko) → 서버 호출어/긴급어/intent → 규칙·DB 조회 또는 필요한 AI 설명 → P4 스피커.
투투스 단독은 armed 후 ‘네, 말씀하세요’ 내장PCM 재생. 배터리/위치 같은 조회는 불필요한 설명 LLM을 호출하지 않는다. 일반 unknown이 장문의 비상 설명을 만들던 분기를 수정했다.
**웨이크워드 UI는 맞지만 현재 P4 로컬 모델이 직접 확정하는 방식은 아니다.** 잘됐던 실제 경로는 서버 STT+P4 내장 안내음이다.

### 4.2 입력·출력 수정

초기 보존 WAV5개는 zero fraction96.35~99.20%,RMS48.80~182.82였다. 발화시점 일치는 미확인이라 이것만으로 원인을 확정하지 않았다. 좌우슬롯 진단, 외부NS OFF 비교 후 사용자가 성공 확인. 현재 NS OFF.
TTS403과 톤 fallback을 구분하고 edge-tts7.3.1 적용 후 실제 문장 청취 확인.
AFE 무음192ms+추가160ms,pre-roll300ms. 안내PCM46,896바이트 내장, 앞 무음 약180ms 제거. 버퍼형 답변 재생으로 네트워크 공급 정체 영향을 줄였다.
답변 WAV114,476/PCM114,432바이트 전체쓰기, 수신247~266ms, 재생 약3.7초 기록. 재생 길이는 응답 대기시간과 다르다.

### 4.3 로컬 모델 시험

69개 분류 중 명확한 단일 호출9개, 추가33개 분류를 진행했다. pilot학습/streaming int8/P4 TFLite frontend 통합은 시험했다.
shadow 관측851추론, 최대처리11.917ms/큐대기13.666ms/drop0. 후보만 기록하며 실제 응답은 실행하지 않는 시험이었다.
연속 합성배치 호출2/3,비호출0/9로 파일별초기화3/3과 달랐다. 독립화자/현장 장기검증이 부족해 운영모델로 확정하지 않았다. 현재 WakeNet/shadow OFF.

### 4.4 인식 저하와 복구의 정확한 내용

대피 작업에서 힌트 문장이 전사되는 문제 때문에 STT prompt를 제거했다. 이후 사용자5회중1회 응답 보고. call active=0/녹음HTTP200/큐대기0ms였고 원본4개의 전사가 Tu/Kršc/Totus/주스로 나와 호출 판정에서 제외됐다.
100Hz 필터 단독은 개선이 없어 미적용. 임시 영문 호출어 허용도 철회. **이전 stt_prompt/stt_command_prompt 전달을 복원**했다.
같은 원본4개 모두 투투스로 인식. 짧은 비호출 후보에서 힌트문장 반복이 재현됐지만 기존 stt_prompt_echo 방어가 차단하는 것을 확인했다.

최신 실제 로그(KST):

|시각|결과|STT ms|서버전체 ms|
|---|---|---:|---:|
|10/17 04:13:23|투투스 armed|834.7|891.8|
|04:13:33|투투스 armed|873.6|926.2|
|04:13:43|투투스 armed|1100.4|1147.8|
|04:13:47|배터리 얼마야 armed_followup|716.2|769.7|

배터리 TTS처리7.0ms는 해당요청 값으로 매번 새 합성7ms라고 하지 않는다. 사용자 ‘잘된다’ 청취 확인. 서버시간은 발화끝→스피커첫소리 종단시간이 아니며0.5초 달성은 아니다. 3건 성공을 장기100% 인식률로 표현하지 않는다.
통화 중에는 호출/STT를 중지한다. 따라서 통화하면서 긴급발화까지 동시에 인식하는 요구는 별도 설계 필요.

## 5. UWB·방향·지도·모의대피

### 5.1 위치 복구와 흔들림

태그4앵커 측량과 서버수신을 구분해 진단했다. 잘못된 서버주소/API경로 수정 후 수신 복구. P4와 UWB태그는 독립 Wi-Fi장치다.
30cm 이동후보를 같은방향3회 확인해 이동 시작. 후속30초82수신에서 표시좌표범위0m 확인했지만 절대정확도0m가 아니다.
방크기 참고추정은 동일높이·기존종횡비1.515 가정 약5.66×3.74m. 다른종횡비에서도 비슷한 잔차가 나와 유일한 방크기를 확정할 수 없다. 실제XY는 실측해서 수동입력. 자동지도 생성 복원 아님.

### 5.2 100ms와 전송 개선

1번앵커와태그100ms 갱신,2~4번은poll응답이라 이번주기변경만으로 추가업로드 불필요.

|단계|서버Hz|간격중앙|
|---|---:|---:|
|100ms RF+기존HTTP|3.87|173ms|
|TCP재사용/compactACK|5.56|127ms|
|로그만료검사60초|5.56|125ms|
|NODELAY추가|4.38|124ms|
|첫WS60초|8.85|80.7ms|

측정조건 차이가 있어 인과를 단정하지 않는다. WebSocket에서도 같은 검증·중복/역순·필터·DB·로그를 사용한다. 미확인ACK최대4개,1초초과재연결. 필터이력DB WAL/NORMAL, 반복실패이벤트5초제한, 원본실패로그유지.
현재기록 uwb-net-20261017.3/tag-10hz-ws/USB460800. 921600후보는 미적용·소스복구. stage산출물을 무조건재사용하지 않는다.

### 5.3 이동 부드러움

표본당 작은변화3회 정지를 최근0.8초 시간창으로 변경. 좌표범위대각선30cm/전후중앙차4cm 조건, 수신공백0.5초초과면증거초기화. 30cm시작은유지.
화면100ms선형보간,외삽없음,위험판단좌표와분리,아이콘축소.
합성0.15m/s 정지오판5→0,0.5m/s13→0. 같은739후보재생 갱신170→372,최대단계46→35.8cm.
실제후속157.96초1433건:9.07Hz,유효좌표1225(7.76Hz),P95간격340ms/최대1421ms. 실패171중앵커3개미만162건. 최대좌표단계52.6cm남음. 사용자추종개선확인. 이동구간전체표준편차는경로이동이포함돼위치오차가아님.

### 5.4 대피 구현과 제한

책상2.4×1.2m·기존주비상구(3번부근)사용자정보를바탕으로지도기반기능준비. LLM이아닌A*와상대방향계산,2Hz작업. 앞으로/왼쪽/오른쪽단문,±30도정면/150도뒤쪽/1.5m회전예고/1초안정판단.
위치1.5초/방향1초이상오래되면안내중지. 지도확인/서명조건과유효경로필요. 임의새지도에서화재발화만으로무조건안내한다고보장하지않음.
장애물여유25cm,화재구역75cm. 책상안쪽깊이25cm이내도최근10초이력이같은통로를지지할때만route_origin보정. 깊은내부·모호한모서리·위험구역보정거부. 실제worker좌표는변경하지않고책상관통선분추가하지않음.
화재상황발생 무호출표현시험5개,경계/경로시험8개통과. 동일문장8초제한. 이미P4가재생중인안내취소는미구현.
출구까지실제모의보행완료는미검증. 연기·문개폐·계단·동적장애물·화재확산을자동인지하지않음.

## 6. 통화 구조와 실패·개선 이력

PC마이크가없던수신전용시험과양방향시험을구분했다. 사용자양쪽소리확인과장치PCM흐름확인뒤,지속통화실패를추적했다.
call_tx4096스택에서오류경로panic확인→8192증량. 이후136초/172초끊김은남아스택문제와송신정체를구분했다.
서버입력에서상대send를직접기다리던것을소켓별writer/제한큐로분리. 큐6400바이트/32항목/200msTTL. 이미도착한PCM최대1920바이트묶음. asyncio.sleep(0)으로수신루프가writer를굶기지않도록함.
용량/시간/제어폐기별도기록. 강제20ms배치는실패후제거. P4network1000ms/reconnect1000ms/send1500ms. 웹3초무수신경고/10초종료.
Wi-Fi previous_ps=1 확인후WIFI_PS_NONE. 5초자원로그추가. 카메라DQBUF2초제한/stream복구경로도추가했으나실제복구발동검증은아직없음.

|후보|결과|
|---|---|
|8KB/150ms|약136초끊김,재부팅없음|
|8KB/500ms|약172초timeout후종료|
|독립큐초기|약13%폐기및카메라정체|
|한방향coalesce|약0.98%폐기,양방향증거아님|
|양방향coalesce|약6~7%폐기|
|writer실행기회만|서버폐기0이나약53초실패|
|20ms강제배치|약83초실패,미채택|
|명시적timeout|198.16초유지,TX최대1096.716ms/영상실패1|
|절전해제최종|197.16초유지,TX최대44.467ms/영상실패0|

위는각시험당시결과다. 실패후보를최종설정으로재적용하지않는다. 단순히timeout/큐를늘려지연을숨기는방식으로완료하지않았다.

## 7. 최종 수치: 통화·카메라·UWB·트래픽·메모리

근거 call-latency-3min/{summary.json,metrics.jsonl,uart.jsonl,uwb.jsonl}. 활성197.16초,API198표본. 통화중AI는중지된조건.

|지표|값|
|---|---:|
|수신|3165장 /16.053FPS|
|전체분석|2186 /11.087FPS|
|상세|721 /3.657FPS|
|5초창최저 수신/전체/상세|11.793/8.595/2.798FPS|
|영상payload|137,492,624바이트(약137.49MB)|
|영상payload평균|697,369바이트/초,약5.579Mbps|
|stale영상생략|476건,네트워크패킷손실과다름|
|호스트CPU p50/p95|45.1/68.52%,다른앱포함|
|P4재부팅/통화재연결/영상송신실패|0/0/0|
|callTX실패/I2S쓰기실패|0/0|
|callTX최대|44.467ms|
|RSSI표본최저|-57dBm|

|음성구간|송신바이트|폐기바이트|비고|
|---|---:|---:|---|
|서버→안전모|3,534,080|0|서버큐0%|
|서버→웹|6,310,144|2,816|약0.0446%|
|P4TX큐|별도UART|0|큐초과|
|P4RX스피커큐|별도UART|97,920|서버→장치대비약2.8%,세션경계오차가능|

중계송신합계약9.844MB/197.16초=약0.399Mbps. 입력/출력/Wi-Fi오버헤드총합이아님. 서버큐1%미만은충족했지만전체장치음성1%미만은미충족. 서버폐기0은전체음성손실0이아님.
UWB1652건:computed1625/failed17/rejected10. 서버기록간격p50 98.58/p95 348.63/max1256.05ms. 실제종단지연이나무선RTT와다름.

|자원|값|
|---|---:|
|Flash설정|16MiB|
|앱|1,944,624바이트|
|앱파티션|4MiB,사용46.36%/여유53.64%|
|모델파티션|6MiB예약,실파일점유미측정|
|내부heap표본최소|252,087바이트|
|부팅이후heap최저|198,172바이트|
|최대연속블록표본최소|147,456바이트|
|PSRAM표본최소|30,942,940바이트|
|부팅이후PSRAM최저|30,795,072바이트|
|callTX스택최소여유|5,628바이트|

앱사용률과전체Flash사용률은다르다. 후속wake관찰heap_min197,884와통화구간값을섞지않는다. P4/C6코어별CPU,C6heap,소비전류,배터리시간,전체무선손실률은미측정. 절전해제로소비전력증가가능성은남음.

## 8. 유지할 설정·파일·배포 상태

|영역|유지할내용|
|---|---|
|마이크|좌슬롯16kHz PCM16,NS OFF,VAD192+160ms,pre-roll300ms|
|STT|gpt-4o-mini-transcribe/ko,복구prompt,기존alias/fuzzy/prompt echo방어|
|로컬호출|WakeNet/shadow OFF|
|TTS|내장안내PCM·버퍼형답변재생|
|영상|전체640/기존가중치/GPU/상세GPU960/0.20초|
|판정|조끼.25/안전모.45/장갑.40,기존보조규칙|
|밝기|현재gamma/색감유지|
|통화|소켓별큐/실행기회/8KB스택/절전해제|
|UWB|수동XY/100ms태그·1번/WS/30cm3회/시간창정지/100ms표시보간|

주요수정영역:

- P4 main: voice.c,local_wake.cc,speaker.c,command_client.c,call_client.c,network.c,camera_source.c,hanmir.h,Kconfig/CMake/assets.
- UWB: firmware/uwb_multi_test/src/tag.cpp,anchor.cpp,include/uwb_telemetry.h,uwb_ws_transport.h,platformio.ini.
- 서버음성: routers/audio.py,services/whisper_service.py,speech_service.py,tts_generator_service.py,assistant_service.py,voice_trace.py. wake_word_service의임시영문수정은철회.
- 통화: websocket/call_manager.py,main.py,frontend/components/HelmetCall.tsx.
- 영상: routers/camera.py,services/yolo_service.py,detail_model.py,detail_merge.py,camera_trace.py,camera_brightness.py,frame_pacing.py,onnx_yolo.py,openvino_yolo.py 및CameraFrame/CameraMonitor/LiveCameraFrame.
- 위치/대피: uwb.py,evacuation.py,location_filter_service.py,uwb_distance_filter.py,anchor_transition_guard.py,evacuation_navigation.py,route_start_service.py,evacuation_service.py,evacuation_guidance_service.py 및SiteMap/SmoothPosition/mobileWorkerMap.
- 기반: config.py,database.py,models/entities.py,schemas/api.py,tests,측정/재생/보고scripts.

실제P4최종앱업로드/해시검증완료. 마지막STT복원은서버만변경. 태그/1번앵커100ms실제적용. 최신웹소스와설치APK/IPA는별개이며이번최신앱재배포는미완료.
저장소HEAD와미커밋파일은별개다. 이번보고서작성은GitHub업로드를뜻하지않는다. API키/비밀번호/토큰은별도보관하며이문서에포함하지않는다.

## 9. 남은 문제와 다음 작업

1. **정상음성보존:** 복구prompt를다시제거하지않고동일조건호출·후속명령·비호출을분리계측. 종단0.5초는별도로컬모델과음향측정필요.
2. **통화RX큐:** 세션별유입간격/큐나이/재생속도/폐기사유를기록해약2.8%폐기원인축소. 큐증량만으로지연을숨기지않음.
3. **10FPS최저구간:** 평균외1초/5초창/최대공백,영상송신·서버대기·GPU시간을대조.10~30분양방향통화및종료후AI복귀반복.
4. **장갑오탐:** 맨손11/16오탐을우선개선. 피부/빨간물체/다른색장갑과순수모델·색상보조분리. 조끼.25도다른옷음성표본확인.
5. **UWB:** 실측XY/높이/기준점/이동경로확보,앵커누락과보류대조. 표시고정은정확도아님.
6. **대피:** 정확한지도·출구·방향확인후통제된모의시연. 경계/깊은내부/끊김/고개회전/출구근처확인. 통화중AI중지정책재검토.
7. **앱/HW:** 최신APK와iOS실기검증,USB소실재발시포트/전원/리셋동시로그,배터리SOC/지속시간·BNO각도실측.

## 10. 다른 컴퓨터에서 이어받기

- 이MD는상세설명이며코드·모델·설정을자동설치하지않는다. 브랜치와미커밋변경까지확보.
- 프로젝트Python venv/Node/OpenVINO/ESP-IDF5.5.5/PlatformIO환경필요. 시스템Python uvicorn은click누락으로실패한적이있으므로프로젝트.venv사용.
- GPU640/960모델은새PC에서변환/경로설정. C:/dev경로는현재PC전용.
- AP/서버IP/장치토큰은안전한별도전달. 실제운영DB를백업하고동명이름다른DB로덮지않음.
- 서버8000/웹5174→P4→태그/앵커수신확인. 오래된DB값을현재값으로오인하지않음.
- 확인음→투투스/배터리→영상/PPE→정지/보행→양방향통화→종료후AI복귀순.
- stage산출물에미적용시험본이있을수있으므로출처/설정/해시확인없이플래시금지.

## 11. 수치 해석과 원본 보존

FPS는동일구간완료수차이/실제초. 수신/전체/상세/화면표시는별개. payload와Wi-Fi전체트래픽구분. 서버큐·장치큐폐기분리. heap현재/표본최소/부팅최저구분. 단위시험은단계간중복이있어합산금지.
HTTP200·I2S쓰기성공·STT성공·사용자청취는각기다른확인이다. 원본과필터파일(-hp100),오프라인재생과라이브시험구분.
이파일에는31개상세MD를아래부록으로모두담았다. 대용량JSONL/WAV/이미지/DB/Flash바이트전체는별도파일이며경로를보존했다. 다른PC에서는필요한원본도별도이관한다.

핵심근거:

- C:/dev/hanmir-runtime/call-latency-3min/{metrics,uart,uwb}.jsonl,summary.json
- call-explicit-3min/,call-fair-3min/,call-batch20-3min/ — 비교/실패
- wake-five-attempts/restored-prompt-original-probe.json 및원본WAV
- backend/logs/voice-pipeline.jsonl — 실제04:13호출3건/배터리1건
- vest025-live-first20.json,vest025-meta-measurement*,detail3to5-final-summary.json
- uwb-walk-smooth-20261017/,uwb-ws-optimized/
- backend/logs/evacuation-navigation.jsonl



### 자동 대피 시작의 최신 코드 조건

현재 `evacuation_service.py`는 현장별 `EvacuationNavigationPolicy`가 활성화되어 있고, 저장된 지도 서명과 현재 지도 서명이 일치할 때 화재 사건에 `navigation_enabled=True`, `navigation_auto=True`를 설정한다. 따라서 이미 확인한 지도에서는 자동 안내 시작이 연결되어 있다. 지도가 바뀌었거나 정책이 없으면 무조건 자동 실행하지 않는다. 부록의 초기 ‘매 사건 수동 시작’ 설명은 이 후속 변경 이전 기록이다. 경로 유효성 및 위치·방향 최신성 검사는 별도로 유지한다.

### 최종 결론을 팀원에게 전달할 때

카메라와 보호구 분석을 분리하고 GPU를 활용해 전체 분석 평균 11FPS, 상세 평균 3~4FPS까지 개선했다. UWB는 100ms 측량과 지속 연결·이동 필터·보간을 적용했고, 통화는 큐 구조와 Wi-Fi 절전을 조정해 약 3분간 재연결 없이 유지했다. 마지막 음성 인식 설정도 복구해 실제 호출과 배터리 응답을 확인했다.

다만 순간 FPS 하락, 스피커 큐 폐기, 맨손 장갑 오탐, UWB 수신 공백은 남아 있다. 로컬 웨이크워드 0.5초와 실제 모의 대피 완료, 최신 Android/iOS 설치 검증은 다음 단계다.

## 작성 시점 저장소

- 작성: 2026-10-17 04:21:18 KST
- 브랜치: `integration/hanmir-final-prd-20261016`
- HEAD: `e5cf548`
- 미커밋 변경 및 미추적 파일 존재. HEAD에 모든 개선이 담겼다는 뜻이 아님.


## 문서 작성 시점 파일 변경 목록

아래는 작업 폴더의 실제 Git 상태다. M은 추적 파일 수정, ??는 미추적 파일이다. 이 목록 전체가 이번 한 단계에서 새로 수정됐다는 뜻은 아니며, 인수인계 시 빠뜨릴 수 있는 로컬 변경을 확인하기 위한 스냅샷이다. 민감 설정·DB·원본 자료를 무조건 git add하라는 의미가 아니다.

```text
 M .gitignore
 M backend/app/config.py
 M backend/app/database.py
 M backend/app/main.py
 M backend/app/models/entities.py
 M backend/app/routers/audio.py
 M backend/app/routers/camera.py
 M backend/app/routers/dashboard.py
 M backend/app/routers/evacuation.py
 M backend/app/routers/uwb.py
 M backend/app/schemas/api.py
 M backend/app/services/assistant_service.py
 M backend/app/services/audio_service.py
 M backend/app/services/camera_service.py
 M backend/app/services/evacuation_guidance_service.py
 M backend/app/services/evacuation_service.py
 M backend/app/services/location_filter_service.py
 M backend/app/services/speech_service.py
 M backend/app/services/tts_generator_service.py
 M backend/app/services/uwb_distance_filter.py
 M backend/app/services/uwb_log_service.py
 M backend/app/services/whisper_service.py
 M backend/app/services/yolo_service.py
 M backend/app/websocket/call_manager.py
 M backend/requirements.txt
 M firmware/helmet_p4/CMakeLists.txt
 M firmware/helmet_p4/dependencies.lock
 M firmware/helmet_p4/main/CMakeLists.txt
 M firmware/helmet_p4/main/Kconfig.projbuild
 M firmware/helmet_p4/main/call_client.c
 M firmware/helmet_p4/main/camera_source.c
 M firmware/helmet_p4/main/command_client.c
 M firmware/helmet_p4/main/hanmir.h
 M firmware/helmet_p4/main/idf_component.yml
 M firmware/helmet_p4/main/network.c
 M firmware/helmet_p4/main/speaker.c
 M firmware/helmet_p4/main/voice.c
 M firmware/uwb_multi_test/include/uwb_telemetry.h
 M firmware/uwb_multi_test/platformio.ini
 M firmware/uwb_multi_test/src/anchor.cpp
 M firmware/uwb_multi_test/src/tag.cpp
 M frontend/src/App.tsx
 M frontend/src/components/CameraFrame.tsx
 M frontend/src/components/CameraMonitor.tsx
 M frontend/src/components/HelmetCall.tsx
 M frontend/src/components/LiveCameraFrame.tsx
 M frontend/src/components/SiteMap.tsx
 M frontend/src/components/mobile/WorkerMap.tsx
 M frontend/src/hooks/useSafetyData.ts
 M frontend/src/services/api.ts
 M frontend/src/styles.css
 M frontend/src/types/index.ts
?? backend/app/services/anchor_transition_guard.py
?? backend/app/services/camera_brightness.py
?? backend/app/services/camera_trace.py
?? backend/app/services/detail_merge.py
?? backend/app/services/detail_model.py
?? backend/app/services/evacuation_navigation.py
?? backend/app/services/frame_pacing.py
?? backend/app/services/onnx_yolo.py
?? backend/app/services/openvino_yolo.py
?? backend/app/services/route_start_service.py
?? backend/app/services/voice_trace.py
?? backend/requirements-camera-experiments.txt
?? backend/tests/test_anchor_transition_guard.py
?? backend/tests/test_camera_brightness.py
?? backend/tests/test_detail_merge.py
?? backend/tests/test_detail_model.py
?? backend/tests/test_evacuation_auto_navigation.py
?? backend/tests/test_fire_phrase_bypass.py
?? backend/tests/test_frame_pacing.py
?? backend/tests/test_location_timed_stop.py
?? backend/tests/test_unknown_voice_routing.py
?? backend/tests/test_uwb_stream_transport.py
?? backend/tests/test_voice_silence_guard.py
?? backend/tests/test_wake_ack_audio.py
?? docs/CALL_3MIN_LOAD_TEST_2026-10-17.md
?? docs/CALL_DROP_CAUSES_2026-10-17.md
?? docs/CALL_DUPLEX_VALIDATION_2026-10-17.md
?? docs/CALL_SERVER_QUEUE_TEST_2026-10-17.md
?? docs/CALL_STABILITY_2026-10-17.md
?? docs/CALL_STACK_AND_WATCHDOG_2026-10-17.md
?? docs/CAMERA_AUDIO_COALESCE_2026-10-17.md
?? docs/EVACUATION_LIVE_GUIDANCE_2026-10-17.md
?? docs/FINAL_SYSTEM_BOTTLENECK_REVIEW_2026-10-17.md
?? docs/FUNCTION_TEST_RESULTS_2026-10-16.md
?? docs/HANMIR_2.0_FULL_WORK_REPORT_2026-10-16_17.md
?? docs/HANMIR_INTEGRATED_DIAGNOSTICS_2026-10-10_EVIDENCE.zip
?? docs/HARDWARE_RECONNECT_2026-10-16.md
?? docs/PERFORMANCE_MEASUREMENT_PROTOCOL_2026-10-16.md
?? docs/TUTUS_LOCAL_WAKE_MODEL_PLAN_2026-10-16.md
?? docs/TUTUS_PILOT_TRAINING_2026-10-16.md
?? docs/UWB_100MS_TRIAL_2026-10-17.md
?? docs/UWB_HTTP_BOTTLENECK_2026-10-17.md
?? docs/UWB_LAP_REVIEW_2026-10-17.md
?? docs/UWB_MOVEMENT_STUTTER_ANALYSIS_2026-10-17.md
?? docs/UWB_STATIONARY_DIAGNOSIS_2026-10-16.md
?? docs/UWB_TIMED_STOP_AND_INTERPOLATION_2026-10-17.md
?? docs/VEST_RECALL_AND_BOX_REFRESH_2026-10-16.md
?? docs/VOICE_LATENCY_2026-10-16.md
?? docs/VOICE_RESTORE_2026-10-17.md
?? docs/YOLO_10FPS_TRIAL_2026-10-16.md
?? docs/YOLO_BRIGHTNESS_VALIDATION_2026-10-16.md
?? docs/YOLO_DETAIL_3TO5FPS_2026-10-16.md
?? docs/YOLO_DETAIL_TTS_2026-10-16.md
?? docs/YOLO_SPLIT_AND_HELMET_2026-10-16.md
?? docs/YOLO_VOICE_BRIGHTNESS_2026-10-16.md
?? firmware/helmet_p4/main/assets/
?? firmware/helmet_p4/main/local_wake.cc
?? firmware/helmet_p4/main/local_wake.h
?? firmware/uwb_multi_test/include/uwb_ws_transport.h
?? firmware/wake_model_lab/
?? frontend/src/components/SmoothPosition.tsx
?? safety.db
?? scripts/capture_camera_fixture.py
?? scripts/capture_p4_wake_trace.py
?? scripts/capture_ppe_live_evidence.py
?? scripts/collect_wake_samples.py
?? scripts/collect_wake_system_metrics.py
?? scripts/compare_bright135_fixture.py
?? scripts/compare_detail_hybrid.py
?? scripts/compare_fullhand_fixture.py
?? scripts/compare_gamma_fixture.py
?? scripts/compare_onnx_camera.py
?? scripts/compare_openvino_camera.py
?? scripts/compare_preview_color.py
?? scripts/compare_split_fixture.py
?? scripts/compare_tight_helmet_fixture.py
?? scripts/enable_camera_gpu.py
?? scripts/evaluate_wake_continuous.py
?? scripts/evaluate_wake_pilot.py
?? scripts/export_detail_gpu960.py
?? scripts/inspect_wake_model.py
?? scripts/merge_wake_sessions.py
?? scripts/prepare_wake_training.py
?? scripts/probe_glove_roi.py
?? scripts/probe_helmet_image.py
?? scripts/probe_raw_helmet.py
?? scripts/probe_wake_templates.py
?? scripts/report_camera_network.py
?? scripts/report_ppe_evidence.py
?? scripts/report_split_camera.py
?? scripts/report_uwb_stationary.py
?? scripts/report_yolo10_trial.py
?? scripts/review_wake_samples.py
?? scripts/run_wake_board_benchmark.py
?? scripts/set_yolo10_trial.py
?? scripts/summarize_p4_wake_trace.py
?? scripts/sweep_helmet_views.py
?? scripts/train_wake_pilot.ps1
```

## 상세 부록 인덱스

1. `GITHUB_BRANCH_SYNC_2026-10-16.md`
2. `FINAL_PRD_IMPLEMENTATION_TRACKER_2026-10-16.md`
3. `HARDWARE_RECONNECT_2026-10-16.md`
4. `FUNCTION_TEST_RESULTS_2026-10-16.md`
5. `VOICE_LATENCY_2026-10-16.md`
6. `TUTUS_LOCAL_WAKE_MODEL_PLAN_2026-10-16.md`
7. `TUTUS_PILOT_TRAINING_2026-10-16.md`
8. `YOLO_10FPS_TRIAL_2026-10-16.md`
9. `YOLO_SPLIT_AND_HELMET_2026-10-16.md`
10. `YOLO_BRIGHTNESS_VALIDATION_2026-10-16.md`
11. `YOLO_VOICE_BRIGHTNESS_2026-10-16.md`
12. `YOLO_DETAIL_TTS_2026-10-16.md`
13. `YOLO_DETAIL_3TO5FPS_2026-10-16.md`
14. `VEST_RECALL_AND_BOX_REFRESH_2026-10-16.md`
15. `UWB_STATIONARY_DIAGNOSIS_2026-10-16.md`
16. `UWB_100MS_TRIAL_2026-10-17.md`
17. `UWB_HTTP_BOTTLENECK_2026-10-17.md`
18. `UWB_MOVEMENT_STUTTER_ANALYSIS_2026-10-17.md`
19. `UWB_LAP_REVIEW_2026-10-17.md`
20. `UWB_TIMED_STOP_AND_INTERPOLATION_2026-10-17.md`
21. `EVACUATION_LIVE_GUIDANCE_2026-10-17.md`
22. `CALL_STABILITY_2026-10-17.md`
23. `CALL_3MIN_LOAD_TEST_2026-10-17.md`
24. `CALL_STACK_AND_WATCHDOG_2026-10-17.md`
25. `CALL_SERVER_QUEUE_TEST_2026-10-17.md`
26. `CAMERA_AUDIO_COALESCE_2026-10-17.md`
27. `CALL_DUPLEX_VALIDATION_2026-10-17.md`
28. `CALL_DROP_CAUSES_2026-10-17.md`
29. `FINAL_SYSTEM_BOTTLENECK_REVIEW_2026-10-17.md`
30. `VOICE_RESTORE_2026-10-17.md`
31. `PERFORMANCE_MEASUREMENT_PROTOCOL_2026-10-16.md`


---

## 부록 1. GITHUB_BRANCH_SYNC_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/GITHUB_BRANCH_SYNC_2026-10-16.md

# GitHub 브랜치 확인 및 P4·UWB 통합 업데이트 — 2026-10-16

## 1. 범위와 현재 적용 상태

사용자 요청에 따라 GitHub의 모든 원격 브랜치 참조를 확인하고 최신 UWB 안정화 변경을 기존 P4/웹/앱 통합판에 이식했다.

- 작업 브랜치: `integration/p4-mobile-live-heading-20261010`.
- 기존 기준: `722c9fd`.
- 신규 변경: `codex/uwb-stabilization-handoff-20261015`, `5bb4c67`.
- main은 `389317e`로 변경되지 않았다. 다른 앱/웹 브랜치는 10월 10일 통합 기록과 동일했다.
- 기존 Git fetch 설정은 특정 브랜치 하나만 추적해 원격 참조가 오래된 상태였다. 전체 heads를 명시적으로 가져왔고 이후 전체 브랜치를 추적하도록 로컬 설정을 정리했다.
- **이번 작업은 소스 통합이다. 실제 P4·UWB 태그·앵커 업로드, 운영 서버 재시작, 새 APK/IPA 배포는 수행하지 않았다.**
- P4 스피커와 실제 장치 버전은 10월 10일의 마지막 확인 기록만 있다. 현재 하드웨어 상태를 새로 검증한 것이 아니다.

## 2. 단순 브랜치 교체를 하지 않은 이유

신규 UWB 브랜치는 기존 main에서 출발한 선별 공유본이다. P4 전체, 다중 현장 인증, 앱 디자인, AV/방향/통화 변경을 포함하지 않는다. 현재 통합 브랜치와 병합 기준 조상이 없어 전체 파일 교체 대신 `5bb4c67` 변경분을 이식하고 충돌을 조정했다.

이 과정에서 보존한 항목:

- 다중 현장 DB migration·앵커/위치 조회 범위.
- 작업자 근무 요약, 최신 상세 화면 디자인과 연결 상태 표시.
- P4 영상 인증·실시간 방향·카메라·통화 코드.
- 기존 수동 지도와 앵커 코드. 자동 측량을 다시 도입하지 않았다.
- 기존 `.env`, DB, 키 및 로컬 Wi-Fi 설정.

## 3. 반영한 기능

### 태그 및 전송

- 부팅 세션·64bit cycle·measurement ID·장치 uptime을 포함한 측정 스냅샷.
- 각 Response 수신 직후 DW3000 원시 진단 복사. ranging 경로와 USB/HTTP 송신 분리.
- USB/Wi-Fi에서 같은 측정 ID/스냅샷 사용.
- USB 큐8, HTTP 큐4. 포화 시 오래된 대기 회차 폐기.
- HTTP 최신 측정 우선, 원 측정 후 1.5초 지난 새 요청/재시도 금지, 연결300ms/읽기500ms, 최대2회/간격200ms 정책.
- 태그 시리얼460800baud, 앵커115200baud. USB 로그 전용 환경 `tag-usb-log` 추가.
- 기존 clock offset 중복 부호 확장 제거를 유지했다.

위 설정이 실제 장애 중 측정 주기 유지까지 검증됐다는 의미는 아니다. 이미 진행 중인 HTTP 호출의 전체 시간 상한도 보장하지 않는다.

### 서버 처리

프레임 검증/중복 제거 → 신호 품질 관찰 → 거리 보정/중앙값 → solver 유효성 → 속도 관찰 → 기존 좌표 평활화/정지 처리 → 현장 지도 제한 → 위치/위험구역 갱신.

- 같은 ID의 USB/Wi-Fi 중복, 역순, 과거 부팅 및 잘못된 시각을 구분한다.
- 거리 처리를 서버 공통 경로로 모아 브리지 이중 보정/필터 및 과거 앵커 hold를 제거했다.
- Ipatov RX/첫 경로 전력·전력 차이·경로 인덱스 차이·진단 무효 이유를 기록한다.
- 유효 앵커 수, 수렴, 기하 조건, 잔차를 검사한다.
- 위치 후보와 표시 좌표, 위치 검사 수락과 실제 적용 여부를 구분한다.
- worker_states에 last_valid_location_at / last_valid_location_json / position_status_json 추가 migration을 반영했다.
- 위치 계산 실패 시 이전 위치와 나이/사유를 제공한다.
- 마지막 유효 위치·좌표·검사 상태·사용 앵커 수를 상세 화면에 추가했다.
- 로그 회전·보존, 수집/분석/비교/백업 도구와 기존 브랜치 테스트 파일을 함께 가져왔다.

## 4. 유지한 기본 정책

```dotenv
UWB_CALIBRATION_ENABLED=false
UWB_MEDIAN_ENABLED=true
UWB_MEDIAN_WINDOW=5
UWB_QUALITY_MODE=observe
UWB_SPEED_MODE=observe
```

- 관찰 모드에서는 품질/속도 기준을 근거로 강제 제외하지 않는다.
- 임계값은 현장 안전 한계로 검증된 값이 아니다. 임의 enforce 전환은 하지 않았다.
- 서버 프로세스는 1개를 사용한다. 거리 SQLite 직렬화만으로 전체 처리의 다중 프로세스 일관성이 보장되지는 않는다.
- 로컬 `.env`에 위 정책 덮어쓰기 항목이 없어 신규 코드의 기본값이 사용될 예정이다. 이번 작업에서 실제 운영 `.env`는 수정하지 않았다.

## 5. 통합 충돌 및 호환 처리

| 파일/영역 | 처리 |
|---|---|
| .gitattributes | 기존 LF/PowerShell 규칙과 측정 자료 원문 바이트 보존 규칙 결합 |
| .env.example / config.py | 기존 영상·통화·인증 설정에 UWB 설정 추가 |
| database.py | 기존 다중 현장 migration + 신규 위치 상태 열 migration 유지 |
| serializers.py | 근무 요약/현장/방향 정보에 위치 상태 추가 |
| WorkerDetail.tsx | 최신 디자인·오프라인 상태에 신규 위치 진단 표시 추가 |
| routers/uwb.py | 신규 처리 경로에 worker.site_id 앵커 범위 유지 |
| 장치/필터 현장 | 등록된 장치·작업자 현장 불일치는409, 필터의 유효 현장은 작업자 등록값 사용. 조직은 기존 장치 등록값 우선 |
| UWB 폴더 | ASCII 경로 `firmware/uwb_multi_test` 복원, 기존 `uwb_multi_test - 복사본`도 신규 태그/헤더로 맞춤 |
| 앵커 | 신규 브랜치에서 변경하지 않은 영역이므로 기존 검증 수동 지도 앵커 소스 보존 |

새 도구와 configure_wifi_tag.py는 ASCII UWB 프로젝트 경로를 사용한다. 기존 로컬 ignored Wi-Fi 설정은 그 경로로 복사해 유지했으며 Git에는 포함하지 않았다. 두 프로젝트 사본을 독립적으로 수정하면 차이가 생길 수 있으므로 이후 신규 수정은 ASCII 경로를 기준으로 진행한다.

## 6. 10월 15일 공유 자료에서 확인한 수치

| 비교 | 이전 | 수정 후 | 해석 |
|---|---:|---:|---|
| 2m 거리 평균 절대오차 | 5.84cm | 4.93cm | 정지 입력의 중앙값 재생 비교 |
| 2m 거리 표준편차 | 5.71cm | 2.59cm | 해당 정지 로그에서 산포 감소 |
| 위치 참고점 평균오차 | 74.73cm | 36.98cm | 기준점은 대략값이며 정밀 실측 아님 |
| 위치 표시 산포 | 5.29cm | 14.02cm | 수정본이 더 흔들렸음 |
| 위치 계산 성공 | 382/382 | 381/382 | 실패 회차는 이전 표시 좌표 유지 |

거리386표본은 같은 원시 입력의 필터 전/후이며 펌웨어를 바꿔 각각 측정한 A/B가 아니다. 위치382회차의 P4는 `722c9fd` 수치 모듈 재생, 수정본은 실제 서버 출력이다. 입력 정밀도·보정 계약·필터 등이 달라 중앙값 한 항목의 효과로 볼 수 없다.

따라서 **위치 정확도와 표시 안정성이 모두 좋아졌다고 결론 내리지 않는다.** 원본 제공자의 숫자를 정리한 것이며 오늘 재측정한 값도 아니다. 측정 자료의2×1m는 실험 조건이고 실제 지도/DB에 적용하지 않았다.

## 7. 이번 작업의 확인 범위

- 충돌 마커 및 미해결 Git 항목 정리.
- 기존 P4 펌웨어 영역에 변경이 들어가지 않은 것을 변경 목록으로 확인.
- Python 앱/분석 스크립트 구문 컴파일 통과.
- 프런트 TypeScript/Vite production build 통과.
- **pytest·네이티브 단위시험·실물 시험은 이번에 실행하지 않았다.**
- 원본 브랜치의157 passed 기록은 원본 작성자의 선별 브랜치 결과이며, 이번 통합판의 테스트 성공으로 대체하지 않는다.
- P4/태그 펌웨어 신규 빌드·업로드 및 앱 설치 검증은 하지 않았다.

## 8. 로컬 백업과 적용 절차

기존 기본 DB는 읽기 전용 연결의 SQLite backup으로 아래에 보관했다.

`C:/dev/hanmir-runtime/safety-before-uwb-sync-20261016.db`

이번 코드 작업에서는 DB migration을 실행하거나 현장 지도값을 변경하지 않았다. 운영 적용 때 실제 DATABASE_URL/DB를 확인하고 백업 후 단일 worker로 서버를 재시작한다. 신규3개 열은 init_database에서 추가된다.

다음 순서:

1. 통합 코드와 실제 등록 장치/지도/서버 주소 확인.
2. 서버 재시작 후 구형 태그 입력 호환·새 위치 상태 응답 확인.
3. 신규 태그 기능이 필요할 때 실제 보드/포트/비밀번호를 확인해 별도 빌드·업로드. P4 AV와 앵커는 이 UWB 변경만으로 자동 업로드하지 않는다.
4. 같은 정답 위치에서 stationary bias/scatter, 같은 이동 경로에서 지연·누락·수락 여부 비교.
5. Android/iOS 자산 및 신규 앱 배포는 필요 시 별도로 진행. 저장소 build13 APK가 이번 웹 변경을 이미 포함한다고 하지 않는다.
6. 스피커는10월10일 GPIO20/21 교차 관측이 마지막 근거다. 현재 상태를 확인한 뒤 신호선/앰프전원/분리 비교를 이어간다.

## 9. 관련 문서

- [UWB 원본 인수인계](UWB_HANDOFF_2026-10-15.md)
- [DW3000 측정 식별자·신호 진단](UWB_MEASUREMENT_LOGGING.md)
- [선택한 네 가지 비교 자료](measurements/2026-10-15-comparison/README.md)
- [10월9~10일 전체 인수인계](HANMIR_2.0_FULL_HANDOFF_2026-10-09_10.md)
- [스피커 독립 진단](P4_SPEAKER_SIGNAL_DIAGNOSIS_2026-10-10.md)

이 문서는10월16일 소스 통합 기록이며 과거 기능 검증을 오늘 다시 확인했다는 의미가 아니다.


---

## 부록 2. FINAL_PRD_IMPLEMENTATION_TRACKER_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/FINAL_PRD_IMPLEMENTATION_TRACKER_2026-10-16.md

# HANMIR 최종 PRD 적용 및 실물 확인 순서

기준: 사용자 제공 `HANMIR_2.0_CODEX_FINAL_PRD_2026-10-16.md`.
시작점: bc0f779 (P4/모바일 + 10/15 UWB 통합).
작업 브랜치: `integration/hanmir-final-prd-20261016`.

## 1. 이번 단계의 범위

최종 PRD 전체 구현 완료가 아니다. 첫 단계는 운영 기준과 최신성 메타데이터 도입이다.
원격 전체 브랜치를 다시 fetch했으며, 직전 통합 이후 새 원격 변경은 없었다.
브랜치별 비교는 `GITHUB_BRANCH_SYNC_2026-10-16.md`를 함께 참고한다.

- 공통 enum: DataHealth, DetectionState, Priority, IncidentState.
- 버전 있는 최신성 config: `backend/app/services/operating_policy.py`.
- 관리자 인증 API: `GET /api/operating-policy`.
- 기존 장치/작업자 JSON에 `data_health` 추가. 기존 필드 유지.
- heartbeat, camera 수신시각, heading, 마지막 채택 UWB 위치의 나이를 판정.
- 배터리 측정 성공 시각과 YOLO 추론 완료 시각은 아직 연결하지 않아 UNAVAILABLE.
- 실제 측정 시각을 모르는 UWB는 server_acceptance 기준임을 명시.
- verified=false는 이번 정책의 실물 미검증 표시이며, 최신 데이터가 없다는 뜻과 구분한다.
- 사건 enum은 공통 계약이다. 기존 Event 저장/ACK/해결 로직 전체 전환은 아직 하지 않았다.
- 기존 위험 로직은 아직 이 data_health를 강제 조건으로 사용하지 않는다.

## 2. 설정과 경계

`backend/.env`에서 예를 들어 `OPS_HEADING__VALID_SECONDS=2`,
`OPS_HEADING__UNAVAILABLE_SECONDS=5`로 변경한다. 서버 재시작 후 적용된다.
정책 버전은 `OPS_VERSION`으로 기록한다. 실제 .env는 Git에 넣지 않는다.

| 데이터 | VALID 마지막 경계 | STALE 마지막 경계 |
|---|---:|---:|
| heading / UWB | 2초 | 5초 |
| camera / YOLO | 3초 | 10초 |
| battery / heartbeat | 15초 | 30초 |

두 번째 경계 초과는 UNAVAILABLE. 시각 없음·잘못된 시각·미래 시각도 UNAVAILABLE.
DEGRADED는 신선하지만 품질 저하가 확인된 경우를 위한 별도 상태이다.
현재 기존 online 판정 timeout과 새 정책은 아직 통합 전이다. 새 필드만 보고 전체 이관으로 해석하지 않는다.

## 3. 코드에서 확인한 주요 차이

| 영역 | 현재 | 다음 수정 |
|---|---|---|
| UWB | 거리 median 5, 좌표 smoothing, quality/speed observe, 마지막 유효 위치 | PRD jump pending 확인, RMSE 품질, stale 위험확정 금지, 경계 margin |
| UWB 지도 | 수동 XY | 유지. 자동 측량은 P2로 보류 |
| heading | live WebSocket + 보정 | circular EMA와 freshness 일관성 |
| 화재 허가 | 역할/구역/시간대 조건 | 실제 permit/시간/감시자/ROI 검증 |
| PPE | 기존 검출/위험 필드 | 판정 가능한 ROI와 UNKNOWN, 분석 프레임 연속성 |
| 낙상 | 영상 쓰러짐 관련 위험 | 착용자 IMU 낙상과 전방 쓰러짐 별도 사건 |
| 음성 | 서버 STT 후 wake/긴급어/intent | 부정·조건문 오작동, 실패/재질문 상태, 실제값 freshness |
| 사건 | Event open/acknowledged/resolved | 감지 상태와 사건 상태 분리, 우선순위/증거/재알림 |
| 스피커 | 마지막 실물 시험 무음 | 출력부 원인 확인이 필요; 소프트웨어 재생 성공은 청취 성공 아님 |

거리 median_window 5와 PRD의 좌표 median_window 3은 서로 다른 필터이므로 일괄 3으로 바꾸지 않는다.
낙상 3초 목표는 후보/센서 확정 시간과 10초 무응답 승격 시간을 나눠 측정해야 한다.
음성 끝 무음 2초는 단순 조회 3초 목표의 대부분을 소비하므로 초기값 적용 전 후 지연을 각각 측정한다.
전방 카메라 PPE를 안전모 착용자 자신의 PPE로 단정하지 않는다.

## 4. 구현 순서와 완료 기준

1. **공통 기반(이번 단계)**: 최신성/config/상태 계약, 회귀시험. API 필드와 미검증 범위 확인.
2. **위험 사건 기반**: reason_code/evidence, 사이트 분리, 명시적 ACK/RESOLVE, P0/P1 자동 종료 방지. 관리자 재알림 및 실제 통화 연결 결과 구분.
3. **UWB/방향**: 이상점 재확인, 품질/최신성 gate, margin 진입·이탈, 원형 방향 smoothing. 기록 재생으로 기존 위치 기능 비교.
4. **화재/PPE**: 분석 프레임 기준 count, UNKNOWN, permit 조건과 예외 취소. 증거 저장 및 이벤트 연결.
5. **Voice/AI**: 긴급 규칙 우선 저장, 명령 경계/부정문, 단순 조회 tool, stale 응답, 재질문 1회. TTS 실패가 사건 저장을 취소하지 않도록 확인.
6. **P4/낙상**: 실제 accel/gyro sampling과 단위 확인, 후보/확정/응답대기, 데이터 누락 시 판정 금지. 착용자와 전방 쓰러짐 분리.
7. **관리자 웹/앱**: 상태·증거·ACK 표시, 새 APK 버전으로 패키징. 기존 build13이 최신 소스를 포함한다고 가정하지 않는다. iOS 실기 별도 확인.
8. **실물 단위→연동→전체부하**: 아래 순서로 시행하고, 결과에 따라 한 설정씩 변경.

각 단계마다 변경 파일/이유/테스트/실물 여부/남은 문제를 이 문서에 추가한다.
현재 source 정책은 전체 최종 펌웨어가 아니다. 이전 진단 build 디렉터리 산출물을 그대로 flash하지 않는다.

## 5. 안전모 전원을 켠 후 함께 진행할 순서

| 순서 | 사용자 동작 | 확인할 데이터 | 다음 단계 조건 |
|---|---|---|---|
| 1 | P4·태그 USB 연결, 같은 Wi-Fi, 안전모/앵커 켜기 | 포트, firmware_version, IP, heartbeat, 재부팅 원인 | 정상 앱/올바른 서버 확인 |
| 2 | 60초 정지 | 카메라 수신 FPS·frame age, UWB anchor count/RMSE, heading age, battery 측정 성공 | 값이 실제 갱신되는지 확인 |
| 3 | 짧은 확인음 청취 | PCM 송신/수신/쓰기와 실제 청취 결과 | 스피커 청취가 안 되면 음성 안내 완료로 처리하지 않음 |
| 4 | 좌우 90도 회전, 알려진 위치 이동 | 지도 방향/지연, 위치 raw/filtered/P95 | 보정 및 수동 XY 일치 |
| 5 | 사람·보호구가 카메라에 보이게 하기 | 원본/분석 FPS, 판정 가능한 ROI, 검출/UNKNOWN | 카메라·YOLO 개별 확인 |
| 6 | 배터리·위치 질문을 각각 발화 | STT 원문/intent/tool/최신성/응답시간/청취 | 입력 횟수와 처리 건수 비교 |
| 7 | 시험용 SOS·화재 신고 | 사건 저장→관리자 표시→TTS→통화→ACK→종료 | 실제 외부 신고와 구분한 통제 시험 |
| 8 | 통제된 센서 자세 변화 | accel/gyro/후보/확정/취소 | 사람을 실제로 넘어뜨리지 않고 매트/더미로 검증 |
| 9 | 5~10분 동시 사용 | camera freeze/drop, 음성 지연, UWB age, WS 재연결, heap/PSRAM/stack | 단위 성공과 전체부하 성공을 따로 기록 |

사용자가 먼저 준비할 것은 데이터 USB, 동일 네트워크, 실제 밝은 카메라 장면, 앵커 고정이다.
무음 문제가 남으면 현재 납땜을 임의 변경하기 전에 앰프 전원/신호 측정 도구로 확인해야 한다.

## 6. 검증 기록

- 공통 최신성 단위시험: 13 passed.
- frontend production build: 성공.
- 전체 backend 최초 실행: 137 passed / 3 failed / 2 skipped, maxfail=3에서 중단.
- 최초 실패는 가져온 UWB 시험이 관리자 인증이 필요한 GET에 인증 컨텍스트를 주지 않은 데서 발생했다. 두 시험 fixture에서 사이트 의존성을 시험 범위에서만 설정했다. 운영 API 인증은 유지했다.
- 최종 전체 backend 회귀시험: **205 passed, 2 skipped, 18 warnings (32.56초)**. 경고는 남아 있으며 무경고 완료로 표현하지 않는다.
- P4 펌웨어: 이번 단계 변경/빌드/업로드 없음. 실제 전원 시험 없음.
- 서버 실행/DB 마이그레이션/앱 설치: 이번 단계 미실행.


---

## 부록 3. HARDWARE_RECONNECT_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/HARDWARE_RECONNECT_2026-10-16.md

# 2026-10-16 실물 재연결 점검

- 서버 8000, 웹 5174 정상. PC Wi-Fi WISET_5G, IPv4 192.168.0.40.
- 사용자 전원 투입 후 COM25 P4와 COM6 UWB 태그를 각각 확인.
- P4 UART: Wi-Fi AIHSLab2 접속 실패 반복(reason=201), 서버 192.168.0.223:8000 Host unreachable. 현재 PC 환경과 불일치.
- P4 마이크 PCM peak와 BNO085 yaw/pitch/roll 출력 확인. 이 사실은 STT/통화/음성 출력 성공을 의미하지 않는다.
- UWB 태그 USB: 앵커 1~4 거리 관측 모두 valid. 표본 약 2.42/4.02/2.82/3.77m. 정확도나 지도 좌표 정상은 아직 검증하지 않음.
- 서버 카메라 수신/분석 0프레임. UWB와 P4 서버 last_seen은 10/10 값. 화면의 기존 값은 현재 측정값 아님.
- P4 16MiB 전체 플래시 로컬 백업 완료: C:/dev/hanmir-runtime/p4-before-network-fix-20261016.bin (비밀정보 포함 가능, 업로드 금지).
- UWB 백업 중 COM6 연결 끊김, 미완료. 부분 파일을 복원용 정상 백업으로 사용하지 않는다.
- 이후 COM25/COM6 모두 사라짐. Windows PresentOnly에도 Bluetooth COM4/5만 확인됨.
- P4 stage 기존 main/sdkconfig 별도 로컬 압축 백업 후 현재 저장소 main 동기화.
- 로컬 sdkconfig: WISET_2.4G, 서버192.168.0.40, 서버 로컬 카메라/통화 토큰 동기화. 비밀번호/토큰 출력·Git 저장 안 함.
- P4 빌드 성공: 0x1ce540 bytes, 앱 파티션 0x400000, 55% 여유. 업로드 미실행.
- UWB 소스/네트워크 설정은 ASCII stage에 준비. 사용자명 한글 경로로 컴파일 실패하여 PLATFORMIO_CORE_DIR=C:/pio-core로 재빌드 진행.
- 다음: USB 인식 복구 → UWB 백업 재시도 → 각 펌웨어 업로드 → 실제 heartbeat/camera/UWB 재수신 → 스피커/음성/방향 기능 시험.
- 앵커 펌웨어/현장 XY/위험 임계값은 이번 연결 작업에서 변경하지 않음.


---

## 부록 4. FUNCTION_TEST_RESULTS_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/FUNCTION_TEST_RESULTS_2026-10-16.md

# 2026-10-16 기능 시험 기록

## 원칙

사용자 발화 횟수, 실제 청취 결과, 장치 로그, 서버 기록을 구분한다.
HTTP 200은 명령 인식 성공을 뜻하지 않는다. PCM peak는 발화 내용의 정확성 증거가 아니다.
직접 텍스트 API 시험은 마이크/STT 인식 성공률에 포함하지 않는다.
기존 DB 값과 현재 수신을 구분하며 UWB 오프라인 위치를 현재 위치로 쓰지 않는다.

## 실제 결과

1. P4 네트워크를 WISET_2.4G / 192.168.0.40으로 맞춰 업로드, 쓰기 검증 성공.
2. 스피커 1400Hz 1초 톤: 사용자 청취 성공. 기존 무음 문제가 영구 해결됐다는 의미는 아님.
3. 단독 P4 USB 관찰 50초: USB/heartbeat/방향 유지. 영상 전송 실패 1회 후 회복.
4. 45.02초 기능 시험: 영상 수신 512장(11.37fps), 분석 154장(3.42fps). 표본 16개에서 person_seen 0. 사람 노출이 충분했는지 확인 없이 검출 실패율로 계산하지 않는다.
5. 방향 표본 약 226.27~245.07도. 값 갱신은 확인했으나 실제 회전각 대비 오차 미측정.
6. 배터리 약 45.28%. 계측기 대비 정확도는 미검증.
7. 사용자: 투투스 2회 호출, 응답 0회. 이 작은 시험에서 응답 성공 0/2이며 일반 성능값으로 외삽하지 않는다.
8. 같은 구간 PCM peak 15060~32575, 음성 업로드 HTTP200 5건, 크기 159148/31148/60844/86444/96684바이트. 발화 2회와 clip 5건은 일대일 대응하지 않는다.
9. 해당 clip은 기존 코드에서 삭제됐고 STT 원문이 보존되지 않아 실패 단계 소급 확정 불가.
10. 상세 추적 적용 후 사용자 1회 추가 발화, 응답 없음. 서버 새 upload 기록 없음; 직후 15초 PCM peak 1만 관측. 발화 순간과 사후 표본을 동일시하지 않는다. 입력/녹음 단계 우선 확인 필요.
11. 직접 텍스트 배터리 조회: HTTP200, intent=battery_query, confidence=.98, 응답 '현재 배터리는 45퍼센트입니다'. 전체 약5937ms, TTS5878.2ms. audio_url=null, play_tone으로 fallback, 전달 연결1.
12. TTS 실패 원인: 외부 합성 WebSocket HTTP403. 실제 문장 음성 생성 실패. 마이크 호출 실패와 별도 문제.
13. UWB 태그 USB에서는 앵커4개 거리 수신 확인했지만 서버 연결 미완료. 현재 단독 P4 시험 중 UWB USB 제외.

## 추가한 추적

- backend/logs/voice-pipeline.jsonl: audio_received → stt → wake_decision → execution_gate/response.
- 동일 trace_id로 wav 길이/샘플레이트/peak/RMS/clipping, STT 원문/오류 종류/status/시간, 호출어 판정, 명령/전달 결과 연결.
- 5MiB × 최대4파일, 7일 보관. VOICE_TRACE_ENABLED 등 config 조정 가능.
- API 키/원본 오류 URL은 기록하지 않음. STT 원문은 로컬 진단 데이터이며 Git에 올리지 않음.
- 원본 WAV 보존은 추가하지 않음. 상세 메트릭은 앞으로 수신되는 clip부터 적용.
- 음성 관련 회귀시험:22 passed,1 warning. TTS 오류 로그의 URL 노출을 막도록 오류 종류/status만 기록하도록 변경.

## 로컬 증거 파일

- C:/dev/hanmir-runtime/p4-only-usb-observation-20261016.json
- C:/dev/hanmir-runtime/functional-test-1-20261016.json
- C:/dev/hanmir-runtime/direct-battery-test-20261016.json
- backend/logs/voice-pipeline.jsonl (새 수신이 있을 때 생성)

## 다음 순서

1. 마이크 입력: 정지 상태 발화와 보드/케이블 움직임을 분리하여 raw PCM 기록. L/R 선택·전원·연결·I2S 설정을 증거로 비교.
2. TTS403 원인 확인 및 생성 복구. 실제 문장 청취까지 성공해야 완료.
3. STT 원문과 wake 판정을 함께 수집해 동일 문장 반복, 성공/미탐/지연 집계.
4. 카메라 앞 사람/보호구 조건을 명확히 하고 원본 프레임과 분석 결과 비교.
5. UWB 서버 연결 후 위치·방향·영상·음성 동시부하 검증.

현재 웹의 비상 상태에는 과거 시험 사건이 남아 있다. 현재 새 위험과 혼동하지 않으며 임의로 전체 사건을 종료하지 않는다.

## 19시대 마이크·TTS 추가 진단
- 사용자: 배선 문제 없음을 재확인. 배선 변경 없이 SW 비교 진행.
- TTS: edge-tts 7.3.1 적용 후 배터리 안내 문장 재생을 사용자가 들었다고 확인.
- 마이크: 좌우 슬롯 진단 후 호출어 3회, 배터리 명령 1회에 응답이 없었다고 사용자 보고. 인식 성공으로 처리하지 않음.
- 별도 STT 대조: 합성 TTS WAV는 배터리 문장으로 전사. 과거 마이크 WAV는 프롬프트 포함 시 프롬프트 반복, 프롬프트 제외 시 빈 문자열. 과거 WAV의 실제 발화 내용은 확인되지 않음.
- 최근 보존 WAV 5개(발화 시점 미확인): 1.804~3.116초, zero fraction 96.35~99.20%, RMS 48.80~182.82. 간헐적 피크만으로 음성 입력 정상이라고 판단할 수 없음.
- 다음 비교: 로컬 sdkconfig에서 외부 WebRTC NS만 끄고 같은 I2S GPIO/선택 슬롯/AFE VAD로 확인. 이 설정은 진단용이며 기본 설정 변경으로 확정하지 않음.
- 원본 WAV는 로컬 보존 최대 12개. 개인정보가 포함될 수 있어 Git 업로드 제외.

## UWB 위치 미수신 추가 점검
- 서버 조회 시 UWB 태그와 앵커 4개 last_seen은 2026-10-10으로 오래된 값. 오늘 위치 수신은 확인되지 않음. P4는 별도로 정상 heartbeat 수신.
- PC USB는 COM25(P4), COM4/5만 표시. 태그 USB 연결 요청.
- 준비된 로컬 태그 설정의 HANMIR_SERVER_URL이 호스트 주소만 포함한 오류 발견. 송신 코드는 해당 URL에 직접 POST하므로 /api/uwb/distances가 필요.
- 로컬 stage와 기본 UWB 프로젝트의 해당 호스트 주소를 완전한 API 경로로 수정하고 tag 빌드 시작. 실제 장치 설치 상태 확인 및 업로드/실시간 수신 검증은 USB 연결 후 수행. 현재 해결 완료 아님.

## UWB 복구 및 호출어 음성 응답 적용
- COM6 태그 연결 후 업로드 전 12초 동안 40개 측량 사이클 수신. 앵커 4개 거리 모두 출력되어 무선 측량 자체가 동작함을 확인.
- 태그의 Wi-Fi/서버 설정을 현재 환경으로 빌드하고 COM6 업로드 성공. 서버 UWB 태그·앵커 4개 온라인 복구.
- 확인 시 위치 X=2.3921m, Y=1.4771m, confidence=0.858, frame_dt=0.300초, 데이터 나이 약 0.050초. 반사파/직접파 약함 관련 품질 경고 존재. 지도 XY 설정 변경 없음. 절대 위치 정확도는 아직 검증하지 않음.
- 사용자: NS 비활성화 비교 펌웨어에서 투투스 후 배터리 질문에 답변을 들었다고 확인.
- 서버에서도 호출어 단독 armed(19:11:27, STT 1083.6ms), 이어 배터리 알려줘 armed_followup(19:11:33, STT 1208.5ms) 확인. 1회 성공이며 인식률 개선 수치로 일반화하지 않음. 간헐적 무음/프롬프트 반복도 남아 추가 검증 필요.
- 호출어 단독 응답 기존 경로는 play_ack로 P4에서 1200Hz 180ms 확인음만 출력. audio.py에서 캐시된 '네, 말씀하세요.' WAV 생성 및 play_audio 전달로 수정. 생성 실패 시 기존 확인음 폴백 유지.
- 안내 WAV 사전 생성 완료. 서버 재시작 적용. 호출어/무음 보호 테스트 16개 통과. 실제 새 호출 문장의 청취 확인 요청 중.
- 원본 오디오 및 측정 로그는 C:/dev/hanmir-runtime 및 backend 로컬에 보존. 민감 설정 파일은 커밋 대상 아님.


---

## 부록 5. VOICE_LATENCY_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/VOICE_LATENCY_2026-10-16.md

# 호출 지연 진단과 0.5초 목표 — 2026-10-16

## 측정 근거
- 실제 설정 CONFIG_HANMIR_ENABLE_WAKENET=n. 현재 호출어 판정은 서버의 STT 문자열 매칭이며 P4 로컬 WakeNet 판정이 아니다.
- 성공 호출 19:11:27: 녹음 길이 2508ms, STT 1083.6ms, 서버 처리 1158.7ms.
- 느린 성공 호출 19:14:43: 녹음 길이 4652ms, STT 3634.9ms, 서버 처리 3761.3ms.
- 녹음 길이는 발화 자체와 프리롤/무음을 포함하므로 응답 지연과 그대로 합산하면 안 된다. 실제 발화 종료 시각은 미측정.
- ESP-SR 헤더의 AFE vad_min_noise_ms 기본값은 1000ms이며 기존 앱은 이를 지정하지 않았다. 앱은 VAD 무음 판정 뒤 추가 500ms를 기다렸다. 실제 런타임 기본값을 확인할 부팅 로그를 추가했다.

## 1차 수정
- AFE 무음 192ms + 앱 추가 무음 160ms로 명시. 프레임 양자화와 VAD 판단 때문에 실제 발화 종료 지연은 별도 측정 필요.
- 기존 300ms 프리롤 유지. 문장 중간 350ms 이상 쉼에서는 분할될 수 있으므로 긴 명령 회귀 시험 필요.
- 네, 말씀하세요 안내 PCM을 펌웨어에 내장. PCM16 mono 16kHz, 46896 bytes, 앞부분 무음 약180ms 제거. 생성 원본은 현재 사용 중인 edge-tts 안내 WAV.
- 서버 play_audio payload의 local_asset=acknowledgement일 때 P4가 내장 PCM 재생. 다른 TTS는 기존 경로 유지. 이전 펌웨어는 서버 audio_url로 재생 가능.
- 외부 NS는 현재 비교 설정대로 OFF 유지. 이 설정의 인식률 통계는 아직 없음.
- 호출어/음성 응답/무음 방어 백엔드 시험 17개 통과. 테스트 DB 분리.

## 0.5초 목표와 남은 작업
기준: 사람이 호출어의 마지막 음절을 끝낸 시점부터 스피커의 첫 유효 음성까지 500ms 이내. 평균만 아니라 p95와 누락률/오호출률도 함께 기록.
현재 API 기반 STT는 실제로 1~3.6초 소요되므로 이번 수정만으로 목표 달성을 주장할 수 없다.
최종 경로: 연속 PCM → 검증된 투투스 로컬 키워드 모델 → P4 내장 안내 즉시 재생 → 제한된 후속 명령 구간을 STT로 전달.
필요: 한국어 투투스 전용 모델 확보/학습, 작업자별 거리·소음별 양성/음성 데이터, 오호출/누락 검증. 현재 저장소에는 해당 모델이 없다. WakeNet 설정만 켜서 다른 호출어 모델을 투투스로 사용하는 것은 불가.
비상 발화의 무호출 경로, TTS 자체 재호출 방지, 통화 중 상태, 후속 명령 타임아웃을 함께 유지해야 한다.
공식 참고: https://docs.espressif.com/projects/esp-sr/en/latest/esp32p4/wake_word_engine/README.html

## 원인 판단의 한계
UWB 업데이트 직후 체감 지연만으로 UWB가 원인이라고 단정하지 않음. 관측된 직접 근거는 길어진 녹음과 STT 지연이다. 네트워크 혼잡·음성 업로드 큐 대기는 추가 로그로 분리해야 함.

## 적용 상태
- 빌드 및 COM25 업로드 성공, 플래시 해시 검증 완료.
- 앱 SHA256: e60580a9f017ea25456ce3f2ca3737ed90c7f98a941b82cd4a5e85fc918095a0
- 음성 큐 대기 시간 및 업로드 왕복 시간 로그 추가.
- UART 측정: C:/dev/hanmir-runtime/voice-latency-live-20261016.log
- 실제 새 호출의 인식/응답 시간은 사용자 발화 시험 대기 중. 0.5초 목표 달성 미확인.

## 19:20~19:21 실제 호출·위치 질의 분석
- 사용자 보고: 호출어 3회 모두 체감 1초 이내, 위치 질의 불명확 및 비상 상태 안내 청취.
- 서버 호출어 판정 3회: STT 932.3/847.4/784.2ms, 서버 전체 1066.8/1032.3/870.2ms. 이는 업로드 수신 이후 측정이며 실제 발화 종료→스피커 지연은 아님.
- 19:20:37 현재 위치 알려줘 → location_query 0.97, X2.6/Y1.4m 응답. STT725.8ms, TTS1768.2ms, 서버2573.0ms. P4 19:20:39.539 play_audio 실행.
- 19:21:04 비슷하네 → unknown인데 LLM 실행(response3045.7ms). 생성 답변: 비상 상태가 확인되어 관제실에 전송했습니다… 실제 새 비상 intent로 분류된 것이 아니며 관제실 전송을 새로 실행한 근거가 아니다. 기존 비상 상태를 참조해 만든 부적절한 답변.
- 19:21:10 현재 위치 알려줘 → location_query 0.97, X2.5/Y1.7m. STT807.2ms, TTS1235.6ms, 서버2188.1ms. 서버19:21:11.730 응답 완료 대비 P4 play_audio 19:21:19.484: 약7.75초 지연. 단일 command_task가 앞선 음성을 동기 재생하여 다음 명령을 대기시킨 경로와 일치.
- 19:21:42 일단 투투스 5초까지 한 2초 정도 올리고 → unknown인데 LLM이 다시 비상 안내 생성.
- 수정: 길이만으로 복잡한 질문을 판단하던 분기 제거. 명시적 설명/분석/대처 질문만 LLM 허용, 일반 unknown은 1회 재질문. 비상 감지/기존 비상 상태는 임의 해제하지 않음.
- 관련 테스트24개 통과. 서버 재시작 적용. 실제 위치 질문 재시험 요청.
- 위치 숫자가 바뀔 때 TTS 새 생성 비용(관측1.24~1.77초)은 남아 있음. 불필요한 LLM 장문을 제거한 뒤 별도 측정 필요.


---

## 부록 6. TUTUS_LOCAL_WAKE_MODEL_PLAN_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/TUTUS_LOCAL_WAKE_MODEL_PLAN_2026-10-16.md

> **최신 진행 기록:** [TUTUS_PILOT_TRAINING_2026-10-16.md](TUTUS_PILOT_TRAINING_2026-10-16.md). 아래의 미학습 표기는 당시 기록이며, 현재는 초기 모델 학습·변환 완료 / 검증 미통과 / P4 운영 미전환 상태입니다.

# 투투스 로컬 웨이크워드 준비 — 2026-10-16

## 1. 과거 구현 확인
10월2일 커밋 b549f44의 voice.c는 WakeNet 히트를 로그로만 기록했다. 기본값 비활성. docs/HANMIR_2_VOICE_PREP_2026-10-02.md 및 10월9~10일 인수 문서에도 한국어 맞춤 모델 미확보 명시. 실제 모델 파티션 파일은 4bytes였다.
따라서 과거 빠른 응답은 로컬 투투스 모델이 동작했다는 증거가 아니다. 이전 응답 시간 변동의 정확한 원인은 당시 측정 자료 없이는 단정하지 않는다.
현재 VAD는 음성 여부 판정이고 웨이크워드 분류기가 아니다. 조용하면 계속 WAV를 전송하는 구조는 아니지만 주변 대화/잡음이 음성으로 판정되면 계속 서버 STT에 전달된다.

## 2. 선택 경로
### 직접 학습 후보: micro-wake-word + TFLite Micro
- upstream: https://github.com/OHF-Voice/micro-wake-word
- 로컬 검토용: C:/dev/hanmir-wake-training/micro-wake-word
- 조회한 소스 고정 revision: 4665173cd35f1cff9a61e06fc427f124766c488e
- 사용자 데이터로 한국어 투투스 이진 키워드 모델 학습을 시도한다. 한국어에서 검증된 완성 모델이라는 뜻은 아니다.
- 16kHz mono PCM, upstream micro_speech 특징 추출과 streaming quantized 모델을 함께 사용. 학습·P4의 특징 추출/정규화/상태 초기화가 반드시 같아야 한다.
- 기존 ESP-SR WakeNet 바이너리와 .tflite는 호환 형식이 아니다. 모델 파일만 교체할 수 없으며 별도 TFLite Micro 실행기와 특징 추출기 통합이 필요.
- Espressif TFLite Micro: https://components.espressif.com/components/espressif/esp-tflite-micro
- 실제 DFR1172 P4 revision + ESP-IDF5.5.5 조합에서 지원 연산, arena 메모리, 프레임당 추론 시간을 먼저 확인. 현재 컴파일/실행 검증 전.
- PC에는 Intel Arc Graphics가 보임. CUDA GPU 학습 가능하다고 가정하지 않음. 서버 .venv와 분리된 학습 환경에서 CPU 소규모 실험부터 준비. 대규모 학습 자원과 소요 시간 미확정.

### 대안: Espressif 맞춤 WakeNet
공식 문서에는 TTS 기반, 공급사 수집, 고객 데이터 기반 맞춤 제작이 있으며 비용 문의가 필요. 공급사 이슈의 한국어는 planned로 표시되어 한국어 투투스 납품 가능 여부·P4 호환성·기간을 별도 확인해야 한다. 외부 연락/유료 신청은 하지 않았다.
https://docs.espressif.com/projects/esp-sr/en/latest/esp32p4/wake_word_engine/ESP_Wake_Words_Customization.html
https://github.com/espressif/esp-sr/issues/88

## 3. 데이터 준비
- 수집기 scripts/collect_wake_samples.py: 새 helmet WAV를 별도 폴더에 보존, 16kHz/16bit/mono와 완전한 프레임 확인, SHA256 및 speaker/session 메타 기록.
- recordings/wake/20261016-pilot 아래 원음은 Git 제외. 모든 라벨은 unreviewed. STT 결과를 정답 라벨로 자동 확정하지 않는다.
- 오늘 20회는 수집·발음·분할 점검용. 이 양만으로 현장 모델 완성 또는 인식률 주장 금지.
- 1차 자체 학습 계획(보장된 최소 요건 아님): 다양한 화자 10명 이상, 화자별 50~100회, 속도/크기/마이크거리 다양화. 별도 화자·녹음일로 validation/test를 분리한다.
- 양성: 투투스 단독, 문장 앞 투투스, 조용함/대화/팬/바람 환경.
- 호출어와 헷갈리기 쉬운 비호출 음성(negative): 투두, 블루투스, 주스 등 비슷한 말, 실제 작업 대화, 배터리/위치 명령, 안내 TTS. '두두스' 등을 호출 별칭으로 허용할지는 별도 정책 결정 후 일관되게 라벨.
- 배경음: 최소 수시간 규모의 실제 환경 음원을 점진 수집. 지속 음원에서 오호출/시간 측정. VAD에 걸린 짧은 파일만으로 상시 오호출률을 평가할 수 없다.
- 단말 VAD 후 업로드 WAV는 초기 발음/음질 점검용이다. 최종 학습/평가에는 VAD 전 연속 PCM 수집도 추가해야 한다. NS/AGC 구성은 학습과 추론을 일치시킨다.
- 한국어 TTS 증강은 실제 발음을 사람이 확인하고 별도 출처/사용권 기록. 합성 음성만으로 현장 성능 검증 대체 금지.

## 4. 실행 순서
1. 현재 수집기의 표본 보존 → 청취·발화끝 시각 라벨 → 양성/음성/폐기 분류.
2. 별도 학습 환경 구성, upstream basic_training_notebook 절차로 특징 추출/양성·음성·배경 데이터 준비. 현재 모델 학습 미시작.
3. 학습/검증 화자 분리 및 데이터 중복 해시 확인, streaming int8 모델 export.
4. PC에서 동일 streaming 입력과 연속 배경음으로 threshold 및 연속 판정 횟수 결정. 시험세트를 튜닝에 사용하지 않음.
5. P4 전용 실험 빌드에서 TFLite Micro와 같은 전처리 통합. 카메라·UWB·통화 부하를 포함한 메모리/시간 측정.
6. 로컬 검출 이벤트를 비차단 큐로 보내 내장 안내 재생. 오디오 캡처 태스크에서 동기 재생하지 않음.
7. 안내 재생 중 자기 음성 재감지 방지, 후속 명령 최대 대기/한 번 소비/연속 발화 프리롤 처리. 서버에 로컬 감지 이벤트와 세션 ID를 전달해 이중 안내 방지.
8. 비상어는 별도 로컬 KWS 또는 기존 서버 감시 경로 유지. 투투스 감지 전 WAV 전송을 무조건 막으면 비상어가 깨진다.
9. 모델 검증 통과 후 배포. 현재 서버/STT 방식으로 되돌릴 설정 유지.

## 5. 합격 기준 제안 (아직 미달성)
- 발화 마지막 음절 종료 → 실제 첫 스피커 음성 p95 <=500ms. 기기 검출→재생 로그만으로 전체 지연을 대체하지 않음.
- 보지 않은 화자/소음 조건별 미탐률 및 시간당 오호출률 보고. 초기 목표 recall>=95%, false accept<=1/hour는 제품 합격 협의용 목표이며 현재 성능 아님.
- 호출 성공 표본만 따로 시간 통계 내고, 실패 수와 전체 분모도 함께 공개.
- 오디오 처리 프레임 deadline 위반, heap/PSRAM, 카메라 FPS, Wi-Fi 송신, watchdog 포함 측정.
- 모델 SHA256, upstream revision, 전처리/threshold, 학습 데이터 버전, 테스트 보고서와 펌웨어 버전을 함께 보존.

## 현재 완료/미완료
완료: 과거 구현 조사, 공식 경로 비교, 학습 소스 분리 확보, 원음 수집 스크립트 작성/수집 시작, P4 내장 안내 음성은 이전 단계에서 구현.
미완료: 라벨 데이터셋, 한국어 모델 학습, P4 TFLite 실행 통합, 0.5초/오호출/누락 검증. 로컬 투투스 전환 완료가 아니다.

## 첫 실제 수집 결과 (중간 집계)
사용자는 투투스 20회 완료 보고. 저장 파일49개에는 대화/잡음도 포함되어 분모로 사용할 수 없다. 그 시점의 STT상 정확한 호출어 후보6개(길이1.068~1.356초), 추투스/투스/투투스 두 번 등 다른 전사도 존재. 완전0 PCM 파일은0개. STT후보 수를 로컬 모델 인식률 또는 실제 발화 수로 해석하지 않는다. 라벨은 모두 unreviewed 유지.
로컬 검토 파일: recordings/wake/20261016-pilot/review_candidates.json. 원음 청취/분할과 발화끝 표시 후에만 학습 정답 확정. 초기20회 자료로 모델 학습 완료를 주장하지 않음.

## 사용자 최종 목표 확정 및 빠른 후보 실험
사용자 목표: 통신 원활 + 투투스 발화 종료 후 최대500ms 내 음성 시작. 위 p95만으로 합격 처리하지 않는다. 모든 시험의 최대값 및 deadline miss 수를 보고하며 유한 시험으로 모든 환경의 절대 최댓값을 보장하지 않는다.
최종 실행 위치는 P4. PC 음성 비교는 학습/평가용이며 서버 로컬 인식을 최종 P4 로컬 인식으로 혼동하지 않는다.
수집 완료 총69개 WAV. STT 정확 일치 후보6개. scripts/probe_wake_templates.py로 MFCC 유사 특징+DTW 가능성 평가(학습 아님): host 비교 총0.4764초/69파일, 특징 추출 시간 제외. P4 처리 시간 또는 end-to-end 시간이 아니다.
후보끼리 leave-one-out 거리0.1760~0.2210. 나머지 미라벨 파일 일부 거리0.1848/0.1903/0.1969로 겹침. 이 파일들을 실제 음성(negative)으로 확정하지 않았으며, 오호출률 측정으로 해석 불가. 후보 유사도만으로 production 감지기로 배포하지 않음.

500ms 설계 예산(측정값 아님): 호출어 말미 이후 특징/감지 확정 <=300ms, 비차단 이벤트 큐/오디오 시작 <=100ms, 여유100ms. 각 프레임 처리 기한과 카메라 동시 부하에서 실측 필요.
상시 WAN API 호출 제거는 로컬 투투스와 비상어/별도 비상 경로 검증 후 가능. API 호출을 줄이기 위해 비상 인식 기능을 임의로 제거하지 않음.
다음 필수 단계는 실제 녹음 정답 검토 및 독립 화자/배경 데이터 확보다. 현재 모델 미학습, P4 감지 실행 미통합, 500ms 미검증.

## 실제 학습 준비 진행
- 별도 venv: C:/dev/hanmir-wake-training/venv. 운영 서버 .venv와 분리. upstream 의존성 설치 중.
- 녹음 분류 UI: scripts/review_wake_samples.py, loopback127.0.0.1:8091. labels는 recordings/.../human_labels.json에만 저장.
- scripts/prepare_wake_training.py: 사람 라벨만 사용, 원본 SHA256 중복 방지, 파일 단위 학습/검증/시험 분리, microfrontend 특징과 mmap 생성, 300step CPU pilot config 출력.
- scripts/train_wake_pilot.ps1: CPU 스레드2개로 제한한 실험 모델 학습/streaming int8 변환 실행 명령. 아직 학습 실행하지 않았음.
- 현재 자료는 동일 세션이므로 화자 독립 평가가 아니다. 양성 최소6/음성 최소12는 스크립트 동작을 위한 pilot 하한이지 실사용 데이터 충분성 기준이 아니다.



---

## 부록 7. TUTUS_PILOT_TRAINING_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/TUTUS_PILOT_TRAINING_2026-10-16.md

# 투투스 로컬 모델 학습 실제 진행 기록

## 상태

초기 모델 학습 및 int8 streaming TFLite 변환 완료. **운영 배포 불가, P4 로컬 호출 전환 미완료.**
기존 안전모 펌웨어의 서버 STT 호출 방식은 유지한다. 500ms 응답 성능은 아직 측정하지 않았다.
이 문서는 이전 모델 준비 문서의 '학습 미시작' 상태 이후 진행 기록이다.

## 사용자 정답과 데이터

- 1차 수집 69개를 사용자가 청취·분류: positive 9, negative 60, discard 0.
- 이 숫자는 발화 성공률이 아니다. 주변 소리, VAD 분할 등의 영향으로 파일 수와 발화 수는 다르다.
- 원본 WAV와 사람 라벨은 Git 제외된 `recordings/wake/20261016-pilot/`에 보존.
- 파일 SHA256 중복을 검사하고 원본 단위로 training 7/36, validation 1/12, testing 1/12 (양성/음성) 분리.
- 동일 화자·같은 녹음 세션이므로 화자 독립 평가가 아니다.
- VAD 후 클립이므로 연속 배경 오호출/시간, 발화 끝 지연 평가 자료가 아니다.

## 학습 재현

- upstream: https://github.com/OHF-Voice/micro-wake-word
- revision: `4665173cd35f1cff9a61e06fc427f124766c488e`
- 별도 환경: `C:/dev/hanmir-wake-training/venv` (운영 backend 환경과 분리).
- TensorFlow 2.21.0, keras 3.15.1, pymicro-features 2.0.2, ai-edge-litert 2.3.0.
- 전체 의존성: `C:/dev/hanmir-wake-training/pilot-v1/environment-freeze.txt`.
- prepare_wake_training.py → train_wake_pilot.ps1 → inspect_wake_model.py → evaluate_wake_pilot.py.
- 16kHz mono PCM16, microfrontend 40채널, 10ms step, clip 1500ms.
- MixedNet 5601 parameters (5473 trainable), CPU 2스레드, batch 16, 300 steps, learning rate .001.
- 양성 가중치 1 / 음성 가중치 5. best_weights export.
- 첫 실행은 TensorBoard 누락으로 중단; 설치 후 `model-run2`에서 완료. 실패 로그도 보존.
- 완료 로그: `C:/dev/hanmir-runtime/wake-pilot-train3.log`.

## 모델

- 파일: `firmware/wake_model_lab/main/tutus_pilot.tflite`
- 크기: 29,336 bytes.
- SHA256: `402f96e16879eabc35603fd7758f03ee44884b327d28f8903486d4b50985bdb8`.
- 입력 int8 [1,3,40], scale .10196078568696976 / zero -128.
- 출력 uint8 [1,1], scale .00390625 / zero 0.
- resource variables로 내부 streaming state 유지. 각 독립 클립 평가는 새 interpreter로 초기화.
- PC delegate 항목은 모델의 실제 연산으로 계산하지 않는다.
- 실제 연산: AssignVariable, CallOnce, Concatenation, Conv2D, DepthwiseConv2D,
  FullyConnected, Logistic, Quantize, ReadVariable, Reshape, SplitV, StridedSlice, VarHandle.

## 독립 실행 평가 결과

학습 도구의 출력만 믿지 않고 export된 양자화 모델을 전체 클립으로 다시 실행했다.
출력 tensor에 기록된 실제 scale을 사용했다. 기준 점수 **0.5**, 클립 내 최대 점수가 넘으면 검출:

| 구분 | 양성 검출 | 비호출 클립의 오검출 |
|---|---:|---:|
| training | 6 / 7 | 0 / 36 |
| validation | 1 / 1 | 0 / 12 |
| testing | 0 / 1 | 0 / 12 |

검증 데이터가 너무 작고 시험용 호출을 놓쳤으므로 배포하지 않는다.
threshold 0.7 이상은 validation 호출도 놓침. 시험세트를 보고 기준을 내려 성능을 주장하지 않는다.
이후 개발에 이미 확인한 시험 파일은 미사용 최종 시험으로 재사용하지 않는다.
상시 음원이 없어 false accepts/hour는 **미측정**. 도구의 nan 값은 0회/시간이 아니다.
평가 원본: `C:/dev/hanmir-wake-training/pilot-v1/clip-evaluation.json`.

## P4 준비

`firmware/wake_model_lab/`에 실제 모델 연산/메모리 실험 프로젝트 작성.
esp-tflite-micro 1.4.1 / ESP-IDF 5.5.5 / P4 revision 1.0 설정.
내부 resource variable 저장소를 할당하고 100회 Invoke 시간과 30ms 기한 초과를 로그로 남긴다.
128KiB는 예약 arena이며 사용량 실측값이 아니다.
마이크/카메라/통신이 없는 독립 실험 앱이므로 정상 안전모 펌웨어 대신 상시 설치하지 않는다.
빌드 및 실제 보드 실행 결과는 확인 후 별도로 기록한다. 현재 문서 작성 시 실물 실행하지 않았다.

## 추가 녹음

사용자 요청에 따라 2차 수집기를 실행했고 사용자가 투투스 30회 완료를 보고했다.
수집 종료 시 WAV **38개**, 총 **41.7초**, 전체 0값 클립 0개.
클립 RMS 범위 42.22~8084.44 (PCM16), 최대 포화 샘플 비율 약 0.0096%.
이 수치만으로 발음의 정확성/배선 정상 여부/인식률을 판정하지 않는다.
사람 분류 화면 http://127.0.0.1:8092, 데이터 `recordings/wake/20261016-session2/`.
수집 중간 집계33개 이후 종료까지5개 추가되어 최종38개다.
분류가 끝나기 전 자동 STT 결과를 정답으로 쓰지 않는다.
merge_wake_sessions.py는 완료된 사람 라벨과 세션 출처를 보존해 병합하며 기존 데이터는 변경하지 않는다.

## 다음 단계

1. 추가 사람 라벨 확보 및 원본 단위 학습/검증/신규 시험 분리.
2. 추가 데이터로 재학습. 소음/화자 독립 평가와 연속 배경 녹음은 별도 확보.
3. 동일 microfrontend를 P4에 통합하고 먼저 감지 점수만 기록하는 모드로 검증.
4. 검출 이벤트는 비차단 큐로 내장 ACK 재생에 전달. 안내 중 이중 감지 및 서버 중복 안내 방지.
5. 호출어 말미 → 실제 스피커 첫 소리의 최대 지연, 500ms 초과 수, 누락, 오호출을 함께 기록.
6. 카메라·UWB·음성 동시 부하에서 프레임 처리 기한, 메모리, 송신 대기 검증.
7. 비상어 로컬 경로가 없으면 기존 서버 감시를 유지. 로컬 투투스 하나만으로 모든 WAV 송신을 중단하지 않는다.

## 2차 학습 완료

사람 분류 최종 9 positive / 28 negative / 1 discard. 총 18 positive / 88 negative 병합.
원본 파일과 출처 세션을 provenance.json에 기록. 1차에서 보았던 시험 파일은 새 시험에 넣지 않았다.
새 세션에서 validation/test를 각 3 positive / 9 negative로 분리하고 나머지 12 positive / 70 negative로 학습했다.
같은 화자의 세션 내 분리이므로 독립 화자/새 환경 평가가 아님을 유지한다.
1000 steps, 음성 가중치 2, 나머지 MixedNet 구조 유지. best_weights 양자화 export 완료.

v2 SHA256: `42709ab464158d10ef48083269af60e06c1a9a433c946c46de9facb0d83c471d`, 29,336 bytes.
현재 lab 폴더의 모델은 v2이며 v1은 로컬 pilot-v1 폴더에 보존한다.

| 기준 점수 | validation 호출 검출 | validation 비호출 오검출 | test 호출 검출 | test 비호출 오검출 |
|---|---:|---:|---:|---:|
| 0.5 | 3/3 | 9/9 | 3/3 | 9/9 |
| 0.7 | 2/3 | 0/9 | 3/3 | 0/9 |
| 0.8 | 1/3 | 0/9 | 1/3 | 0/9 |

0.5로 설정하면 비호출도 모두 잡히므로 단순 threshold 하향은 해결책이 아니다.
0.7 시험 결과도 단 3개여서 높은 현장 인식률의 근거가 되지 않는다. validation 누락이 남아 운영 미승인.
위 표는 기준별 조사 결과이며 최종 threshold 확정/독립 제품 성능 검증이 아니다.
로그: C:/dev/hanmir-runtime/wake-v2-train.log, wake-v2-evaluation.log.
자료: C:/dev/hanmir-wake-training/pilot-v2/clip-evaluation.json, split_manifest.json, training_parameters.yaml.

P4 전처리는 pymicro-features 2.0.2와 같은 소스·설정으로 구현했다.
합성 PCM 8000 samples에서 PC 기준 48 frames, raw feature FNV checksum 3207448957.
실물에서 일치 여부를 로그로 확인한 뒤 모델 Invoke 검사를 진행하도록 했다.

## 초기 상태 오검출 원인 조사

v2 비호출 88개 중87개는 각 interpreter의 두 번째 출력에서 최대값을 기록했다.
첫 .5초에 무음을 삽입했으므로 이 피크는 실제 발화 이전 초기 상태에 해당한다.
대표 초기 점수 .53125 → .56640625 → .53125 → .48046875로 감소.
모델 시작·리셋 직후 감지 금지와 상태 안정화가 필요하다. 매 오디오 프레임마다 상태를 초기화하면 안 된다.
진단 목적으로 첫17개 출력(30ms씩, 출력 시퀀스 약510ms)을 제외하면:

- validation threshold .5: 호출3/3, 비호출오검출1/9.
- testing threshold .5: 호출3/3, 비호출오검출0/9.
- threshold .7 결과는 이전 표와 같음.

사후 분석 결과이며 이를 새 독립 성능 검증으로 간주하지 않는다. 실제 기기에서는 전원 기동 안정화 시간이 추가될 수 있다.
재현 옵션: evaluate_wake_pilot.py --ignore-startup-outputs 17. 기본값0은 초기 출력도 평가한다.
실제 threshold/연속 확정 횟수는 새 연속 음원과 실시간 점수 로그로 결정해야 한다.

## P4 실물 실행 완료

COM25 / ESP32-P4 revision1.0에 app 영역(0x10000)만 임시 업로드했다.
기존 bootloader, partition table, NVS, SR model 영역은 변경하지 않았다.
시험 후 보존된 정상 앱을 다시 업로드하고 hash verification 및 서버 재접속 확인 완료.

| 항목 | 실측 |
|---|---:|
| PC 대비 frontend 결과 | 48 frames, checksum 3207448957 일치 PASS |
| 500ms 합성 PCM 전처리 총 시간 | 14,281µs |
| 모델 arena 실제 사용 | 13,644 bytes |
| 실험 arena 예약 | 131,072 bytes |
| 내부 resource handles | 12 |
| Invoke 100회 평균 | 328µs |
| Invoke 최대 | 1,815µs |
| 30ms 기한 초과 | 0/100 |
| 시험 종료 internal free heap | 470,088 bytes |
| 실험 앱 전체 flash 크기 | 357,392 bytes |

합성 입력, 독립 앱, Wi-Fi/카메라 없음. 마이크 검출률·발화끝 지연·동시 부하 성능과 다르다.
13,644 bytes는 모델 arena 사용량으로 전체 전처리/큐/스택 메모리 합계가 아니다.
증거: C:/dev/hanmir-runtime/wake-board-v2/uart.log, result.json, flash-experiment.log, flash-restore.log.
실험 앱 hash: 1bbc0546115c19dcb2a891e051d3bc89c95c264724260c98363d51cae97bc729.
복구 앱 hash: e60580a9f017ea25456ce3f2ca3737ed90c7f98a941b82cd4a5e85fc918095a0.
복구 후 AV online/camera capturing/heading 갱신, UWB online을 서버에서 확인했다.

## 실제 마이크 감지 점수 연결

helmet_p4/main/local_wake.cc에 shadow-only 실행 경로 추가. 기본 비활성화.
AFE 출력에서 160sample 블록을 복사하고 독립 태스크가 같은 frontend 및 모델을 실행한다.
큐는12블록, 송신은 대기0이므로 모델이 지연돼도 마이크/VAD를 막지 않는다.
모델 arena 예약32KiB, 태스크스택8KiB. 모델 처리 실패 시 기존 서버 음성 경로 유지.
큐 누락 시 sequence 차이를 감지하여 상태 초기화 및 준비구간 재시작.
매초 peak/추론횟수/처리시간최대/큐대기최대/drop 수/후보 수 기록.
관측 후보기준 .70×1회, 초기1.5초 억제, 재생/통화구간 억제. 후보는 NO_ACTION으로 기록한다.
추가 분석에서 .70×3회 연속 규칙은 양성18개 모두 놓치는 것으로 확인하여 운영 규칙으로 채택하지 않았다.
1회 규칙은 점수 피크의 실제 시각을 관찰하기 위한 로그 전용이며 재생을 허용하는 확정 판정이 아니다.
20:32 KST에 통합 빌드와 COM25 앱 업로드를 완료했다. 실제 마이크 입력을 이용한 감지 점수 기록 모드가 실행 중이다. 후보 검출은 재생 동작을 일으키지 않으며, 기존 서버 STT 및 응답 경로를 유지한다.

## 20:33 작업 마감 및 카메라 작업 전 기준값

### 이후 정정: 20:35 기존 앱으로 복구

사용자가 호출 무응답을 보고하여 shadow 앱을 제거하고 기존 백업 앱으로 전체 앱 파티션을 복구했다.
복구 SHA256: e60580a9f017ea25456ce3f2ca3737ed90c7f98a941b82cd4a5e85fc918095a0. esptool 쓰기 해시 검증 성공.
아래 shadow 측정값은 복구 전 실험 기록이며 현재 실행 상태가 아니다.
20:34 수신 음성 3건에서 STT가 프롬프트 문장을 반환했고 stt_prompt_echo로 응답이 차단됐다.
복구 후에도 같은 STT 결과가 관측됐다. UART에 음성 큐 포화 및 약 2.6~3.0초 대기가 있어 복구만으로 해결됐다고 판정하지 않는다.
녹음 품질/STT 원인 구분과 사용자 재확인이 남아 있다. 추가 펌웨어 실험은 중단한다.

사용자의 5분 내 정리 요청에 따라 추가 학습·녹음 요청은 중단했다.
현재 단계는 로컬 모델 실행과 계측까지이며, 로컬 호출에 따른 0.5초 이내 응답 완료 상태가 아니다.

- 통합 앱 크기: 2,115,216 bytes, 앱 파티션 4 MiB의 약 50.4%.
- 업로드 검증: esptool 데이터 해시 일치, 재부팅 후 AV와 UWB 온라인.
- UART 25개 통계 구간: 추론 851회, 처리 최대 11.917ms, 큐 대기 최대 13.666ms.
- 큐 드롭 0, 기록된 deadline 초과 0, 모델 오류 로그 0.
- 내부 가용 힙 관측 최저 207,723 bytes, 부팅 이후 최저 157,448 bytes, 태스크 스택 여유 최저 4,208 bytes.
- 관측 구간 후보 로그 3개. 발화 정답과 대조하지 않았으므로 성공 호출이나 오탐으로 판정하지 않는다.
- 기존 음성 경로는 유지되지만 이번 짧은 계측에서 새 발화에 대한 스피커 응답을 별도 확인하지 않았다.

카메라 기준: 재부팅 직후를 제외한 약 16.95초 구간에 서버 수신 12.15fps, 분석 완료 3.60fps.
설정은 전송 목표 15fps, JPEG quality 75, 서버 분석 목표 4fps.
전체 30초 관측의 최근 추론 시간 필드는 88.2~317.0ms였으며, 모든 프레임의 시간 분포는 아니다.
UART 전송 표본은 20회 중 실패 0, 평균 전송 시간 75~131ms, JPEG 약 68KB였다.
최신 프레임 우선 처리에 따른 생략은 네트워크 패킷 손실과 구분한다.
짧은 구간이므로 장시간 무병목 또는 보호구 인식률을 확정하지 않는다.

다음 카메라 작업 순서: 동일 장면에서 수신 FPS와 분석 FPS 분리 측정 → 전송 대기와 추론 시간 확인 → 사람·헬멧·조끼 검출 결과 확인 → 병목에 맞춰 설정 한 항목씩 조정.

증거 파일:
- C:/dev/hanmir-runtime/wake-shadow-build4.log
- C:/dev/hanmir-runtime/wake-shadow-final-uart.jsonl
- C:/dev/hanmir-runtime/wake-shadow-final-summary.json
- C:/dev/hanmir-runtime/wake-shadow-camera-final.jsonl
- 이전 정상 앱 복구용: C:/dev/hanmir-runtime/wake-board-v2/known-good-app.bin

## 연속 상태 추가 진단

evaluate_wake_continuous.py로 시험용12개 클립을 순서를 고정해 이어 붙였다.
앞2초 및 클립 사이2초 합성 무음을 넣고 같은 interpreter/frontend 상태를 유지했다.
호출클립 종료 후1초까지 같은 구간으로 평가, .7×1회/2초 cooldown 적용.
호출 후보2/3, 비호출 후보0/9, 나머지 무음 후보0.
파일별 초기화 결과3/3과 다르므로 파일 단위 결과만으로 상시 인식 성능을 보고할 수 없다.
합성 무음은 현장 배경음 시험이 아니며, 이미 사용한 시험 자료의 사후 진단이다.
클립 끝은 정확한 발화 끝이 아니므로 이 자료로 500ms 응답을 계산하지 않는다.
자료: C:/dev/hanmir-wake-training/pilot-v2/continuous-probe.json.


---

## 부록 8. YOLO_10FPS_TRIAL_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/YOLO_10FPS_TRIAL_2026-10-16.md

# YOLO 10FPS 목표 실측 — 2026-10-16

## 조건과 현재 상태

사용자 정답: 카메라 앞 사람이 안전모·조끼·장갑 착용, 자세가 조금씩 변함.
20:44~20:46 KST에 실제 장치 수신 영상으로 비교했다. 저장한 화면에서도 세 보호구 착용을 확인했다.
같은 고정 영상의 A/B 시험은 아니므로 자세·네트워크·음성 부하 차이가 포함된다.
P4 펌웨어 및 음성 코드 변경 없음. 서버 재시작으로 웹 재로그인이 필요할 수 있다.

YOLO 목표 10FPS를 설정했으나 실측 10FPS는 달성하지 못했다.
현재 최종 설정: 전체 640, 상세 640+960, 상세 간격 0.30초, 목표 10FPS.
320 시험은 보호구 검출 빈도가 감소해 최종 운영 설정으로 채택하지 않고 복구했다.
음성 처리 중 기존 1FPS 우선순위를 유지한다. CUDA 사용 가능 여부는 False였다.

## 비교

| 항목 | 640 + 상세 640/960 | 320 + 상세 640 1초 간격 |
|---|---:|---:|
| 분석 구간 | 46.42초 | 48.48초 |
| 수신 FPS | 10.49 | 9.51 |
| 분석 완료 FPS | 2.13 | 5.49 |
| 처리시간 중앙값 | 371.63ms | 113.97ms |
| 처리시간 P95 | 577.71ms | 246.15ms |
| 처리시간 최대 | 724.15ms | 442.47ms |
| 상세 분석 프레임 | 79/98 | 43/265 |
| 상태 표본 중 음성 처리 활성 | 8/19 | 0/20 |

처리시간은 분석 프로세스 호출부터 결과 반환까지이며 모델 계산만의 시간이 아니다.
시작 10초는 제외했다. 최초 모델 로딩 포함 8.19초 지연은 정상 추론 분포에서 제외한다.
기존 4FPS 기준 짧은 측정은 수신 7.56/분석 1.31FPS였으나 음성 활성 3/4표본이어서 단순 개선 배수 비교에 사용하지 않는다.

## 검출 신뢰도 (최소 / 평균 / 최대)

| 대상 | 640 설정: 검출 수, 신뢰도 | 320 시험: 검출 수, 신뢰도 |
|---|---|---|
| 사람 | 98, .651 / .767 / .843 | 265, .900 / .917 / .934 |
| 안전모 | 0, 계산 불가 | 5, .505 / .531 / .563 |
| 조끼 | 65, .406 / .537 / .756 | 6, .450 / .609 / .755 |
| 장갑 | 78, .413 / .770 / .894 | 43, .416 / .635 / .756 |

수치는 필터를 통과한 양성 검출 항목의 신뢰도다. 정확도나 재현율이 아니며 미검출 프레임을 평균 신뢰도에 넣지 않는다.
원시 모델의 임계값 미만 후보는 이 로그에 포함하지 않는다. 전체 분석별 검출 상자·클래스·positive 값·신뢰도·PPE 최종 판정은 JSONL에 기록한다.
착용 중인데 helmet=false가 관측되므로 현재 미검출을 실제 미착용으로 간주하면 오경고가 발생한다.
빠른 전체 분석 사이 상세 분석을 생략한 프레임도 기존 연속 미검출 카운터를 올린다. 상세 검사 주기와 미착용 판정 주기를 분리해야 한다.

## 병목 및 다음 수정 순서

1. 10FPS에는 평균 전체 처리 예산 약 100ms가 필요하나 현재 상세 추론 비용이 초과한다.
2. 현재 전체 640 + crop 640 + crop 960 최대 세 번 호출. 상세 작업을 별도 주기로 처리하고 결과의 시각·유효기간을 명시하는 구조 검토.
3. ONNX/OpenVINO 등 CPU 추론 최적화는 동일 저장 영상으로 속도 및 보호구 검출 일치도를 먼저 비교한 뒤 채택. 이번에는 설치/전환하지 않았다.
4. PPE 미검출과 미착용 구분, 상세 검사를 하지 않은 프레임의 음성/경고 영향부터 수정할 필요가 있다.
5. 안전모는 영상에 보이지만 640 설정에서 검출 0. 모델 클래스/학습 데이터·노출·입력 크기별 고정 이미지 비교가 필요하다. 원인을 노출 하나로 확정하지 않는다.

## 파일 및 재현

- backend/app/config.py: 목표 FPS, 상세 960 선택, 로그 설정.
- backend/app/routers/camera.py: 설정 기반 속도 제한, 매 분석 로그.
- backend/app/services/camera_trace.py: 20MiB x 현재 1개 + 백업 3개 순환 JSONL.
- backend/app/services/yolo_service.py: 960 상세 분석 선택 가능, 기본 유지.
- scripts/set_yolo10_trial.py: 빠른 실험 설정. --restore-quality로 원래 품질 설정 복구, 목표 10FPS 유지.
- scripts/report_yolo10_trial.py: 수집 자료의 구간 FPS 및 신뢰도 집계.
- backend/logs/camera-analysis.jsonl: 지속 기록 중. 이미지 자체는 로그에 저장하지 않는다.
- C:/dev/hanmir-runtime/yolo10-baseline.jsonl
- C:/dev/hanmir-runtime/yolo10-measurement.jsonl
- C:/dev/hanmir-runtime/yolo10-fast-measurement.jsonl
- C:/dev/hanmir-runtime/yolo10-comparison.json
- C:/dev/hanmir-runtime/yolo10-frame.jpg: 실제 착용 확인용 한 프레임. 외부 업로드하지 않음.

Python 변경 파일 구문 검사 통과. 실제 서버·장치 연결과 두 설정의 실측을 수행했다.
Git 커밋/푸시는 이번 작업에서 수행하지 않았다.


---

## 부록 9. YOLO_SPLIT_AND_HELMET_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/YOLO_SPLIT_AND_HELMET_2026-10-16.md

# YOLO 상세 분석 분리·안전모 인식 개선 기록

작성일: 2026-10-16 (KST). 이전 보고서: YOLO_10FPS_TRIAL_2026-10-16.md.

## 요구와 유지 조건

- 전체 영상 YOLO 10FPS 목표. 보호구 검출을 희생하는 320 축소 방식은 채택하지 않는다.
- 기존 best.pt 가중치와 전체 640 입력, PPE별 판정 임계값 유지.
- 음성 처리 중 1FPS 우선순위 유지. 펌웨어·마이크·TTS 설정은 이번 작업에서 변경하지 않았다.
- 빠른 전체 영상 분석 FPS와 상세 보호구 분석 FPS는 별도 지표다.

## 구현

1. 빠른 분석과 상세 분석을 서로 다른 단일 프로세스 실행기로 분리했다.
2. 빠른 경로는 최신 프레임 큐 하나만 유지하며 전체 640 분석을 수행한다.
3. 상세 경로는 전체 640 + 사람 영역 640/960 분석을 유지하고 필요 시 머리 영역 640/960 검사를 추가한다. 동시에 실행되는 상세 작업은 전체 서버에서 최대 하나이며 대기 프레임을 누적하지 않는다.
4. 상세 분석용 파일을 별도로 복사해 빠른 경로의 임시파일 삭제와 충돌하지 않도록 했고, 완료 후 삭제한다.
5. 상세 결과는 제출 시각 기준 1.5초 이내, 현재와 이전에 모두 한 명의 사람이 확인되고 사람 상자 IoU가 0.5 이상인 경우만 결합한다. 이 조건은 공간 일치 확인이며 사람 신원 추적을 보장하지 않는다.
6. 상세 결과가 없거나 오래됐거나 사람이 바뀌면 PPE 값은 확인 불가(None). 빠른 프레임의 미검출을 상세 미착용 연속 횟수로 누적하지 않는다. 현재 프레임의 양성 검출은 바로 반영한다.
7. 이전 상세 프레임의 검출 상자를 현재 영상 좌표 위에 재사용하지 않는다. 상세 검출·원본 frame_id·age는 detail_evidence에 따로 포함한다.
8. 원래 코드에 있던 빨간 작업장갑의 hand+색상 근거 규칙은 유지했다. 장갑 신뢰도가 항상 순수 glove 클래스 확률을 뜻하지 않으므로 class/source/red_pixel_ratio를 함께 확인해야 한다.

## 안전모가 누락된 이유와 보완

원본에서 안전모 영역이 helmet보다 head로 강하게 분류된다. head를 helmet으로 재분류하거나 임계값을 낮추지 않았다.
상세 경로에서 확인된 한 사람의 상반신 안에 있는 head 후보(0.5 이상)를 머리 ROI 위치 제안으로만 사용한다.
가로 30%, 위 30%, 아래 40% 여유를 둔 원본 ROI를 640/960으로 검사한다. 별도의 helmet 클래스 검출이 기존 0.45 기준을 넘는 경우만 채택한다.

### 동일 원본 고정 비교

| 입력 | 기존 상세 방식 | 머리 검사 추가 |
|---|---:|---:|
| 안전모 착용 8장: helmet 검출 | 0/8 | 3/8 |
| 같은 8장: vest 검출 | 3/8 | 3/8 |
| 같은 8장: glove 검출 | 8/8 | 8/8 |
| 안전모 벗음 8장: 잘못된 helmet 검출 | 0/8 | 0/8 |
| 안전모 벗음 8장: vest / glove 검출 | 8/8 / 8/8 | 8/8 / 8/8 |

정답은 사용자가 착용/벗음 상태를 알려 준 원본이다. 양성 자료와 음성 자료의 첫 원본 화면도 시각 확인했다.
소량·같은 작업자의 인접 프레임이다. 일반화된 정확도/재현율이나 다른 색 안전모의 성능을 보장하지 않는다. 착용 8장 중 5장 미검출은 아직 남아 있다.

## CPU 병목 진단

원래 전체 640 + 사람 영역 640 + 960을 한 경로에서 기다려 처리했다.
분리 후에도 Ultralytics의 predictor 생성/재생성 시 torch 스레드 제한이 8로 되돌아오는 것을 실제 로그에서 확인했다.
pool initializer 또는 첫 setup 직후 제한만으로 충분하지 않았다. on_predict_start 콜백에서 매 호출의 제한을 확인하도록 변경했다.
실제 기록에서 fast=3, detail=1 유지 확인 후 상세 경로는 최종 설정에서 2개로 조정했다.
CPU 콜백 적용 구간(21:03:29~21:04:11 KST): 수신 10.67FPS, 전체 분석 6.83FPS, 상세 분석 0.83FPS. 음성 활성 상태 표본 1/19. GPU 전환 전 수치다.

## 실행 엔진 비교 및 선택

- ONNX CPU, OpenVINO CPU는 비교에서 더 느려 운영에 채택하지 않았다.
- 초기 CPU 비교는 라이브러리의 predictor 재생성으로 스레드 설정이 바뀔 수 있었던 실험이며 엔진의 보편적 성능 비교로 해석하지 않는다.
- Intel Core Ultra 5 125H의 Intel Arc iGPU가 OpenVINO에서 사용 가능했다. PyTorch CUDA 미지원과 내장 GPU 사용 불가는 같은 의미가 아니다.
- GPU FP32 고정 8장 비교: PyTorch 중앙값 109.59ms, OpenVINO GPU 25.02ms. 전체 640, 같은 가중치·후처리·임계값.
- 8장 모두 검출 텐서 shape 동일. 좌표/신뢰도/클래스를 포함한 원소 최대 절대 차이는 약 0.000305. 양자화하지 않았다. 모델의 모든 상황에 대한 일치 보장은 아니다.
- 빠른 경로만 선택적으로 GPU 사용, 상세 경로는 원래 PyTorch CPU 사용. GPU 초기화/실행 실패 시 기존 CPU 모델로 복귀하며 실패 프레임을 한 번 재처리한다.
- 첫 GPU 컴파일은 수십 초 이상 걸릴 수 있다. 모델 디렉터리 .cache 사용. 서버 수신 영상과 YOLO 분석 완료 시각을 구분해서 확인한다.

## 기록 항목과 파일

backend/logs/camera-analysis.jsonl에 lane, engine, frame_id, 실제 CPU threads, 분석 시간, 검출 클래스/상자/신뢰도, 모델 후보, PPE 판단, 상세 근거와 age를 기록한다.
모델 후보는 일반 모델 임계값 0.25 이상만 포함한다. 검출 신뢰도는 정확도가 아니며 검출 수는 서로 다른 사람 수가 아니다.
순환 로그는 현재 파일 20MiB + 백업 3개로 제한된다. 원본 사진은 시험 자료에만 로컬 저장하며 Git/외부로 업로드하지 않았다.

로컬 증거:
- C:/dev/hanmir-runtime/camera-split-fixture/raw-00.jpg 등 착용 원본 8장
- C:/dev/hanmir-runtime/camera-barehead-fixture/raw-00.jpg 등 벗음 원본 8장
- C:/dev/hanmir-runtime/split-fixture-comparison.json (최초 고정 비교)
- C:/dev/hanmir-runtime/camera-barehead-fixture-comparison.json
- C:/dev/hanmir-runtime/raw-helmet-probe.json
- C:/dev/hanmir-runtime/openvino-gpu-camera-comparison.json
- C:/dev/hanmir-runtime/split-camera-summary.json 및 yolo-split-*-measurement.jsonl

## 적용·재현·복구

- 필수 운영 경로는 기존 PyTorch. GPU 옵션 기본값은 false이며 이 PC의 backend/.env에서만 활성화한다.
- 선택 설치: backend/requirements-camera-experiments.txt. 실제 시험 버전 onnx 1.23.2, onnxruntime 1.31.0, openvino 2026.4.1, ultralytics 8.4.174.
- 모델 생성: YOLO('backend/best.pt').export(format='openvino', dynamic=True, quantize=32, imgsz=640).
- scripts/enable_camera_gpu.py로 이 PC의 GPU 빠른 경로 활성화. 원래 .env의 다른 설정은 출력하지 않는다.
- GPU 복귀: YOLO_FAST_OPENVINO_GPU=false 후 서버 재시작.
- 상세 분리 이전 방식: YOLO_ASYNC_DETAIL=false 후 서버 재시작. 전체/상세 해상도는 그대로 유지된다.
- 생성 모델 best.onnx, best_openvino_model/은 Git 제외. 원본 가중치로 재생성 가능하다.
- scripts/compare_split_fixture.py [원본 폴더], compare_openvino_camera.py GPU, report_split_camera.py로 증거를 재현/집계한다.

## 검사

- detail_merge 단위검사 5개 통과: 상세 없음, 신선한 동일 위치, 만료/위치 변경, 현재 양성 우선, 사람 신뢰도 미충족.
- Python 구문 검사 통과.
- 실제 추론 직후 thread=1 검증과 운영 fast=3/detail=1 로그 확인을 수행했다.
- 고정 이미지 양성/음성 비교와 실제 장치 연결 측정을 수행했다.
- Git 커밋/푸시는 아직 수행하지 않았다.

## 최종 운영 측정 — 21:10:20~21:11:02 KST

GPU 준비 완료 후 60초 수집 중 앞 15초를 제외한 42.03초 구간.
다른 모델 비교 프로세스를 동시에 실행하지 않았다. 음성 활성 표본은 1/19였으며, 자세와 발화 상태는 이전 구간과 완전히 동일하지 않다.

| 항목 | 값 |
|---|---:|
| 원본 수신 | 9.85 FPS |
| 전체 640 분석 완료 | 7.73 FPS |
| 상세 보호구 분석 완료 | 1.07 FPS |
| 전체 분석 시간 중앙값 / P95 / 최대 | 43.47 / 103.39 / 306.00 ms |
| 상세 분석 시간 중앙값 / P95 / 최대 | 740.86 / 1099.26 / 1170.78 ms |
| 분석 로그 개수 | fast 325 / detail 45 |
| 빠른 프레임에 결합 가능한 신선한 상세 결과 | 236/325 |

최종 실시간 로그에서 fast=openvino_gpu_fp32, torch threads=3 / detail=pytorch_cpu, threads=2를 확인했다.
이 구간 상세 검출 신뢰도(검출 항목 기준, 정확도 아님):

| 대상 | 검출 항목 수 | 최소 | 평균 | 최대 |
|---|---:|---:|---:|---:|
| 안전모 | 37 | .455 | .568 | .748 |
| 장갑 | 42 | .402 | .678 | .824 |
| 조끼 | 71 | .408 | .556 | .910 |

한 프레임에 전체와 상세 검출 항목이 함께 들어갈 수 있으므로 항목 수를 프레임 수나 사람 수로 해석하지 않는다.
이 라이브 구간은 사용자의 재착용 시점을 프레임별 라벨링하지 않았으므로 정답 기반 인식률 산출에 사용하지 않았다.

**10FPS 목표는 아직 미달이다.** 최초 동일 품질 순차 처리에서 2.13FPS였고, 현재 분리+GPU 구간은 7.73FPS지만 장면·음성 부하가 다른 실제 구간 비교다.
처리시간이 짧아져도 수신 간격, 100ms 속도 제한, 음성 우선 제한, DB/후처리 비용이 있어 완료 FPS는 추론시간 역수와 같지 않다.
다음 최적화는 수신 간격 및 단계별 후처리 시간 계측, 상세 분석 추가 가속, 음성 동시 부하 평가 순서로 진행한다.
모든 상세 검사를 초당 10회 실행한 것은 아니다. 미확인 결과를 착용으로 보간하거나 복제한 프레임을 FPS에 포함하지 않는다.
착용 샘플의 잔여 미검출, 다인원 구분, 물체를 손에 든 경우와 올바른 착용의 구분은 추가 검증이 필요하다.

추가 증거: C:/dev/hanmir-runtime/yolo-gpu-measurement.jsonl, yolo-gpu-live-out.log, yolo-gpu-live-err.log.
운영 오류 로그에서 이번 적용의 Traceback/실행 실패는 관측하지 않았다. 강제 GPU 고장 상황의 CPU 복구는 코드 경로만 마련했으며 실제 강제고장 시험은 하지 않았다.
스레드 설정 참고: https://onnxruntime.ai/docs/performance/tune-performance/threading.html


---

## 부록 10. YOLO_BRIGHTNESS_VALIDATION_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/YOLO_BRIGHTNESS_VALIDATION_2026-10-16.md

# 카메라 밝기 및 안전모 추가 검증 — 2026-10-16

## 21:31 추가 적용 — 더 밝고 선명한 장갑 영상
- 현재 최종 설정은 감마 **1.35**, 약한 unsharp amount **0.2**, 미리보기 JPEG 재압축 품질 **95**. 아래 1.2 기록은 직전 비교 이력이다.
- 원본 해상도는 800×640 유지. 서버 보정으로 센서 세부 정보를 새로 복원하지 않는다. 저장된 P4 빌드 설정의 JPEG 품질은 75였으나 이번에는 P4를 재업로드하지 않았다.
- 동일 새 원본 24장 비교: 안전모 22→22, 조끼 22→23, 장갑 11→14 프레임. 장갑 검출 confidence min/mean/max는 0.464/0.655/0.780 → 0.432/0.603/0.756. 검출 프레임이 늘었어도 평균 confidence는 낮아졌으며 정확도 향상률로 해석하지 않는다.
- 기존 미착용 8장 안전모 오검출 0→0. 미착용 장갑 자료 검증은 아직 없다.
- 단위시험 9개 통과. 웹 재로그인 후 안전모/조끼/장갑 모두 착용 표시 및 새 영상 갱신을 확인했다.
- 45초 측정에서 워밍업 제외 28.238초: 수신14.77 FPS, 전체 추론7.61 FPS, 상세1.10 FPS. 음성 활성 상태 샘플2회. 장면/부하가 직전 측정과 달라 속도 변화가 보정 때문이라고 단정하지 않는다. 10 FPS 미달 유지.
- 증거: `camera-worn-validation2-bright135-comparison.json`, `camera-barehead-fixture-bright135-comparison.json`, `yolo-bright135-measurement.jsonl`, `brightness135-web.png` (모두 C:/dev/hanmir-runtime).
- 추가 파일: scripts/compare_bright135_fixture.py. gamma/sharpen 값은 상태 API 및 프레임별 분석 로그에 기록한다.

## 적용 상태
- 사용자 제공 사진을 밝기 참고로 삼아 서버 감마 1.2 적용. 센서 노출/게인 변경이나 P4 재업로드는 하지 않았다.
- 검은색/흰색 끝값을 유지하는 LUT로 중간 밝기를 올렸다. 촬영 조건이 다르므로 참고 사진과 동일한 밝기/화질을 보장하지 않는다.
- 웹 MJPEG와 앱용 corrected=true 이미지, YOLO 전체 및 ROI 입력에 동일한 보정 적용.
- `/live/image` 기본 응답과 저장 원본은 보정하지 않는다. 원본 검증 자료를 유지한다.
- 웹의 재연결 표시가 사라지고 영상/프레임 번호 갱신을 확인했다. 서버 재시작 시 웹 새로고침 후 연결을 확인했다.
- 밝기 설정: `CAMERA_DISPLAY_GAMMA=1.2`; 1.0으로 되돌리면 보정 없음. 변경 후 서버 재시작 필요.
- 안전모 추가 검사: `YOLO_HEAD_TIGHT_PROBE=true`. 기존 검사에서 안전모가 없을 때만 머리 주변 10% 여백 ROI를 480 크기로 추가 분석. 실제 helmet 클래스와 기존 0.45 기준 유지.

## 동일 원본 비교
| 자료 | 기존 상세 검사 | 좁은 ROI 추가 | ROI 추가+감마1.2 |
|---|---:|---:|---:|
| 기존 착용 8장: 안전모 검출 프레임 | 3/8 | 5/8 | 이번에 미측정 |
| 새 착용 24장: 안전모 검출 프레임 | 20/24 | 22/24 | 22/24 |
| 기존 미착용 8장: 안전모 오검출 | 0/8 | 0/8 | 0/8 |

새 영상에서 감마 적용 전후 조끼 검출 21→22장, 장갑 9→11장.
안전모 검출 confidence: 감마 전 min/mean/max=0.453/0.646/0.768, 감마 후=0.485/0.661/0.804.
Confidence는 정확도가 아니다. 한 사람의 인접 프레임이고 자세/시야가 다르며, 원본 수집에 동일 이미지가 포함될 수 있다. 24개를 독립 표본으로 해석하지 않는다. 장갑이 보이지 않는 장면도 있어 전체 검출 수를 recall로 해석하지 않는다.
기존 8장은 설정 탐색에 사용한 자료이고 새 24장은 그 이후 수집한 별도 시퀀스이다. 다인원/다른 조명/다른 안전모 검증은 남아 있다.

## 실시간 성능
최종 스레드 제한 후 측정: 21:25:53–21:26:36 KST 부근, 워밍업 첫 15초 제외한 42.995초.
- 수신 13.84 FPS
- 전체 화면 YOLO 6.21 FPS
- 별도 상세 분석 0.70 FPS
- 상태 샘플에서 음성 처리 활성 0회(샘플 사이의 짧은 호출까지 부정하지 않음)
- 10 FPS 목표는 미달. 화면 수신 FPS와 실제 추론 FPS를 구분해야 한다.
- OpenCV 기본 18스레드 확인 후 서버 및 분석 워커 각각 1스레드로 제한했다. 직전 보정 적용 측정 5.60 FPS와 촬영 장면/부하가 동일하지 않아 개선폭의 인과관계는 단정하지 않는다.
- 상세 분석 시간이 길어 TTL 1.5초 내 결과 사용률이 낮아질 수 있다. 오래된 판정을 재사용하기 위해 TTL을 무작정 늘리지 않았다.
- 다음 병목 분석은 전체 추론 지연의 긴 꼬리, CPU 상세 작업과 GPU 실행 경쟁, 상세 검사 단계별 비용을 분리해야 한다. 화질/임계값을 낮추어 FPS 수치만 올리지 않았다.

## 기록과 검증
- `backend/logs/camera-analysis.jsonl`: fast/detail/pipeline 구분, 후보 confidence, 좌표, 엔진, 감마, 추론 시간. pipeline은 대기시간과 후처리 시간 추가.
- `C:/dev/hanmir-runtime/camera-worn-validation2`: 새 원본 24장.
- `camera-worn-validation2-tight-comparison.json`, `camera-worn-validation2-gamma-comparison.json`: 프레임별 비교.
- `camera-barehead-fixture-tight-comparison.json`, `camera-barehead-fixture-gamma-comparison.json`: 미착용 검사.
- `helmet-roi-sweep.json`: 탐색 결과. 운영에서는 모든 후보를 실행하지 않는다.
- `yolo-bright-measurement.jsonl`, `yolo-bright-limited-measurement.jsonl`, `split-camera-summary.json`: 성능 자료.
- Python 구문 검사 성공. 상세 병합 및 밝기 단위시험 8개 통과. frontend production build 성공.
- 첫 pytest 실행은 저장소 루트의 import 경로 오류로 수집 실패했고 backend 디렉터리에서 재실행해 통과했다.

## 변경 파일
- backend/app/config.py: 감마, 좁은 ROI 옵션
- backend/app/services/camera_brightness.py: 공통 LUT와 미리보기 보정
- backend/app/services/camera_service.py: 원본/미리보기 캐시 분리
- backend/app/services/yolo_service.py: 전체/ROI 보정과 추가 안전모 검사, 감마 추적
- backend/app/routers/camera.py: 미리보기 응답, 보정 작업 스레드 분리, OpenCV 제한, 파이프라인 지연 로그
- backend/tests/test_camera_brightness.py: LUT 단위시험
- frontend/src/components/CameraMonitor.tsx, LiveCameraFrame.tsx: 보정 영상에 맞는 표기
- frontend/src/services/api.ts: 앱 미리보기 corrected=true
- scripts/capture_camera_fixture.py: 수집 수/간격 옵션
- scripts/compare_tight_helmet_fixture.py, compare_gamma_fixture.py, sweep_helmet_views.py, report_split_camera.py: 비교/측정

로컬 서버와 웹에 적용했다. 이번 단계에서 GitHub push, APK 재빌드, P4 재업로드는 하지 않았다.


---

## 부록 11. YOLO_VOICE_BRIGHTNESS_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/YOLO_VOICE_BRIGHTNESS_2026-10-16.md

# 영상·음성 동시 부하 / 밝기·검출 확인 — 2026-10-16

## 적용 변경

- 대시보드 응답 JSON 변환을 동기 엔드포인트의 스레드에서 수행. 이벤트 누락/삭제 없이 전체 응답 유지.
- 이벤트 조회에서 ORM 객체 생성 대신 동일 컬럼의 행을 읽어 불필요한 객체 생성 감소. 현장 필터 유지.
- 빠른 추론에서 상세 ROI용 밝기 보정 중복 실행 제거.
- 전체 화면 분석 상한 10→12 FPS로 여유 확보. 해상도·모델·검출 임계값 유지. 실제 처리량은 아래 실측 참조.
- 50ms 간격 이벤트 루프 지연 계측 추가. 지연 p95는 최근 200개 표본의 이동 구간이며 전체 실험 p95와 다름.
- 화면 표시 밝기를 추론 입력에서 분리: 최종 preview gamma 1.75, R gain 1.08, B gain 0.96. 상세 추론 gamma 1.35 / sharpen 0.2, 전체 화면 추론 원본 유지.
- 실시간 영상과 분석 이미지 모두 화면 보정 적용. 사진 속 빨간 장갑 영역만 임의로 칠하는 방식이 아니라 전체 영상에 같은 색 균형 적용.
- 웹에 상세 결과 경과 시간 및 검출 신뢰도 표시. 색상 보조 장갑 점수와 일반 검출 신뢰도를 구분. 사람이 보이는 상세 분석 대기를 ‘사람 없음’으로 잘못 표시하던 문구 수정.
- 로컬 backend/.env에 표시 보정 3개 및 YOLO_TARGET_FPS=12 저장. 비밀 값은 출력/문서화하지 않음.
- P4 펌웨어 재업로드 없음. 따라서 이번 변경으로 flash 사용량이 바뀌었다고 보고하지 않음.

## 속도 실측

| 실험 | 유효 시간 | 수신 FPS | 전체 YOLO FPS | 상세 FPS | 영상 Mbps | 서버 대기+IPC p95 |
|---|---:|---:|---:|---:|---:|---:|
| 앞선 기준: indexed | 69.63초 | 13.20 | 8.56 | 0.83 | 6.74 | 131.82ms |
| projection: 같은 분석 상한10 | 71.21초 | 14.03 | 9.42 | 0.70 | 7.01 | 84.96ms |
| headroom: 상한12, 중복 보정 제거 | 69.24초 | 14.46 | 11.48 | 0.87 | 7.13 | 72.40ms |
| 최종 preview gamma1.75 | 45.05초 | 14.36 | 11.16 | 0.71 | 7.33 | 97.80ms |

최종 구간22:18:06–22:18:51 KST: 음성 활성 표본이 있는 구간27.56초에서11.32FPS, 그 외17.49초에서10.92FPS. 순간 루프 지연 최대325ms는 남았다. 음성 파일17개/743.5KB. 따라서 평균 처리량 목표는 넘겼지만 지연 상한이나 음질 정상은 보장하지 않는다. 최종 웹 화면 `C:/dev/hanmir-runtime/yolo-bright175-web.png` 저장 및 화면 연결 확인.

headroom 구간: 22:12:34–22:13:43 KST. 음성 활성 표본이 있는 인접 구간 합계 25.96초에서 11.48 FPS, 나머지 43.28초에서 11.48 FPS. 음성 구분은 약 2초 간격 표본의 양 끝 상태로 분류하므로 정밀한 발화/재생 구간 분리는 아니다. 모든 순간에 10FPS 이상임을 보장하지 않는다. 장면·발화량 차이가 있어 변경별 효과를 완전히 분리한 통제 실험은 아니다.

render-thread 중간 결과 9.52 FPS는 47.26초의 중간 집계다. 이후 프로파일러를 실행했으므로 그 파일 전체를 깨끗한 성능 비교 기준으로 사용하지 않는다.

headroom 리소스:

- 평균 JPEG 61.66KB, 영상 총 61.72MB.
- WAV 업로드 28개, 1.052MB.
- PC Wi-Fi 수신 7.75Mbps / 송신 0.51Mbps. 다른 앱 포함. OS NIC 오류/드롭 카운터 증가 0; 무선 재전송 없음의 증거는 아님.
- PC CPU p50/p95 47.9/60.47%. 시스템 RAM 12,734–13,203MiB.
- 서버 RSS 160–167MiB, 추론 프로세스 각각 464–519MiB 및 638–641MiB.
- 모델 추론 p50/p95 13.51/15.99ms, 워커 전체 44.43/55.10ms.
- 최대 관측 이벤트 루프 지연 185ms. 평균 FPS 개선 후에도 꼬리 지연은 남아 있음.
- P4 free heap/PSRAM 실측은 여전히 미수집. 기존 로컬 앱 bin 2,115,216bytes / 4MiB 약50.43%는 실행 펌웨어 사용량 확인값이 아님.

## 밝기 비교

동일 원본 `camera-color-live/raw-00.jpg`를 비교. gamma1.35 평균 밝기138.31, gamma1.50 평균144.87, gamma1.65+색 균형 평균153.47 (0–255). 한 채널이라도255인 픽셀 비율은 각각0.349%,0.326%,2.134%. 밝아질수록 밝은 영역 포화가 늘 수 있음. 최종1.75는 사용자의 추가 밝기 요청이며 별도 최신 결과 파일을 참조.

표시 설정 전후 추론 입력 픽셀 동일 확인. 이는 표시 보정이 추론을 바꾸지 않는다는 검증이지 현장 인식률 전체가 개선됐다는 의미는 아님. 참고 사진과 센서·조명·시점이 달라 동일 화질을 보장하지 않음.

## 실제 착용 확인

사용자가 안전모·조끼·장갑 모두 착용했다고 확인한 장면을 25초간 수집. 인접 원본 영상에서도 보호구가 보임. API 분석과 원본은 원자적으로 묶인 한 프레임이 아니며 원본 전후 frame_id를 저장함.

45개 화면 표본에서 중복을 제거한 유효 상세 결과23개:

| 장비 | 상세 결과 검출 | 점수 범위 | 화면 상태 |
|---|---:|---:|---|
| 안전모 | 23/23 | 0.605–0.843 | 착용30, 대기15 |
| 조끼 | 16/23 | 0.410–0.615 | 착용22, 대기23 |
| 장갑 | 23/23 | 0.546–0.873 | 착용30, 대기15 |

장갑에는 hand 검출+빨간 픽셀 비율 보조 규칙이 포함된다. 이를 장갑 모델 정확도100%로 표현하면 안 된다. 최신 전체 화면만 보면 보호구 검출이 매우 적고, 현재 장비 판정은 상세 분석에 크게 의존한다. 23개는 유효한 상세 결과에 조건을 둔 작은 단일 장면 표본이므로 전체 시간에 대한 재현율도 아니다.

결론: 안전모·장갑은 이 장면의 상세 결과에서 잘 검출되지만, 상세 갱신0.87FPS 및 유효시간1.5초로 인한 대기 공백, 조끼 미검출7/23이 남았다. 유효시간을 늘려 오래된 착용 결과를 유지하거나 임계값을 낮춰 개선된 것처럼 만들지 않음. 별도 맨손 표본에서 기존 오탐11/16이 확인됐던 문제도 아직 해결하지 않음.

## 음성

사용자: 응답 빨라짐 확인 후, 후속 시험에서 목소리가 조금 깨졌다고 보고.
이전 호출 서버 처리736–789ms, 배터리 질문1297ms. 실제 음향 종단 지연과 다름.
최근 배터리 WAV `/tts/73e6f27dedff56c0554fd3ed.wav`: 3.576초, peak19169/32767, 디지털 클리핑0%. PCM 자체 과대출력 근거 없음.
현재 소스는 HTTP WAV를 작은 버퍼로 받아 I2S에 쓰는 구조라 전송/스케줄 지연 가능성이 있으나 원인 확정 안 됨. UART 수집은 사용자 보고 후 시작했으므로 깨진 순간을 포착했다고 주장하지 않음. 소리 깨짐 해결 확인 전 ‘동시 기능 완전 정상’으로 판정하지 않음.

## 검증 및 재현 파일

- 서버 관련 테스트:16개, API/인증/밝기15개, 추가 밝기/음성·카메라11개 통과(집합 중복 있음). 프런트엔드 빌드 통과.
- `scripts/collect_wake_system_metrics.py`: 지연 생성되는 추론 프로세스도 추적하도록 보완.
- `scripts/report_camera_network.py`: 표본 구간별 FPS·음성 관측 여부·이벤트 루프 지연 추가.
- `scripts/compare_preview_color.py`: 같은 원본의 밝기 및 추론 입력 불변 비교.
- `scripts/capture_ppe_live_evidence.py`: 사용자 착용 정답, 분석 결과, 인접 원본/frame_id 저장.
- 원본/요약: `C:/dev/hanmir-runtime/yolo-projection-measurement*`, `yolo-headroom-measurement*`, `yolo-final-bright-measurement*`.
- 착용 증거: `C:/dev/hanmir-runtime/ppe-worn-2214/observations.jsonl`, `summary.json`, `raw-*.jpg`.
- UART: `C:/dev/hanmir-runtime/yolo-headroom-speaker-uart.jsonl`.
- 프로파일: `C:/dev/hanmir-runtime/server-render-thread-profile.txt`.

다음 우선순위: 음성 깨짐을 실제 재현하며 재생 버퍼/전송시간 확인 → 상세 PPE 처리 지연 단축 → 조끼 검출과 맨손 오탐을 별도 정답 영상으로 비교. 현재 프레임 목표는 평균 기준 달성했으며 상세 보호구10FPS 또는 모든 순간10FPS 달성은 아님.


---

## 부록 12. YOLO_DETAIL_TTS_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/YOLO_DETAIL_TTS_2026-10-16.md

# 상세 PPE 분석·조끼·TTS 개선 기록

## 목표와 상태

밝기를 유지하면서 상세 분석 대기를 줄이고, 조끼 미검출과 음성 깨짐을 개선한다. 전체 화면 YOLO 평균 10FPS와 상세 PPE 갱신 속도는 서로 다른 지표다. 모든 순간 10FPS 또는 보호구 상세 분석 10FPS 달성을 의미하지 않는다.

서버 개선안과 P4 TTS 버퍼 변경을 적용했다. 사용자는 새 펌웨어에서 안내와 답변이 빠르고 잘 들린다고 확인했다. 장시간·다양한 현장 조건에서의 검증은 별도다.

## 서버 변경

- 상세 분석의 640 입력은 GPU FP32, 960/480 입력은 기존 CPU 모델을 사용한다. GPU 오류 시 CPU로 전환한다.
- 한 사람의 몸통이 검출됐지만 조끼가 없으면 몸통 ROI를 추가 분석한다. 실제 조끼 클래스와 기존 임계값을 사용하며 색만으로 조끼를 판정하지 않는다.
- 640 머리 분석에서 안전모가 확인되면 추가 960 머리 분석을 생략한다. 검출되지 않으면 기존 고해상도 분석을 유지한다.
- 음성 처리 중에도 상세 작업을 제출할 수 있다. 상세 작업은 동시에 하나만 처리하고 오래된 작업을 쌓지 않는다.
- 오래된 착용 상태의 유효 시간을 늘리거나 신뢰도 기준을 낮추지 않았다.
- 화면 gamma 1.75, red gain 1.08, blue gain 0.96 유지. 상세 분석 gamma 1.35/sharpen 0.2 유지.

주요 파일: `backend/app/services/detail_model.py`, `yolo_service.py`, `camera_service.py`, `backend/app/config.py`.

## 영상 검증

원본과 API 결과는 인접 시점이며 원자적인 같은 프레임이 아니다. 원본 전후 frame_id를 저장한다. 아래 수치는 소규모 단일 장면 결과이며 일반적인 정확도가 아니다.

| 구간 | 안전모 | 조끼 | 장갑 |
|---|---:|---:|---:|
| 기존 착용 상세 23개 | 23/23 | 16/23 | 23/23 |
| 개선 후 착용 상세 37개 | 37/37 | 37/37 | 37/37 |
| 개선 후 신뢰도 범위 | .674–.852 | .621–.903 | .486–.888 |

개선 후 화면 표본 44개 중 43개는 모두 착용으로 표시되고 1개는 상세 분석 대기였다. 장갑 37개는 모두 색상 보조 규칙이 포함되며 장갑 모델 정확도 100%로 표현하지 않는다. 기존 맨손 표본 오탐 11/16은 아직 해결하지 않았다.

- 조끼 미착용 원본 10장: 기존/하이브리드/몸통 ROI 방식 모두 조끼 검출 0/10.
- 안전모 미착용 원본 8장: 개선 방식 안전모 검출 0/8.
- 동일 착용 원본 12장 비교: 기존 평균 약 1407.63ms, 하이브리드+몸통 ROI+머리 조기 종료 약 715.20ms(첫 표본 제외). 컴파일 및 다른 작업 부하가 존재하므로 실시간 성능 보장값이 아니다.
- 보호구가 없으면 추가 분석을 계속하므로 처리 시간이 더 길 수 있다.

증거 경로: `C:/dev/hanmir-runtime/detail-hybrid-early-worn.json`, `detail-hybrid-no-vest.json`, `detail-hybrid-barehead.json`, `ppe-hybrid-worn-live/summary.json` 및 `observations.jsonl`.

## 음성 수정

기존 WAV를 작은 청크로 수신하며 바로 I2S에 쓰던 방식을, 최대 512KiB PSRAM에 수신 완료 후 PCM을 재생하는 방식으로 변경했다. RIFF/WAVE, PCM mono 16kHz 16bit, 데이터 길이, HTTP 완료를 검증한다. 짧은 답변용이며 초과 파일은 실패로 기록한다. 메모리는 모든 경로에서 해제한다.

기록 항목: 다운로드 시간, PCM 바이트, 실제 I2S 쓰기 바이트, 최대 쓰기 대기, 재생 시간, 내부 heap 및 PSRAM 여유량. 수신 완료 선행으로 초기 재생 지연이 추가될 수 있으며 실제로 측정해야 한다. 네트워크 지연에 의한 재생 끊김은 가설이며 원인 확정은 아니다.

호출 안내 내장 PCM, GPIO, 밝기는 변경하지 않는다. 실험용 local wake shadow는 비활성화한다.

실행 앱 백업: `C:/dev/hanmir-runtime/p4-before-buffered-tts-app.bin`. 장치에서 읽은 앱 앞 1,941,744바이트가 정상 복구본 `wake-board-v2/known-good-app.bin`과 일치했다. 정상 복구본 SHA256: `e60580a9f017ea25456ce3f2ca3737ed90c7f98a941b82cd4a5e85fc918095a0`.

## 검증 절차

관련 단위 테스트는 backend 디렉터리에서 실행해야 한다. 저장소 루트에서 실행하면 app import 경로 오류가 발생한다. 올바른 작업 디렉터리로 재실행해 상세 모델·상세 병합·밝기·프레임 조절 19개 통과.

빌드 종료 → 앱 이미지 크기 확인 → 앱 파티션만 업로드 → 부팅/UART 확인 → 빌드 없는 구간에서 영상·음성 동시 부하 기록 → 사용자 청취 확인 순서로 진행한다. 평균 FPS 외에 대기 p95, 상세 FPS, 트래픽, 호스트 CPU/RAM, 장치 heap/PSRAM을 구분해 보고한다.

## 최종 적용·실측 (22:50–22:55 KST)

- 빌드 성공, COM25 앱 오프셋 0x10000만 업로드, esptool 해시 검증 성공. 카메라·마이크·방향·UWB 서버 수신 복구 확인.
- 새 앱 1,942,176바이트 / 4MiB 앱 파티션 46.31%. 이것은 앱 이미지 크기이며 전체 플래시 사용량이나 RAM 사용량과 다르다.
- SHA256: `2beb94fe9af18ab2f199ed69aa4adf142c514c74d999a3ceacbf2a954ca3f57d`.
- 빌드 중 PC 여유 RAM 약1.1GB까지 감소하여 서버를 잠시 중단한 후 재시작했다. 아래 최종 측정에는 컴파일이 포함되지 않는다.
- 음성 다운로드 266ms, WAV 114,476바이트, PCM 114,432바이트 전체 쓰기 성공, 재생3696ms, 최대 I2S 쓰기71ms. 이는 DMA 공급 대기 시간을 포함하며 그 자체로 소리 끊김을 의미하지 않는다.
- TTS 버퍼 보유 중 내부 heap269,783바이트 / PSRAM30,449,788바이트. 재생 후 내부 heap268,235 / PSRAM30,971,008바이트. 모든 시점의 최소 여유량은 아니다.
- 사용자 청취: “개잘들리고 빨리 대답나옴”. 이번 시험의 음성 깨짐 개선 확인이며 음향 종단 지연 0.5초 달성 측정은 아니다.

### 상세 작업 간격 조절

첫 버전은 상세 작업이 빨라졌지만 전체 영상 부하가 늘었다. 상세 시작 최소 간격을 0.8초로 저장했다. 검출 임계값·영상 밝기·결과 유효시간은 유지했다.

| 항목 | 간격 조절 전 (99.20초) | 최종 (69.48초) |
|---|---:|---:|
| 카메라 수신 FPS | 12.87 | 13.69 |
| 전체 YOLO FPS | 9.32 | 10.25 |
| 상세 PPE FPS | 1.78 | 1.08 |
| 음성 활성 관측 구간 YOLO FPS | 9.53 | 10.01 |
| 영상 페이로드 Mbps | 6.26 | 6.58 |
| 서버 대기+IPC p95 ms | 139.60 | 125.54 |

음성 활성은 약2초 표본의 구간 양끝 관측값으로 분류한다. 연속적인 실제 발화/재생 전체 구간을 뜻하지 않는다. 최종 호스트 CPU p50/p95=48.1/58.04%, 호스트 RAM 12,877.59–13,267.38MiB. 다른 앱 사용량이 포함된다. 평균10FPS를 달성했지만 순간 하락과 대기 꼬리 지연은 남아 있다.

### 사용자 요청: 20프레임 중 18프레임 이상 3종 동시 검출

사용자가 3종 착용을 확인한 후 API에서 새 상세 frame_id를 중복 제거하여 처음 관측한 20개를 평가했다. 전송 원본의 연속20장 또는 전체 화면 추론의 연속20장이 아니라 약16초간 관측한 서로 다른 상세 결과20개다. API 폴링 사이의 상세 결과가 빠졌을 가능성은 있다.

| 항목 | 검출 | 점수 범위 |
|---|---:|---:|
| 안전모 | 20/20 | .498–.844 |
| 조끼 | 20/20 | .420–.871 |
| 장갑 | 19/20 | .405–.870 |
| 세 가지 동시 | **19/20** | 장갑 미검출1개 |

요청한18/20 기준을 현재 설정으로 충족하여 추가 임계값 하향은 하지 않았다. 안전모 .45, 조끼 .40, 장갑 .40 기준 유지. 장갑은 색상 보조 판정을 포함한다. 맨손 오탐 문제는 별도 남아 있으며, 모든 장면에서 무조건 탐지된다고 보장하지 않는다.

근거:

- `C:/dev/hanmir-runtime/ppe-20frame-request/first20.json`: 20개 frame_id·시간·각 점수·동시 검출 여부.
- 같은 폴더 `observations.jsonl`, `raw-*.jpg`: 인접 원본과 API 결과.
- `detail-buffer-measurement.summary.json`, `detail-paced-measurement.summary.json`: 전후 성능.
- `detail-buffer-uart.jsonl`, `detail-paced-uart.jsonl`: 장치 로그.
- `tts-buffer-build-final.log`, `tts-buffer-flash.log`: 빌드·업로드 근거.

최종 로컬 설정: `YOLO_DETAIL_HYBRID_GPU=true`, `YOLO_VEST_BODY_PROBE=true`, `YOLO_DETAIL_EARLY_EXIT=true`, `YOLO_DETAIL_DURING_VOICE=true`, `YOLO_PPE_DETAIL_INTERVAL_SECONDS=0.8`. GPU와 변환된 FP32 모델이 준비된 현재 PC용 검증 설정이다.


---

## 부록 13. YOLO_DETAIL_3TO5FPS_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/YOLO_DETAIL_3TO5FPS_2026-10-16.md

# 보호구 상세 분석 3–5FPS 개선

작성: 2026-10-16, 측정 시간 23:06–23:13 KST. 서버는 최종 설정으로 실행 중이다.

## 무엇이 다른가

- 전체 YOLO: 전체 화면에서 사람, 보호구, 화재 등 후보를 탐지한다. 작은 보호구는 놓칠 수 있다.
- 상세 PPE: 같은 모델로 사람·머리·몸통 ROI를 확대하고 필요에 따라 여러 번 추론한다. 보호구 판정 및 최근 분석 화면의 박스에 사용한다.
- 둘 다 YOLO 추론이다. 전체 FPS와 상세 작업 완료 FPS를 합하거나 같은 값으로 해석하지 않는다. 상세 한 작업은 여러 추론 패스를 포함한다.

## 변경

기존 960 입력 CPU 패스가 로그 평균 약327ms로 가장 큰 비용이었다. 같은 best.pt를 960 입력 OpenVINO FP32로 변환하고 GPU에서 실행하도록 선택 옵션을 추가했다. 640도 기존 GPU, 480은 CPU를 유지한다. GPU 오류 시 CPU로 전환한다.

원본 가중치 SHA256: `7a76705efeffcdc651268b49939f5e0d1e4fb91a1f8b8553abd152f85cf1b4b0`.

밝기, 보호구 임계값, 모델 가중치, 음성 펌웨어는 변경하지 않았다. 별도 상세 프로세스에는 서버에서 이미 제출 간격을 적용하므로 내부 ROI 간격 제한을 중복 적용하지 않도록 했다. GPU 모델의 입력 형태에 따라 수치 차이가 생길 수 있어 동일 이미지 비교를 진행했다.

최종 설정:

```dotenv
YOLO_DETAIL_HYBRID_GPU=true
YOLO_DETAIL_GPU960_MODEL_PATH=C:/dev/hanmir-runtime/gpu960/best_openvino_model
YOLO_PPE_DETAIL_INTERVAL_SECONDS=0.20
YOLO_DETAIL_DURING_VOICE=true
```

다른 PC에서는 `scripts/export_detail_gpu960.py --output <새 디렉터리>`로 모델을 변환하고 출력된 경로를 설정해야 한다. 로컬 절대 경로를 그대로 복사하면 안 된다. 재현에는 기존 GPU640 모델과 OpenVINO 환경도 필요하다.

## 동일 영상 비교

서버를 잠시 멈추고 같은 이미지를 두 방식에 입력했다. 첫 프레임 시간은 평균에서 제외했다. 오프라인 속도는 실시간 성능 보장값이 아니다.

| 표본 | 기존 CPU960 | 새 GPU960 |
|---|---|---|
| 기존 착용20장: 안전모/조끼/장갑 | 20/20, 20/20, 20/20 | 동일 |
| 위 표본 평균 상세 시간 | 258.24ms | 158.74ms |
| 조끼 미착용10장: 조끼 오탐 | 0/10 | 0/10 |
| 안전모 미착용8장: 안전모 오탐 | 0/8 | 0/8 |
| 맨손16장: 장갑 오탐 | **11/16** | **11/16** |
| 이번 자세22장: 안전모/조끼/장갑 | 22/22, 18/22, 19/22 | 동일 |
| 이번 자세 평균 상세 시간 | 305.33ms | 144.86ms |

표본의 검출 수가 같다는 의미다. 전체 현장의 인식률 불변을 입증한 것은 아니다. 특히 기존 색상 보조 장갑 판정의 맨손 오탐은 해결되지 않았다.

## 실시간 전후

워밍업15초를 제외한 구간. 각 구간은 다른 시간·자세·PC 메모리 상태이므로 모든 차이를 코드 변경 효과로 단정하지 않는다.

| 항목 | 기존 0.8초 간격 | GPU960·0.30초 | 최종 GPU960·0.20초 |
|---|---:|---:|---:|
| 유효 측정 시간 | 38.91초 | 70.93초 | 70.14초 |
| 영상 수신 | 10.90FPS | 14.72FPS | 14.26FPS |
| 전체 YOLO | 7.92FPS | 11.32FPS | **11.46FPS** |
| 상세 PPE | 1.00FPS | 2.81FPS | **3.71FPS** |
| 음성 활성 관측 구간 전체 YOLO | 8.60FPS | 11.14FPS | **11.38FPS** |
| 영상 페이로드 | 4.96Mbps | 6.75Mbps | 6.58Mbps |
| 서버 대기+IPC p95 | 148.94ms | 17.15ms | 22.55ms |

최종 상세 갱신은 평균 약270ms다. 5FPS 고정 달성은 아니다. 전체 분석은 29개 표본 구간 중 1개가 10FPS 미만(6.42FPS)이었다. 따라서 **평균 목표는 달성했지만 모든 순간 10FPS 유지는 미달성**이다. 음성 구간은 약2초 폴링 양끝의 활성값으로 구분하며 실제 음향 재생 구간과 완전히 같지 않다.

최종 CPU p50/p95 35.0/44.31%, 호스트 사용 RAM 14,871–15,001MiB. 다른 앱을 포함하며 메모리 여유가 작아 장시간 시험이 필요하다. Wi-Fi 어댑터 RX7.30/TX0.50Mbps, 관측 드롭·오류 카운터 증가0. 이는 무선 패킷 손실 전체가0이라는 증명은 아니다.

## 장치·음성

- UART 수집 전체의 카메라 TX 표본 71개: 시도1,420건, 보고된 실패0. 각 20회 평균 전송시간59–212ms. 이 UART 범위는 성능표 구간보다 길다.
- 최종 답변 WAV114,476바이트, PCM114,432바이트 전부 쓰기 성공. 수신263ms, 재생3698ms, 최대 I2S 쓰기70ms.
- TTS 버퍼 보유 시 내부 heap263,743바이트, PSRAM30,455,932바이트. 재생 후 내부 heap263,395, PSRAM31,038,196바이트. 전체 기간 최소치는 아니다.
- 사용자 두 시험 모두 잘 된다고 확인. 발화 종료부터 소리까지의 음향 지연은 직접 측정하지 않았다.
- 펌웨어 미변경: 직전 검증 앱1,942,176바이트, 4MiB 앱 파티션46.31%. 전체 플래시 사용량과는 다르다.

## 최종 착용 장면의 한계

API에서 중복을 제거해 관측한 상세 결과52개: 안전모52/52(.462–.862), 장갑52/52(.454–.891), 조끼29/52(.400–.642). 장갑은 전부 색상 보조 판정을 포함한다. 현재 자세의 조끼 미검출은 남아 있으며 세 가지 동시18/20을 모든 장면에서 만족했다고 주장하지 않는다. 박스는 실제 검출된 위치에만 그린다.

## 검증·파일

- 상세 GPU 라우팅/실패 시 CPU 복귀/병합 테스트8개 통과.
- 변경 파일: `backend/app/config.py`, `services/detail_model.py`, `services/yolo_service.py`, `backend/tests/test_detail_model.py`, `scripts/compare_detail_hybrid.py`, `scripts/export_detail_gpu960.py`.
- 증거 루트 `C:/dev/hanmir-runtime/`: `detail3to5-final-summary.json`, `detail3-baseline*`, `detail3-live-measurement*`, `detail4-live-measurement*`, `detail4-live-uart.jsonl`, `detail3-paired-*.json`, `detail3-current-paired.json`, `detail4-live-ppe/`.
- 원시 프레임·개인 음성·인증 정보는 GitHub에 업로드하지 않았다.

다음 우선순위는 현재 자세의 조끼 미검출과 맨손 장갑 오탐을 개선하고, 장시간 음성 동시 부하에서 10FPS 미만 구간의 원인을 추가 측정하는 것이다.


---

## 부록 14. VEST_RECALL_AND_BOX_REFRESH_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/VEST_RECALL_AND_BOX_REFRESH_2026-10-16.md

# 조끼 검출·박스 갱신 개선

2026-10-16 KST. 사용자는 안전모·조끼·장갑 모두 착용 중임을 확인했다.

## 분석 영상 구분

전체 YOLO는 전체 화면을 분석하며 사람 및 직접 검출한 보호구 박스를 만든다. 상세 PPE는 확대 ROI를 추가 추론하며 그 원본 영상에 박스를 그린다. 현재 ‘최근 분석 화면’은 상세 영상이다. 상세 박스를 이전 좌표 그대로 새 전체 영상에 붙이지 않는다. 전체11FPS 영상에 상세 박스까지11FPS로 정확히 표시하려면 별도 추적과 좌표 갱신이 필요하며 이번 작업에는 포함하지 않았다.

기존 웹 이미지 확인 주기가1초여서 상세 서버 처리3–4FPS와 화면 갱신 속도가 달랐다. 상세 화면 확인 주기를200ms로 변경했다. 새 프레임이 없을 때 이미지를 재다운로드하지 않으며, 같은 프레임의 시간이3초를 넘으면 정지 상태로 처리한다. 요청은 완료 후 다음 요청을 예약해 겹치지 않는다. 실제 표시 속도는 네트워크·디코딩 시간에도 영향을 받는다.

## 조끼 임계값 비교

현재 장면 원본의 첫20장을 모든 후보에 동일하게 사용했다. 조끼만 조정하고 안전모·장갑·밝기·모델 가중치는 유지했다.

| 조끼 임계값 | 착용20장 검출 | 미착용19장 오탐 |
|---|---:|---:|
| .40 | 6/20 | 0/19 |
| .35 | 9/20 | 0/19 |
| .30 | 15/20 | 0/19 |
| **.25** | **19/20** | **0/19** |

착용 표본의 안전모·장갑은 모든 후보에서 각각20/20. 최종 `YOLO_VEST_CONFIDENCE=0.25`를 로컬 설정에 저장했다. 낮은 신뢰도 후보를 더 받아들이므로 다른 평상복에서 오탐이 늘 가능성은 남아 있다. 이 작은 음성/영상 시험을 산업 안전 성능 인증으로 해석하면 안 된다. 기존 맨손→장갑 색상 보조 오탐도 이번 변경에서 해결하지 않았다.

## 새로운 영상으로 검증

워밍업15초 뒤 로그의 첫 **연속 상세 분석20개**를 성공 여부와 무관하게 선택했다. 결과를 고르거나 이전 프레임을 중복 집계하지 않았다.

- 안전모20/20, 점수 .456–.726.
- 조끼19/20, 점수 .250–.616.
- 장갑20/20, 점수 .666–.839.
- 세 가지 동시19/20. 현재 시험의18/20 목표 통과.
- 사용자: ‘잘들림 잘체킹된다’. 후속 화면 경량화 후 ‘잘되는거같네’ 확인.

## 화면 갱신 부하 감소

처음 실시간 측정에서 전체 평균은 약9.75FPS, 음성 활성 표본 구간10.03FPS, 상세3.16FPS로 경계였다. 호스트 RAM 사용량도 약15.75GiB까지 관측됐다.

이미지 갱신에는 분석 전체 JSON이 필요하지 않으므로 `latest?metadata_only=true`를 추가했다. 새 이미지 확인은 frame_id/시간만 받는다. 실제 한 표본에서5016바이트→106바이트로 줄었다. 상세 결과 패널은 기존 전체 분석 API를 유지한다. 호스트 RAM과 장면도 변했으므로 이후 성능 차이 전부를 이 변경 하나의 효과로 단정하지 않는다.

## 장치 기록

조끼 적용 후 답변 WAV114,476바이트, PCM114,432바이트 전체 쓰기 성공. 다운로드247ms, 재생3700ms. 버퍼 보유 시 내부 heap265,519바이트·PSRAM30,292,912바이트, 재생 후274,515·31,038,424바이트. 모든 시점 최소치는 아니다. 펌웨어 미변경, 직전 앱 크기1,942,176바이트/4MiB 약46.31% 유지.

## 재현 자료

증거 루트 `C:/dev/hanmir-runtime/`:

- `vest-threshold-worn.json`, `vest-threshold-negative.json`: 동일 이미지 후보별 결과·신뢰도·시간.
- `vest-improve-current/`: 수정 전 원본/관측값.
- `vest025-live-first20.json`: 새 연속20개 frame_id·시간·점수.
- `vest025-live-measurement*`, `vest025-meta-measurement*`: 화면 경량화 전후 성능 원시 로그·요약.
- `vest025-live-uart.jsonl`: 장치 재생·전송 로그.
- `vest025-live-evidence/`: 적용 후 인접 원본/관측값.

프런트엔드 TypeScript 및 Vite 빌드 성공. 경량 메타데이터 API의 응답 크기와 키를 실제 서버에서 확인했다. 변경 파일은 `backend/app/routers/camera.py`, `frontend/src/services/api.ts`, `frontend/src/components/CameraFrame.tsx`, `scripts/compare_detail_hybrid.py`, 로컬 `.env`다. 원본 영상과 인증 정보는 업로드하지 않았다.

## 최종 성능 결과

워밍업 제외 56.13초.

| 항목 | 결과 |
|---|---:|
| 영상 수신 FPS | 14.66 |
| 전체 YOLO FPS | 11.17 |
| 보호구 상세 FPS | 3.58 |
| 영상 페이로드 Mbps | 6.89 |
| 음성 활성 관측 구간 YOLO FPS | 11.04 |

표본 구간 21개 중10FPS 미만 0개, 최소 10.14FPS. 약2초 단위 구간 평균이며 매100ms에 대한 보장은 아니다. 음성 활성 구분도 구간 양끝 표본을 이용한다. 실제 음향 종단 지연·표시 FPS를 직접 측정한 값은 아니다.

서버 대기+IPC p95 41.85ms. 호스트 CPU p50/p95 [38.8, 52.324999999999996], 사용 RAM 범위MiB [14377.68359375, 14604.2734375]. 다른 앱 포함.


---

## 부록 15. UWB_STATIONARY_DIAGNOSIS_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/UWB_STATIONARY_DIAGNOSIS_2026-10-16.md

# UWB 정지 상태 진단 및 1차 수정 — 2026-10-16

## 조건
안전모 정지, 앵커 4개 전원 ON. 사용자 확인: 앵커와 태그 모두 약 0.8~1m 높이.
카메라·음성 설정 및 펌웨어는 이번 수정에서 변경하지 않았다. 서버만 재시작했다.
현재 지도는 X 5.0m / Y 3.3m. 앵커 설정 z=2.2m이나 현재 좌표 계산은 XY만 사용한다.

## 결과 요약
|항목|수정 전 60초|수정 후 60초|
|---|---:|---:|
|수신 회수|179|180|
|표시 좌표 최대 한 번 이동|34.2cm|20.5cm|
|표시 X 전체 범위|34.3cm|49.1cm|
|표시 Y 전체 범위|70.1cm|105.2cm|
|중앙 위치 기준 거리 95백분위|32.8cm|54.1cm|
|계산 후보 최대 한 번 이동|111.4cm|112.4cm|

**순간 점프는 줄었지만 전체 정지 흔들림은 해결되지 않았다.** 두 구간의 RF 거리 노이즈가 달라 전체 범위 개선으로 해석하면 안 된다.
동일 수정 전 로그 재생 비교에서는 최대 한 번 이동 34.18→19.94cm, 중앙 위치 기준 95백분위 32.88→30.74cm였다.

## 원인 근거
수정 전 후보 좌표 0.5m 초과 점프 21회 중 20회가 3개↔4개 앵커 전환과 겹쳤다. 주로 1번 누락/복귀.
1번 누락: 수정 전 14/179, 수정 후 14/180.
2번은 수정 전 거리 3.141~4.596m, 중앙 3.682m, 표준편차 0.296m. 수정 후 표준편차 0.348m.
2번 수정 전 품질 분류: NLOS 의심 91회, suspect 82회, nominal 5회. 진단 분류이며 반사 원인의 확정 증명은 아니다.
클라이언트 quality=0.95는 고정 전달값이어서 실제 정확도 95%로 해석하면 안 된다.
서버 위치 confidence 중앙값은 전 0.86 / 후 0.845이며 거리 잔차 기반 점수이지 실제 위치 정답 확률이 아니다.
현재 신호 품질 처리는 observe 모드이고 신호 지표에 따른 거리 제외/가중치 보정은 적용되지 않는다.

## 적용한 변경
backend/app/services/anchor_transition_guard.py 및 routers/uwb.py:
앵커 조합 변경과 후보 좌표 0.4m 초과 이동이 함께 발생하면 3회 연속·0.6초 이상 확인 후 반영한다.
기존 조합 복귀와 같은 조합의 이동은 즉시 통과시킨다. 기존 위치 필터는 그대로 적용된다.
수정 후 14회 보류. 앵커 3개 미만으로 계산 불가 2회.
단위 시험 4개 통과. 실제 보행 반응은 아직 시험하지 않았다.
태그·앵커 펌웨어 업로드 없음. 플래시 사용량 변화 없음. 이번 구간 전용 CPU/힙/전체 트래픽 측정은 하지 않았다.

## 방 크기 — 수동 입력 참고값
현재 비율 5:3.3, 직사각형, 동일 높이 가정으로 수정 전 거리 중앙값에 맞춘 값은 X=5.645m, Y=3.726m.
수동 시험 입력은 **X 5.6m / Y 3.7m**. 자동 적용하지 않았다.
고정 태그 한 지점의 거리만으로 X/Y를 고유하게 결정할 수 없다. 다른 종횡비도 설명 가능하고 NLOS 거리 편향이 존재한다.
이는 측량 결과가 아니며 줄자로 인접 앵커 거리 확인이 필요하다. 지도 크기를 바꾸는 것만으로 거리 노이즈가 없어지지 않는다.

## 다음 검증 순서
1. 현재 지도 치수 유지한 채 태그 약 1m 이동 후 정지해 이동 지연/정지 흔들림 기록.
2. 앵커 1번·2번과 태그 사이 가림/금속 근접 여부를 확인하고, 배치 변경은 하나씩 비교.
3. 높이를 바꿀 경우 앵커와 실제 태그의 높이 차이도 기록. 현재 2D 계산에서 수직 거리 편향에 유의.
4. 실측 X/Y 입력 후 같은 정지 시험 재측정.
5. 품질 가중치·강건 위치 계산은 현재 로그로 먼저 비교하고, 보행 반응을 확인한 뒤 적용.

## 재현
프로젝트 루트에서:
```powershell
./.venv/Scripts/python.exe scripts/report_uwb_stationary.py --output C:/dev/hanmir-runtime/uwb-next --seconds 60
```
원본 상세 로그와 요약은 C:/dev/hanmir-runtime/uwb-stationary-before.jsonl 및 uwb-stationary-after.jsonl,
각 -summary.json, uwb-anchor-transition-replay.json에 보관.

## 상세 통계

### 수정 전
```json
{
  "start": "2026-10-16T14:40:41.069343+00:00",
  "seconds": 60,
  "cycles": 179,
  "status": {
    "computed": 177,
    "failed": 1,
    "ignored": 1
  },
  "reason": {
    "유효한 서로 다른 UWB 앵커가 3개 미만입니다.": 1,
    "out_of_order": 1
  },
  "anchors": {
    "anchor-001": {
      "status": {
        "valid": 165,
        "missing": 14
      },
      "raw_m": {
        "n": 165,
        "median": 3.38952,
        "min": 2.646439,
        "max": 4.718116,
        "std": 0.31189362857703423,
        "p05_p95": [
          3.015872,
          3.7427265999999997
        ]
      },
      "filtered_m": {
        "n": 164,
        "median": 3.272485,
        "min": 2.815621,
        "max": 3.763853,
        "std": 0.25773449700923445,
        "p05_p95": [
          3.075703,
          3.71115
        ]
      },
      "raw_step_m": {
        "n": 164,
        "median": 0.06677899999999992,
        "min": 0.0003420000000002865,
        "max": 1.382536,
        "std": 0.22416449532872104,
        "p05_p95": [
          0.008096850000000155,
          0.5665464499999996
        ]
      },
      "quality": {
        "nlos_suspected": 67,
        "suspect": 95,
        "unknown": 2
      },
      "diagnostics": {
        "rx_power_dbm": {
          "n": 163,
          "median": -87.51641,
          "min": -93.752261,
          "max": -85.187706,
          "std": 1.167666348488104,
          "p05_p95": [
            -89.4144108,
            -85.979518
          ]
        },
        "first_path_power_dbm": {
          "n": 163,
          "median": -99.191319,
          "min": -108.484067,
          "max": -94.607473,
          "std": 2.512590347063483,
          "p05_p95": [
            -106.8713544,
            -97.3205961
          ]
        },
        "power_difference_db": {
          "n": 163,
          "median": 11.818593,
          "min": 5.408262,
          "max": 20.898462,
          "std": 2.6455084901327464,
          "p05_p95": [
            9.6880938,
            17.5852462
          ]
        },
        "peak_minus_first_path_samples": {
          "n": 163,
          "median": 16.9375,
          "min": 5.140625,
          "max": 25.484375,
          "std": 4.722525740004847,
          "p05_p95": [
            6.1140625,
            21.34375
          ]
        }
      }
    },
    "anchor-002": {
      "status": {
        "valid": 179
      },
      "raw_m": {
        "n": 179,
        "median": 3.682184,
        "min": 3.14147,
        "max": 4.596115,
        "std": 0.2964676967947481,
        "p05_p95": [
          3.2330208,
          4.1775213
        ]
      },
      "filtered_m": {
        "n": 178,
        "median": 3.683972,
        "min": 3.20322,
        "max": 4.263894,
        "std": 0.23231685408525152,
        "p05_p95": [
          3.282152,
          4.073896
        ]
      },
      "raw_step_m": {
        "n": 178,
        "median": 0.1563285000000001,
        "min": 0.0023359999999996717,
        "max": 1.3241850000000004,
        "std": 0.236827478110297,
        "p05_p95": [
          0.014091600000000381,
          0.7020626500000002
        ]
      },
      "quality": {
        "suspect": 82,
        "nlos_suspected": 91,
        "nominal": 5
      },
      "diagnostics": {
        "rx_power_dbm": {
          "n": 179,
          "median": -85.105374,
          "min": -88.360364,
          "max": -83.629537,
          "std": 1.003169584148892,
          "p05_p95": [
            -87.279165,
            -84.1546255
          ]
        },
        "first_path_power_dbm": {
          "n": 179,
          "median": -97.928205,
          "min": -108.237359,
          "max": -87.909361,
          "std": 4.485058641873508,
          "p05_p95": [
            -104.0388457,
            -89.5121168
          ]
        },
        "power_difference_db": {
          "n": 179,
          "median": 12.744071,
          "min": 3.329031,
          "max": 23.440005,
          "std": 4.64101138667127,
          "p05_p95": [
            4.5939342000000005,
            19.6164674
          ]
        },
        "peak_minus_first_path_samples": {
          "n": 179,
          "median": 11.0,
          "min": 0.984375,
          "max": 16.484375,
          "std": 2.2741277922934904,
          "p05_p95": [
            7.8421875,
            14.092187499999996
          ]
        }
      }
    },
    "anchor-003": {
      "status": {
        "valid": 179
      },
      "raw_m": {
        "n": 179,
        "median": 3.620239,
        "min": 3.117371,
        "max": 4.382647,
        "std": 0.20165916601364248,
        "p05_p95": [
          3.3154161,
          3.9745418
        ]
      },
      "filtered_m": {
        "n": 178,
        "median": 3.6185665,
        "min": 3.348769,
        "max": 4.080893,
        "std": 0.12574899065201078,
        "p05_p95": [
          3.419472,
          3.824229
        ]
      },
      "raw_step_m": {
        "n": 178,
        "median": 0.15558649999999963,
        "min": 9.999999996956888e-07,
        "max": 0.903546,
        "std": 0.1541857154203382,
        "p05_p95": [
          0.018853349999999967,
          0.4903717499999998
        ]
      },
      "quality": {
        "suspect": 175,
        "nlos_suspected": 3
      },
      "diagnostics": {
        "rx_power_dbm": {
          "n": 179,
          "median": -79.85168,
          "min": -81.281298,
          "max": -73.929983,
          "std": 1.908669172900996,
          "p05_p95": [
            -80.664729,
            -76.080388
          ]
        },
        "first_path_power_dbm": {
          "n": 179,
          "median": -100.173475,
          "min": -108.336873,
          "max": -92.925207,
          "std": 3.2678890439117,
          "p05_p95": [
            -104.7918117,
            -94.4932345
          ]
        },
        "power_difference_db": {
          "n": 179,
          "median": 20.514964,
          "min": 16.858602,
          "max": 27.992833,
          "std": 1.9967589927675449,
          "p05_p95": [
            18.1941966,
            24.4962936
          ]
        },
        "peak_minus_first_path_samples": {
          "n": 179,
          "median": 7.046875,
          "min": 5.3125,
          "max": 11.1875,
          "std": 0.8232953599849523,
          "p05_p95": [
            6.09375,
            8.495312499999999
          ]
        }
      }
    },
    "anchor-004": {
      "status": {
        "valid": 178,
        "missing": 1
      },
      "raw_m": {
        "n": 178,
        "median": 2.885299,
        "min": 2.210353,
        "max": 3.360933,
        "std": 0.21679791711443616,
        "p05_p95": [
          2.5035384,
          3.1979357
        ]
      },
      "filtered_m": {
        "n": 177,
        "median": 2.895119,
        "min": 2.504505,
        "max": 3.115852,
        "std": 0.12696619173986987,
        "p05_p95": [
          2.6346344,
          3.0223722
        ]
      },
      "raw_step_m": {
        "n": 177,
        "median": 0.18042200000000008,
        "min": 0.004692999999999614,
        "max": 0.8816069999999998,
        "std": 0.1776223541885883,
        "p05_p95": [
          0.022633399999999873,
          0.5797327999999998
        ]
      },
      "quality": {
        "suspect": 158,
        "nlos_suspected": 19
      },
      "diagnostics": {
        "rx_power_dbm": {
          "n": 178,
          "median": -84.593849,
          "min": -86.435956,
          "max": -83.589151,
          "std": 0.4196708422062141,
          "p05_p95": [
            -85.28475540000001,
            -83.967037
          ]
        },
        "first_path_power_dbm": {
          "n": 178,
          "median": -95.8736145,
          "min": -105.175412,
          "max": -93.880003,
          "std": 1.5020368392355117,
          "p05_p95": [
            -98.45397285,
            -94.5813511
          ]
        },
        "power_difference_db": {
          "n": 178,
          "median": 11.1549135,
          "min": 9.361765,
          "max": 20.581563,
          "std": 1.5514540944404263,
          "p05_p95": [
            10.008447400000001,
            14.06534575
          ]
        },
        "peak_minus_first_path_samples": {
          "n": 178,
          "median": 14.90625,
          "min": 6.9375,
          "max": 19.296875,
          "std": 3.4382167473242355,
          "p05_p95": [
            7.3453125,
            17.461718750000003
          ]
        }
      }
    }
  },
  "candidate_position": {
    "n": 177,
    "center": [
      2.143,
      1.969
    ],
    "span_xy": [
      0.7579999999999998,
      1.525
    ],
    "radius_from_median_m": {
      "n": 177,
      "median": 0.198338095180931,
      "min": 0.02061552812808825,
      "max": 0.8506826670386556,
      "std": 0.1762427232017385,
      "p05_p95": [
        0.06705918420306808,
        0.6534879341500237
      ]
    },
    "step_m": {
      "n": 176,
      "median": 0.06868696366632389,
      "min": 0.0,
      "max": 1.1138850928170283,
      "std": 0.2768475872205062,
      "p05_p95": [
        0.011857369452070565,
        0.9653947370362399
      ]
    }
  },
  "filtered_position": {
    "n": 177,
    "center": [
      2.1767978831895034,
      1.9453277040001618
    ],
    "span_xy": [
      0.34282101185607305,
      0.7009946036804162
    ],
    "radius_from_median_m": {
      "n": 177,
      "median": 0.12969135969558973,
      "min": 0.018931650714505706,
      "max": 0.4770768329588481,
      "std": 0.08912019034214858,
      "p05_p95": [
        0.08630132398504009,
        0.3287980837196326
      ]
    },
    "step_m": {
      "n": 176,
      "median": 0.0,
      "min": 0.0,
      "max": 0.3417592904413936,
      "std": 0.06145648926453344,
      "p05_p95": [
        0.0,
        0.15668343817838942
      ]
    }
  },
  "final_position": {
    "n": 179,
    "center": [
      2.1767978831895034,
      1.9453277040001618
    ],
    "span_xy": [
      0.34282101185607305,
      0.7009946036804162
    ],
    "radius_from_median_m": {
      "n": 179,
      "median": 0.12969135969558973,
      "min": 0.018931650714505706,
      "max": 0.4770768329588481,
      "std": 0.08884093988127487,
      "p05_p95": [
        0.08547783515200376,
        0.32803008293527736
      ]
    },
    "step_m": {
      "n": 178,
      "median": 0.0,
      "min": 0.0,
      "max": 0.3417592904413936,
      "std": 0.06118736532632329,
      "p05_p95": [
        0.0,
        0.15562929629989233
      ]
    }
  },
  "confidence": {
    "n": 177,
    "median": 0.86,
    "min": 0.821,
    "max": 0.997,
    "std": 0.034966503809352956,
    "p05_p95": [
      0.8328,
      0.9363999999999999
    ]
  },
  "server_interval_seconds": {
    "n": 178,
    "median": 0.2941558361053467,
    "min": 0.10586738586425781,
    "max": 0.9470686912536621,
    "std": 0.1816244310106457,
    "p05_p95": [
      0.1300649881362915,
      0.683934533596039
    ]
  },
  "room_assumption_fits": [
    {
      "aspect_X_over_Y": 1.5151515151515151,
      "assumed_vertical_gap_m": 0,
      "X_m": 5.645423371615534,
      "Y_m": 3.7259794252662526,
      "tag_xy_m": [
        2.5091892594438288,
        2.1331336709762625
      ],
      "residual_rmse_m": 0.09947559041871432
    },
    {
      "aspect_X_over_Y": 1.5151515151515151,
      "assumed_vertical_gap_m": 1,
      "X_m": 5.388687933195132,
      "Y_m": 3.556534035908787,
      "tag_xy_m": [
        2.365884262378407,
        2.061281552590862
      ],
      "residual_rmse_m": 0.09947559041871441
    },
    {
      "aspect_X_over_Y": 1,
      "assumed_vertical_gap_m": 0,
      "X_m": 4.780861355809818,
      "Y_m": 4.780861355809818,
      "tag_xy_m": [
        2.0202114356760896,
        2.6009682328500143
      ],
      "residual_rmse_m": 0.09947559041871429
    },
    {
      "aspect_X_over_Y": 1,
      "assumed_vertical_gap_m": 1,
      "X_m": 4.563022077016579,
      "Y_m": 4.563022077016579,
      "tag_xy_m": [
        1.8936174788046312,
        2.5020996825415325
      ],
      "residual_rmse_m": 0.09947559041871422
    },
    {
      "aspect_X_over_Y": 2,
      "assumed_vertical_gap_m": 0,
      "X_m": 6.043300446765397,
      "Y_m": 3.0216502233826983,
      "tag_xy_m": [
        2.728769399861463,
        1.8439380561006067
      ],
      "residual_rmse_m": 0.09947559041871509
    },
    {
      "aspect_X_over_Y": 2,
      "assumed_vertical_gap_m": 1,
      "X_m": 5.7671256492372445,
      "Y_m": 2.8835628246186222,
      "tag_xy_m": [
        2.576656588624155,
        1.7908463925005595
      ],
      "residual_rmse_m": 0.09947559041871493
    }
  ]
}
```
### 수정 후
```json
{
  "start": "2026-10-16T14:45:52.930972+00:00",
  "seconds": 60,
  "cycles": 180,
  "status": {
    "computed": 164,
    "position_rejected": 14,
    "failed": 2
  },
  "reason": {
    "anchor_set_change_pending": 14,
    "유효한 서로 다른 UWB 앵커가 3개 미만입니다.": 2
  },
  "anchors": {
    "anchor-001": {
      "status": {
        "valid": 166,
        "missing": 14
      },
      "raw_m": {
        "n": 166,
        "median": 3.642835,
        "min": 3.019918,
        "max": 5.167313,
        "std": 0.1861795210660635,
        "p05_p95": [
          3.534008,
          3.8135585
        ]
      },
      "filtered_m": {
        "n": 166,
        "median": 3.640602,
        "min": 3.50391,
        "max": 3.835476,
        "std": 0.05190396996773741,
        "p05_p95": [
          3.589765,
          3.7651492500000003
        ]
      },
      "raw_step_m": {
        "n": 165,
        "median": 0.051369999999999916,
        "min": 0.000672000000000228,
        "max": 1.8614000000000002,
        "std": 0.23074547087228786,
        "p05_p95": [
          0.006163600000000269,
          0.4814697999999996
        ]
      },
      "quality": {
        "suspect": 135,
        "unknown": 6,
        "nlos_suspected": 25
      },
      "diagnostics": {
        "rx_power_dbm": {
          "n": 160,
          "median": -87.850385,
          "min": -92.463101,
          "max": -86.685329,
          "std": 1.0033255501665903,
          "p05_p95": [
            -90.73950715000001,
            -87.228906
          ]
        },
        "first_path_power_dbm": {
          "n": 160,
          "median": -99.50676150000001,
          "min": -103.465412,
          "max": -93.6883,
          "std": 1.1244233984548742,
          "p05_p95": [
            -101.0814628,
            -98.0122262
          ]
        },
        "power_difference_db": {
          "n": 160,
          "median": 11.4219665,
          "min": 6.459394,
          "max": 16.236506,
          "std": 1.4805121142934934,
          "p05_p95": [
            8.30835195,
            13.337873749999998
          ]
        },
        "peak_minus_first_path_samples": {
          "n": 160,
          "median": 6.8203125,
          "min": 5.21875,
          "max": 24.921875,
          "std": 4.855772982309001,
          "p05_p95": [
            5.76484375,
            16.140625
          ]
        }
      }
    },
    "anchor-002": {
      "status": {
        "valid": 177,
        "missing": 3
      },
      "raw_m": {
        "n": 177,
        "median": 3.46381,
        "min": 3.033895,
        "max": 4.40347,
        "std": 0.34784749074886306,
        "p05_p95": [
          3.2088608,
          4.2729174
        ]
      },
      "filtered_m": {
        "n": 177,
        "median": 3.435667,
        "min": 3.129262,
        "max": 4.301842,
        "std": 0.3228439017172359,
        "p05_p95": [
          3.257952,
          4.235411
        ]
      },
      "raw_step_m": {
        "n": 176,
        "median": 0.10356200000000015,
        "min": 1.8999999999991246e-05,
        "max": 1.2835790000000005,
        "std": 0.2203608160326189,
        "p05_p95": [
          0.006061500000000053,
          0.6375190000000001
        ]
      },
      "quality": {
        "nlos_suspected": 68,
        "suspect": 108,
        "nominal": 1
      },
      "diagnostics": {
        "rx_power_dbm": {
          "n": 177,
          "median": -85.685294,
          "min": -87.146574,
          "max": -84.075371,
          "std": 0.48916455747495297,
          "p05_p95": [
            -86.519878,
            -84.99266300000001
          ]
        },
        "first_path_power_dbm": {
          "n": 177,
          "median": -97.906412,
          "min": -107.542631,
          "max": -88.713864,
          "std": 3.412938627867263,
          "p05_p95": [
            -103.172053,
            -92.806143
          ]
        },
        "power_difference_db": {
          "n": 177,
          "median": 12.097806,
          "min": 4.638493,
          "max": 22.38081,
          "std": 3.233044801605292,
          "p05_p95": [
            7.2340306,
            16.797921999999996
          ]
        },
        "peak_minus_first_path_samples": {
          "n": 177,
          "median": 11.5,
          "min": 1.84375,
          "max": 16.640625,
          "std": 2.1961696914909954,
          "p05_p95": [
            8.678125,
            15.23125
          ]
        }
      }
    },
    "anchor-003": {
      "status": {
        "valid": 178,
        "missing": 2
      },
      "raw_m": {
        "n": 178,
        "median": 3.65503,
        "min": 3.208243,
        "max": 4.078445,
        "std": 0.13635423405963146,
        "p05_p95": [
          3.4496974999999996,
          3.8896055
        ]
      },
      "filtered_m": {
        "n": 178,
        "median": 3.655743,
        "min": 3.480201,
        "max": 3.842582,
        "std": 0.07217168632487758,
        "p05_p95": [
          3.5508074,
          3.7907822
        ]
      },
      "raw_step_m": {
        "n": 177,
        "median": 0.13497899999999996,
        "min": 0.00034700000000009723,
        "max": 0.6210019999999998,
        "std": 0.11523993636678401,
        "p05_p95": [
          0.01728439999999978,
          0.3542567999999998
        ]
      },
      "quality": {
        "suspect": 178
      },
      "diagnostics": {
        "rx_power_dbm": {
          "n": 178,
          "median": -79.5508835,
          "min": -80.014037,
          "max": -74.141876,
          "std": 1.8631610265260725,
          "p05_p95": [
            -79.8392343,
            -74.444695
          ]
        },
        "first_path_power_dbm": {
          "n": 178,
          "median": -97.266948,
          "min": -100.011013,
          "max": -91.398594,
          "std": 1.9801011180630361,
          "p05_p95": [
            -99.13322765000001,
            -93.10808645
          ]
        },
        "power_difference_db": {
          "n": 178,
          "median": 18.589892,
          "min": 16.014469,
          "max": 21.391498,
          "std": 0.7906568068801099,
          "p05_p95": [
            17.5451167,
            20.014652350000002
          ]
        },
        "peak_minus_first_path_samples": {
          "n": 178,
          "median": 6.5859375,
          "min": 5.703125,
          "max": 7.546875,
          "std": 0.40743373482806217,
          "p05_p95": [
            5.921875,
            7.26796875
          ]
        }
      }
    },
    "anchor-004": {
      "status": {
        "valid": 178,
        "missing": 2
      },
      "raw_m": {
        "n": 178,
        "median": 2.854299,
        "min": 2.089434,
        "max": 4.211771,
        "std": 0.3069593300093827,
        "p05_p95": [
          2.47837765,
          3.44396515
        ]
      },
      "filtered_m": {
        "n": 178,
        "median": 2.8266720000000003,
        "min": 2.509786,
        "max": 3.593546,
        "std": 0.20550262347975382,
        "p05_p95": [
          2.661171,
          3.431726
        ]
      },
      "raw_step_m": {
        "n": 177,
        "median": 0.23392800000000014,
        "min": 0.0,
        "max": 1.0038690000000003,
        "std": 0.22857106724143278,
        "p05_p95": [
          0.030105000000000007,
          0.7721513999999996
        ]
      },
      "quality": {
        "suspect": 146,
        "nlos_suspected": 32
      },
      "diagnostics": {
        "rx_power_dbm": {
          "n": 178,
          "median": -84.676181,
          "min": -87.690896,
          "max": -83.400909,
          "std": 0.6376913557948312,
          "p05_p95": [
            -86.10881355000001,
            -84.02994695
          ]
        },
        "first_path_power_dbm": {
          "n": 178,
          "median": -95.5901465,
          "min": -107.014118,
          "max": -93.047655,
          "std": 2.3549129237915043,
          "p05_p95": [
            -102.03571205,
            -94.31397695000001
          ]
        },
        "power_difference_db": {
          "n": 178,
          "median": 10.9369365,
          "min": 7.512758,
          "max": 22.485922,
          "std": 2.3410395460636777,
          "p05_p95": [
            9.097557100000001,
            16.782417050000003
          ]
        },
        "peak_minus_first_path_samples": {
          "n": 178,
          "median": 13.3671875,
          "min": 7.046875,
          "max": 20.953125,
          "std": 3.095319122756011,
          "p05_p95": [
            9.15234375,
            17.80703125
          ]
        }
      }
    }
  },
  "candidate_position": {
    "n": 178,
    "center": [
      2.237,
      2.0965
    ],
    "span_xy": [
      0.9990000000000001,
      1.8830000000000002
    ],
    "radius_from_median_m": {
      "n": 178,
      "median": 0.28303048126418473,
      "min": 0.011672617529929074,
      "max": 1.140259290687868,
      "std": 0.2558517837073481,
      "p05_p95": [
        0.0649178695719977,
        0.8218511870701986
      ]
    },
    "step_m": {
      "n": 177,
      "median": 0.07884795495128587,
      "min": 0.0,
      "max": 1.1244914406077084,
      "std": 0.27934825670393226,
      "p05_p95": [
        0.009358261933272704,
        0.8708787185290975
      ]
    }
  },
  "filtered_position": {
    "n": 164,
    "center": [
      2.2921093641603547,
      2.12592105974604
    ],
    "span_xy": [
      0.490505606696646,
      1.051899354061765
    ],
    "radius_from_median_m": {
      "n": 164,
      "median": 0.205620797527668,
      "min": 0.012747573041881519,
      "max": 0.6570638097355364,
      "std": 0.18142540243205485,
      "p05_p95": [
        0.03822172631905347,
        0.5412422629724319
      ]
    },
    "step_m": {
      "n": 163,
      "median": 0.0,
      "min": 0.0,
      "max": 0.20522003614951914,
      "std": 0.049836618876679,
      "p05_p95": [
        0.0,
        0.142971733486935
      ]
    }
  },
  "final_position": {
    "n": 180,
    "center": [
      2.294171086704231,
      2.12592105974604
    ],
    "span_xy": [
      0.490505606696646,
      1.051899354061765
    ],
    "radius_from_median_m": {
      "n": 180,
      "median": 0.20708244268968728,
      "min": 0.013664271166055567,
      "max": 0.6563271352890485,
      "std": 0.1833047203230675,
      "p05_p95": [
        0.03996586183256505,
        0.5406463039772528
      ]
    },
    "step_m": {
      "n": 179,
      "median": 0.0,
      "min": 0.0,
      "max": 0.20522003614951914,
      "std": 0.048199679539274336,
      "p05_p95": [
        0.0,
        0.1344573246071592
      ]
    }
  },
  "confidence": {
    "n": 164,
    "median": 0.845,
    "min": 0.804,
    "max": 0.874,
    "std": 0.015725772892788138,
    "p05_p95": [
      0.81015,
      0.861
    ]
  },
  "server_interval_seconds": {
    "n": 179,
    "median": 0.3031582832336426,
    "min": 0.12117433547973633,
    "max": 1.7297863960266113,
    "std": 0.17127989401601115,
    "p05_p95": [
      0.1421367645263672,
      0.5894985437393185
    ]
  },
  "room_assumption_fits": [
    {
      "aspect_X_over_Y": 1.5151515151515151,
      "assumed_vertical_gap_m": 0,
      "X_m": 5.6634884685177225,
      "Y_m": 3.737902389221697,
      "tag_xy_m": [
        2.631913798269267,
        2.161319775072565
      ],
      "residual_rmse_m": 0.23760859166244702
    },
    {
      "aspect_X_over_Y": 1.5151515151515151,
      "assumed_vertical_gap_m": 1,
      "X_m": 5.408800926020548,
      "Y_m": 3.5698086111735616,
      "tag_xy_m": [
        2.4951604855115233,
        2.091039822663079
      ],
      "residual_rmse_m": 0.23760859166244713
    },
    {
      "aspect_X_over_Y": 1,
      "assumed_vertical_gap_m": 0,
      "X_m": 4.802047309626921,
      "Y_m": 4.802047309626921,
      "tag_xy_m": [
        2.1653455487362856,
        2.628602683689236
      ],
      "residual_rmse_m": 0.23760859166244708
    },
    {
      "aspect_X_over_Y": 1,
      "assumed_vertical_gap_m": 1,
      "X_m": 4.586833429068379,
      "Y_m": 4.586833429068379,
      "tag_xy_m": [
        2.046680606512029,
        2.5316737318707543
      ],
      "residual_rmse_m": 0.23760859166244697
    },
    {
      "aspect_X_over_Y": 2,
      "assumed_vertical_gap_m": 0,
      "X_m": 6.058948908777068,
      "Y_m": 3.029474454388534,
      "tag_xy_m": [
        2.842686723819298,
        1.87547476691237
      ],
      "residual_rmse_m": 0.23760859166244788
    },
    {
      "aspect_X_over_Y": 2,
      "assumed_vertical_gap_m": 1,
      "X_m": 5.784422940458359,
      "Y_m": 2.8922114702291797,
      "tag_xy_m": [
        2.6965588790617514,
        1.823963705700855
      ],
      "residual_rmse_m": 0.2376085916624477
    }
  ]
}
```


## 후속: 30cm 이동 확인 강화 및 아이콘 축소
- 기존 30cm 이상 2회 → 같은 방향(첫 후보와 내적 0.8 이상) 3회 연속 확인으로 변경.
- 이동 상태에서 작은 후보 변화가 5회 → 3회 이어지면 정지 상태로 복귀.
- 이동 중 EMA 보간은 유지. 30cm는 실제 이동거리의 보증이 아니라 중앙값 후보와 표시 기준점의 차이.
- 약 3Hz 수신에서 확인용 세 표본은 약 0.7초 간격을 차지하며 중앙값 필터 등의 지연이 추가될 수 있음.
- 관리자 지도 아이콘과 방향 표시 75%, 모바일 점 9→7 SVG 단위. 이름/비상 라벨은 유지.
- 방향 갱신과 카메라/음성 설정은 변경하지 않음. 웹 TypeScript 빌드 성공.
- 동일 방향의 지속적인 거리 편향은 실제 이동과 혼동 가능. 보행 시험 미실시.
- 30초 후속 로그: C:/dev/hanmir-runtime/uwb-motion-confirm3/

후속 정지 측정 30초: 82회 수신, 80회 계산, 1회 무시, 1회 계산 실패. 표시 좌표 X/Y 범위 및 최대 순간 이동 모두 0m. 이 구간에서 표시가 유지됐다는 뜻이며 실제 측위 오차가 0이라는 뜻은 아니다. 보행 반응은 아직 검증 전.


---

## 부록 16. UWB_100MS_TRIAL_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/UWB_100MS_TRIAL_2026-10-17.md

# UWB 100ms 시험 준비

사용자 요청: 1m 이동 시험 대신 수신 주기를 0.1초로 시험.
기본 300ms/150ms 슬롯은 유지하고 tag-10hz 및 anchor-01-10hz 별도 PlatformIO 환경 추가.
시험값: TDMA 100ms, 태그 슬롯 60ms, 가드 20ms. TAG_ID=0 한 대만 지원.
태그의 동기 상실 시간은 기존과 같은 900ms로 유지. 앵커 2~4는 poll 응답 방식이므로 프로토콜 변경 없음.
태그와 1번 앵커의 frame/slot 값이 일치해야 동기화됨. 둘 중 하나만 업로드하면 위치 수신이 중단될 수 있음.
태그 기본 환경으로 복구 시 1번 앵커도 기본 환경으로 함께 복구.
카메라/음성/지도 필터는 이번 변경에서 수정하지 않음.
100ms는 목표 무선 주기이며 서버 실제 10Hz를 보장하지 않음. 마스터 RX 대기, 재동기화, HTTP 전달 지연을 측정해야 함.
샘플 기반 3회 확인의 시간 폭은 수신률 증가에 따라 짧아지므로 정지 흔들림도 재검증해야 함.
빌드 위치 C:/dev/hanmir-uwb-link/uwb_multi_test, 정상 도구 환경 pio-fast 사용.
기존 pio-core에는 toolchain 헤더 누락이 있어 사용하지 않음.
업로드 전 장치 식별 및 현재 펌웨어 백업 필요. 1번 앵커 USB 연결 대기.
아직 실제 100ms 수신 검증 및 업로드 완료로 보고하지 않음.

## 실제 적용 및 45초 결과
태그 COM6 및 1번 앵커 COM7 앱 0x10000 업로드 완료. esptool 해시 검증 성공.
백업: C:/dev/hanmir-runtime/uwb-100ms-backup/ (태그 파일은 0x8000부터 시작하므로 app0 복구 시 앞 0x8000 바이트 제외 필요).
앱 빌드: 태그 824713 / 1310720 bytes (62.9%), 앵커 285661 / 1310720 (21.8%). 정적 RAM 태그 51752 bytes, 앵커 21800 bytes; 런타임 힙 실측값 아님.
45초 서버 수신 172회 (3.82Hz), 계산 성공166, 실패4, 위치 보류2.
서버 도착 간격 중앙176ms, 95백분위583ms, 최대787ms.
같은 세션의 기기 cycle_id 증가418 / 기기 시간44.329초 = 무선 측정9.43Hz.
입력 JSON 재직렬화 평균 약6583 bytes. HTTP 헤더/실제 무선 트래픽 포함 수치는 아님.
무선 측정 100ms 목표에 접근했으나 서버 10Hz는 미달. 전송 큐/HTTP 경로 후속 진단 필요.
30cm 필터와 카메라/음성 설정은 그대로 유지. 배치 변경 가능성 때문에 이번 좌표 변화는 정지 정확도 비교에 사용하지 않음.
원본 로그: C:/dev/hanmir-runtime/uwb-10hz-live/uwb-stationary.jsonl


---

## 부록 17. UWB_HTTP_BOTTLENECK_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/UWB_HTTP_BOTTLENECK_2026-10-17.md

# UWB HTTP 병목 개선 기록 — 2026-10-17

## 변경 범위
태그 전송과 UWB 서버 수신 경로만 변경. 카메라·음성·위치 30cm/동일 방향 3회 필터 그대로.
1번 앵커는 앞선 100ms 펌웨어 유지. 2~4번은 poll 응답 방식이어서 이번 추가 업데이트 필요 없음.

## 단계별 실제 기록
|단계|관측 길이|서버 Hz|간격 중앙값|
|---|---:|---:|---:|
|100ms 무선 + 기존 HTTP|30초|3.87|173ms|
|TCP 재사용 + compact ACK|45초|5.56|127ms|
|로그 만료 검사 60초 간격|45초|5.56|125ms|
|TCP_NODELAY 추가|45초|4.38|124ms|
표본 RF 상황이 다르므로 단순 인과 비교에는 제한이 있다. TCP_NODELAY만으로 목표 달성 못함.
HTTP 응답 대기 -11 오류 및 서버 처리 대기 존재. 초기 UART HTTP 왕복138~145ms.
서버 프로파일 표본58ms 중 만료 파일 검사28ms. 상세 JSONL은 계속 저장하고 만료 검사만60초로 변경.
기존 클래스 기본값은 요청마다 검사, 운영 UWB 인스턴스만60초 사용. 만료 삭제 최대60초 지연 가능.

## 지속 연결 시험 구조
/api/uwb/stream WebSocket → 같은 upload_distances → 같은 순서 잠금/DB/필터/로그 → ack:cycle:status.
태그 전송 후 ACK를 기다리며 다음 전송을 막지 않음. 미확인 최대4개, 1초 초과시 재연결.
연결 복구 시 최신 큐 항목 사용, 오래된 샘플은 전송 제한. 서버가 처리한 뒤에만 ACK.
USB 진단의 기존 http_duration_us/http_age_us 필드는 WS에서는 전송→서버 ACK / 측정→서버 ACK 시간 의미.
측정 카운트, 송신 시도, 서버 성공 ACK, 화면 위치 반영은 구분해야 함.
빌드환경 tag-10hz-ws(WebSockets2.6.1), 기존 tag-10hz는 HTTP 복구용.
단위시험18개 통과. 카메라/음성은 사용자가 1차 HTTP 수정 이후 정상이라고 확인.

## 로그 위치
C:/dev/hanmir-runtime/uwb-http-before, uwb-http-after, uwb-http-final, uwb-http-nodelay
각 폴더의 uwb-stationary.jsonl/summary.json. UART는 같은 상위 폴더의 각 *-uart.log.
서버 프로파일 backend/logs/uwb-http-profile-*.txt.
WS 실제 적용 결과는 후속 기록으로 추가한다.


## 사용자 확인 후 작업 종료
사용자가 현재 추종 속도로 충분하다고 확인하여 추가 튜닝 중단.
현재 실제 태그 펌웨어: uwb-net-20261017.3, tag-10hz-ws, USB 460800 baud.
921600 baud(.4)는 준비/빌드만 했고 업로드하지 않았으며 소스도 실제 적용값으로 복구.
주의: C:/dev/hanmir-uwb-link의 빌드 산출물에는 미적용 시험본이 있을 수 있으므로 재사용하지 말고 저장소 소스로 다시 빌드할 것.
태그 및 1번 앵커가 100ms 프로파일. 2~4번은 추가 업로드 불필요.
실제 서버 적용: WebSocket 입력, 기존 위치 필터 유지, UWB 로그 만료검사60초, 필터 이력 SQLite WAL/NORMAL,
요청 내 DB 연결 재사용, 동일 LOCATION_FAILED 이벤트는5초 간격(각 실패 원본 JSONL 기록 유지).
WAL/NORMAL은 전원 손실시 최근 필터 이력 일부가 소실될 수 있으나 이벤트 DB 설정은 변경하지 않음.
첫 WS 60초 결과: 서버531회(8.85Hz), 간격 중앙80.7ms,95백분위373.8ms,최대741.8ms.
해당 구간 좌표계산 성공510회, 실패18회, 보류3회. 서버10Hz 고정 도달로 보고하지 않음.
동시 카메라 표본: 수신13.02FPS, YOLO8.97FPS, 상세2.95FPS. 모든 구간10FPS 유지는 미확인.
다른 튜닝 구간에는 빌드/시험 부하와 RF 품질 변동도 있어 성능 인과를 단정하지 않음.
사용자는 카메라·음성 정상 및 추종 속도 충분함을 확인. 가장 최근 로그 uwb-ws-optimized 폴더 및 -camera.jsonl에 보존.
단위시험: 기존로그/스트림18개, wifi-ws 검증2개, 거리필터/스트림/앵커전환27개 통과(일부 중복).


---

## 부록 18. UWB_MOVEMENT_STUTTER_ANALYSIS_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/UWB_MOVEMENT_STUTTER_ANALYSIS_2026-10-17.md

# UWB 이동 추종 끊김 분석 — 2026-10-17

사용자: 동일 속도로 이동해도 추종 지연이 달라지고 아이콘이 뛰엄뛰엄 움직임.
이번 작업은 분석만 수행. 서버·펌웨어·화면 설정 변경 및 재시작 없음.

## 실로그
KST 00:35:43~00:37:44 약119초, 686회 기록. 정지/이동 시점의 외부 정답 표시는 없으므로 전 구간을 연속 보행으로 취급하면 안 됨.
기록률5.75Hz, 처리완료 로그 간격 중앙78.8ms /95백분위606.6ms /최대2103.5ms.
server_received_at(처리 시작)~logged_at_unix 구간 중앙41.2ms /95백분위395.1ms /최대1927.8ms.
이 구간은 전체 무선/화면 지연이 아니라 서버 처리시간의 근사값. 로그 시각은 소켓 도착 시각과 동일하지 않음.
1cm 초과 표시 이동 1회의 크기 중앙10.9cm /95백분위56.1cm /최대84.2cm.
2.745초 동안 갱신이 없다가84.2cm 옮겨진 사례 확인. 해당 구간 수신5회, 계산 성공5회, 최대 처리완료 로그 간격1.981초.
31.7초 등 긴 위치 유지 구간도 있으나 실제 정지 여부를 몰라 이를 추종 지연이라고 단정하지 않음.

## 확인된 필터 구조 문제
정지 판정: 후보 좌표의 표본 간 이동<=8cm가3회이면 정지 복귀.
100ms 주기에서0.5m/s 등속 보행은 표본당5cm이므로 정지 후보로 계산된다.
정지 복귀 후30cm/같은 방향3회 확인을 다시 기다려 멈춤→이동을 반복할 수 있다.
이번에 강화한 정지 기준이100ms 표본 간격을 고려하지 못한 문제다.
현행 필터를 별도 프로세스에서 잡음 없는0.5m/s·10Hz 입력으로6초 재생:
이동 시작0.9,1.6,2.3,3.0,3.7,4.4,5.1,5.8초.
잘못된 정지 복귀1.1,1.8,2.5,3.2,3.9,4.6,5.3,6.0초.
표시좌표 최대 후행0.419m. 실제 센서 결과가 아니라 알고리즘 합성 재현 결과다.

## 화면 표시
SiteMap은 SVG transform 위치를 수신 좌표로 즉시 교체. 위치 보간 없음.
HeadingArrow의80ms 애니메이션은 방향 회전에만 적용.
따라서 서버가 새 좌표를 주면10~80cm를 한 번에 이동한 것처럼 보일 수 있다.

## 권장 최소 수정
1. 시작 기준30cm는 유지.
2. 정지 판정을 표본당8cm 대신 최근0.5~0.8초 구간의 이동량/속도/분산에 따라 판단. 초기 후보 범위이며 적용 전 정지 및 느린 보행 로그 재생 필요.
3. 이동 중 매번30cm 확인을 다시 하지 않도록 이동/정지 상태 전환 개선.
4. 서버 좌표/위험구역 계산은 그대로 두고 화면만80~120ms 목표점 보간. 외삽은 하지 않고 데이터 끊김 표시 유지. 화면 보간에는 추가 표시 지연이 발생할 수 있음.
5. 간헐적인 서버 처리1~2초 지연은 별도 추적. 보간만으로 해결됐다고 보고하면 안 됨.

원본: C:/dev/hanmir-runtime/uwb-motion-review-20261017.jsonl
합성 재생: C:/dev/hanmir-runtime/uwb-constant-speed-replay.json

## 상세 요약
```json
{
  "cycles": 686,
  "duration_s": 119.1876311302185,
  "hz": 5.747240661672375,
  "status": {
    "computed": 662,
    "failed": 17,
    "position_rejected": 7
  },
  "reasons": {
    "기존 위치 계산이 제한 회차 안에 수렴하지 않았습니다.": 4,
    "anchor_set_change_pending": 7,
    "유효한 서로 다른 UWB 앵커가 3개 미만입니다.": 13
  },
  "arrival_ms": {
    "p50": 78.77,
    "p95": 606.599,
    "max": 2103.535
  },
  "processing_ms": {
    "p50": 41.192,
    "p95": 395.144,
    "max": 1927.815
  },
  "position_steps_m": {
    "p50": 0.109,
    "p95": 0.561,
    "max": 0.842
  },
  "position_update_gap_ms": {
    "p50": 122.428,
    "p95": 2516.811,
    "max": 31684.198
  },
  "held_fraction": 0.8350364963503649,
  "xy_span_m": [
    3.069254931559693,
    3.277613793617493
  ],
  "start": "2026-10-16T15:35:43.966089Z",
  "end": "2026-10-16T15:37:44.099057Z",
  "long_update_gaps": [
    {
      "gap_s": 31.684,
      "cycles": 281,
      "largest_arrival_ms": 667,
      "step_m": 0.178,
      "status": {
        "computed": 280,
        "failed": 1
      }
    },
    {
      "gap_s": 25.476,
      "cycles": 58,
      "largest_arrival_ms": 2044,
      "step_m": 0.342,
      "status": {
        "computed": 55,
        "failed": 3
      }
    },
    {
      "gap_s": 13.842,
      "cycles": 103,
      "largest_arrival_ms": 683,
      "step_m": 0.128,
      "status": {
        "computed": 103
      }
    },
    {
      "gap_s": 4.096,
      "cycles": 31,
      "largest_arrival_ms": 576,
      "step_m": 0.168,
      "status": {
        "computed": 31
      }
    },
    {
      "gap_s": 3.293,
      "cycles": 31,
      "largest_arrival_ms": 516,
      "step_m": 0.188,
      "status": {
        "computed": 28,
        "failed": 3
      }
    },
    {
      "gap_s": 2.745,
      "cycles": 5,
      "largest_arrival_ms": 1981,
      "step_m": 0.842,
      "status": {
        "computed": 5
      }
    },
    {
      "gap_s": 2.33,
      "cycles": 3,
      "largest_arrival_ms": 1739,
      "step_m": 0.294,
      "status": {
        "computed": 3
      }
    },
    {
      "gap_s": 1.98,
      "cycles": 15,
      "largest_arrival_ms": 606,
      "step_m": 0.08,
      "status": {
        "computed": 11,
        "position_rejected": 2,
        "failed": 2
      }
    },
    {
      "gap_s": 1.604,
      "cycles": 3,
      "largest_arrival_ms": 1059,
      "step_m": 0.542,
      "status": {
        "position_rejected": 2,
        "computed": 1
      }
    },
    {
      "gap_s": 1.597,
      "cycles": 5,
      "largest_arrival_ms": 665,
      "step_m": 0.652,
      "status": {
        "failed": 2,
        "position_rejected": 2,
        "computed": 1
      }
    }
  ]
}
```


---

## 부록 19. UWB_LAP_REVIEW_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/UWB_LAP_REVIEW_2026-10-17.md

# UWB 한 바퀴 이동 분석 — 2026-10-17

설정 변경 없이 기록. 사용자는 한 바퀴를 일정 속도로 이동했고 화면이 잘 움직였다고 보고.
총89.7초776회. 좌표 변화가 큰 구간은 기록 시작 약30~60초. 정확한 물리적 출발/정지 시각이나 기준 경로 측정이 없으므로 이동 속도 오차/실제 추종 지연을 확정할 수 없음.

## 표준편차 해석
전체 좌표 표준편차 X1.02m/Y0.79m는 경로를 실제 이동한 공간적 분산을 포함한다. 정지 위치 오차로 해석하면 안 된다.
원시 앵커 거리도 이동하면 실제로 변하므로 전체 표준편차에 실제 이동과 측정 잡음이 섞인다.
정지 구간 분산, 같은 위치 복귀 차이, 표본 도착 간격, 한 번의 위치 이동량을 따로 봐야 한다.

## 실제 기록
- 서버 처리완료 로그 약8.64Hz. 간격 중앙65ms/95백분위445ms/최대1393ms. 값이 몰려 처리될 수 있어 중앙값만으로15Hz라고 해석하면 안 됨.
- 서버 처리시간 근사값 중앙33.8ms/95백분위287.5ms/최대644.9ms.
- 1cm 초과 표시 이동 중앙9.3cm/95백분위22.7cm/최대46.0cm.
- 출발/종료 중심 차이 약21.1cm. 출발/종료 지점을 정확히 같게 두었다는 조건에서 참고 가능한 복귀 편차이며 절대 정확도가 아님.
- 마지막10초 좌표 표준편차 X16.2cm/Y16.2cm, 전체 범위 X39.3cm/Y80.5cm. 이 구간이 실제 완전 정지였다면 잔여 흔들림이 존재한다.
- 표시 경로 누적17.58m에는 측정 흔들림이 포함되므로 실제 걸은 거리로 제시하지 않음.
- 계산 성공739회/실패22회/위치 보류15회.

## 판단
사용자 체감상 경로 추종은 양호. 전체 이동 표준편차가 큰 것은 그 자체로 문제 아님.
다만 실제 시간 간격 불균일과 최대46cm 표시 이동이 있어 완전히 균일/부드럽다고 단정하지 않음.
물리적 이동과 동기화된 영상/기준 좌표 없이 지연을 정확히 계측할 수 없으며 이번에는 웹 화면을 직접 녹화하지 않음.
카메라/음성/필터/펌웨어는 변경하지 않음.

원본 C:/dev/hanmir-runtime/uwb-walk-lap-20261017/review.jsonl

```json
{
  "start_utc": "2026-10-16T15:40:11.402085+00:00",
  "seconds": 89.66498255729675,
  "cycles": 776,
  "hz": 8.643285013798646,
  "status": {
    "computed": 739,
    "failed": 22,
    "position_rejected": 15
  },
  "arrival_ms": {
    "n": 775,
    "median": 65.30928611755371,
    "p95": 445.30644416809076,
    "max": 1392.897605895996
  },
  "processing_ms": {
    "n": 776,
    "median": 33.84673595428467,
    "p95": 287.53066062927246,
    "max": 644.9470520019531
  },
  "xy_std_m": [
    1.02128117099172,
    0.791472048548595
  ],
  "xy_span_m": [
    3.7825160761659475,
    3.3910963986768987
  ],
  "nonzero_steps_m": {
    "n": 168,
    "median": 0.09262959687865441,
    "p95": 0.2274496661983878,
    "max": 0.45992525014549535
  },
  "changed_gaps_seconds": {
    "n": 167,
    "median": 0.0751187801361084,
    "p95": 3.0636701822280763,
    "max": 8.20259165763855
  },
  "start_center": [
    0.7807641900940416,
    0.7336309824811836
  ],
  "end_center": [
    0.6198456237077896,
    0.5965540594979777
  ],
  "return_difference_m": 0.21138795571732646,
  "end_10s_span_m": [
    0.3925897307029622,
    0.8052648630114592
  ],
  "end_10s_std_m": [
    0.16162155643600842,
    0.16240367947066128
  ],
  "display_path_length_m": 17.57946597358877,
  "blocks": [
    {
      "offset_s": 0,
      "n": 89,
      "span": [
        0.144,
        0.165
      ],
      "median_xy": [
        0.781,
        0.734
      ],
      "max_step": 0.11,
      "max_interval_ms": 536
    },
    {
      "offset_s": 10,
      "n": 91,
      "span": [
        0.126,
        0.189
      ],
      "median_xy": [
        0.763,
        0.757
      ],
      "max_step": 0.12,
      "max_interval_ms": 570
    },
    {
      "offset_s": 20,
      "n": 87,
      "span": [
        0.245,
        0.189
      ],
      "median_xy": [
        0.527,
        0.568
      ],
      "max_step": 0.15,
      "max_interval_ms": 720
    },
    {
      "offset_s": 30,
      "n": 74,
      "span": [
        3.537,
        0.723
      ],
      "median_xy": [
        1.878,
        1.038
      ],
      "max_step": 0.46,
      "max_interval_ms": 1393
    },
    {
      "offset_s": 40,
      "n": 86,
      "span": [
        3.192,
        2.541
      ],
      "median_xy": [
        3.845,
        3.032
      ],
      "max_step": 0.335,
      "max_interval_ms": 655
    },
    {
      "offset_s": 50,
      "n": 93,
      "span": [
        0.66,
        2.698
      ],
      "median_xy": [
        0.912,
        0.697
      ],
      "max_step": 0.29,
      "max_interval_ms": 641
    },
    {
      "offset_s": 60,
      "n": 86,
      "span": [
        0.229,
        0.397
      ],
      "median_xy": [
        0.822,
        0.629
      ],
      "max_step": 0.19,
      "max_interval_ms": 579
    },
    {
      "offset_s": 70,
      "n": 90,
      "span": [
        0.212,
        0.303
      ],
      "median_xy": [
        0.681,
        0.629
      ],
      "max_step": 0.17,
      "max_interval_ms": 609
    },
    {
      "offset_s": 80,
      "n": 80,
      "span": [
        0.393,
        0.805
      ],
      "median_xy": [
        0.62,
        0.597
      ],
      "max_step": 0.193,
      "max_interval_ms": 815
    }
  ]
}
```


---

## 부록 20. UWB_TIMED_STOP_AND_INTERPOLATION_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/UWB_TIMED_STOP_AND_INTERPOLATION_2026-10-17.md

# UWB 이동 정지 판정 및 화면 보간 — 2026-10-17

## 적용
30cm 이동 시작 및 동일 방향3회 확인 유지. 카메라/음성/태그 전송 변경 없음.
정지 판정: 최근0.8초, 좌표 범위 대각선30cm 이내이며 전반/후반 중앙 위치 차이4cm 이내. 수신 간격0.5초 초과 시 정지 증거 초기화.
따라서 표본당8cm/3회 정지 방식 제거. 매우 느린 이동은 여전히 정지와 구별하기 어려울 수 있음.
관리자 지도 및 작업자 지도 SVG 위치를100ms 선형 보간. 새 표본이 오면 현재 표시 위치에서 새 목표로 재시작. 외삽 없음.
좌표/위험구역 판단값은 화면 보간과 독립. 지도 크기 변경시 보간 초기화, reduced-motion 선호 시 즉시 표시.
모바일 소스 반영이며 설치된 APK 재패키징은 이번 작업에서 하지 않음.

## 검증
TypeScript 빌드 성공. 위치 필터/앵커전환 단위시험10개 통과.
합성10초 등속 입력:0.15m/s 잘못된 정지5→0,0.5m/s13→0,1m/s0→0.
실제 한 바퀴의 동일739개 계산 후보 재생:1cm 이상 갱신170→372회, 최대단계46.0→35.8cm.
재생은 동일 입력에 대한 비교로 실제 화면 프레임/지연 계측이 아님. 필터 결과는 지도 경계 클램프 전 값.
첫20초 좌표범위 X14.4/Y18.9cm→X34.5/Y40.1cm, 마지막10초 X39.3/Y80.5cm→X42.9/Y92.1cm.
따라서 이동 중 정지 오판 개선과 정지 흔들림 사이 상충이 남아 있으며 실제 정지/보행 확인이 필요. 이 구간들의 정확한 물리적 정지 시각은 없음.
100ms 보간은 추가 표시 지연을 만들 수 있으며 서버의1초 이상 지연 자체를 없애지 않음.

## 기록
새 실시간 JSONL motion_filter에 이동/정지, 시작확인 표본수, 정지창 표본수/기간 추가.
변경 전후 재생: C:/dev/hanmir-runtime/uwb-smoothing-*-replay.json
새 실험: C:/dev/hanmir-runtime/uwb-walk-smooth-20261017/

```json
{
  "before": {
    "0.15": {
      "false_stops": 5,
      "end_lag_m": 0.22735888058371634
    },
    "0.5": {
      "false_stops": 13,
      "end_lag_m": 0.32207478829205094
    },
    "1": {
      "false_stops": 0,
      "end_lag_m": 0.2857142857142847
    },
    "replay": {
      "updates": 170,
      "max_step_m": 0.45992525014549535,
      "first20_span": [
        0.1436028243894656,
        0.18866276760671463
      ],
      "last10_span": [
        0.3925897307029622,
        0.8052648630114592
      ]
    }
  },
  "after": {
    "0.15": {
      "false_stops": 0,
      "end_lag_m": 0.04285714285714359
    },
    "0.5": {
      "false_stops": 0,
      "end_lag_m": 0.14285714285714235
    },
    "1": {
      "false_stops": 0,
      "end_lag_m": 0.2857142857142847
    },
    "replay": {
      "updates": 372,
      "max_step_m": 0.3579414437298165,
      "first20_span": [
        0.3448501345108683,
        0.4013245122691095
      ],
      "last10_span": [
        0.4293645406699669,
        0.9208964310676158
      ]
    }
  }
}
```

## 적용 후 실제 한 바퀴 기록

- 기록: C:/dev/hanmir-runtime/uwb-walk-smooth-20261017/review.jsonl 및 summary.json
- 완료 응답 직후 최초 확인 시점까지의 157.96초, 1,433건. 이전 기록은 89.66초 776건으로 길이와 무선 조건이 다르므로 개선 효과를 직접 단정하지 않는다.
- 서버 처리 완료 기록 빈도: 이전 8.64Hz → 이번 9.07Hz. 유효 좌표 계산은 1,225건, 약 7.76건/초.
- 기록 간격 P95: 445 → 340ms. 최대 공백: 1,393 → 1,421ms로 긴 공백은 남아 있다.
- 수신 시각부터 처리 기록 완료까지 중앙값: 33.85 → 24.52ms, P95: 287.53 → 110.07ms.
- 좌표 계산 실패: 22/776(2.8%) → 171/1,433(11.9%). 이번 실패 중 유효 앵커 3개 미만 162건, 계산 수렴 실패 9건. 앵커 구성 변경 보호에 의한 보류 37건은 별도.
- 이동이 두드러진 시작 후 40~80초: 계산 성공 232건 모두 moving. 실제 이동 시작·종료 타임스탬프가 없으므로 모든 정지 오판정이 제거됐다고 단정하지 않는다.
- 1cm 이상 좌표 갱신의 중앙 이동폭: 9.3 → 6.4cm. 최대: 46.0 → 52.6cm. 작은 갱신은 늘었지만 최대 점프는 개선되지 않았다.
- 마지막 10초 XY 표준편차: 3.4cm / 12.1cm, 범위 15.6cm / 30.5cm. 정지 상태에도 완전히 고정되지는 않았다. 이전 마지막 10초 표준편차는 16.2cm / 16.2cm였으나 정지 시점과 무선 조건 차이를 고려해야 한다.
- 전체 이동 구간 표준편차는 이동 경로 자체를 포함하므로 위치 오차로 해석하지 않는다.
- 30cm 시작 기준, 카메라와 음성 설정 유지. 100ms 화면 보간은 적용했으나 실제 화면의 체감 개선은 사용자 확인이 필요하다. 이번 구간은 음성 동시 부하 FPS를 별도 계측하지 않았다.

### 남은 원인과 다음 단계

정지 판정과 화면 보간 수정은 유지한다. 남은 끊김은 유효 앵커 부족 및 최대 1.42초 기록 공백과 함께 발생할 수 있다. 다음 분석은 앵커별 수신 누락 시간대와 좌표 보류를 대조하며, 현재 로그만으로 RF 누락과 서버 거리 필터의 영향을 단정하지 않는다. 임계값을 더 낮추거나 위치를 예측해서 공백을 숨기는 변경은 하지 않았다.


---

## 부록 21. EVACUATION_LIVE_GUIDANCE_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/EVACUATION_LIVE_GUIDANCE_2026-10-17.md

# 실시간 대피 방향 안내 구현 — 2026-10-17

## 목적과 적용 범위
UWB 위치, 지도 기준 BNO 방향, 등록된 벽·장애물·비상구 및 관리자 지정 화재구역을 사용하여 짧은 음성 방향 안내를 제공한다. 방향 판단에 LLM을 호출하지 않는다. 현재는 단층 평면 지도 기반 현장 검증용 기능이다. 연기 속 실제 통행 가능성, 화재 확산, 출입문 개폐, 동적 장애물, 계단은 자동 인식하지 않는다. 이 기능이 실제 화재 대피 안전성을 검증했다는 뜻은 아니다.

## 기존 구조와 변경
- 기존 A* 경로 계산은 비상구 거리만 반환하고 path를 비웠다. 이제 경유점 경로를 반환한다.
- 벽 안의 시작점이나 막힌 비상구를 임의로 주변 빈 공간으로 옮겨 연결하지 않는다. 사용할 수 없으면 경로 없음으로 처리한다.
- 경로 계산은 별도 2Hz 작업에서 수행한다. UWB 수신 처리 경로에서는 최신 결과를 조회한다.
- 등록 지도에서 장애물 25cm, 지정 화재구역 75cm 여유 폭은 기존 계산값을 유지했다. 실제 현장의 안전거리 보장값이 아니며 검증 후 조정해야 한다.
- 지도 크기·벽·출구가 변경되면 확인한 지도 서명과 달라져 방향 안내를 중단한다.
- 사건마다 관리자가 지도와 방향 보정을 확인하고 안내를 시작한다. 비상 사건만 생성했다고 방향 안내가 자동 시작되지는 않는다.

## 안내 판단
- 좌표계: 오른쪽 +X, 위쪽 +Y, 지도 보정 각도 0도 +X / 90도 +Y.
- 목표 방향과 BNO 방향 차이가 ±30도면 정면, 그 밖은 좌·우 회전, 150도 이상은 뒤쪽 안내.
- 다음 회전 지점까지 1.5m 이내면 회전 예고. 고개 방향은 보행 방향과 다르므로 1초 연속 동일 판단 후 음성 전송한다. 보행 방향을 별도로 추정하는 기능은 아직 없다.
- 경로 거리 0.5m 이내는 ‘등록된 비상구 근처’로 안내한다. 탈출 성공으로 처리하지 않는다.
- 위치 1.5초 초과 / 방향 1초 초과 데이터는 방향 지시를 중단한다.
- 2Hz 재계산으로 경로 이탈과 변경된 화재구역을 반영한다. 경로 고정·출구 변경 히스테리시스는 향후 현장 검증 후 개선 대상이다.

## 음성 및 서버
- 동일 문장은 기존 8초 반복 제한을 적용한다.
- 작업자별 생성 작업 하나를 유지하고 행동이 바뀌면 이전 합성을 취소한다.
- 합성이 끝난 후 사건 활성 여부·최신 안내·위치/방향 갱신 상태를 다시 확인한다.
- 이미 P4로 전송되어 재생 중인 음성을 취소하는 프로토콜은 아직 없다. 네트워크 단절 시 서버 안내도 들리지 않을 수 있다.
- 카메라/음성 인식/UWB 30cm 기준 및 펌웨어는 변경하지 않았다.
- 웹은 실시간 안내 이벤트를 받고 청록색 점선으로 경로를 표시한다. 기존 설치 APK/IPA는 이번 변경으로 재빌드하지 않았다.

## 사용 순서
1. 지도 설계에서 실제 크기·벽·장애물·비상구를 입력한다. 통행 가능한 출구 영역이 벽과 겹쳐 막히지 않도록 현장 구조를 정확히 반영한다.
2. 지도 화살표와 실제 안전모 방향 보정을 확인한다.
3. 안전한 시험 환경에서 화재 수동발령 후 기존 화재 위치 확인 절차를 진행한다.
4. ‘지도 확인 후 방향 안내 시작’을 눌러 확인한다.
5. 직진 → 회전 → 출구 근처, 고개만 돌리기, UWB/방향 끊김, 지도 수정, 안내 중지를 확인한다.
6. 실제 출구가 막히거나 지도에 없는 장애물이 있으면 현재 시스템이 자동 판별하지 못하므로 관리자 지도 수정이 필요하다.

## 기록 및 확인 상태
- backend/logs/evacuation-navigation.jsonl: 2Hz 판단, 목표 각도, 상대 각도, 다음 목표 거리, 위치·방향 데이터 나이, 계산 ms.
- delivery 기록: 전송 성공 여부와 합성/전송 소요시간. 전송 성공은 실제 스피커 청취 확인과 다르다.
- 로그는 크기·기간 제한을 적용한다.
- Python 문법 컴파일과 웹 TypeScript 빌드 통과. 새 단위시험/실제 보행 시험은 이번 적용에서 실행하지 않았다.
- 변경 전후 카메라 FPS 및 실제 안내 시점 정확도는 아직 측정하지 않았다. 지도 등록 후 모의 대피에서 확인해야 한다.

## 수정 파일
backend/app/services/evacuation_navigation.py (신규), evacuation_service.py, evacuation_guidance_service.py
backend/app/routers/evacuation.py, uwb.py, audio.py 및 app/main.py
frontend/src/App.tsx, components/SiteMap.tsx, hooks/useSafetyData.ts, services/api.ts, types/index.ts

## 경계 보정 적용
- 실제 장애물 안쪽 깊이 25cm 이내: 최근 10초, 최대100개 이력 중 1m 이내 정상 좌표가 같은 통로 쪽을 지지할 때만 보정한다. 깊은 내부·모호한 모서리·화재 제외구역은 보정하지 않는다.
- 장애물 밖 25cm 여유 폭에 있는 좌표는 같은 측면의 열린 격자점으로 보정한다.
- 보정 최대거리 80cm는 내부 깊이+여유 폭+20cm 격자 오차의 상한이며, 허용하는 내부 오차가 80cm라는 뜻이 아니다.
- 실제 worker 좌표는 수정하지 않는다. route_origin으로 방향을 계산하며 경로에 원본→보정 좌표를 이동 선분으로 추가하지 않는다.
- start_correction에 원본/보정 좌표, 이동 거리, 경계 내부 깊이, 측면, 장애물 ID, 허용/거부 이유를 남긴다.
- 다른 장애물과 화재구역을 건너 보정하지 않는다.
- 경계·깊은 내부·이력 없음·책상 우회 등 관련 시험 총8개 통과. 실제 모의 대피 결과는 별도 기록한다.

## 화재 발화 누락 수정
- ‘화재상황 발생’, ‘화재 상황이 발생’ 표현이 기존 화재 명령 목록에서 누락되어 추가했다. 호출어 없이 화재 판정하는 회귀시험 5개 통과.
- 최근 STT에서 instruction-style prompt 자체가 전사되어 stt_prompt_echo로 거부되는 현상을 확인했다. 전사 요청에서 prompt를 제외하고 언어/model은 유지했다. 실제 마이크 재시험 필요.
- 진단 서버에서는 최신 WAV 최대12개 보관을 켰다. 모의시험 종료 후 비활성화할 것.

## 짧은 상대 방향 안내
사용자 요청으로 앞으로/왼쪽/오른쪽 중심으로 문장을 단축하고 첫 안내의 앵커 번호 설명을 제거했다. 회전 예고와 즉시 회전은 별도 문구를 유지한다. 2Hz 판단·1초 방향 안정화 조건은 유지하며 실제 지연 개선 수치는 후속 시연에서 측정한다. 통화 수정과 함께 서버에 재적용할 예정이다.


---

## 부록 22. CALL_STABILITY_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/CALL_STABILITY_2026-10-17.md

# 웹 통화 끊김 수정 — 2026-10-17

## 변경 전
35초 UART 기록에서 통화 채널 재연결 3회. 마이크 입력 peak 최대7965/32768, 웹에서 받은 PCM peak 최대21615/32768, 스피커 I2S 쓰기 실패0회. 디지털 오디오 경로는 정상이나 연결 유지 불안정.

## 원인 및 수정
- 기존 TX 전송 제한20ms. 실패 시 클라이언트를 강제 stop/start했다.
- 설치된 esp_websocket_client 라이브러리는 실제 transport 실패 시 자체 abort/reconnect한다. 외부 stop/start가 중복되는 구조였다.
- TX 제한150ms로 변경. 실패 프레임 재전송 없이 대기큐를 비우며 라이브러리 자동복구를 사용한다.
- 큐6개 제한 유지. 지연·끊김 균형은 실측 필요.
- 5초마다 TX 성공/실패/최대 지연us, 연결·active 상태 기록. 통신 오류 이벤트 기록 추가.
- 웹은 장치 재연결을10초 대기하고 재연결 중 마이크 데이터 송신 중지.

## 적용
C:/dev/hanmir-p4/helmet_p4 및 저장소 call_client.c 반영. COM25 앱 영역0x10000에1942720바이트 업로드, flash hash 확인. 앱 파티션46% 사용(54% 여유). 카메라·음성 인식 설정 변경 없음.

## 자료
변경 전: C:/dev/hanmir-runtime/call-uart-live.log
변경 후: C:/dev/hanmir-runtime/call-uart-after.log

## 적용 후 실측
- 약80초간 양방향 통화 유지 후 시험 종료. 웹에서도 1분 이상 연결 상태 확인.
- 서버 누적: 안전모→웹 5000패킷/2560000바이트, 웹→안전모 3498패킷/2238720바이트.
- 수집한 통화 중 UART 구간: TX 실패0, 재연결0, 스피커 I2S 실패0. 두 UART 수집 사이 공백이 있어 전체 시간의 모든 프레임을 UART로 관찰한 것은 아님.
- TX 최대50.473ms 관측. 이전20ms 제한 초과가 실제 발생함을 확인.
- 부팅 직후 Wi-Fi 연결 전 Host unreachable 오류는 통화 시작 전이며, 통화 유지 실패 수치와 분리한다.
- 장시간/다른 Wi-Fi 조건 안정성 및 종단 음성 지연은 추가 검증 필요.
- 후속 로그: C:/dev/hanmir-runtime/call-uart-after-continued.log, call-after-end.json.


---

## 부록 23. CALL_3MIN_LOAD_TEST_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/CALL_3MIN_LOAD_TEST_2026-10-17.md

# 카메라·UWB·양방향 통화 동시 시험 — 2026-10-17

## 결론
**연속 안정성 시험 실패.** 통화 세션은 198.16초 유지되었으나 시작 약 166.1초 후 P4의 call_tx 작업에서 Stack protection fault가 발생해 재부팅했다. 웹과 서버 상태 플래그가 계속 온라인으로 표시되어 연결 상태만으로는 장애를 발견할 수 없었다. UART 및 영상 카운터를 대조해 확인했다. 통화는 시험 후 직접 종료했다.

## 조건
카메라·UWB·양방향 웹 통화 동시 사용. 카메라/밝기/YOLO/위치 필터 설정 변경 없음. 1초 주기 API 기록과 연속 COM25 UART 기록. 통화 전 19.02초, 통화 중 198.16초, 통화 후 46.04초 기록. 각 구간 길이가 다르며 대조군 반복 실험은 아니다.

| 지표 | 통화 전 | 통화 중 | 통화 후 |
|---|---:|---:|---:|
| 카메라 수신 FPS | 15.566 | 13.964 | 14.945 |
| YOLO 완료 FPS | 10.728 | 9.861 | 10.709 |
| 보호구 상세 완료 FPS | 3.523 | 3.255 | 3.562 |

통화 중 5초 구간 중앙값: 카메라 14.791FPS, YOLO 10.393FPS, 상세 3.397FPS. 재부팅 구간에는 모두 0FPS인 5초 창이 존재한다. 따라서 **항상 YOLO 10FPS 유지는 달성하지 못했다.**

## 통화 및 장애 원인
- 서버 수신 누적 차이: 안전모→서버 6,021,120바이트, 웹→서버 4,938,880바이트. 합계 10.960MB, 평균 0.442Mbps. 서버 중계 이후 추가 전송량/프로토콜 오버헤드는 제외.
- 정상적으로 완료되어 기록된 TX 통계 실패 합계 0, 최대 송신 대기 54.897ms. **실패 처리 중 크래시해 카운터에 남지 않은 전송 오류가 있으므로 실제 실패 0이라는 뜻이 아니다.**
- UART에 transport_poll_write(0), esp_transport_write returned 0 직후 Stack protection fault.
- task call_tx, SP=0x4ff6c120, stack bounds=0x4ff6c124–0x4ff6d120. 하한보다 4바이트 아래로 넘어감.
- call_client.c의 call_tx 스택은4096바이트. ELF 해석은 임계구역/세마포어와 printf 출력 경로를 가리킨다. 송신 오류 처리/로그 출력 경로에서 스택 부족이 드러난 것으로 판단한다. 다른 메모리 손상 가능성까지 이번 시험만으로 완전히 배제하지는 않는다.
- 스피커 쓰기 실패 기록 0회. 출력 peak 최대32766/32768로 포화 근처 신호도 있었음. 실제 청취 품질·왕복 지연을 측정한 시험은 아니다.
- 재부팅 뒤 Wi-Fi 연결 전 transport 이벤트는 최초 원인과 구분해야 한다.

## UWB
- 통화 구간 관측 1674건, 약 8.45Hz.
- server_received_at 기준 간격 중앙값 96.94ms, 95백분위 380.16ms, 최대 1213.76ms.
- 결과 {'failed': 8, 'position_rejected': 21, 'computed': 1645}.
- 태그 누적 dropped_cycles 증가 606회. 통화 전에도 간헐적인 간격 증가가 있었으며, 통화만의 원인이라고 단정할 수 없다. 기존 위치 필터 유지.

## 트래픽·메모리
- 카메라 payload 147.346MB, 평균 5.949Mbps. JPEG 평균 53.24KB.
- PC CPU 중앙값/95백분위 [47.3, 70.78]%. 네트워크 어댑터 원시 카운터는 metrics.jsonl에 저장(다른 프로그램 트래픽 포함).
- 현재 업로드된 앱 바이너리1,942,720바이트, 4MiB 앱 파티션 약46.3%. 런타임 힙/PSRAM 연속 사용량 계측은 이번 펌웨어에 없어 수치를 만들지 않음. 이번 오류는 플래시 용량 부족이 아니라 call_tx 스택 경계 위반.

## 다음 수정 우선순위
1. call_tx 스택을8192바이트로 늘리고 stack high-water mark 계측 추가. 오류 시에도 충분한 여유가 있는지 재시험.
2. call 채널 온라인 플래그와 별도로 마지막 실제 음성 패킷 시각·정체 시간을 표시. 웹 연결 표시만으로 정상 판단 금지.
3. 동일한3분 시험을 반복해 재부팅0, 영상 정체0을 먼저 확인. UWB 지터는 별도 구간 비교.

## 원본 파일
C:/dev/hanmir-runtime/call-3min/metrics.jsonl
C:/dev/hanmir-runtime/call-3min/uart.jsonl
C:/dev/hanmir-runtime/call-3min/uwb.jsonl
C:/dev/hanmir-runtime/call-3min/summary.json
수집기: C:/dev/hanmir-runtime/capture_call_3min.py
집계기: C:/dev/hanmir-runtime/report_call_3min.py

이번 요청은 동시 부하 측정이며, 시험 결과 보존을 위해 측정 도중 펌웨어/분석 설정은 수정하지 않았다.


---

## 부록 24. CALL_STACK_AND_WATCHDOG_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/CALL_STACK_AND_WATCHDOG_2026-10-17.md

# 통화 스택·음성 정체 감지 수정 — 2026-10-17

## 변경 범위
- call_tx 스택4096→8192바이트. 5초마다 최소 잔여 스택 기록(ESP-IDF 단위:바이트).
- 실제 PCM이3초 이상 없으면 웹에 음성 정체 경고. 10초 미수신 시 종료. 무음이어도 PCM 프레임이 전송되는 현재 프로토콜에 적용.
- 복구 시 실제 PCM 수신으로 상태 회복. 기다리는 중 버튼으로 종료 가능.
- 카메라 해상도·밝기·분석률·UWB 설정 유지.

## 첫 재시험: 8KB 스택 / 송신 제한150ms
- 약136초 후 통화 종료. P4 재부팅 없음.
- transport_poll_write 타임아웃이 다시 발생했으나 오류 처리 후 스택 최소4076바이트 남음. 이전4KB 스택에서 발생한 panic은 재현되지 않음.
- 웹에서3초 정체 경고 로그를 기록하고10초 미수신 종료 메시지를 실제 표시함. 인위적인 장애 주입 없이 실제 장애로 확인.
- 이후 송신 제한500ms로 변경. 6프레임 큐 제한 및 실패 프레임 재전송 금지 유지. 일시 전송 지연 허용을 늘린 것이며 종단 지연500ms 보장을 의미하지 않음.
- 원본: C:/dev/hanmir-runtime/call-stack-3min/

## 빌드·적용
TypeScript noEmit 검사 통과. ESP-IDF 빌드 완료. COM25 앱 업로드 및 해시 검증 완료.
앱 크기1,942,800바이트. 4MiB 앱 파티션 약46.3% 사용, 약53.7% 여유.
최종 재시험 기록: C:/dev/hanmir-runtime/call-final-3min/

## 최종 재시험: 8KB 스택 / 송신 제한500ms
**3분 무중단 통화 실패. 스택 재부팅 수정과 웹 정체 감지는 확인.**

통화 세션 표본 181.14초. 약172초에 transport_poll_write 타임아웃 발생, TX 최대505.509ms. 이후 웹은 음성 미수신10초 기준으로 종료. 서버의 operator_connected 상태가 유지되는 시간은 실제 음성이 연속 전달된 시간과 다름.

| 지표 | 통화 전 | 통화 중 평균 | 통화 중 5초 창 최저 |
|---|---:|---:|---:|
| 카메라 수신 FPS | 9.77 | 15.088 | 10.789 |
| YOLO FPS | 7.272 | 10.942 | 8.794 |
| 보호구 상세 FPS | 2.443 | 3.572 | 2.798 |

- P4 panic/재부팅0회. 송신 실패1회. 스피커 I2S 쓰기 실패0회.
- 최소 잔여 스택4076바이트. 오류 처리 경로를 실제 거친 뒤에도 여유가 남음.
- 이전처럼 재부팅에 따른 영상0FPS 구간은 없었음. 하지만 YOLO 최저5초 창이10FPS 미만이므로 항상10FPS라고 표현하지 않음.
- 카메라 payload 143.047MB, 평균 6.318Mbps.
- 양방향 음성 서버 수신 합계 8.598MB, 평균 0.380Mbps. 중계 송신과 오버헤드는 제외.
- UWB 관측: {'records': 1556, 'interval_ms_min_p50_p95_max': [23.81, 98.82, 321.8, 1010.29], 'status_counts': {'computed': 1521, 'failed': 26, 'position_rejected': 9}}. 기존 위치 필터/무선 설정 변경 없음. 간격은 logged_at_unix 기준이며 순수 무선 왕복지연이 아님.
- 전체 PC CPU 중앙값/95백분위: [43.4, 62.14]%.

## 남은 문제와 다음 조사
500ms까지 늘려도 송신 제한 초과가 재현됐으므로 단순 제한시간 확대로 해결됐다고 볼 수 없다. 서버 call_manager.py는 입력을 받을 때 상대 소켓 send_bytes를 직접 await한다. 느린 수신자 때문에 입력 읽기가 막힐 수 있는 구조이며, 이번 기록만으로 이것이 유일 원인이라고 확정할 수는 없다. 다음은 중계 송신 대기시간·소켓별 송신큐 길이를 계측하고, 입력 수신과 제한된 크기의 송신큐를 분리해 원인을 검증해야 한다.

이번 단계에서는 서버 중계 구조를 변경하지 않았으며, 남은 끊김은 해결 완료로 표시하지 않는다. 실제 청취 품질/종단 지연과 장시간 안정성도 별도 시험이 필요하다.


---

## 부록 25. CALL_SERVER_QUEUE_TEST_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/CALL_SERVER_QUEUE_TEST_2026-10-17.md

# 서버 통화 송신 큐 분리 및 동시 부하 시험 — 2026-10-17

## 변경 내용
backend/app/websocket/call_manager.py: 상대방 send_bytes를 수신 루프에서 기다리던 구조를 소켓별 송신 작업으로 분리. 음성 큐 최대6개, 200ms 이상 묵은 데이터 폐기, 제어 메시지 우선 전송. 송신1초 제한 초과 시 해당 소켓 종료. disconnect 시 작업 취소·큐 정리. 제어 큐 최대8개. backend/app/main.py: 상태API relay 계측 추가.
카메라·UWB 설정, P4 펌웨어 변경 없음. 기존 서버 프로세스 환경을 저장해 그대로 재시작했다.

## 검증
느린 가짜 수신자 시험:30프레임 입력이 상대 송신을 기다리지 않음, 큐6개 제한, 초과24개 폐기, 제어 우선 및 정리 통과.
실제 양방향 통화 세션 202.17초 후 직접 종료. 수신 API1초 기록 및 COM25 UART 연속 수집.

## 판정
**통화 세션 유지 확인. 전체 동시 동작 합격은 아님.**
- 통화 중 P4 panic/재부팅0, call transport disconnect/reconnect0, 서버 송신 오류0.
- P4 송신 잠금 대기 실패3회. 연결 유지된 상태에서 프레임 폐기. 최대500.548ms, 스택 최소4076바이트.
- I2S 쓰기 실패0. 실제 귀로 듣는 품질과 종단 음성 지연은 이번 자동 계측만으로 검증하지 않음.
- 통화 시작 약 191.2초 후 카메라 수신 카운터가 멈췄다. 통화·방향값은 계속 수신. 해당 시점 UART에는 명시적인 카메라 오류나 panic 없이 capture/TX 진행 로그가 멈춤. 센서 캡처 대기인지 네트워크 송신 정체인지 추가 계측 필요. 서버 큐 변경과의 인과관계는 확정할 수 없음.

| 항목 | 전체 통화 평균 | 5초 구간 중앙값 | 5초 구간 최저 |
|---|---:|---:|---:|
| 카메라 FPS | 13.281 | 14.591 | 0.0 |
| YOLO FPS | 9.334 | 10.192 | 0.0 |
| 상세분석 FPS | 3.126 | 3.397 | 0.0 |

통화 전 구간은 서버 재시작 후 모델 준비 영향이 포함돼 공정한 성능 대조군으로 사용하지 않는다. 평균에는 끝부분 카메라 정지가 포함된다. YOLO10FPS 항상 유지 미달.

## 서버 큐
- helmet-001-av:to_helmet: 성공6558개(제어 포함), 폐기977개, 오류0회, 큐 최대6개, 송신 최대140.0ms, 대기 최대391.0ms.
- helmet-001-av:to_web: 성공10720개(제어 포함), 폐기1541개, 오류0회, 큐 최대6개, 송신 최대250.0ms, 대기 최대453.0ms.

폐기 비율은 양방향 각각 약13%로 무시할 수 없다. 버퍼 크기만 늘리면 지연이 늘 수 있으므로 원인을 확인해야 한다. max_wait는 폐기 직전 프레임도 포함하며, 네트워크 종단 지연이 아니다.

## 기타 계측
- 카메라 payload 141.483MB, 평균 5.599Mbps.
- UWB 1661건, 기록 간격 중앙값/95백분위/최대 [92.34, 461.23, 1406.68]ms. 위치/무선 설정 유지.
- 펌웨어 크기1,942,800바이트, 4MiB 앱 파티션46.3%. 이번 서버 수정으로 펌웨어 크기는 바뀌지 않음. 연속 heap/PSRAM 계측은 없음.

## 남은 작업
1. 카메라 capture dequeue/encode/송신 각각의 마지막 진행 시각을 계측해 정지 위치 확인.
2. 서버 event loop 지연과 송신 큐 폐기 시점을 대조해 약13% 음성 폐기 감소.
3. P4의 약48초 주기 송신 잠금 대기 원인 계측. 이번에는 재연결로 이어지지 않았음.
4. 위 문제 수정 후 같은 동시 부하 시험 반복. 3분 연결 성공을 장시간 안정성 보장으로 확대하지 않음.

원본: C:/dev/hanmir-runtime/call-queue-3min/metrics.jsonl, uart.jsonl, uwb.jsonl, summary.json
서버 로그: C:/dev/hanmir-runtime/call-queue-server-out.log, call-queue-server-err.log
서버 로그에는 인증 관련 URL이 포함될 수 있어 외부 공유 전 비밀값 제거 필요.


---

## 부록 26. CAMERA_AUDIO_COALESCE_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/CAMERA_AUDIO_COALESCE_2026-10-17.md

# 카메라 대기 제한·음성 묶음 전송 — 2026-10-17

## 적용
- camera_source.c: VIDIOC_DQBUF 무제한 대기를2초로 제한. 실패 시 STREAMOFF, 버퍼 재등록, STREAMON으로 같은 설정의 스트림 복구. 캡처/인코딩 최대시간·누적 복구횟수·잔여 스택5초 계측.
- call_manager.py: 이미 큐에 도착한 PCM을 최대1920바이트(60ms)로 묶어 송신. 묶기 위한 추가 대기 없음. 큐 최대6400바이트(200ms),32항목 제한. 200ms 지난 음성 폐기 유지. 프레임 수·바이트 기반 폐기/송신 계측 추가.
- UWB·카메라 밝기·화이트밸런스·YOLO 모델 및 임계값 변경 없음.
- ESP-IDF 빌드·COM25 업로드·flash hash 검증 완료. 앱1,943,504바이트. 서버는 기존 프로세스 환경을 유지해 재시작.
- 자동 시험: PCM 순서/내용 보존,6400바이트 제한,10프레임→4개 송신으로 묶기, 소켓 작업 정리 통과.

## 실제 시험 범위
PC 마이크가 NotFoundError로 감지되지 않아 양방향 통화를 시작하지 못함. 사용자에게 마이크 연결 요청. **안전모→웹 듣기 전용 시험**으로 진행했다. 웹에는3분13초 이상 표시됐고 직접 종료. 연속 수집기로 확보한 활성 구간은186.15초(수집 종료가 UI 종료보다 앞섬). 양방향 합격이나 동일 부하 전후 비교로 해석하지 않는다.

| 계측 | 결과 |
|---|---:|
| 카메라 평균 FPS | 15.267 |
| YOLO 평균 FPS | 11.271 |
| 상세분석 평균 FPS | 3.664 |
| YOLO 5초 창 최저 FPS | 8.595 |
| 카메라 5초 창 최저 FPS | 10.194 |
| 음성 폐기 바이트 비율 | 0.97% |
| P4 재부팅/통화 재연결 | 0 / 0 |
| 카메라 dequeue 복구 발생 | 0 |
| call TX 실패 | 0 |
| call TX 최소 잔여 스택 | 5708바이트 |

음성 송신 5,902,464바이트, 폐기 58,112바이트. 송신 최대125.0ms, 큐 대기 최대219.0ms(폐기 프레임 포함). 서버 입력/출력 프레임과 웹 오디오 스피커 실제 재생은 다른 지표이며, 청취 품질은 별도 확인 필요.

## 판단과 한계
카메라는 이번 시험에서 멈추지 않았지만 대기 제한 후 자동 복구 경로는 실제 타임아웃이 발생하지 않아 현장 검증되지 않았다. 이전 정지가 DQBUF였다는 확정 증거도 아직 없으며 이번 수정은 무한 대기 제거 및 진단/복구 강화다. 인코딩이 멈추는 다른 원인을 완전히 배제하지 않는다.
YOLO 평균10FPS 이상은 확인했으나 최저5초 구간8.60FPS로 항상10FPS 미달. 음성 폐기는 이전 양방향 약13%에서 이번 수신 전용0.98%였으나 부하가 다르므로 개선률을 확정하지 않는다.
UWB 기록 1600건, 중앙값/95백분위/최대 간격 [98.41, 323.94, 966.44]ms. 설정 유지.

## 이어서 할 일
PC 마이크 연결 후 양방향3분 이상 동일 시험. 카메라 단계 로그·복구횟수, 양방향 폐기 바이트 비율, YOLO5초 구간 하한 비교. 연결 상태뿐 아니라 실제 음성 패킷과 카메라 카운터 증분으로 판정.

원본 C:/dev/hanmir-runtime/call-coalesce-3min/ (metrics.jsonl, uart.jsonl, uwb.jsonl, summary.json)
빌드 로그 C:/dev/hanmir-runtime/camera-recovery-build.log


---

## 부록 27. CALL_DUPLEX_VALIDATION_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/CALL_DUPLEX_VALIDATION_2026-10-17.md

# PC 마이크 연결 후 양방향 통화 시험 — 2026-10-17

## 조건
카메라 대기 제한·음성 묶음 전송 적용 상태에서 PC 마이크 연결 후 실제 양방향 통화. 설정/코드 추가 변경 없음. UWB·밝기·모델·임계값 유지. 약199.16초 활성 통화 기록 후 직접 종료. 서버 API 1초 주기, UART 연속 기록.

## 결과
- P4 panic/재부팅0, 통화 채널 disconnect/reconnect0. 실제 양쪽 PCM 송수신 확인. 실제 청취 품질과 종단 지연은 사용자 청취 확인이 별도로 필요.
- 카메라 전송 실패2회, 두 번 모두 전송 재개. 무한 정지는 관찰되지 않음. 이번 복구는 카메라 WebSocket 송신 실패 경로이며 새 DQBUF 스트림 복구가 동작했다는 증거는 아님.
- call TX 잠금 획득 실패2회, 연결은 유지. 최대498.131ms. 최소 잔여 스택5628바이트.
- 스피커 I2S 쓰기 실패0. RX peak 최대28429/32768.

| 지표 | 평균 | 5초 구간 최저 |
|---|---:|---:|
| 카메라 수신 FPS | 15.209 | 9.792 |
| YOLO 완료 FPS | 10.323 | 6.594 |
| 상세분석 완료 FPS | 3.404 | 2.198 |

평균 YOLO10FPS는 달성했으나 항상10FPS는 미달. 카메라 무한 정지는 이번 표본에서 재현되지 않았지만 송신 정체가 남아 있음.

## 음성 큐
서버 계측은 프로세스 누적이므로 이번 시험 직전값을 빼서 계산. 예전 수신 전용 기록을 포함하지 않음.
- helmet-001-av:to_helmet: 송신4,931,840바이트, 폐기369,920바이트, 폐기율6.98%.
- helmet-001-av:to_web: 송신5,912,704바이트, 폐기380,288바이트, 폐기율6.04%.

수신 전용0.98%와 직접 비교하면 안 된다. 이전 양방향 약13%보다 낮지만 PC부하·무선 상태가 동일한 통제실험은 아님. 실제 음질 개선율이나 인식률을 의미하지 않는다.

## 기타
UWB 1664건. 기록 간격 중앙값/95백분위/최대 [92.79, 425.07, 1758.05]ms. 위치 필터 수정 없음.
카메라 payload 138.54MB, 평균5.56Mbps. 프로토콜 오버헤드 제외.

## 남은 개선 대상
카메라 송신 오류와 call TX 잠금 대기가 겹치는 시점의 P4 WebSocket 동작/공유 Wi-Fi 대기 분석. 서버 송신 큐 폐기와 event loop 지연을 함께 비교. 평균만으로 목표 달성 판단하지 말고5초 구간 하한과 폐기율도 확인.
원본: C:/dev/hanmir-runtime/call-duplex-3min/metrics.jsonl, uart.jsonl, uwb.jsonl, summary.json


---

## 부록 28. CALL_DROP_CAUSES_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/CALL_DROP_CAUSES_2026-10-17.md

# 음성 폐기 원인 분리 및 실행 순서 개선 — 2026-10-17

## 최종 변경
- 서버 call_manager.py: capacity_drop_bytes(큐6400바이트/32개 초과), age_drop_bytes(200ms 초과), control_drop_bytes(통화 제어에 의한 비우기)를 분리. 기존 dropped_bytes는 용량+시간 합계. 송신 바이트·입력 간격 최대값도 기록.
- receive()가 버퍼에서 즉시 반환하는 상황에서도 _send_bytes 끝의 asyncio.sleep(0)으로 송신 작업에 실행 기회를 제공. 네트워크 송신을 기다리는 구조로 되돌리지 않음.
- 큐6400바이트/200ms 한도·이미 도착한 PCM 최대1920바이트 묶음 유지. 임계값 증가로 폐기를 숨기지 않음.
- 20ms 강제 묶음 대기는 시험 후 제거. 최종 코드에 없음.
- P4 통화 채널: network_timeout_ms 기본10000→1000 명시, reconnect_timeout_ms2000→1000, send timeout500→1500ms. TX스택8192 유지. 더 오래 기다리는 것은 음성 종단 지연 보장이 아님.
- 카메라/UWB/밝기/모델/인식 임계값 변경 없음. 앱1,943,504바이트 업로드·hash 검증 완료.

## 후보 비교
1. 실행 기회 제공만 적용: 서버 큐 폐기0이나 약53초 세션에서 P4 송신 오류·10초 무수신 종료. call-fair-3min 로그.
2. 20ms 강제 묶음 추가: 용량·시간 폐기가 모두 발생하고 약83초 세션에서 실패. call-batch20-3min 로그. 이 후보는 제거.
3. 실행 기회 제공+P4 명시적 대기시간: 최종 198.16초 양방향 통화 후 직접 종료. call-explicit-3min 로그.

실행 순서가 서버 큐 적체의 주요 기여 요인임을 지지하지만, 매 시험 무선/PC 부하가 완전히 동일하지 않아 유일 원인으로 확정하지 않는다. P4 송신 대기 문제는 별도로 존재.

## 최종 실측
| 항목 | 평균 | 5초 창 최저 |
|---|---:|---:|
| 카메라 수신 FPS | 14.665 | 5.796 |
| YOLO FPS | 10.315 | 4.397 |
| 상세분석 FPS | 3.442 | 1.599 |

서버 양방향 큐 폐기0%, 큐 최대1개. 통화 채널 재연결0, P4재부팅0, call TX 실패0, I2S쓰기 실패0. 실제 청취 품질/종단 지연은 별도 확인이 필요.

- helmet-001-av:to_helmet: PCM송신3,712,000바이트, 용량폐기0, 시간폐기0, 제어비우기0바이트. 입력 간격 최대500.0ms.
- helmet-001-av:to_web: PCM송신6,283,520바이트, 용량폐기0, 시간폐기0, 제어비우기0바이트. 입력 간격 최대1203.0ms.

## 반드시 남겨둘 한계
- 서버 큐0%는 장치→서버 도착 이전의 누락이나 P4 내부큐 폐기를 포함하지 않는다. 현재 P4 내부큐 초과 폐기는 별도 연속 카운터가 없으므로 전체 음성손실0%로 표현하면 안 된다.
- 안전모 음성 도착 간격 최대1203ms, P4 송신 최대1096.716ms. 기다리다 연결을 끊는 빈도는 줄었지만 지연·짧은 무음 가능성은 남음.
- 평균 YOLO10FPS 이상은 달성. 최저5초 창4.397FPS로 항상10FPS 목표는 미달.
- UART transport_poll_write 오류1회는 camera_tx frame3343 전송 실패로 확인. 카메라 WebSocket 재시작 후 전송 재개. 단기 정체가 완전히 제거된 것은 아님.
- UWB 기록 1591건, 간격 중앙값/95백분위/최대 [99.76, 336.42, 1526.65]ms. 설정 유지. 결과별 {'failed': 46, 'computed': 1542, 'position_rejected': 3}.

## 검증/자료
자동 시험에서 용량폐기/시간폐기를 각각 유발하고 dropped_bytes=두합계 확인, 소켓 작업 정리 통과.
원본 C:/dev/hanmir-runtime/call-explicit-3min/metrics.jsonl, uart.jsonl, uwb.jsonl, summary.json.
부정적 결과도 call-fair-3min, call-batch20-3min에 보존. 실패 시험 수집기는 종료 후 중단했으나 해당 활성구간 기록은 저장됨.
후속: P4 내부큐 폐기 카운터와 소켓 잠금/송신 지연을 분리 계측하고, 카메라 송신 정체와 YOLO5초창 하락을 대조. 큐 한도 확대로 결과를 좋게 보이게 만들지 않음.


---

## 부록 29. FINAL_SYSTEM_BOTTLENECK_REVIEW_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/FINAL_SYSTEM_BOTTLENECK_REVIEW_2026-10-17.md

# HANMIR 오늘 최종 통신·자원 검증 기록 — 2026-10-17

## 결론
Wi-Fi 절전 해제 후 197.16초 양방향 통화에서 P4재부팅/통화재연결/카메라전송실패0회. YOLO평균11.087FPS. 그러나 모든 상황에서 병목이 없다는 검증은 아니다. 장치 스피커큐 폐기·짧은 FPS하락·UWB 간격변동이 남아 있다. 통화 중 AI 호출은 현재 설계상 중지되므로 네 기능이 동시에 모두 작동한다고 표현하면 안 된다.

## 최종 변경
network.c: esp_wifi_get_ps 확인 결과 previous_ps=1, esp_wifi_set_ps(WIFI_PS_NONE)=ESP_OK. 모뎀 절전 해제(전력 소모 증가 가능; 배터리 지속시간은 미측정). 5초 자원 로그 추가.
call_client.c: TX/RX 큐 초과 폐기 바이트 계측. 8KB TX스택, 명시된1초 내부 네트워크 대기/1.5초 송신제한 유지.
서버: 수신루프에서 송신 작업에 실행 기회 제공, 소켓별 제한큐, 용량/시간/제어 폐기 분리 유지.
카메라 해상도·JPEG품질·밝기·모델/임계값·UWB설정 변경 없음. TCP 송수신버퍼5760바이트는 메모리 증량 없이 유지.

## 전후 비교
| 항목 | 절전 해제 전 최종시험 | 이번 |
|---|---:|---:|
| call TX 최대 송신시간 |1096.716ms|44.467ms|
| 카메라 전송 실패 |1회|0회|
| YOLO 평균 |10.315FPS|11.087FPS|
| 카메라 평균 |14.665FPS|16.053FPS|
| 상세 평균 |3.442FPS|3.657FPS|
| 통화 재연결/P4재부팅 |0/0|0/0|

순차 현장시험이며 PC부하·장면·무선상태가 완전히 통제된 비교는 아니다. 절전 해제가 지연 개선에 기여했다는 근거이나 유일 원인 확정은 아니다.

## 메모리/플래시
- 보드 플래시 설정16MiB. 현재 앱1,944,624바이트 / 앱파티션4MiB =46.36%, 여유53.64%. 전체16MiB 사용률이 아님.
- 모델 파티션6MiB가 예약돼 있으나 실제 파일 사용량은 이번 시험에서 측정하지 않음.
- 내부 힙 현재값 표본 최소252,087바이트, 부팅 이후 최소198,172바이트, 가장 큰 연속 블록 표본 최소147,456바이트.
- PSRAM 현재값 표본 최소30,942,940바이트, 부팅 이후 최소30,795,072바이트.
- call TX스택 최소여유5628바이트. 카메라 스택도 별도UART 기록.
- RSSI 표본최저-57dBm. 실제 전력·CPU코어별 사용률·C6내부메모리·전체 패킷손실률은 미측정. '모든 HW 병목을 검증했다'고 표현하지 않음.

## 음성
- helmet-001-av:to_helmet: 실제시험 송신3,534,080바이트, 폐기0바이트, 폐기율0.0000%.
- helmet-001-av:to_web: 실제시험 송신6,310,144바이트, 폐기2,816바이트, 폐기율0.0446%.
- 장치 TX큐 초과폐기0, RX스피커큐 누적폐기97,920바이트 관측(서버→안전모 송신 대비 약2.8%). 통화 전후 경계가 포함될 수 있어 정밀비율은 차후 세션별 카운터로 보완. 장치 내부큐도 관측해야 함.
- 서버 큐0%가 전체 음성0%를 의미하지 않는다. TCP 도착 간격과 사람이 듣는 종단 지연은 별도다.
- 통화 PCM 실제 양쪽 송수신 및 I2S쓰기 확인. 청취 품질은 사용자 응답 필요.

## 영상/위치 한계
YOLO 최저5초창8.595FPS. 카메라 최저5초창11.793FPS. 평균10FPS는 달성했으나 항상10FPS 미달.
UWB1652건, 간격 중앙값/95백분위/최대[98.58, 348.63, 1256.05]ms. 결과{'failed': 17, 'position_rejected': 10, 'computed': 1625}. 위치 튐 필터는 유지. 무선 왕복지연이 아니라 서버로그 기록 간격이다.

## AI 호출 검증 상태
voice.c는 hanmir_call_active()일 때 로컬호출과 STT업로드를 중지한다. 통화 음성이 AI명령으로 오인되지 않도록 설계돼 있음. 통화 종료 후 '투투스→배터리 얼마야' 실제 발화를 요청한 상태. 아직 사용자 결과/로그 대조 전이며 완료로 표시하지 않는다.

## 오늘 보존할 상태
서버와웹은 실행중, 통화시험은 종료. 최종펌웨어업로드·hash검증 완료. GitHub push는 이 턴에서 수행하지 않음.
원본 C:/dev/hanmir-runtime/call-latency-3min/metrics.jsonl, uart.jsonl, uwb.jsonl, summary.json
빌드 C:/dev/hanmir-runtime/wifi-latency-build.log
이전 비교 C:/dev/hanmir-runtime/call-explicit-3min/
다음 우선순위: 스피커큐의 유입 burst와 재생속도 계측 → 용량만 늘려 지연을 숨기지 않고 조정, YOLO 최저구간의 서버처리/전송지연 비교, 통화 종료 후AI 호출 확인.


---

## 부록 30. VOICE_RESTORE_2026-10-17

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/VOICE_RESTORE_2026-10-17.md

# 음성 인식 이전 설정 복구 — 2026-10-17

## 사용자 보고
통화 종료 후 투투스 5회 중 1회 응답. 사용자 보고 기준 20%이며 장기 인식률이 아님.

## 확인과 변경
- 통화 active=0, 녹음 HTTP 200, 업로드 큐 대기 0ms 확인.
- 마이크 코드 마지막 변경은 10월16일20:06. NS 및 WakeNet OFF 유지.
- 대피 음성 수정 시 제거됐던 STT prompt를 이전처럼 복구: command_only에 따라 settings.stt_command_prompt 또는 settings.stt_prompt 전달.
- 모델 gpt-4o-mini-transcribe, 언어 ko 유지. 원음 필터 및 호출 임계값 변경 없음.
- 임시 영문 호출어 허용 수정은 사용자 요청대로 제거.
- 카메라·UWB·통화 펌웨어 재업로드 없음.

## 동일 원본 녹음 재처리
| 파일 접두어 | 복구 전 | prompt 복구 후 |
|---|---|---|
|331cb|Tu|투투스|
|89adc|Kršc|투투스.|
|78d78|Totus|투투스|
|83c27|주스|투투스|
|c2678|배터리 질문 표본|배터리 얼마야?|

4개 호출 녹음 모두 기존 호출어 판정에서 armed 확인. 원본 파일 재처리 결과이며 새 발화 성공률이나 실제 응답 지연을 뜻하지 않음. 호출 5회와 개별 파일의 일대일 대응은 확정하지 않음.
100Hz 필터 단독 비교는 인식 개선이 없어 운영 미적용.
짧은 비호출 후보 녹음에서 prompt 문장이 전사되는 문제가 재현됐으나 기존 stt_prompt_echo 방어가 ignored 처리하는 것 확인. 독립 오탐 시험은 별도 필요.

## 운영 적용
서버를 프로젝트 venv Python으로 재시작. 첫 재시작 시 시스템 Python 경로로 실행되어 click 의존성 오류가 났으며 프로젝트 venv로 바로잡음.
증거: C:/dev/hanmir-runtime/wake-five-attempts/restored-prompt-original-probe.json 및 원본 WAV.
새 사용자 발화와 실제 스피커 응답 확인은 대기 중. 완전 해결이나 0.5초 달성 주장하지 않음.


---

## 부록 31. PERFORMANCE_MEASUREMENT_PROTOCOL_2026-10-16

> 당시 기록 원문입니다. 최신 완료 상태와 수치는 본문 우선. 출처: docs/PERFORMANCE_MEASUREMENT_PROTOCOL_2026-10-16.md

# HANMIR 기능별 성능 계측 및 병목 개선 기록

## 적용 원칙

2026-10-16 사용자 요청: 모든 변경에서 기능 수행 중 HW/SW 데이터와 로그를 남기고, 변경 전후를 비교한다. 목표는 영상·음성·UWB 동시 실행과 YOLO 10 FPS이며, 목표값과 실측값을 구분한다.

1. 실험 ID, 시작/종료 시각, 코드 변경, 실행 프로세스, 펌웨어 식별 정보, 카메라 설정, 장면과 발화 내용을 기록한다.
2. 먼저 기준 구간을 수집하고 한 종류의 병목을 수정한 뒤 같은 조건으로 재측정한다. 다른 장면에서 측정한 수치는 참고 비교이며 인과관계 입증으로 쓰지 않는다.
3. 기본 90초 수집, 첫 15초 제외. 영상만/호출·질문/음성 재생/동시 부하를 나눈다. 성능 수집 중 테스트·모델 벤치마크를 병행하지 않는다.
4. 전체 구간 평균 외 1초 FPS와 지연 p50/p95/최댓값을 확보한다. 누락된 항목은 미수집으로 표시한다.
5. 수신 FPS, 전체 화면 YOLO FPS, 상세 보호구 분석 FPS, 웹 표시 FPS는 별도 지표다. 하나로 합쳐 표시하지 않는다.
6. 검출 신뢰도·실제 착용 정답·오탐·미탐을 함께 기록한다. 신뢰도는 정확도가 아니다.

## 수집 항목과 현재 범위

| 구분 | 필수 항목 | 현재 수집 여부 |
|---|---|---|
| 영상 | 수신/YOLO/상세 FPS, 큐 깊이, 프레임 교체, 추론·대기시간 | 서버 JSONL 및 분석 로그 |
| 영상 품질 | 크기·JPEG 바이트, 밝기, 클래스별 신뢰도/박스, 정답 | 프레임 보관 및 분석 로그; 정답은 사용자 확인 필요 |
| 트래픽 | 영상 payload, WAV 업로드, PC NIC RX/TX·오류 | 수집; NIC는 다른 앱도 포함 |
| 음성 | 발화 종료→인식→명령→재생, STT/서버 지연, 실제 청취 | 서버·UART 기록 및 사용자 확인 조합; 음향 기준 종단 지연은 별도 측정 필요 |
| 서버 | 프로세스별 CPU 누적 시간·RSS·스레드, PC CPU/RAM | 수집기 추가 완료 |
| P4 | RSSI, 연결 상태, 카메라 교체 카운터, 전송 지연 | heartbeat/UART 제공 항목 수집 |
| P4 RAM | 내부 free/min heap, largest block, PSRAM free/min, 태스크 stack | 현재 미수집. 펌웨어 텔레메트리 추가 후 검증 필요 |
| Flash | 앱 바이너리 크기/파티션, 실행 이미지 해시, 모델/파일시스템 사용량 | 빌드 크기만 확인. 실행 이미지 및 실제 사용량 미확인 |
| UWB/방향 | 최신 수신 시각, 갱신 간격, 거리 품질, heading | 상태 수집; 거리 품질 상세는 UWB 로그 별도 필요 |

프레임 교체 카운터는 최신 프레임 우선 정책의 결과를 포함하므로 네트워크 패킷 손실로 해석하지 않는다. NIC 오류가 0이어도 무선 재전송·장치 내부 드롭이 없다는 뜻은 아니다.

## 도구와 증거 위치

- `scripts/collect_wake_system_metrics.py`: 인증 정보는 환경변수로 전달. JSONL에 장치/카메라/NIC/CPU/RAM 수집.
- `scripts/report_camera_network.py`: 첫 15초 제외 후 FPS·트래픽·처리 시간·CPU/RAM 요약 JSON 생성.
- `scripts/capture_p4_wake_trace.py`: UART 수집. 포트 점유 및 재부팅 영향을 확인하고 사용.
- `backend/logs/camera-analysis.jsonl*`: 추론 신뢰도·지연. 회전 로그이므로 실험 후 보관 필요.
- `backend/logs/voice-pipeline.jsonl`: STT·호출어·응답 단계 기록.
- 이번 실험 원본: `C:/dev/hanmir-runtime/yolo-uwb-thread-measurement.jsonl`, `yolo-io-thread-measurement.jsonl`, `yolo-indexed-measurement.jsonl` 및 각 `.summary.json`.

측정기의 dashboard 조회 자체도 서버에 부하를 주므로 비교 때 동일 주기를 유지한다. 원본에는 현장 영상·음성·위치가 포함될 수 있으며 공개 저장소에 일괄 업로드하지 않는다. 인증 정보는 기록하지 않는다.

## 이번 변경 및 확인

- 음성 중 전체 화면 YOLO 1 FPS 강제 제한 제거. 상세 분석 신규 작업은 음성 중 잠시 억제한다.
- UWB DB 처리와 카메라 저장/DB 처리를 이벤트 루프 밖으로 이동.
- 위치 이력 조회용 복합 인덱스 추가. 웹 중복 refresh 방지, 이력 재조회 15초 간격. 실시간 위치/방향 WebSocket 유지.
- OpenCV 스레드 제한 및 중복 영상 디코딩 감소.
- 밝기 gamma 1.35, sharpen 0.2 유지. 전체 화면 모델은 원본, 상세 ROI는 밝기 보정 영상 사용.
- P4 펌웨어는 이번 성능 변경에서 업로드하지 않음.
- 관련 서버 테스트 59개 및 카메라 관련 12개 통과. 프런트엔드 빌드 통과. 인덱스 실제 DB 생성 성공.

| 실험 | 수신 FPS | YOLO FPS | 상세 FPS | 영상 payload Mbps |
|---|---:|---:|---:|---:|
| UWB 처리 분리 | 12.63 | 7.53 | 0.70 | 6.20 |
| 카메라 저장/DB 분리 추가 | 14.93 | 8.64 | 0.86 | 7.35 |
| 인덱스·웹 중복 조회 억제 추가 | 13.20 | 8.56 | 0.83 | 6.74 |

최신 측정: 22:00:22–22:01:32 KST, 유효 69.63초. 음성 처리 중인 표본 19/29개, WAV 44개·1.414 MB. PC Wi-Fi RX 7.41 / TX 0.515 Mbps, OS NIC 오류/드롭 증가 0. YOLO 모델 추론 p50/p95 13.05/15.50 ms, 워커 전체 38.45/45.65 ms, 서버 대기+IPC 3.29/131.82 ms. 모델 실행보다 대기 꼬리 지연이 커서 추가 분석 대상이다. 인덱스 후 평균 FPS 개선은 이번 구간에서 확인하지 못했다.

PC CPU p50/p95 40.7/52.34%, 시스템 사용 RAM 12,139–12,375 MiB. 서버 PID 30700 RSS 180–189 MiB, 추론 프로세스 PID 26068 638–645 MiB / PID 31280 522–558 MiB. 각 CPU 사용량은 0.78 / 2.01 / 1.35 논리 코어 상당이며 전체 PC CPU 백분율과 다른 단위다. 프로세스 RSS에는 공유 메모리가 포함될 수 있다.

위 비교는 장면과 음성 부하가 완전히 동일하지 않다. 최신 인덱스 적용 결과는 `yolo-indexed-measurement.summary.json` 참조. 10 FPS 달성과 음성 중 유지 여부는 별도로 판정한다.

## Flash 확인값과 한계

로컬 `C:/dev/hanmir-p4/helmet_p4/build/hanmir_helmet_p4.bin`: 2,115,216 bytes, 2026-10-16 20:31:27 생성. factory 앱 파티션 4 MiB 대비 약 50.43%. 설정상 flash 16 MB, model 파티션 6 MiB. 이 수치는 **로컬 빌드 산출물** 기준이며 현재 P4에 실행 중인 이미지와 일치한다고 확인하지 않았다. 전체 flash 실제 사용량 또는 RAM 사용량으로 해석하지 않는다.

## 아직 해결되지 않은 항목

- 안정적인 전체 화면 YOLO 10 FPS 및 음성 동시 지연 목표 달성 미확인.
- 기존 모델의 맨손→장갑 오탐 11/16장 확인. 단순 검출 수 증가를 정확도 개선으로 보고하지 않는다. 추가 hand evidence 옵션은 비활성 유지.
- P4 실시간 heap/PSRAM/stack 및 실행 이미지 식별 계측 추가 필요.
- PC GPU 사용률, 무선 재전송량, 웹 실제 렌더 FPS, 스피커 음향 출력 시작 시각은 현재 수집기의 미수집 항목이다.
