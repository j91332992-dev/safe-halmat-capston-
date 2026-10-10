# HANMIR 2.0 — 2026-10-09~10 전체 작업 상세 인수인계

작성일: 2026-10-10, 한국 시각. 용도: 팀원 공유, 다른 PC에서 작업 인수, 코드·장치 버전 및 실제 검증 범위 확인.

이 문서는 현재 상태 요약과 날짜별 상세 원문을 한 파일에 합친 인수인계 자료다. **본문의 현재 상태를 우선한다. 부록의 진행 중/정상/미업로드 문구는 해당 기록 작성 당시의 상태다.**

## 1. 현재 상태 — 가장 먼저 확인

| 항목 | 현재 상태 |
|---|---|
| 저장소 | https://github.com/j91332992-dev/safe-halmat-capston- |
| 통합 브랜치 | `integration/p4-mobile-live-heading-20261010` |
| 작성 직전 최신 코드 | `c9d0209`, 스피커 전용·독립 GPIO 진단 및 교차 핀 관측 |
| 최신 소스 | P4 통신·영상·센서·음성, 최신 웹/앱 디자인, 새 통화 모듈 포함 |
| Android 배포 | v1.8 / build13 APK |
| iOS | build13 자산 동기화, 신규 서명 IPA 미제작 |
| **실제 P4 버전** | **통화 수정 전 `df52167` 소스 기반 일반 펌웨어로 롤백·복구** |
| 새 양방향 통화 | 현재 P4에서는 비활성. `channel_online=false`는 롤백 상태에서 예상되는 값 |
| 스피커 | 무음 미해결. 전체 롤백과 6가지 출력 설정에서도 무음 |
| 핵심 추가 근거 | GPIO20(BCLK)·21(WS)이 서로 HIGH/LOW를 따라가는 현상이 독립 GPIO 검사에서도 2회 재현 |
| UWB 지도 | 사용자 직접 X/Y 입력. 자동 측량/자동 지도 생성 제거, 앵커 4개 재업로드 완료 |
| 장시간 안정성 | 카메라 수 분 정지 이력이 있어 전체 병목 해소 완료로 판단하지 않음 |

문서 작성 때 읽기 확인: P4 online=true, 배터리 보고값 약 73.07%, last_error=null, call channel_online=false. 순간 상태이며 새로운 동시 부하 시험은 아니다. 배터리 값은 앰프에 5V가 공급된다는 증거가 아니다.

**GitHub 최신 소스와 현재 P4의 펌웨어가 다르다.** 다음 작업자는 이 차이를 먼저 확인한다. 최신 통화 펌웨어로 곧바로 덮어쓰기보다 스피커 신호 경로를 먼저 조사한다.

## 2. 유지한 프로젝트 구조

- 기존 ESP32-S3 펌웨어/서버를 삭제하지 않고 P4 AV 구조를 추가·통합했다.
- OV5640 DVP에서 OV5647 MIPI CSI로 전환했다.
- P4는 내장 C6 경유 2.4GHz Wi-Fi를 사용한다. 외부 C5는 이번 운영에 미사용이다.
- UWB는 독립 태그·앵커 체계이며 P4와 데이터 GPIO를 연결하지 않는다.
- FastAPI/YOLO/STT/DB/React 구조를 유지했다.
- 연결 성공, 데이터 쓰기 성공, 실제 가청 출력, 인식률 향상은 별도의 판정이다.

```text
OV5647 → P4 CSI/RGB565/JPEG → 최신 프레임 큐 → C6 Wi-Fi/WS
       → FastAPI → YOLO 워커 → 원본/분석 화면 → 웹·앱
INMP441 → I2S RX → NS/AFE VAD → 음성 구간 업로드 → STT
        → 호출어/의도 분류 → 조회·규칙 또는 설명형 LLM → TTS
        → P4 I2S TX → MAX98357A → 스피커
BNO085 → UART/SH-2 → yaw/pitch/roll → 100ms 방향 이벤트 → 지도
UWB 앵커 ↔ 독립 태그 → 자체 Wi-Fi → 거리/좌표 → 수동 지도
최신 통화 소스: 휴대폰 PCM ↔ 서버 WebSocket ↔ P4 call_client
현재 물리 P4: 통화 수정 전 버전이므로 새 통화 경로는 꺼져 있음
```

## 3. 어제·오늘 작업 흐름

### 10월 9일

1. ESP-IDF 5.5.5 빌드·업로드 환경과 ASCII 경로 staging 준비.
2. P4/C6 Wi-Fi·서버 연결, OV5647·마이크·배터리·UWB·웹 개별 확인.
3. BNO085 UART 무수신 원인 분석. 바이트별 TX 완료와 1ms 간격, 폴링 yield로 SH-2/회전벡터 수신 복구.
4. 지도 기준 방향 보정, 사용자 회전 확인.
5. 사용자 요청으로 부팅 시 약 5초 스피커 테스트 제거.
6. 15fps/YOLO640 시도. 촬영·수신·분석·화면 FPS를 분리 계측.
7. 카메라 전송 버퍼16KB, timeout1500ms, 실패 후 재연결, 전송 로그, 웹 MJPEG 적용.

### 10월 10일

1. WISET 환경에 맞춰 P4/태그 주소 갱신, 서버·웹 재실행.
2. 영상/음성/UWB/BNO 동시 로그, 플래시·메모리 분석 및 카메라 후속 측정.
3. 10초 앵커간 자동 측량/지도 실험 후 사용자 요청으로 수동 X/Y 방식 완전 롤백. 앵커1~4 실제 재업로드.
4. 방향 전송을 heartbeat와 분리해 약10Hz 송신, 웹 화살표 보간. 사용자가 반응 정상 확인.
5. 최신 모바일/PC 웹 디자인 병합, 네이티브 이미지 No Frame 수정, 작업자 방향 연결.
6. Android build11→12→13 생성·배포, CI 서명키 경로/캐시 보완. iOS 자산 동기화.
7. 통화 ticket409/주소 오류 수정, P4 양방향 통화 추가, 실제 Android PCM 로그 확인.
8. 하향 음성·일반 확인음 무음 조사. 충전/전원 재시작/상세 로그/전체 이전 소스 롤백.
9. 전용 I2S 6조건 비교와 독립 GPIO 검사로 GPIO20·21 교차 현상 발견.
10. 진단 종료 후 P4를 통화 수정 전 일반 버전으로 복구. 진단 코드·결과까지 GitHub 업로드.

## 4. 카메라·YOLO: 변경과 수치

현재 기록 기준: 실제 영상800×640, JPEG75, 목표15fps, YOLO 전체 입력640. ‘640’은 원본640×480이 아니다. ROI sharp640/original960 추가 추론이 있어 프레임당 최대3회 실행 가능. 일반 분석 목표4fps, 음성 활성 시1fps.

| 구간 | 서버 수신 FPS | YOLO FPS |
|---|---:|---:|
| 10/9 초기15fps/640 | 2.57 | 1.98 |
| 16KB/1500ms·복구 적용 | 6.93 | 2.90 |
| 10/10 정지 포함 최초 구간 | 10.39 | 2.36 |
| 카메라 정지 구간 | 0 | 0 |
| 재부팅 후 약29초 | 16.25 | 3.31 |
| 후속44.266초 | 12.33 | 2.21 |
| 후속19.265초 | 11.99 | 3.01 |

서로 다른 장면/부하의 측정이므로 특정 설정의 개선 효과로 단정하지 않는다. 최신 큐 폐기는 무선 패킷 손실률이 아니다.

11:12:14.742 이후 frame ID12034와 수신/분석 카운터가 정지했다. 분석 큐0인 동안 음성 HTTP200/UWB/BNO는 계속됐다. 프레임 나이가 수 분까지 증가했고 재부팅으로 복구됐다. CSI DQBUF·캡처·인코더·센서/FPC 원인 위치는 미확정이다. 상태 capturing/connected가 실제 진행을 보장하지 못한다.

후속 서버CPU 중앙52.5%/최대57.7%, 가용RAM 최소약3.20GiB. 전체 서버 고갈의 증거는 없었지만 프레임 나이 최대1.609~2.453초가 있어 장시간 안정성은 남았다.

사용자 조끼·헬멧 착용 장면에서 person0.607/vest0.483/helmet0.549 검출 사례, 최종 두 PPE=true 확인. 머리 잘림·직전 helmet=null도 있어 정확도/재현율은 미계산이다.

아직 적용 결과가 아닌 개선 후보: 정지 감시·단계별 시각·동적 메모리, 동일 장면 JPEG75→85, 상세960 조건/주기 최적화, 1280×960 후보 검증, 같은 JPEG 오프라인 비교, 실제 장착 시점 정답 자료 평가.

## 5. AI Agent·STT·TTS의 실제 범위

| 항목 | 확인한 설정/코드 |
|---|---|
| STT | gpt-4o-mini-transcribe, 한국어, timeout10초, SDK retry0 |
| 설명형 LLM | gpt-6-luna, timeout5초, 출력80토큰, reasoning effort none 요청 |
| 후처리 | 한 줄 공백 정리, 최대120문자 |
| TTS | Edge TTS ko-KR-SunHiNeural, WAV16kHz/16bit/mono 캐시 |
| P4 전처리 | WebRTC NS/AFE VAD |
| 음성 구간 | 최대5초, pre-roll300ms, 종료무음500ms, 업로드 큐3 |
| 호출어 | 서버 별칭/유사도 판별, 후속 질의20초 |
| 로컬 WakeNet | 비활성. 전용 투투스 모델 없음 |
| AEC | 미구현/비활성 |

모델명은 로컬 설정 확인값이다. 최신 가격/한국어 모델 성능 비교를 새로 수행한 자료는 아니다.

FAST_INTENTS의 배터리/위치/PPE/장치/방향·경고/비상/대피 등은 서버 조회·규칙/고정 응답을 먼저 사용한다. 설명형 요청만 제공된 최신 상태를 문맥으로 API에 보내고 실패 시 fallback. 프롬프트는 보통1문장/필요 시2문장, 없는 센서값 생성 금지다.

PRD의 get_worker_status/location/heading/battery, get_ppe_status, get_recent_events, get_nearest_exit, get_device_status는 완성된 Tool Calling 인터페이스로 모두 구현된 상태라고 확인되지 않았다. 현재는 서버 함수·의도 분기 중심이다.

미완료/문제:

- heading_query는 확인 불가 응답. 지도 화살표와 음성 길 안내는 범위가 다름.
- worker.ppe와 전방 사람YOLO PPE의 출처/대상 구분 필요.
- ‘조그만’의 ‘그만’ 부분 문자열을 stop_speaking으로 오인한 사례.
- ‘비상 상황이면’ 같은 조건문 경보 정책 미정리.
- 일반 주변 발화도 STT에 업로드해 비용·큐·부하 발생.
- 재생 중 음성 억제에 따른 비상 발화 누락 가능성 별도 시험 필요.
- 호출 횟수/실패 원음/단계별 시간표 부족. 기억상60~70%와 새 성공률 비교 불가.

10/9 배터리 응답,10/10 위치/배터리 응답 실제 청취 성공은 기록돼 있다. 일부 배터리42% 기록과 사용자34% 청취 차이는 시각/음원 대조가 남았다. DB STT 저장→이벤트 간격은 전체 응답 지연이 아니다. 오늘 분석·통화 작업이 위 AI 논리 문제를 모두 해결했다는 뜻은 아니다.

## 6. UWB 지도 롤백과 실시간 방향

자동 지도는 시행 기록만 보관하며 현재 제거됐다. 서버 API/서비스·웹 패널·앵커 survey 코드 제거, X/Y 입력→설계 저장→현장 적용 유지. 앵커1~4 일반 앱 재업로드·해시 검증 완료. 태그 시계 오프셋 부호 확장 오류 및 SQLite NullPool 변경은 유지했다.

앵커 당시 COM7/8/9/10, 앱286032/285776/285776/285776bytes. 지도 치수는 사용자 설정에 따라5.2×3.2→4.8×2.5→후속5.0×3.3m 기록이 있으므로 과거값을 강제하지 말고 layout/draft/적용값을 대조한다. 작업자 X/Y와 작업장 크기를 구분한다.

UWB mask=F는4개 거리 입력 관측. 약12초UART POST34건HTTP200, 약2.78Hz/간격중앙0.313초/최대0.719초. 실제 위치 오차와 개별 앵커 heartbeat는 별도다. 낮은 confidence도 기록됐다.

BNO UART:GPIO23 RX/51 TX,3Mbps,바이트별1ms송신. 센서10Hz를 별도100ms 방향 이벤트로 서버에 전달. 송신대기30ms/최신값만, live 캐시/샘플별DB쓰기 없음/단일서버프로세스 전제. 서버신선도2초, 웹live3초 초과 숨김, 80ms 보간 및359↔0 최단각도.

12초실측 방향95건/7.95Hz, 간격중앙109.5ms/최대219ms. 사용자 실제 회전 후 ‘잘된다’ 확인. 자기장·장착축 오차와 센서→휴대폰 전체지연은 별도 검증이다. 앵커1·4 벽면 기준 보정값을 보존한다.

## 7. 웹·앱 병합과 APK/iOS

- 최신 앱 원본775d06f, 로컬P4 묶음8a62933, 병합43b7ebe.
- 네이티브 카메라/작업자 방향1a6c753.
- 최신 PC웹 디자인51d555c, 병합a62f7a7. DesktopSafetyOverview/메뉴아이콘/작업자선택/최근이벤트정렬/PC CSS 적용.
- 원본 관리자·작업자 앱 기능을 유지했다. 달력/채팅/교육/허가/작업시간 등을 오늘 모두 휴대폰 검증했다는 뜻은 아니다.

Android No Frame:서버JPEG/API 정상, 휴대폰metadata조회는 있으나 실제이미지요청이 없던 상태. CapacitorHttp로 JPEG→bytes→Blob URL, 순차조회/200ms간격/중첩방지/Blob해제 적용. PC는MJPEG. 앱 표시목표최대약5fps와P4송신15fps는 다르다. **새 APK에서 카메라 실제 표시 성공의 최종 사용자 확인은 기록이 부족하다.**

작업자/me 장치상태 및 작업자범위WebSocket, WorkerMap 방향 추가.2초폴링 보조, 느린응답의 최신방향 덮어쓰기 방지. 실제작업자계정 휴대폰 전체검증은 남았다.

| 배포 | 상태 |
|---|---|
| build10 | 팀원 원본, 최신P4 전체 변경 아님 |
| build11 | 초기통합, 원본서명과 불일치 |
| 최종build12 | 최신PC웹 포함, CI서명키경로/캐시 보완 |
| build13 | 앱통화주소·오류표시 수정, 현재최신 |

build13 파일:`releases/HanmirSafety-p4-mobile-v1.8-build13.apk`,Actions38029735257 성공,version1.8/code13.

APK SHA256:`47a0bba1c4b09cfc5b303a836d4e5ce560799eccf035a8b70d2768bc885ba1ab`.

최종build12·13 인증서SHA256:`267e18f5d8ec2585c4b6a0b67abcd576f90635033ff9a0aba616960d6a49d974`.

원본build10/초기build11과 서명이 달라 사용자가 삭제·재설치 선택. build12→13은 동일서명. CIdebug키캐시 유지가 필요하며 정식배포키 운영 완료 의미는 아니다. 사용자는 build13 설치·로그인·통화 시도했다. iOS는 자산/build13만 동기화, 새 IPA는Mac/Xcode/인증서/프로비저닝 필요. 기존IPA와build10 ZIP을 최신으로 혼동하지 않는다.

## 8. 통화 수정·실제 PCM 결과

원인:P4 새call_client 부재/CALL_DEVICE_TOKEN 미설정, 앱WS가window localhost 기준 주소 사용. ticket409와 앱 일반 권한안내를 구분했다.

수정:저장서버주소 getWsBaseUrl, 구체적 권한/오프라인/로그인/비보안주소 오류, 스트림/AudioContext 정리, 연결확정전 송신억제. 서버 Authorization헤더 지원/상태API/PCM카운터. P4 기존AFE공유,16kHz mono PCM16,20ms640bytes,TX/RX큐6/오래된프레임폐기/재연결,재생mutex,통화중AI업로드억제,play_alert우선중단,DMA160/6개버퍼. AEC는 추가하지 않았다.

새 펌웨어 업로드 시 ticket200/채널등록 확인. 첫통화 안전모→관리자1176패킷602112bytes, 관리자→안전모936패킷599040bytes(약18.82/18.72초PCM). P4 RX는2초당60160~64640bytes/peak10818~32768/speaker_write=ok. 사용자는 안전모마이크가폰에서 들림,폰마이크는안전모에서안들림 확인.

웹마이크는localhost/HTTPS조건 확인. LAN HTTP제한을앱권한과혼동하지 않는다. 현재P4 롤백으로 새통화는 비활성이다.

## 9. 스피커 문제: 모든 비교와 결론

사용자는 통화권한 수정 전까지 분명 작동했고 배선은 건드리지 않았다고 확인했다. 이를 유지한 채 다음 비교를 수행했다.

1. 서버전달·ACK,휴대폰PCM 실제P4 수신.
2. 통화종료 상태 확인음, DMA변경,수정전speaker.c/통화중지 비교.
3. 충전기·배터리스위치·전체전원재시작.
4. 실행/lock/I2S활성화/쓰기 상세로그.1000Hz1500ms24000샘플,48000/48000bytes ok.
5. df52167 전체31개파일 복원,부트로더/파티션/앱/model 업로드.
6. I2S1 mono left/right16bit,stereo16/32bit,I2S0 stereo16bit,48kHz 등6조건. 모두무음.
7. I2S삭제 후100펄스 교차검사.
8. I2S·PCNT 없는 별도 일반GPIO검사2회.

사용자가 ‘하나 이상 들림’이라고 했다가 즉시 ‘전부 안들림’으로 정정했다. 최종결과 모두무음. 전용진단의 초기버퍼 스택오류는static버퍼로고쳐 정상완료했으며 기존문제와구분한다. 라이브러리esp_hosted 부팅자동초기화는 존재했다.

핵심관측(읽기순서20,21,22):

```text
GPIO20 LOW  → 0,0,0 / HIGH → 1,1,0 / 100펄스 → 100,100,0
GPIO21 LOW  → 0,0,0 / HIGH → 1,1,0 / 100펄스 → 100,100,0
GPIO22 LOW  → 0,0,0 / HIGH → 0,0,1 / 100펄스 → 0,0,100
```

독립GPIO시험에서도2회 동일, SigOut ID256(simple GPIO),나머지핀OutputEn0 확인. **20·21이 서로 전기적으로 영향을 받는 관측이 있어 BCLK/WS경로가 최우선이다.** 단락0옴/정확한위치/앰프내부/전원/배선/P4원인 또는스피커단품고장은 확정하지 못했다.

사용자는납땜이라분리불가·측정기없음·배선표대로연결이라고 답했다. 다음 확인은 전체전원OFF 확대사진(P4 GPIO20/21 및MAX BCLK/LRC 앞뒷면),가능하면전압/저항측정,앰프쪽 신호선분리비교. 외관정상은측정된교차현상을배제하지 않는다. 임의5V추가/단자쇼트/SPK−GND연결은 하지않는다.

현재 일반롤백앱1890400bytes/SHA256:`135166fbc2d99b694fe0a704c220c37eb6f3c5f4871d5b7e695fd543128a0950`. 당시sdkconfig/바이너리 완전스냅샷은없어비트동일이라고하지않는다. 진단후일반앱 재업로드·해시·재부팅·online확인.

**빌드stage main소스도 복구했으나 build폴더 BIN/ELF는 마지막진단일수있다. 새업로드 전 정상소스로 반드시재빌드한다.** 저장소 최신통화코드는 보관했다.

## 10. GPIO·전원 기준

| 부품 | 연결 |
|---|---|
| OV5647 | CSI FPC, SCCB7 SDA/8 SCL/0x36 |
| INMP441 | VDD3.3V/GND,SCK31/WS34/SD36,L/R GND |
| MAX98357A | VIN스위치후5V/GND,BCLK20/LRC21/DIN22,SD/GAIN설계상미연결 |
| 스피커 | MAX SPK+→+/SPK−→−,SPK−는공통GND에연결하지않음 |
| MAX17048 | VIN3.3V,SDA33/SCL32/I2C1/0x36,배터리측JST |
| BNO085 | TX(SDA)→23 RX,RX(SCL)→51 TX,P1HIGH/P0LOW |
| UWB | 5V/GND만공유,P4데이터선없음 |
| C6 | SDIO14~19/RESET54 |
| microSD | 내장39~45,전체기능검증완료아님 |
| C5 | 초기미사용 |

OV5647과MAX17048은주소0x36이지만다른버스. GPIO정적중복검사는물리쇼트를검출하지못한다. 배터리→SW6106→5V→스위치→P4/UWB/MAX. P4 PC USB전원과MAX5V가별개라P4 ACK만으로앰프전원확인불가.

## 11. 플래시·메모리

P4 Flash16MiB/PSRAM32MiB 확인. 당시초기앱1890048bytes,4MiB앱45.06%/약55%여유. 현재롤백1890400bytes,최신상세진단통화앱1893696bytes(당시산출물). 정적D/IRAM161232/576464bytes(27.97%),data/bss/text22812/42112/96308bytes. model실파일4bytes,로컬WakeNet없음.

파티션:NVS0x9000/24KiB,PHY0xF000/4KiB,factory0x10000/4MiB,model0x410000/6MiB예약,0xA10000이후약5.9375MiB미배정. OTA슬롯이없어현재그대로OTA가능이라하지않는다.

RGB565800×640버퍼2개약1.953MiB는전체PSRAM사용량아님. 동적free/min/largest heap·PSRAM잔량·스택여유는정기계측없어확인불가. 정적여유/부팅시험성공으로누수배제불가.

UWB Flash물리16MiB/현재파티션4MiB.앱807585/1310720bytes61.6%,BIN814160bytes,정적RAM46140/327680bytes14.1%. C6개별메모리미계측. PC당시RAM약15.59GiB/CPU18,YOLORSS약592.5MiB/backend181.5~191.1MiB. 날짜별버전수치는서로다를수있다.

## 12. 주요 소스 위치

- P4:`firmware/helmet_p4/main/`의app_main/network/api_client/camera_source/camera_transport/voice/speaker/command_client/sensors/pin_guard/call_client,hanmir.h,bno_sh2 및CMake/Kconfig/config예제.
- 진단:`firmware/diagnostics/p4_speaker_isolation/`의app_main.c,gpio_only.c,CMakeLists.txt,README.md. 운영에자동포함되지않음.
- AI:`backend/app/services/speech_service.py,assistant_service.py,tts_generator_service.py`,config.py.
- 서버영상:`routers/camera.py,services/camera_service.py`및분석워커.
- 방향:`orientation_service.py,serializers.py,routers/devices.py,main.py`.
- 통화:`main.py,websocket/call_manager.py`.
- 웹/앱:`CameraFrame.tsx,LiveCameraFrame.tsx,HelmetCall.tsx,SiteMap.tsx,mobile/WorkerMap.tsx,hooks/useSafetyData.ts,services/cameraImage.ts`.
- APK:`.github/workflows/android-p4-integration.yml`,frontend네이티브자산/버전,releases.
- UWB:별도태그·앵커프로젝트.자동측량제거/기존anchor복원.

정확한전체변경은브랜치Git diff/log로확인한다. 모든파일전체를이번에새로작성했다는뜻은아니다.

## 13. 다른 PC 인수·실행

현재repo:`C:/Users/조성준/OneDrive - pukyong.ac.kr/바탕 화면/hanmmir2.0`.

P4stage:`C:/dev/hanmir-p4/helmet_p4`,UWBstage:`C:/dev/hanmir-uwb-link/uwb_multi_test`,로그/백업:`C:/dev/hanmir-runtime`. IDF5.5.5:`C:/Espressif/frameworks/esp-idf-v5.5.5`,TEMP/TMP:`C:/dev/tmp`,P4현재COM25(다른PC재확인).

서버:`http://192.168.0.40:8000`,PC웹:`http://localhost:5174`,LAN웹:`http://192.168.0.40:5174`. DHCP주소변경가능. 최신서버로그backend-speaker-recheck.out/err.log. 서버재시작시메모리세션초기화→앱재로그인.

```powershell
git clone https://github.com/j91332992-dev/safe-halmat-capston-.git
cd safe-halmat-capston-
git switch integration/p4-mobile-live-heading-20261010
```

backend의Python환경/requirements와로컬.env/DB준비후:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

frontend에서:

```powershell
npm ci
npm run dev -- --host 0.0.0.0 --port 5174
```

앱은Vite없이실행하지만API서버필요. 서버주소저장/로그인. IDF export활성화/실제sdkconfig확인/정상source staging후빌드·업로드. 현재롤백과최신통화소스를혼동하지말것.

별도안전한경로로인수할항목:backend/.env/API키/네트워크비밀번호/장치sdkconfig/호출·영상토큰/DB/보정값. 토큰은장치와서버일치필요. 문서·GitHub에비밀값포함안함. DB미전달시사용자/지도/보정값재현안됨. 원시증거ZIP은사진·로그포함으로공개업로드대신로컬보관,필요시검토후별도전달.

## 14. 주요 커밋과 다음 작업

8a62933 P4검증통합 /43b7ebe 모바일병합 /1a6c753 네이티브카메라·작업자방향 /a62f7a7 PC웹 /df52167 build12·현재롤백기준 /eeddb02 통화주소 /3b876c4 build13 /d35102d P4통화 /b5ce98f DMA·RX /8dc4711 I2S진단 /64ed41e·dce4587 전체롤백 /c9d0209 독립GPIO.

우선순위:

1. GPIO20·21영향범위/앰프전원확인→확인음/TTS가청복구→최신통화펌웨어반영→양방향/종료후AI/경고우선권검증.
2. 카메라정지위치·동적메모리·장시간동시부하계측/복구.
3. AI부분문자열오인·조건문비상·재생중비상·PPE출처·단계별ID시간계측.
4. Android관리자/작업자전체기능확인,새IPA제작후iPhone동일검증.
5. 실측위치/방위오차,낙상/화재/대피/microSD/배터리장시간시험.

## 15. 팀원에게 전달할 두 줄

> P4 카메라·마이크·BNO 방향·UWB 수동 지도·AI 서버를 최신 웹/Android build13과 통합하고 실제 부하·통화 로그까지 확인했습니다.
> 현재 P4는 스피커 무음 때문에 통화 수정 전 버전이며, GPIO20(BCLK)·21(WS)이 서로 따라가는 현상을 찾았으니 이 경로부터 확인한 뒤 최신 통화 펌웨어와 앱 전체 기능을 이어서 검증해 주세요.

## 16. 아래 부록의 읽기 규칙

아래는 날짜별상세기록원문이다. 완료이력/설정/측정근거보존을위해포함했으며본문현재상태와다른과거문구를최신상태로해석하지않는다. 특히이전IP/지도치수/build11·12/스피커정상/통화online/미업로드표기는시점별기록이다. 현재기준은build13소스,물리P4통화수정전롤백,스피커미해결,자동지도제거다.


---

# 부록 — 날짜별 상세 작업 기록 원문



---

## 부록 1: HANMIR_2_PC_HANDOFF_2026-10-09.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## HANMIR 2.0 — 다른 PC 인수인계 및 현재 진행상황

작성일: 2026-10-09 / 마지막 실물 확인: 같은 날 13:10 KST 부근.

이 문서는 다른 컴퓨터·다른 담당자가 현재 작업을 이어가기 위한 시작 문서다. 아래 상태는 확인 시점의 기록이며 장치가 계속 온라인이라는 뜻은 아니다. 비밀번호·API 키·장치 토큰은 포함하지 않았다.

### 1. 먼저 알아야 할 현재 상황

**P4 실물 업로드와 기본 서버 연결까지 완료했다.** 카메라 원본 전송, 서버 YOLO 추론, 배터리 읽기, 음성 처리 초기화, 명령 수신·스피커 재생 완료 보고를 확인했다. 독립 UWB 태그도 서버 주소를 고쳐 업로드했으며 앵커 4개 거리 수신과 서버 위치 갱신을 확인했다.

**남은 우선 작업은 UWB 실제 좌표 등록과 마이크의 유효 음성 입력 확인이다.** ‘투투스’ 맞춤 WakeNet, BNO085 방향·낙상, 양방향 통화는 완료 상태가 아니다. 모든 프로그램이 실제 안전모에서 검증됐다고 설명하면 안 된다.

다른 PC에서 GitHub 코드만 받으면 로컬 설정·DB·설치 환경은 따라오지 않는다. P4와 UWB 태그에는 기존 PC 서버 주소가 저장돼 있으므로 새 서버 PC 주소로 각각 설정을 맞춰야 한다.

### 2. 이어받을 저장소·브랜치·커밋

- 저장소: https://github.com/j91332992-dev/safe-halmat-capston-
- 브랜치: `feature/mobile-safety-app-20261001`
- 이 문서 작성 시작 시 코드 기준 커밋: `8d9fbc6`. 이 문서를 포함한 후속 문서 커밋도 받는다.
- 기존 PC 저장소: `C:\Users\조성준\OneDrive - pukyong.ac.kr\바탕 화면\hanmmir2.0`

| 커밋 | 주요 내용 |
|---|---|
| `ef7c68f` | P4 CSI 영상·C6 Wi-Fi 실물 구동 및 최신 데이터 기반 음성 응답 보완 |
| `d9b2846` | 부팅 시 스피커 TX 비활성, 실제 재생 때만 활성·종료 후 비활성 |
| `8d9fbc6` | 실제 UWB 프로젝트 경로 보완, 로컬 비밀설정 Git 제외, 태그 연결 복구 기록 |

새 PC의 영문 경로를 권장한다. 예:

```powershell
New-Item -ItemType Directory -Force C:\dev | Out-Null
Set-Location C:\dev
git clone --branch feature/mobile-safety-app-20261001 https://github.com/j91332992-dev/safe-halmat-capston- hanmir
Set-Location C:\dev\hanmir
git status
git log -5 --oneline
```

이미 작업 중인 저장소에서는 변경사항을 먼저 확인하고, 무조건 reset하거나 기존 작업을 덮어쓰지 않는다. 기존 ESP32-S3·UWB 프로젝트는 보존한다.

### 3. 현재 실제 확인 결과와 미완료 항목

| 항목 | 확인된 것 | 남은 것 |
|---|---|---|
| P4 보드 | DFR1172, ESP32-P4 rev 1.3, Flash 16MB, PSRAM 32MB, COM25 업로드·해시 검증 | USB 재연결·새 PC에서 COM 번호 재확인 |
| 내장 C6 | ESP-Hosted SDIO 4bit/40MHz, Wi-Fi·서버 heartbeat·WS 연결 | 장시간 동시 부하·AP/서버 재접속 시험 |
| 카메라 | OV5647 PID 확인, 800×640 캡처·JPEG·웹 원본 영상 | 사람/PPE 장면의 품질·정확도, 실제 FPS·지연 |
| YOLO | `backend/best.pt` 실제 로드·CPU 추론 | 안전모 영상의 PPE 인식률 평가·성능 조정 |
| 배터리 | MAX17048 SOC 약 9% 수신 | 실제 잔량 정확도·충방전 추적 |
| 스피커 | 명령 전달·WAV 완료 보고, 부팅 TX 비활성 수정 후 재업로드 | 실제 청취·음량·잡음 평가 |
| 마이크 | INMP441 I2S, WebRTC NS, AFE VAD 초기화 | 실제 발화 PCM·녹음 내용·STT·응답 전체 경로 |
| AI API | 기존 PC에서 인증 및 합성 음성 STT·설명 응답 확인 | 새 PC 키 설정, 실제 마이크 인식률·지연 측정 |
| UWB | 태그 Wi-Fi 전송 HTTP 200, 앵커 4개 온라인, 위치 이력 갱신 | 실제 앵커 좌표 등록·보정·실제 위치 정확도 |
| BNO085 | 핀 설정 후보 존재, 상태 `unverified` | 표준 UART/SHTP 드라이버·방향·낙상 구현/시험 |
| 호출어 | 서버 STT 결과에 별칭·유사도·후속 발화 게이트 적용 | ‘투투스’ 전용 로컬 WakeNet 모델 확보·평가 |
| 긴급어 | STT 결과의 긴급 표현은 호출어 없이 서버 판정 가능 | 로컬 긴급어 검출·오프라인 전달 보장 |
| 통화 | 기존 서버/웹 기능 존재 | P4 양방향 PCM 통화 미구현 |

초기 마이크 진단에서 PCM peak `1/32768`이 관측됐다. 이후 서버의 `last_audio_at` 갱신은 관측했지만, 이것만으로 실제 음성이 제대로 들어왔다거나 명령이 정상 인식됐다고 판단하지 않았다. **발화 중 PCM·서버 WAV·전사 내용을 함께 확인해야 한다.**

기존 서버 시험 77개 및 웹 TypeScript/Vite 빌드는 앞선 작업에서 통과했다. 이 인수인계 문서 작성 시 전체 시험을 새로 수행한 결과는 아니다.

### 4. 시스템 구조·주요 코드

```text
OV5647 → P4 CSI/ISP → 하드웨어 JPEG → 영상 전용 WebSocket
                                         ↓
                                   FastAPI → YOLO → React

INMP441 → P4 WebRTC NS → VAD/앞부분 보존 → WAV 업로드
                                                ↓
                      서버 STT → 호출어/긴급어 → intent/규칙/설명 AI
                                                ↓
                    Edge TTS → WAV → 별도 장치 명령 WS → P4 스피커

MAX17048 → P4 I2C1 → heartbeat → 서버/웹

UWB 앵커 4개 ↔ ESP32+DW3000 태그 → 자체 Wi-Fi → FastAPI 거리/위치 API
```

P4에는 내장 C6가 Wi-Fi를 담당한다. 외부 ESP32-C5는 초기 구조에 연결하지 않았고 ESP-NOW 통신도 사용하지 않는다. UWB 태그는 P4에 데이터선을 연결하지 않는다.

| 영역 | 주요 파일/폴더 |
|---|---|
| 현재 P4 통합 펌웨어 | `firmware/helmet_p4/` |
| P4 설정 | `sdkconfig.defaults`, `sdkconfig.dfr1172.example`, `main/Kconfig.projbuild` |
| P4 통신·명령 | `main/network.c`, `api_client.c`, `camera_transport.c`, `command_client.c` |
| P4 카메라·음성·센서 | `main/camera_source.c`, `voice.c`, `speaker.c`, `sensors.c`, `pin_guard.c` |
| 음성 실험 프로젝트 | `firmware/helmet_p4_voice_lab/` — 현재 안전모 통합 펌웨어와 구분 |
| 실제 UWB 다중 앵커 펌웨어 | `firmware/uwb_multi_test - 복사본/` |
| UWB 드라이버·도구 | `firmware/lib/Dw3000/`, `configure_wifi_tag.py`, `uwb_tool.py`, `uwb_live_bridge.py` |
| 서버 음성·Agent | `backend/app/routers/audio.py`, `services/audio_service.py`, `safety_agent_service.py`, `voice_execution_gate.py`, `tts_generator_service.py` |
| 서버 영상·위치 | `routers/camera.py`, `routers/uwb.py`, `services/camera_service.py`, `location_service.py`, `uwb_service.py` |
| 서버 설정 | `backend/app/config.py`, `backend/.env.example` |
| 웹 | `frontend/`, `frontend/vite.config.ts` |

`firmware/uwb_position_device` 등 다른 UWB 폴더에는 모의/미완성 드라이버 경로가 있으므로 실제 다중 앵커 태그에 잘못 업로드하지 않는다. 현재 사용한 것은 **`uwb_multi_test - 복사본`의 `tag` 환경**이다.

### 5. AI Agent 현재 모델·논리·한계

- STT: OpenAI `gpt-4o-mini-transcribe`, 한국어, 기본 제한 10초.
- 설명 생성: 설정상 OpenAI `gpt-6-luna`, reasoning none, 기본 최대 출력 80 tokens·제한 5초. 기존 PC의 단일 호출에서 확인한 설정이며 새 키에서도 접근 가능한지 확인한다.
- TTS: Edge TTS `ko-KR-SunHiNeural`, P4 재생용 16kHz/16bit/mono WAV.
- 배터리·PPE·위치·연결 상태 등은 서버 데이터·규칙으로 답하며 LLM을 호출하지 않는다.
- 긴급 표현은 일반 상태 질문보다 먼저 처리한다. 오래된 센서 값은 현재 상태로 단정하지 않고 ‘확인 불가’로 응답한다.
- 호출어 별칭 예: 투투스, 투투, 투투즈, 두두스. 서버 fuzzy 기본값 65는 매칭 임계값이며 인식 성공률 65%를 뜻하지 않는다.
- 현재 파이프라인은 **NS → VAD → 서버 STT → 호출어/긴급어 판단**이다. 맞춤 로컬 WakeNet이 이미 동작하는 구조가 아니다.
- 스피커 재생 중에는 마이크 구간을 버린다. AEC와 재생 중 긴급어 감지는 미완료다.
- 업로드 큐는 메모리 기반이다. 전원 차단·네트워크 실패 시 긴급 신고 보존·전달을 보장하지 않는다.

기존 PC 합성 음성 단일 연결 시험은 STT 약 7.0초, 설명 생성 약 3.7초, TTS 약 3.3초였다. 실제 마이크의 종단 지연이나 안정적인 성능 수치가 아니다. 사용자가 기억한 호출 성공률 60~70%도 정식 기준 시험 결과가 아니며, 현재 개선율을 숫자로 주장할 근거는 없다.

### 6. 새 PC 서버·웹 준비

기존 PC 실행 환경: Python **3.12.10**, Node **24.18.0**. Python 3.14에서는 선택 AI 패키지 일부가 설치되지 않으므로 재현에는 Python 3.12를 사용한다. ESP-IDF 전용 Python과 서버용 가상환경은 분리한다.

저장소 루트 PowerShell에서:

```powershell
py -3.12 -m venv backend\.venv
& .\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
& .\backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-ai.txt
Copy-Item backend\.env.example backend\.env
Set-Location frontend
npm.cmd ci
```

위 `.env` 복사는 **새 파일이 없는 최초 설치 때만** 한다. 이미 설정된 파일을 덮어쓰지 않는다. `TEAM_SETUP_WINDOWS.bat`도 있지만 기본 서버 의존성 설치 중심이며 실제 YOLO에는 AI 의존성이 추가로 필요하다.

#### backend/.env에 직접 설정할 항목

| 항목 | 설정 |
|---|---|
| `OPERATION_MODE` | `hardware` |
| `OPENAI_API_KEY` | 담당자가 발급·전달받은 유효 키를 로컬에 입력 |
| `CAMERA_INGEST_TOKEN` | 비어 있지 않은 토큰. P4 `HANMIR_CAMERA_TOKEN`과 동일 |
| `STT_MODEL`, `GPT_MODEL` | 현재 설정은 위 5절 참고. 새 계정의 접근 가능 여부 확인 |
| `YOLO_ENABLED`, `YOLO_MODEL_PATH` | `true`, backend 기준 `./best.pt` |
| `DATABASE_URL` | backend 기준 `sqlite:///./safety.db` 또는 새 PC 절대 경로 |
| `CORS_ORIGINS` | 사용하는 웹 origin. 아래 5173 예시에는 localhost/127.0.0.1:5173 |
| `SITE_WIDTH_M`, `SITE_HEIGHT_M` | 실제 현장 기준. DB의 기존 앵커/레이아웃 값도 함께 확인 |

기본 관리자 ID는 `TUTUS`이며 암호는 소유자에게 별도로 전달받는다. API 키·암호는 문서나 GitHub에 적지 않는다. `CALL_DEVICE_TOKEN` 등 기존 인증 설정도 사용하는 기능에 맞춰 별도 전달한다.

#### 실행 — 창 2개

창 1, backend 디렉터리:

```powershell
Set-Location C:\dev\hanmir\backend
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

창 2, frontend 디렉터리:

```powershell
Set-Location C:\dev\hanmir\frontend
npm.cmd run dev -- --host 0.0.0.0 --port 5173
```

이번 PC와 같은 주소는 `http://localhost:5173`, 서버 문서는 `http://localhost:8000/docs`다. 저장소 Vite 기본 포트와 `TEAM_RUN_FRONTEND.bat`는 **5174**이므로 위처럼 5173을 지정하지 않으면 포트·CORS를 5174에 맞춘다. 새 PC에서는 가상환경 위치가 root `.venv`인지 backend `.venv`인지 구분한다. 위 절차는 backend `.venv`로 통일했다.

P4·UWB가 PC에 접속할 수 있도록 Windows 방화벽의 해당 서버 8000 포트 접근을 허용하고 같은 LAN을 사용한다. 방화벽 전체를 끄지 않는다. 휴대폰 웹을 쓸 때 localhost는 휴대폰 자신이므로 실제 서버 주소·웹 프록시·CORS를 확인한다.

### 7. PC 변경 시 반드시 맞출 네트워크 설정

| 이전 확인값 | 용도 |
|---|---|
| `192.168.0.40:8000` | 기존 PC FastAPI 서버 |
| `192.168.0.43` | 기존 P4 DHCP 주소 |
| `192.168.0.20` | 기존 UWB 태그 DHCP 주소 |
| `WISET_2.4G` | P4 내장 C6·UWB 태그가 연결한 AP |
| `COM25` / `COM6` | 기존 PC P4 / UWB 태그 USB 포트 |

이 값들은 자동으로 새 PC에 맞춰지지 않는다. P4 내장 C6는 2.4GHz AP를 사용한다. PC는 같은 공유기의 5GHz에 연결해도 LAN 상호 접근이 허용되면 된다.

1. `ipconfig`로 새 PC의 해당 LAN IPv4를 확인한다.
2. P4 `HANMIR_SERVER_HOST`와 UWB `HANMIR_SERVER_URL`을 새 PC 주소로 수정한다.
3. 카메라 토큰을 서버와 P4에서 일치시킨다.
4. 변경한 두 장치를 각각 재빌드·업로드한다. 서버 `.env`만 고쳐서는 장치에 저장된 목적지가 바뀌지 않는다.
5. DHCP 주소 변경 재발을 줄이려면 서버 PC의 공유기 DHCP 예약을 검토한다.

### 8. P4 펌웨어 재현·업로드

현재 확인한 ESP-IDF는 **5.5.5**다. Espressif 공식 설치 도구로 설치하고 해당 버전의 ESP-IDF PowerShell 환경에서 진행한다. 기존 PC의 `Initialize-Idf.ps1` 설치 식별자는 새 PC에서 그대로 사용하지 않는다.

기존 빌드 작업 경로는 `C:\dev\hanmir-p4\helmet_p4`였다. 새 PC는 영문 clone 경로의 `firmware/helmet_p4`에서 빌드해도 된다. **이전에 빌드된 같은 폴더의 sdkconfig가 있으면 먼저 별도 보관하고 설정 차이를 확인한다.**

최초 빌드:

```powershell
Set-Location C:\dev\hanmir\firmware\helmet_p4
idf.py -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.dfr1172.example" set-target esp32p4
idf.py menuconfig
idf.py build
idf.py -p COM25 flash
idf.py -p COM25 monitor
```

COM25는 새 PC의 실제 P4 포트로 바꾼다. menuconfig의 **HANMIR P4 integration** 메뉴에서 SSID·암호·서버 IP/포트·카메라 토큰·ID를 설정한다. 연결하지 않은 부품은 해당 기능을 비활성화하거나 핀 `-1`로 유지한다. 예제는 기존 PC에서 연결한 부품 기준으로 카메라·음성을 활성화한다.

- 보드 rev 1.3: `CONFIG_ESP32P4_SELECTS_REV_LESS_V3=y` 및 16MB Flash/PSRAM 설정 확인.
- C6 SDIO: CLK18, CMD19, D0–D3=14–17, RESET54.
- 카메라: CSI 커넥터, SCCB SDA7/SCL8, OV5647 800×640 RAW8 모드, JPEG75·목표10FPS.
- INMP441: BCLK31, WS34, SD36, L/R=GND.
- MAX98357A: BCLK20, WS21, DIN22.
- MAX17048: **표준 I2C1**, SCL32/SDA33, 주소0x36. 카메라 SCCB도 주소0x36이지만 별도 버스를 사용한다.
- BNO085: UART RX23/TX51 후보. 현재 드라이버는 미구현이며 핀 설정만으로 동작하지 않는다.
- microSD GPIO39–45, 내장 C6 및 CSI 예약핀과 충돌하지 않도록 `pin_guard.c` 점검을 유지한다.

현재 펌웨어 버전 문자열은 `2.0.0-p4-hw-bringup-20261009`다. 같은 버전 문자열이어도 후속 수정이 있으므로 **Git 커밋도 함께 기록**한다. 부팅 시 스피커 송신은 켜지지 않아야 하고 실제 명령 때만 켜져야 한다.

`dependencies.lock`을 유지한다. 확인한 컴포넌트는 ESP-Hosted3.0.9, Wi-FiRemote1.6.5, ESP-SR2.5.5, ESP-Video2.5.0, ESP-Cam-Sensor2.6.0이다. C6 출고 버전이 0.0.0으로 표시돼 호스트 버전 경고가 있었으나 연결은 동작했다. 제조사 절차 확인 없이 내장 C6를 재플래시하지 않는다.

### 9. UWB 태그 재현·업로드 및 위치 문제

현재 실제 태그는 ESP32-D0WD-V3 + DW3000, USB CP210x(COM6)다. 앵커 번호는 펌웨어 0~3 ↔ 서버 anchor-001~004 대응이다.

저장소 루트에서:

```powershell
& .\backend\.venv\Scripts\python.exe -m pip install platformio
& .\backend\.venv\Scripts\python.exe configure_wifi_tag.py
& .\backend\.venv\Scripts\python.exe uwb_tool.py upload --role tag-multi --port COM6
```

설정 도구에서 2.4GHz SSID·암호·새 서버 PC IP를 입력한다. `wifi_secrets.h`는 Git 제외 파일이다. 도구는 프로젝트·라이브러리를 영문 경로에 복사하고 PlatformIO도 영문 코어 경로를 사용한다. 최초 설치에는 패키지 다운로드가 필요하다. COM6는 실제 태그 포트로 바꾼다. **앵커에 태그 펌웨어를 올리지 않는다.**

기존 PC의 수동 빌드 경로는 `C:\dev\hanmir-uwb-link\uwb_multi_test`였고, 글로벌 패키지의 한글 경로 컴파일 문제를 영문 경로로 해결했다. 이 경로와 패키지 junction은 새 PC에 필수 복사할 데이터가 아니다. 재현 도구의 영문 경로로 새 환경을 구성한다.

#### 복구 결과

기존 태그의 목적지가 `192.168.0.27`로 남아 `POST failed: -1`이 반복됐다. `.40`으로 고친 태그 앱을 업로드하고 해시 검증했다. 18초 시리얼 관찰: 거리 프레임54개, 4앵커 수신53개, HTTP200 53건, 전송 실패0건. 원시 거리 중앙값은 3.50 / 2.04 / 1.04 / 3.89m였다. 태그와 앵커4개 모두 온라인이며 `last_uwb_at`과 위치 이력의 새 데이터로 수신을 확인했다. USB 브리지는 실행하지 않았다.

#### 아직 해결하지 않은 위치 정확도

서버 등록 좌표는 `(0,0)`, `(5.8,0)`, `(5.8,8.2)`, `(0,8.2)`m이고 실제 설치 배치는 미확인이다. 신뢰도는 **0.05**였다. 이는 잔차 기반 코드 지표이며 정확도5%가 아니다. 관측된 거리 관계가 등록 좌표와 맞지 않아 계산된 위치를 실제 위치로 확정하면 안 된다.

담당자가 확인할 항목:

1. 1~4번 앵커의 실제 번호·좌표, 공간 가로·세로, 태그/앵커 높이.
2. DB에 등록된 앵커 및 레이아웃을 실제 배치로 수정. `.env`의 공간 크기만 바꾸고 기존 DB가 자동 갱신된다고 가정하지 않는다.
3. `uwb_calibration.json`과 서버 거리 보정 확인. 이미 보정한 거리를 다시 보정하지 않는다.
4. 현재 `location_service.py`는 수평2D 모델로 z값을 사용하지 않는다. 높이 차이 보정이 필요한지 실물 시험 후 결정한다.
5. 알려진 위치에서 정지·이동 시험. 필터가 작은 흔들림의 이력을 억제하므로 지도 점이 잠시 정지했다고 수신 실패로 판단하지 않는다. `last_uwb_at`도 확인한다.

USB를 빼도 태그 자체 Wi-Fi 전송은 가능하지만 안전모 전원은 유지돼야 한다. `uwb_live_bridge.py`는 USB 진단 대안이며 태그 직접 전송과 동시에 켜 중복 데이터를 보내지 않는다.

### 10. GitHub 외에 따로 인수할 로컬 데이터

| 데이터 | 전달/설정 방법 |
|---|---|
| API 키·Wi-Fi 암호·장치 토큰 | 소유자에게 별도로 전달받거나 새로 설정. MD/Git에 넣지 않음 |
| `backend/.env` | 새 PC 경로·토큰에 맞춰 재작성 |
| `backend/safety.db` | 기존 현장 좌표·이력·계정을 이어받으려면 별도 전달. 서버 중지 후 일관된 DB 사본 확보 |
| `backend/best.pt` | Git 추적 파일. clone 후 실파일 및 모델 로드 확인 |
| `uwb_calibration.json` | Git 추적 파일. 실제 설치의 보정값인지 확인 |
| P4 로컬 `sdkconfig` | 비밀값 포함. 필요하면 별도 전달 후 새 IP/포트/설정 재검토 |
| UWB `wifi_secrets.h` | 비밀값 포함. 새 PC에서 설정 도구로 재생성 권장 |
| 가상환경·node_modules·빌드 캐시 | 새 PC에서 재설치. 기존 폴더를 그대로 복사하지 않음 |
| 진단 로그·캡처 | 기존 PC `C:\dev\hanmir-runtime`에서 필요한 파일만 별도 전달 |
| P4 원본 전체 백업 | 기존 PC `C:\dev\hanmir-runtime\p4-original-flash.bin` 16MB. 비밀값 포함 가능하므로 Git 제외 |
| UWB 원본 진단 파일 | `uwb-tag-app-prefix.bin`은 앞부분256KiB뿐. 전체 복원용 백업이 아님 |

기존 DB를 전달하지 않으면 새 서버는 초기 데이터로 시작하며 기존 관제 이력·현장 배치가 자동 복원되지 않는다. 원본 백업·로그는 GitHub에 없다.

### 11. 다음 담당자의 실제 작업 순서

#### 1순위 — 새 PC 연결 복구

1. 브랜치 clone, Python/Node/IDF 환경 구성, 비밀설정·필요 DB 인수.
2. 서버8000·웹5173 또는5174 실행. 모델 로드·관리자 로그인 확인.
3. 서버 LAN IP 확인 후 P4·UWB 목적지 및 토큰 갱신·업로드.
4. `GET /api/dashboard/snapshot`에서 hardware모드·장치 온라인·최근 수신 시각 확인.
5. 웹 원본 영상 및 서버 `GET /api/locations/worker-001/history?limit=5`의 새 UWB 이력 확인. 과거 DB 값을 정상 수신으로 오인하지 않음.

#### 2순위 — UWB 정확도

실제 앵커 위치와 서버좌표를 일치시킨 뒤 알려진 위치에서 거리·필터·좌표를 비교한다. 정확도가 확인되기 전 대피 방향·위험구역 진입 위치를 정확하다고 보장하지 않는다.

#### 3순위 — 마이크·음성 전체 경로

1. 배선·3.3V·L/R·I2S 채널 확인, 발화 중 PCM peak 및 WAV 내용 확인.
2. ‘투투스 배터리 얼마야’: 전사 → 호출어 → intent → 최신 배터리 답변 → 스피커 청취.
3. 시험임을 공유한 상태에서 ‘살려주세요’, ‘불이야’: 호출어 없이 긴급 판정·관제 기록·응답 확인. 시험 이벤트는 정리.
4. 화자·거리·소음·문구를 고정해 미탐·오탐·P50/P95 지연을 측정하고, 이후 맞춤 WakeNet/긴급어 모델·AEC를 검토.

#### 4순위 — 영상·통신 성능

사람/PPE를 향한 장면에서 원본 품질부터 확인한다. 캡처 목표10FPS와 실제 수신·추론FPS는 다르다. 원본 수신FPS, YOLO처리FPS, 큐·드롭·종단 지연을 카메라 단독/음성 동시/UWB 동시로 측정한다. 기존 PC 추론은 CPU였으며 GPU 환경이라면 별도로 구성·기록한다.

#### 그다음

BNO085 표준 UART/SHTP 실물 모드 확인과 드라이버 구현, 양방향 통화, 오프라인 긴급 보존, microSD 로그 등은 별도 구현·시험 후 완료 처리한다. GPIO는 사용자 최종 배선표와 보드 예약핀을 기준으로 관리한다.

### 12. 다음 담당자/Codex에게 그대로 전달할 요청

> HANMIR 2.0 작업을 이어받아 주세요. `feature/mobile-safety-app-20261001`의 최신 코드와 `docs/HANMIR_2_PC_HANDOFF_2026-10-09.md`를 먼저 읽으세요. P4 실물 기본 구동과 독립 UWB 태그 전송은 확인했지만 UWB 좌표 보정, 실제 마이크 인식률, BNO085, 맞춤 WakeNet, 양방향 통화는 미완료입니다. 새 PC 서버 주소·카메라 토큰을 P4와 UWB에 맞춰 연결부터 복구하고, UWB 실제 배치와 마이크 유효 입력을 우선 확인해 주세요. 기존 코드를 지우거나 GPIO를 임의로 확정하지 말고, 실제 로그와 최신 수신값을 근거로 작업하고 변경내용·남은 한계를 기록해 주세요.

이 요청과 MD는 작업 기준을 전달한다. 실제 HW·설정·유효 API 키가 없으면 자동으로 모든 기능이 완료되는 것은 아니다.

### 13. 함께 읽을 자료

- [2026-10-09 실물 구동·검증 상세 기록](HANMIR_2_P4_FIRST_BOOT_2026-10-09.md) — 초반 기록보다 뒤의 UWB복구 절이 최신.
- [P4 통합 펌웨어 안내](../firmware/helmet_p4/README.md)
- [P4 통신 개편 계획](HANMIR_2_P4_COMMUNICATION_PLAN_2026-10-02.md)
- [음성 준비 기록](HANMIR_2_VOICE_PREP_2026-10-02.md)
- [하드웨어 재설계 문서](HARDWARE_REDESIGN_ESP32P4.md), [현재 하드웨어 상태](CURRENT_HARDWARE_WIRING_STATUS.md)

문서 내용이 다르면 2026-10-01 사용자 최종 배선표와 실제 보드 확인, 최신 커밋의 코드·실물 로그를 대조한다. 오래된 설계 계획을 현재 완료 기능으로 취급하지 않는다.


---

## 부록 2: HANMIR_2_P4_FIRST_BOOT_2026-10-09.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## HANMIR 2.0 — P4 실물 초기 구동 및 서버·웹 검증

작성일: 2026-10-09. 브랜치: `feature/mobile-safety-app-20261001`.

**최신 상태 안내:** 아래 초기 구동 기록은 확인 순서대로 보존했다. 이후 UWB 태그 연결은 8절에서 복구했고, 서버의 음성 수신 시각 갱신도 관측했으나 실제 마이크 음질·인식 검증은 미완료다. 다른 PC 인수에는 [최신 인수인계 문서](HANMIR_2_PC_HANDOFF_2026-10-09.md)를 먼저 읽는다.

### 1. 실제 확인한 결과

| 항목 | 확인 결과 | 확인 방법 |
|---|---|---|
| ESP32-P4 | DFR1172, 칩 rev 1.3, 16MB Flash, 32MB PSRAM | COM25 부팅 로그, PSRAM 메모리 시험 |
| 펌웨어 업로드 | ESP-IDF 5.5.5 빌드·플래시, 기록 해시 검증 성공 | esptool 로그 |
| 원본 복구 | 플래시 전체 16MB 백업 확보 | PC 로컬 백업 파일 |
| 내장 C6 통신 | P4→C6 SDIO 4비트 40MHz, Wi-Fi 접속 | SDIO 초기화 및 IP 이벤트 |
| 서버 연결 | 장치 등록·heartbeat HTTP 200, 명령·영상 WS 연결 | FastAPI 로그 |
| OV5647 | 센서 PID 0x5647, 800×640 캡처·JPEG 전송 | 보드 로그 및 웹 실제 천장 영상 |
| YOLO | 서버 `best.pt` 모델 로드·실제 추론 | 카메라 API의 `analysis.mode=real` |
| MAX17048 | SOC 약 9% 읽힘 | heartbeat 배터리 값. 정확도·충방전 추적은 별도 검증 |
| 스피커 | 웹 명령 전달 및 WAV 재생 완료 보고 | `last_speaker_status=ok`. 사람이 듣는 음질은 별도 확인 |
| 마이크 처리 | INMP441 I2S·AFE VAD·독립 WebRTC NS 초기화 | 보드 로그. 실제 음성 녹음·인식률 검증은 미완료 |
| OpenAI | API 인증·설정 모델 접근 및 합성 음성 STT/설명 응답 성공 | 로컬 환경에서 API 호출 |
| 웹 | 실시간 연결 복구·P4 영상·배터리 규칙 응답 | 브라우저 확인 |
| 서버 회귀 시험 | 77개 통과 | `pytest tests -q` |
| 웹 빌드 | TypeScript 및 Vite production 빌드 성공 | tsc·Vite 로그 |

**전 기능 완료를 뜻하지 않는다.** 아직 사람을 향한 PPE 정확도, 실제 마이크 호출 성공률, 긴급 음성 종단 전달 시간, 양방향 통화, BNO085 방향·낙상 판정은 확인하지 않았다. UWB 태그는 독립 장치이며 이번 연결에서 오프라인이다.

최종 업로드된 버전은 `2.0.0-p4-hw-bringup-20261009`이다. heartbeat에서 camera=capturing, battery=ready, speaker=initialized, mic=initialized, noise_suppression=ready를 확인했다. **마이크 PCM peak는 1/32768이고 실제 음성 업로드는 아직 없다.** 초기화는 됐지만 유효 음성 입력을 확인하지 못했다. 발화 중에도 같은 값이면 INMP441 3.3V·GND·L/R=GND·BCLK31·WS34·SD36 배선과 채널을 확인한다.

### 2. 이번에 수정한 펌웨어

- 칩 rev 1.3에 필요한 `ESP32P4_SELECTS_REV_LESS_V3` 설정. rev 3 기본 이미지와 혼용하지 않는다.
- DFR1172의 내장 C6 SDIO 핀: CLK18, CMD19, D0–D3=14–17, RESET54. 제조사 자료를 기준으로 설정.
- OV5647 캡처 빈 함수를 V4L2 MIPI CSI·ISP RGB565·하드웨어 JPEG 경로로 구현.
- 초기 영상 설정은 800×640, JPEG 품질 75, 캡처 목표 최대 10 FPS. 카메라 센서 내부 모드 50 FPS와 서버 수신·추론 FPS는 서로 다르다.
- 최신 프레임 1장 큐와 기존 HMR2 바이너리 WS 전송을 연결. 오래된 프레임은 버리므로 프레임 드롭 수 자체가 전송 실패 횟수를 뜻하지 않는다.
- AFE에 `WEBRTC`를 NS 모델 이름으로 넣던 설정은 런타임 초기화에 실패했다. `esp_ns.h`의 WebRTC NS를 독립 10ms 프레임으로 처리한 뒤 AFE VAD로 전달하도록 수정.
- AFE 프레임 512샘플과 NS 프레임 160샘플 크기가 달라 버퍼로 연결. NS 초기화 상태와 마이크 PCM peak 로그를 추가.
- heartbeat에 카메라 캡처·마이크·NS·스피커·배터리·IMU의 실제 초기화 상태를 반영하도록 수정. 초기화 성공은 음질이나 인식률 평가 성공과 다르다.
- 부팅 시 스피커 I2S 송신을 켜지 않도록 변경. 실제 음성·경고 명령에서만 송신을 켜고 재생이 끝나면 끈다. DMA 자동 비우기를 적용해 이전 PCM 반복 출력을 방지한다. 현재 P4 코드에는 별도의 5초 부팅 테스트 호출이 없다.
- `sdkconfig.dfr1172.example`에 연결한 외부 부품 핀과 카메라 센서 선택을 제공. Wi-Fi 비밀번호와 토큰은 포함하지 않는다.
- `dependencies.lock`에 이번 컴포넌트 버전을 기록. ESP-Hosted 3.0.9, Wi-Fi Remote 1.6.5, ESP-SR 2.5.5, ESP-Video 2.5.0, ESP-Cam-Sensor 2.6.0.

#### 확인 과정에서 해결한 문제

1. Wi-Fi SSID `WISET`로는 AP를 찾지 못했다. PC의 실제 스캔 결과 `WISET_2.4G`를 적용해 접속했다.
2. 첫 카메라 초기화는 센서 ID 읽기가 실패했다. 사용자가 카메라 연결을 확인한 뒤 재부팅에서 PID 및 영상 캡처가 성공했다.
3. AFE NS 모델 초기화 실패를 독립 WebRTC NS 경로로 수정했다.
4. C6는 출고 버전을 `0.0.0`으로 보고하여 호스트와 버전 불일치 로그가 있다. 실제 SDIO·Wi-Fi·WS 통신은 동작했으며 C6를 별도 플래시하지 않았다. 장시간 부하·재접속은 추가 시험한다.

### 3. 현재 AI Agent와 수정 내용

#### 모델과 처리 위치

- STT: 서버 OpenAI `gpt-4o-mini-transcribe`.
- 설명형 응답: 서버 OpenAI `gpt-6-luna`, reasoning none, 짧은 출력·호출 시간 제한.
- TTS: 서버 Edge TTS 한국어 음성 → 16kHz·16bit·mono WAV → P4 I2S 스피커.
- P4 로컬: 마이크 입력, WebRTC NS, VAD, 300ms pre-roll, 최대 5초 WAV 구간, 업로드, 명령 수신·재생.
- 서버 로컬: 호출어 게이트, intent 분류, 상태·배터리·위치·PPE 답변, 위험 규칙, 대피 계산, 긴급 처리.

#### 답변 로직

1. 긴급어·신체 위험 표현을 일반 상태 질문·관리자 연결보다 먼저 판정한다.
2. 배터리·PPE·장치 상태·방향 질문 intent를 추가하고 단순 조회에서 LLM을 호출하지 않는다.
3. 위치는 최근 UWB 수신, PPE·영상 상태는 최근 카메라 수신, 배터리는 최근 장치 heartbeat를 근거로 한다.
4. 최신 정보가 없으면 과거 DB 값으로 현재 상태를 확정하거나 안전한 작업 지속을 권하지 않고 ‘확인 불가’로 답한다.
5. 설명형 AI에도 최신 정보가 없는 센서 값은 ‘확인 불가’로 전달한다.
6. BNO085 방향 데이터가 구현·검증되지 않아 방향 질문은 확인 불가로 응답한다.

#### 호출어·긴급어의 현재 한계

‘투투스’ 전용 WakeNet과 로컬 긴급어 모델은 아직 없다. 현재는 **소음 제거 → VAD 녹음 → 서버 STT → 호출어/긴급어 판정**이다. ‘살려주세요’, ‘화재발생’, ‘불이야’ 등은 서버 게이트에서 호출어 없이 통과하지만, 네트워크·STT가 실패하면 로컬에서 긴급 신고를 확정할 수 없다. 스피커 재생 중에는 마이크 구간을 버리므로 재생 중 비상어 감지는 현재 지원하지 않는다.

사용자가 기억하는 60~70% 성공률은 기준 측정치가 아니다. 이번 초기화·합성 음성 API 확인만으로 향상률을 주장할 수 없다. 같은 화자·거리·소음·문구의 반복 실험에서 미탐·오탐·P50/P95 지연을 측정해야 한다.

합성 음성 단일 연결 시험: TTS 약 3.3초, STT 약 7.0초, 설명 생성 약 3.7초. 캐시·네트워크·PC 부하의 영향을 받으며 실제 마이크 호출의 종단 지연이나 정상 성능 목표를 뜻하지 않는다.

### 4. 웹 수정

- React 개발 모드 effect 정리 시 WebSocket 연결 중 상태가 남아 재접속을 막던 문제를 수정. 정리 시 연결 플래그·소켓·이벤트 핸들러를 초기화.
- Vite의 `/tts` 프록시 추가.
- 서버와 웹을 실제 hardware 모드로 시작. 웹에서 장치 1/2 연결 및 실시간 카메라 원본 수신을 확인.

### 5. PC 실행 환경과 재현

- 저장소: `C:\Users\조성준\OneDrive - pukyong.ac.kr\바탕 화면\hanmmir2.0`
- IDF: `C:\Espressif\frameworks\esp-idf-v5.5.5`
- IDF Python: `C:\Espressif\python_env\idf5.5_py3.12_env`
- ASCII 빌드 경로: `C:\dev\hanmir-p4\helmet_p4`
- 장치 포트: COM25. USB 재연결 시 바뀔 수 있다.
- 웹: `http://localhost:5173`, 서버: `http://localhost:8000`.
- 현재 LAN: 서버 PC `192.168.0.40`, P4 `192.168.0.43`. DHCP 주소는 재확인한다.
- 원본 백업: `C:\dev\hanmir-runtime\p4-original-flash.bin`.
- 로그·웹 캡처: `C:\dev\hanmir-runtime`.

빌드는 공식 IDF 환경을 초기화한 PowerShell에서 `idf.py set-target esp32p4`, `idf.py menuconfig`, `idf.py build`, `idf.py -p COM25 flash` 순서로 진행한다. 한글·공백이 있는 저장소 경로 대신 ASCII 작업 경로를 사용했다. 보드 설정 예제를 defaults와 함께 적용하되 SSID·서버주소·카메라 토큰은 사용 장소의 로컬 설정에 입력한다.

서버는 루트 `.venv` Python으로 backend 디렉터리에서 `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`, 웹은 frontend에서 `npm run dev -- --host 0.0.0.0 --port 5173`으로 시작한다. 서버 `backend/.env`의 카메라 토큰과 P4 설정을 일치시킨다.

API 키·비밀번호·카메라 토큰·로컬 sdkconfig·백업 이미지·설정이 포함된 펌웨어 바이너리는 Git에 올리지 않는다. 새 PC에서는 별도로 설정해야 한다.

### 6. 이어서 할 실물 시험

1. 마이크 가까이서 ‘투투스 배터리 얼마야’를 말하고 PCM peak, WAV 업로드, STT 텍스트, intent, 스피커 완료 로그를 대조.
2. 실제 스피커 청취 확인. 소리·음량·잡음·재생 중 마이크 중단 동작 확인.
3. 테스트 환경에서 ‘살려주세요’, ‘불이야’를 호출어 없이 시험. 긴급 이벤트·관제 표시·응답 시간을 확인하고 시험 경보를 정리.
4. 사람과 보호구가 보이는 장면에서 원본/분석 영상을 비교. 이번 천장 장면만으로 PPE 인식률을 평가하지 않는다.
5. 빌드를 멈춘 PC에서 영상 수신 FPS·YOLO 분석 FPS·지연·드롭을 각각 측정. 현재 YOLO는 CPU로 동작한다.
6. BNO085 모드·UART baud·SHTP 보고 검증 후 방향·낙상 기능 구현. 현재 펌웨어는 낙상·방향을 보고하지 않는다.
7. 양방향 통화 PCM, 오프라인 긴급 전달 보존, 맞춤 WakeNet·긴급어 모델, AEC는 별도 작업으로 남아 있다.

### 7. 기준 자료

- [DFRobot 보드·SDIO 핀 자료](https://wiki.dfrobot.com/dfr1172/)
- [Espressif 공식 영상 예제](https://github.com/espressif/esp-video-components/tree/master/esp_video/examples/capture_stream)
- 저장소의 2026-10-01 최종 HW 배선 및 기존 HANMIR 서버·S3 코드.

### 8. UWB 태그 연결 복구 및 실물 확인

2026-10-09 13:10 KST 기준, P4와 별도 장치인 ESP32 + DW3000 태그를 COM6으로 연결해 확인했다. UWB 앵커 펌웨어는 변경하지 않았다.

#### 원인과 조치

- 기존 태그는 앵커 0~3의 거리를 수신했지만 HTTP 전송에서 `POST failed: -1`이 반복됐다.
- 기존 앱 이미지에서 확인한 목적지는 `http://192.168.0.27:8000/api/uwb/distances`였다. 현재 서버 PC는 `192.168.0.40`이다.
- 실제 다중 앵커 프로젝트인 `firmware/uwb_multi_test - 복사본`을 사용해 현재 서버 주소를 적용했다. Wi-Fi 설정은 로컬 `include/wifi_secrets.h`에만 저장하고 Git에서 제외했다.
- 영문 작업 경로에서 PlatformIO 태그 빌드 성공. 앱 크기 814,160 bytes. COM6의 앱 영역 `0x10000`에 업로드하고 플래시 해시 검증을 통과했다. 이번 UWB 작업에서 전체 플래시 백업은 완료하지 못했으며, 로컬의 `uwb-tag-app-prefix.bin`은 앱 앞부분 256 KiB만 읽은 진단 자료다.
- `configure_wifi_tag.py`와 `uwb_tool.py`가 실제 프로젝트 폴더를 찾도록 보완하고, 복사본 폴더를 사용해도 스테이징 경로는 영문으로 만들도록 수정했다.

#### 확인 결과

- 태그 Wi-Fi IP: `192.168.0.20`. 서버 주소 `.40`과 구분한다.
- 약 18초 시리얼 관찰에서 HTTP 200 응답 53건, `POST failed` 0건을 확인했다. 거리 프레임 54개 중 53개는 앵커 4개 모두 수신했으며 1개는 3개 수신했다. 장시간 안정성 시험 결과는 아니다.
- 4개 모두 수신한 프레임의 원시 거리 중앙값: 앵커 1~4 순서로 3.50 / 2.04 / 1.04 / 3.89 m. 서버에는 기존 거리 보정이 적용된다.
- 서버에서 `helmet-001-uwb` 및 앵커 001~004 모두 온라인. `last_uwb_at`이 04:09:35Z에서 04:10:09Z로 갱신됐고 위치 이력 API에도 새 좌표가 기록됐다. 이번 확인은 시리얼·서버 API 기준이며 웹 지도 화면을 추가로 관찰한 결과는 아니다.
- 태그 자체 Wi-Fi로 전송하며 PC의 USB 시리얼 브리지는 실행하지 않았다. USB를 빼면 태그에 안전모 전원이 유지돼야 한다.

#### 위치 정확도는 추가 설정 필요

서버 앵커 좌표는 현재 `(0,0)`, `(5.8,0)`, `(5.8,8.2)`, `(0,8.2)` m다. 실제 설치 위치는 아직 확인하지 않았다. 위치 계산 신뢰도는 `0.05`로 낮으며 이는 코드의 잔차 기반 지표이고 실제 정확도 5%를 뜻하지 않는다. 기록된 `(약 1.8, 4.6)` m를 정확한 실물 위치로 해석하면 안 된다.

예를 들어 등록된 앵커 2~3 간격은 8.2 m인데 관측 거리 합은 약 3.08 m라 현재 등록 좌표와 원시 거리의 기하 관계가 맞지 않는다. 실제 앵커 배치·번호 대응·거리 보정을 확인해야 한다. 현재 계산기는 수평 2D 거리 모델이며 앵커의 z 값을 계산에 사용하지 않으므로 설치 높이 차이도 후속 검토 대상이다. 좌표를 임의로 변경하지 않았다.

다음 작업은 앵커 실제 좌표와 공간 크기를 등록하고, 알려진 위치의 태그를 이동시키면서 거리·좌표·지연·신뢰도를 대조하는 것이다. 서버 PC 주소가 DHCP로 바뀌면 로컬 태그 설정을 갱신해 재업로드해야 하므로 공유기 DHCP 예약도 고려한다.

로컬 증거: `C:\dev\hanmir-runtime\uwb-tag-after-flash.log`, `uwb-tag-flash.log`, `uwb-live-verification.json`. 설정이 포함된 펌웨어 바이너리는 Git에 올리지 않는다.


---

## 부록 3: BNO085_UART_FIX_2026-10-09.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## BNO085 UART 방향 데이터 수신 복구 — 2026-10-09

### 결과

DFR1172 ESP32-P4(COM25)에 수정 펌웨어를 실제 플래시했고, BNO085의 rotation vector 10 Hz 수신 및 yaw/pitch/roll 계산을 확인했다. 22초 부팅 로그에서 방향값이 지속 출력됐으며 watchdog 재발은 관찰되지 않았다.

실측 로그 예:

```text
BNO085 SH-2 reset complete
BNO085 rotation-vector report enabled at 10 Hz
BNO085 orientation yaw=154.5 pitch=77.8 roll=-11.8 deg
BNO085 orientation yaw=148.1 pitch=77.8 roll=-18.3 deg
BNO085 orientation yaw=146.6 pitch=77.8 roll=-19.6 deg
```

### 원인과 수정

GPIO23(RX)/GPIO51(TX)는 펌웨어 pin guard에서 예약 핀 또는 중복 사용으로 검출되지 않았다. 센서는 명령마다 SHTP 채널 0 오류 목록을 반환했으므로 양방향 UART 경로는 동작했다.

기존 송신은 UART-SHTP 프레임 전체를 3 Mbps로 연속 전송했다. 수신 오류 프레임은 `0f 00 00 <seq> 01 02 02 02 02 02 02 02 02 02 0c`였다. CEVA SHTP 문서상 응답 1은 오류 목록, 오류 2는 4바이트 헤더보다 짧은 host write, 오류 12는 오류 목록 잘림이다. 리셋은 실제로 완료되지 않았고 방향 리포트도 활성화되지 않았다.

기준 BNO08x UART HAL과 같이 송신 바이트마다 TX 완료를 기다리고 1 ms 간격을 추가했다. 같은 배선에서 그 수정 후 정상 advertisement(276바이트), SH-2 초기화, 채널 1 reset complete, rotation vector가 차례로 수신됐다. 따라서 이번 증상은 송신 타이밍 문제로 해결됐다. RX 버퍼 초기 정리와 제한된 리셋 재시도도 적용했다.

SH-2 동기 폴링에는 task yield를 추가해 idle task를 굶겨 watchdog을 발생시키는 소프트웨어 문제도 보완했다.

### 유지 설정

- 센서 TX(SDA) → P4 GPIO23 / UART1 RX
- 센서 RX(SCL) → P4 GPIO51 / UART1 TX
- UART-SHTP 모드: P1 HIGH, P0 LOW
- UART: 3,000,000 baud, 8N1
- `CONFIG_HANMIR_ENABLE_BNO_SH2=y`: DFR1172 보드 설정 예제에 저장
- rotation vector: 100,000 us 간격(10 Hz)

현재 실기 빌드 위치는 `C:\dev\hanmir-p4\helmet_p4`이고, 원본 코드는 저장소 `firmware/helmet_p4/main/sensors.c`에 반영했다. 기존 sdkconfig를 재사용하는 PC는 `CONFIG_HANMIR_ENABLE_BNO_SH2=y` 설정을 확인해야 한다.

방향값 수신은 확인했으나 장착 축, 자기장 보정, 실제 방위와의 오차는 아직 검증하지 않았다. 서버는 현재 로그에서 Wi-Fi 연결 실패 및 `192.168.0.40:8000` 접근 불가가 관찰돼 웹 표시 확인은 별도 네트워크 복구가 필요하다.

### 근거

- 실기 로그: `C:\dev\hanmir-runtime\bno-startup-debug.log`
- [CEVA Sensor Hub Transport Protocol](https://www.ceva-ip.com/wp-content/uploads/Sensor-Hub-Transport-Protocol.pdf), UART 송신 간격 및 오류 목록 정의
- Adafruit BNO08x 기준 구현의 UART HAL은 바이트마다 1 ms 간격으로 송신한다.


---

## 부록 4: HARDWARE_WEB_VERIFICATION_2026-10-09.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## HANMIR P4 실물·웹 기능 검증 — 2026-10-09

### 검증 환경

- PC 서버: 192.168.0.222:8000, 웹: http://localhost:5173
- 실제 Windows 연결 SSID: AIHSLab2. 사용자 전달 SSID와 차이가 있어 실제 연결 프로필을 기준으로 설정했다.
- P4: COM25, Wi-Fi IP 192.168.0.226. UWB 태그: COM6, IP 192.168.0.227.
- P4 및 UWB 태그의 이전 Wi-Fi·서버 설정을 현재 환경으로 변경하고 빌드·업로드 완료.
- 비밀번호와 API 키는 이 문서에 포함하지 않는다. 로컬 설정을 다른 PC에서 재입력해야 한다.
- 서버는 hardware 모드. 웹 진단 최종 결과: 장치 2/2 온라인, 앵커 4/4 수신, recent_errors 빈 목록.

### 확인 결과

| 항목 | 확인 근거 | 결과 |
| --- | --- | --- |
| P4 통신 | heartbeat, 명령 WebSocket, 카메라 WebSocket | 실제 서버 연결 확인 |
| OV5647 | 실내 원본 영상, live frame 번호와 수신 시각 갱신 | 영상 수신 확인 |
| YOLO | 보호구 미착용인 사람을 사용자가 비춤. 웹에 전방 사람 추적 및 안전모·조끼·장갑 미착용 표시 | 해당 장면에서 일치 확인 |
| INMP441 | 실제 PCM peak 2914/32768, 음성 업로드 HTTP 200 | 마이크 입력·서버 업로드 확인 |
| 음성 명령 | 사용자가 ‘투투스 배터리 얼마야’ 발화. 명령 ID 8에 ‘배터리얼마야’, battery_query, confidence 0.98 기록 | 실제 STT·명령 분류 확인 |
| 스피커/TTS | 웹 배터리 조회 응답 재생, 장치 ok 응답, 사용자 ‘들림’ 확인 | 실제 소리 확인 |
| MAX17048 | heartbeat SOC 약 8.96%, 웹 9%, 음성 응답 9퍼센트 | 값 수신 확인. 실제 잔량 정확도는 별도 검증 |
| BNO085 | SH-2 reset_seen=1, report_enabled=1, yaw/pitch/roll 지속 수신. 사용자가 비틀었을 때 각도 변함 | 회전 데이터 확인 |
| UWB | 태그 로그 POST 200, 실시간 앵커 4개, 지도 좌표 갱신 | 거리 전송·위치 계산·지도 표시 확인 |
| 규칙 기반 AI | 배터리 질문 즉시 데이터 기반 응답 | 확인 |
| 설명형 AI | 웹 ‘현재 상황을 설명해줘’에 설명 응답 생성 및 TTS 전달 | 호출 경로 동작 확인 |

음성 명령의 confidence 0.98은 명령 분류 점수이며, STT 정확도 98% 또는 웨이크워드 성공률 98%를 의미하지 않는다.

### BNO085 수정 요약

GPIO23 RX / GPIO51 TX는 기존 배정대로 유지했다. UART 전송 시 SH-2 프레임을 한 번에 보내는 방식에서 바이트별 전송 및 1ms 간격으로 변경한 뒤 센서 보고가 시작됐다. UART 무수신 대기에는 태스크 yield를 추가했다. 상세 근거는 `BNO085_UART_FIX_2026-10-09.md` 참고.

각도는 센서 좌표계이다. 안전모 장착 방향·수평·북쪽 기준 보정 전에는 현재 yaw를 현장 이동 방향으로 단정하면 안 된다. 음성 heading_query는 아직 ‘확인 불가’ 응답이므로 웹 각도 표시와 음성 방향 안내의 구현 범위가 다르다.

### 측정한 영상 성능

19:21 무렵 약 10.03초 구간의 서버 카운터 차이:

- 영상 수신: 약 2.99fps.
- YOLO 분석 완료: 약 2.19fps.
- 마지막 추론 시간: 48.5ms.
- 분석 대기열 깊이: 0, 최대 대기열: 1.

이 값은 짧은 실험 결과이다. 설정 목표 분석 4fps를 지속 달성했다고 볼 수 없다. P4 로그에 transport drops 누적도 존재하므로 촬영·전송·음성 처리 동시 부하 및 WebSocket 재연결 원인을 추가 측정해야 한다. 정상 연결과 병목 해소 완료는 별개의 검증 항목이다.

### 남은 검증 및 발견한 제한

1. UWB 좌표는 갱신되지만 실제 앵커 좌표와 배치, 정답 위치를 대조하지 않았다. 지도 신뢰도 약 50~52%는 실측 오차를 대신하지 않는다.
2. 영상 속도·재연결·프레임 폐기의 원인은 장시간 로그와 구간별 지연 측정이 필요하다.
3. 단일 음성 발화 성공으로 기존 호출 성공률 60~70%가 개선됐다고 결론낼 수 없다. 조용한 환경/현장 소음/거리별 반복 실험 필요.
4. 카메라는 전방 작업자를 판정한다. AI 설명 코드 `assistant_service.py`는 worker.ppe 값을 사용하며 전방 사람 PPE와 별개의 값이다. 실제 설명에서 조끼·장갑 착용 응답이 나온 반면 이후 전방 사람 화면은 미착용이었다. 대상 및 최신 판정의 출처를 구분하도록 보완 필요.
5. 현재 설정 모델: STT `gpt-4o-mini-transcribe`, 설명형 응답 `gpt-6-luna`. TTS는 한국어 Edge TTS 경로. 실제 모델별 지연·비용 비교는 이 검증 범위에서 측정하지 않았다.
6. 실제 화재·연기·낙상, 웨이크 없이 비상 발화, 비상구 안내, microSD 저장, 배터리 소진·충전 장시간 운전은 이번 실물 검증에서 확인하지 않았다.
7. 위험도 60점은 서버에 설정된 화기 작업 위험구역 진입에 의한 값이다. 실제 현장 위험구역 배치가 올바른지는 별도 확인 필요.

### 소스 변경과 인수 위치

- P4 센서 드라이버, SH-2 소스 및 초기화·진단 로그가 저장소 작업 트리에 반영되어 있다.
- 웹 진단은 speaker 상태 `initialized`도 초기화 완료로 표시하도록 수정. 프런트엔드 빌드 성공.
- 실제 업로드한 P4 빌드 디렉터리: `C:\dev\hanmir-p4\helmet_p4`.
- 실제 업로드한 UWB 빌드 디렉터리: `C:\dev\hanmir-uwb-link\uwb_multi_test`.
- 로컬 증거: `C:\dev\hanmir-runtime\web-validation-snapshot.json`, `p4-web-validation.log`, `web-camera-validation.jpg`, `web-hardware-validation.jpg`.
- 이 검증 단계의 변경 사항은 아직 Git commit/push하지 않았다.

### 웹에서 다시 확인하는 순서

1. `/hardware`: 장치 2개 ONLINE, 앵커 4개 최근 수신, 각도 갱신 확인.
2. `/camera`: 밝은 곳의 사람을 향하게 하고 원본 및 전방 PPE 판정 확인. 사람이 사라지면 판정 보류가 정상이다.
3. `/assistant`: 배터리 조회 후 스피커 재생 확인. 다음으로 마이크에서 동일 명령 발화 후 새 명령 기록 확인.
4. `/map`: 앵커 배치와 실제 위치를 비교하고 이동 시 좌표 변화를 확인.


---

## 부록 5: MAP_HEADING_2026-10-09.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## 지도 시선 방향 표시

### 구현

- BNO085 yaw에 현장 보정값을 적용하여 지도 방향을 표시한다.
- 현재 앵커 1 (0,0), 앵커 4 (0,8.2)의 벽을 정면으로 바라보면 지도 왼쪽이다. 해당 벽에 수직인 방향으로 보정한다. 특정 앵커의 점을 바라보는 보정은 아니다.
- 사용자 ‘벽 보고 있음’ 확인 후 웹의 보정 버튼으로 기준 저장 완료. 최초 지도 표시: 왼쪽 180도.
- 지도 작업자 아이콘에 파란 화살표와 시선 부채꼴 표시. 위치 이동 경로와 독립적으로 센서 회전에 따라 갱신한다.
- 지도 X/Y 화면 축척 차이를 반영하여 화살표 각도를 계산한다.
- 지도 각도: 오른쪽 0도, 위쪽 90도, 왼쪽 180도, 아래쪽 270도. 지리적 동서남북은 아니다.
- 센서 데이터가 15초 이상 오래됐거나 장치가 오프라인이면 ‘확인 불가’, 화살표 숨김.
- 보정값은 Device의 component_status_json에 저장한다. 펌웨어 heartbeat가 해당 서버 보정값을 덮어쓰지 않게 보존한다. 다른 PC도 같은 서버에 연결하면 동일 기준 사용.

### 사용

센서와 안전모/카메라의 상대 방향을 고정하고, 앵커 1·4 벽을 정면으로 본 상태에서 지도 ‘앵커 1·4 벽을 정면으로 보고 보정’ 버튼을 누른다. 센서 장착 위치 또는 현장 앵커 배치가 바뀌면 다시 보정한다. 현재 방식은 센서 yaw의 회전 변화에 오프셋을 적용하므로 센서의 올바른 장착 축이 필요하다. 눈동자 시선 추적 기능이 아니라 안전모 방향 표시이다.

### 변경 파일

- backend/app/schemas/api.py: 보정 요청 스키마.
- backend/app/routers/devices.py: POST /api/devices/{device_id}/heading-calibration. 최신 IMU 값 확인, 앵커 벽 방향 계산, 보정값 저장.
- backend/app/services/device_service.py: IMU 수신시각, 보정값 보존.
- backend/app/services/serializers.py: heading_deg / heading_at / heading_calibrated_at 전달.
- frontend/src/types/index.ts, services/api.ts: 방향 데이터와 보정 API.
- frontend/src/App.tsx, components/SiteMap.tsx, styles.css: 지도 방향 표시·보정 UI.

프런트엔드 빌드 성공. 서버 재시작 후 실제 웹 보정과 180도 표시 확인. 기존 P4 펌웨어가 yaw를 보내므로 이번 기능은 P4 재플래시 없이 적용됐다. 실제 90도 회전량·장착 축 정확도는 실물 비교 필요.


---

## 부록 6: CAMERA_15FPS_YOLO640_TRIAL_2026-10-09.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## 카메라 15fps / YOLO 640 1차 실물 측정

### 적용

- P4 CONFIG_HANMIR_CAMERA_TARGET_FPS: 10 → 15. 빌드·COM25 업로드 및 해시 검증 완료.
- backend/.env YOLO_IMAGE_SIZE: 320 → 640. 서버 재시작 후 설정 640 확인.
- 카메라 출력 800×640, JPEG 품질 75 유지. 실제 수신 JPEG 69,930바이트.
- YOLO 분석 목표 제한은 기존 4fps 유지. 음성 처리 중에는 기존 1fps 우선 정책 유지.
- 웹 원본 영상 갱신은 기존 500ms 간격으로, 별도의 약 2fps 표시 제한이 있다. 이번에는 서버 수신 카운터로 FPS를 측정했다.

### 실측

빌드 종료 및 P4 재부팅 이후 16개 서버 상태 샘플, 첫/마지막 카운터 사이 약 60.61초:

| 지표 | 측정값 |
| --- | --- |
| P4 촬영 | 약 16fps: 부팅 후 34.795~59.815초에 500→900 프레임 |
| 서버 수신 | 2.57fps |
| YOLO 분석 완료 | 1.98fps |
| 추론 시간 샘플 중앙값 | 80.1ms |
| 추론 시간 샘플 최대 | 148.6ms |
| 음성 처리 활성 샘플 | 16개 중 5개 |
| 분석 대기열 최대 | 0 |
| 서버 stale 폐기 카운터 증가 | 0 |

촬영 목표 15fps는 대기 시간 설정이다. 태스크 tick 반올림과 촬영/인코딩 처리 시간 때문에 정확히 15fps가 보장되는 제어 구조는 아니다.

P4 촬영 500→900 구간에서 transport drops 441→781, 즉 증가량 340/촬영 400이었다. 이 카운터는 최신 프레임 큐 교체와 전송 실패 등을 합친 값이며, 이를 전부 무선 패킷 손실로 해석하면 안 된다.

### 발견 사항

- P4 촬영 속도를 높여도 서버 수신 FPS는 목표 15fps에 도달하지 못했다.
- 실제 로그에 transport_poll_write(0), esp_transport_write() returned 0, send failed bytes=0, 2초 재연결이 반복됐다. 전송 경로에서 프레임이 많이 폐기되는 것은 확인됐다.
- send_bin 호출의 timeout은 600ms이고 WebSocket 전송 버퍼는 사용자 지정 없이 라이브러리 기본값 사용. 버퍼 크기/분할 전송/소켓 대기/내장 C6 통신과 음성 동시 부하를 분리 측정하는 후속 실험이 필요하다. 현재 로그만으로 Wi-Fi 대역폭만의 문제라고 단정하지 않는다.
- 이전 짧은 구간의 수신 약 2.99fps, 분석 약 2.19fps, 마지막 추론 48.5ms와 비교하면 이번 수신/분석은 개선되지 않았다. 장면·음성 부하·측정 시간이 동일한 통제 실험은 아니다.
- YOLO 640에서 추론 시간 부담은 증가했다. 기존 PPE 상세 분석은 별도로 640 및 960 crop pass를 수행할 수 있으므로 기본 입력 640만의 비용으로 해석하면 안 된다.
- 웹에 실제 사람은 보였으나 측정 중 영상이 180도 뒤집힌 장면이었고, 마지막 분석 person_seen=False. 사용자에게 영상 방향 수정 요청. 이번 결과로 인식률 향상은 결론낼 수 없다.

### 현재 상태 및 후속 우선순위

15fps/640 설정은 적용된 상태로 유지한다. 다음 작업은 해상도/JPEG 품질 추가 상승보다 전송 실패·재연결 개선을 우선한다. 그다음 웹 갱신 제한 개선 및 같은 정상 방향 장면에서 320/640 검출 비교를 진행한다.

근거 파일(이 PC): C:\dev\hanmir-runtime\fps15-measurement.json, fps15-serial.log, fps15-boot.log, fps15-camera.jpg.
재현: P4 설정 15fps, 서버 .env YOLO_IMAGE_SIZE=640, 서버 재시작 후 빌드 작업 없이 약 1분간 수신/분석 누적 카운터 차이를 측정.


---

## 부록 7: CAMERA_TRANSPORT_IMPROVEMENT_2026-10-09.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## 카메라 전송 개선 실물 결과

### 적용 내용

1. P4 카메라 WebSocket 버퍼 16KB. 기존에는 라이브러리 기본 버퍼 사용.
2. send timeout을 설정 항목으로 분리. 최종 실물 적용 1,500ms.
3. 실패한 JPEG 전송 이후 연결을 stop/start하여 불완전한 프레임이 다음 프레임에 이어지는 것을 방지. 연결 끊김이 10초 이상 지속되면 복구 시도. 호출은 WebSocket 이벤트 콜백이 아니라 별도 sender task에서 실행.
4. 평균 JPEG 크기, 전송 소요시간 및 20회 단위 실패 횟수 로그 추가.
5. 서버 명령으로 timeout 변경, 범위 100~5,000ms. NVS 저장으로 재부팅 후 유지. heartbeat에 실효 timeout과 버퍼 크기 보고.
6. 웹 원본 영상은 500ms 이미지 재요청에서 MJPEG 스트림으로 변경. 서버 메모리의 최신 프레임만 최대 15fps 전송하고 늦은 클라이언트용 프레임 큐는 쌓지 않는다. 상태 표시용 metadata polling은 500ms로 유지.

800×640, JPEG 품질 75, 촬영 목표 15fps, YOLO 기본 입력 640, 분석 상한 4fps 및 음성 우선 정책은 유지했다. 회전 보정은 이번 변경에 포함하지 않았다. 서버 프레임 디스크 저장 제거 및 음성/영상 전송률의 별도 제어는 아직 적용하지 않았다.

### 비교 결과

| 조건 | 서버 수신 FPS | YOLO 완료 FPS | 추론 ms 샘플 중앙값 |
| --- | ---: | ---: | ---: |
| 이전 15fps/640 | 2.57 | 1.98 | 80.1 |
| 16KB·600ms, 명시적 복구 추가 전 | 2.71 | 1.01 | 62.7 |
| 16KB·1,500ms, 복구 추가 후 | 6.93 | 2.90 | 70.95 |
| 같은 복구 코드·16KB·600ms 재비교 | 5.33 | 2.09 | 66.9 |

최종 선택: 16KB·1,500ms·명시적 복구. 기존 측정 대비 수신 약 2.7배. 단, 장면·음성 처리 상태가 완전히 통제된 실험은 아니며 개선을 특정 설정 하나의 효과로 단정하지 않는다.

최종 1,500ms 실험 카운터 구간은 약 36.50초, 직렬 로그 구간 약 35초. 해당 직렬 로그의 20회 단위 TX sample 12개는 모두 failures=0. 평균 전송 102~177ms, JPEG 약 68~69KB. 이 짧은 구간에서 전송 실패가 없었다는 의미이며 장시간 안정성을 보장하지 않는다.

600ms 재비교에서는 연결 끊김 복구 로그가 3회 기록됐다. 복구 처리가 있는 상태에서 전송을 다시 시작할 수 있었다. 마지막 카메라 분석은 person_seen=True였으나 이는 검출 사례 하나이며 정확도 검증 결과는 아니다.

### 검증

- P4 빌드·업로드·해시 검증 완료.
- 프런트엔드 TypeScript/Vite 빌드 성공.
- 실제 웹 img 소스 `/api/camera/helmet-001-av/live/mjpeg`, naturalWidth=800 / naturalHeight=640 확인.
- 최종 timeout 명령 전달 후 heartbeat camera_send_timeout_ms=1500, camera_ws_buffer_bytes=16384 확인.
- 측정 후 서버와 웹을 실행 상태로 유지.

### 설정·인수 방법

Kconfig: HANMIR_CAMERA_WS_BUFFER_BYTES / HANMIR_CAMERA_SEND_TIMEOUT_MS.
새 보드용 sdkconfig.dfr1172.example은 16KB·1,500ms로 설정했다.
실험용 업로드 바이너리는 최초 기본값 600ms로 빌드했고, 이후 명령으로 1,500ms를 NVS에 저장했다. NVS 값이 기본값보다 우선한다. NVS를 지우거나 새 보드에 올릴 때는 example의 1,500ms 설정으로 빌드한다.

명령: POST /api/devices/helmet-001-av/command

```json
{"command_type":"set_camera_timeout","payload":{"send_timeout_ms":1500}}
```

명령 delivered는 전달 여부다. 적용 완료는 `/api/diagnostics/devices`의 component_status.camera_send_timeout_ms로 확인한다. 다른 부품 배선·GPIO 변경은 없다.

### 증거 및 다음 단계

로컬 파일: C:\dev\hanmir-runtime\ws16k-600ms-measurement.json, ws16k-1500ms-recovery-measurement.json, ws16k-600ms-recovery-measurement.json 및 대응 serial.log.

아직 실제 15fps는 달성하지 못했다. 평균 전송 자체가 100~180ms로, 현재 구간에서는 연속 전송 가능한 속도에 한계가 있다. 후속은 동일 장면의 장시간 실험, 32KB 비교, 내장 C6 경로/음성 업로드 동시 부하 측정, JPEG 크기 최적화, 서버 수신 디스크 쓰기 제거 순서로 검토한다. 지금 개선만으로 통신 병목이 전부 해결됐다고 판단하지 않는다.


---

## 부록 8: HANMIR_INTEGRATED_DIAGNOSTICS_2026-10-10.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## HANMIR 2.0 통합 동작·통신·메모리 실측 보고서

작성일: 2026-10-10. 시각은 한국 표준시(KST, UTC+9).

### 1. 최종 판단

**현재 상태를 ‘모든 기능 정상, 병목 없음’으로 판정할 수 없다.** 음성 명령·스피커·UWB·BNO가 동작하는 동안 카메라 입력이 정지했다. 장치 재부팅 후 영상은 복구됐지만, 장시간 정지 원인은 아직 확정하지 못했다.

- 위치 질문은 서버 명령 기록·음성 전송 기록과 사용자의 실제 청취 확인이 일치한다.
- 배터리 명령 2건은 기록상 42%로 답변했다. 사용자는 약 34%로 들었다고 했으므로, 해당 발화의 실제 음원을 함께 듣기 전에는 일치 여부를 확정할 수 없다.
- UWB 업로드는 정상 응답하지만 좌표 계산의 신뢰도는 낮다. 서버 앵커 배치와 측정 거리 사이에 기하학적 불일치가 있다.
- 재부팅 후 약 29초 동안 수신 16.25 FPS, YOLO 분석 3.31 FPS를 측정했다. 이 짧은 성공 구간만으로 장시간 안정성을 보장하지 않는다.
- P4 플래시 용량은 여유가 있다. 다만 실행 중 힙·PSRAM 잔량은 계측되지 않아 메모리 부족 가능성을 배제할 수 없다.

### 2. 측정 조건과 범위

| 항목 | 조건 |
|---|---|
| 서버 PC | 192.168.0.40, WISET_5G |
| P4 | 192.168.0.43, 2.4 GHz Wi-Fi, USB COM25 |
| 독립 UWB 태그 | 192.168.0.20, 2.4 GHz Wi-Fi, USB COM6 |
| 백엔드 | FastAPI, 포트 8000 |
| 웹 | Vite, 포트 5174 |
| 영상 | 실제 프레임 800×640, 전송 목표 15 FPS |
| YOLO | best.pt, 입력 640, 보호구 상세 분석 입력 640 |
| 분석 목표 | 일반 4 FPS, 음성 처리 활성 시 1 FPS |
| 근거 | 서버 API 누적 카운터, DB 명령/이벤트, P4·태그 UART, 프로세스 자원, 빌드 map, 물리 flash_id |

현재 네트워크에 맞춘 장치 설정과 실행 서버를 기준으로 측정했다. 이 보고서의 플래시 ID 확인은 읽기 작업이지만 도구가 장치를 의도적으로 재부팅했다. 이 재부팅을 자발적 크래시로 집계하지 않는다. 본 진단에서는 카메라 복구 코드를 추가하지 않았다.

### 3. 카메라·YOLO 실측

| 구간 | 관측 시간 | 샘플 | 수신 증가 | 분석 증가 | 평균 수신 FPS | 평균 분석 FPS |
|---|---|---:|---:|---:|---:|---:|
| 정지 발생을 포함한 최초 구간 | 11:11:30.448~11:12:28.593 | 19 | 604 | 137 | 10.39 | 2.36 |
| 정지 상태, UART 동시 기록 | 11:13:50.968~11:14:50.541 | 58 | 0 | 0 | 0 | 0 |
| 의도적 재부팅 후 | 11:21:25.182~11:21:54.489 | 28 | 476 | 97 | 16.25 | 3.31 |

FPS는 마지막·첫 누적 카운터 차이를 실제 단조 시계 경과 시간으로 나눈 값이다. 최초 측정은 프로세스 조회 비용 때문에 약 3.2초 간격이며, 이후는 약 1초 간격이다. 최초 구간 평균에는 마지막 약 14초의 정지 시간이 포함된다.

#### 3.1 실제 정지 증거

- 마지막 영상 수신: **11:12:14.742**, 마지막 원시 프레임 ID 12034.
- 서버 수신 카운터 16,772, 분석 완료 3,581에서 정지.
- 서버 분석 큐 깊이 0. 분석 대기 프레임이 쌓여 멈춘 상황은 관측되지 않았다.
- P4의 카메라 드롭 카운터도 2,717에서 정지.
- UART 동시 측정에서 마지막 영상 나이는 95.828초 → 155.391초로 증가했다. 이후 확인에서는 약 236초까지 오래된 영상이었다.
- 같은 구간에 음성 POST 15건이 HTTP 200으로 응답했고, BNO 자세 로그와 UWB 위치 갱신은 계속됐다.
- YOLO 프로세스 CPU 증가량은 정지 측정 구간에서 0이었다. 서버가 바쁘게 추론하면서 영상을 못 따라가는 상황보다 **영상 공급 자체가 멈춘 상황**에 가깝다.
- 상태 표시는 camera=capturing, video_transport=connected였다. 이 표시는 실제 프레임 진행 여부를 보장하지 않는다.

정지 중 표시된 last_inference_ms=85.5는 마지막 성공 추론의 보관 값이다. 정지 중 새 추론이 85.5ms로 실행됐다는 뜻이 아니다.

#### 3.2 코드상 의심 지점과 확정 한계

`firmware/helmet_p4/main/camera_source.c`의 캡처 루프는 `VIDIOC_DQBUF`를 호출해 버퍼를 기다린다. 현재 코드에는 이 대기에 대한 명시적 제한 시간이나 프레임 정지 감시·재초기화가 없다. JPEG 인코더 제한 시간은 1,000ms이다. 버퍼 반환 실패 시 루프를 종료하는 경로에는 충분한 오류 기록이 없다.

`capturing`은 초기화 성공 시 설정되는 값이다. 캡처 진행이 멈춰도 그대로 표시될 수 있다. `camera_transport.c`는 전송 오류 시 WebSocket을 재연결하지만, 멈춘 CSI/캡처 소스를 복구하지는 않는다.

따라서 우선 의심할 부분은 CSI 버퍼 대기, 캡처·JPEG 처리, 태스크 진행 정지이다. **어느 호출에서 멈췄는지 직접 찍힌 로그가 없으므로 SW 버그로 확정하지 않는다.** FPC 접촉·센서 전원도 확인 대상이다. 전체 Wi-Fi 장애나 전체 서버 장애만으로는 음성·UWB가 계속 성공한 현상을 설명하기 어렵다.

#### 3.3 재부팅 후 상태

- 펌웨어 수정 없이 재부팅으로 영상이 복구됐다.
- 약 35초 UART에서 20프레임 단위 전송 로그 28묶음: 560회 시도, 보고된 전송 실패 0회.
- 묶음별 평균 전송 시간의 중앙값 55ms, 가장 큰 묶음 평균 117ms. 개별 프레임 최댓값이나 p95가 아니다.
- 묶음별 평균 JPEG 크기의 중앙값 약 48,483바이트.
- API 샘플에서 마지막 프레임 나이 최댓값 47ms. 브라우저 표시 지연까지 포함한 값은 아니다.
- 샘플에 표시된 최근 추론 시간 중앙값 102.6ms, 최대 123.9ms. 전체 추론 호출의 분포가 아니다.
- 서버 오래된 프레임 제거 카운터는 63 증가했다. 최신 영상 우선 정책에 따른 분석 생략이며, Wi-Fi 패킷 손실률로 해석하면 안 된다.
- 음성 활성 상태는 28샘플 중 5샘플이었다. 음성 처리 중 분석 목표가 1 FPS로 내려가므로 수신 FPS와 YOLO FPS가 다르게 나오는 것은 일부 의도된 동작이다.

영상은 정상 전송돼도 YOLO가 모든 프레임을 분석하지 않는다. 15 FPS 영상 전송과 15 FPS YOLO 추론은 별도 목표다.

#### 3.4 인식률 검증 한계

저장한 재부팅 후 영상에는 큰 물체가 시야 대부분을 가리고 벽·문·천장이 보인다. 사람이 보이지 않아 person_seen=false는 이 장면과 모순되지 않는다. 이번 측정으로 보호구 검출 정확도 향상을 입증할 수 없다. 같은 거리·조명에서 사람이 보호구를 착용/미착용한 영상을 확보해야 한다.

### 4. 음성·AI·스피커

#### 4.1 현재 실제 파이프라인

I2S 마이크 → WebRTC 노이즈 억제 → AFE VAD → 음성 구간 HTTP 업로드 → STT → 서버 웨이크 표현 검사 → intent 분류 → 조회/계산/LLM → TTS → P4 스피커.

| 항목 | 현재 값/동작 |
|---|---|
| STT | gpt-4o-mini-transcribe, 제한 시간 10초, SDK 재시도 0 |
| 설명형 LLM | gpt-6-luna, 제한 시간 5초, SDK 재시도 0, 최대 출력 80토큰 |
| TTS | Edge TTS ko-KR-SunHiNeural, WAV 캐시, 16kHz·16bit·mono |
| 단순 조회 | 배터리·위치는 서버 템플릿; LLM 미호출 |
| 비상 | STT 이후 서버 비상 판별·이벤트 처리 |
| 로컬 WakeNet | **비활성화**. 전용 ‘투투스’ 모델 실행 중이 아님 |
| 음성 구간 | 최대 5초, 프리롤 300ms, 종료 무음 500ms, 업로드 큐 3 |
| 연속 질의 | 서버 웨이크 후속 허용 20초 |

따라서 현 상태를 로컬 전용 웨이크 모델로 호출 성공률을 개선한 상태라고 설명하면 안 된다. 일반 음성도 STT에 보낸 뒤 서버에서 거르는 구조가 남아 있다. 모델 이름은 설정 확인값이며, 오늘 단순 조회 성공이 설명형 LLM의 정확도를 검증한 것은 아니다.

#### 4.2 명령 기록과 시간

아래 시간은 DB의 STT 결과 저장 시각 → 관련 이벤트 저장 시각 차이이다. 녹음 시작·VAD 종료·STT 시간이 이미 지난 뒤이므로 **전체 응답 지연이나 첫 소리 지연이 아니다.**

| KST / 명령 ID | 인식 내용 | 응답/결과 | STT 이후 이벤트 간격 |
|---|---|---|---:|
| 11:04:49 / 15 | 바로 온다던 왜 이렇게 안 오는 거야? | 설명형 응답 전달 | 5,307.7ms |
| 11:05:08 / 16 | 비상 상황이면 반드시 연락 달라. | 비상 이벤트·스피커·관리자 호출 요청 | 17.9ms |
| 11:05:39 / 17 | 위치 조회 | X 3.6m, Y 4.8m | 652.1ms |
| 11:08:09 / 18 | 아 | 요청 확인 불가 안내 | 2,763.0ms |
| 11:08:24 / 19 | 빈 인식 결과 | 빈 응답, 음성 없음 | 1.0ms |
| 11:10:18 / 20 | 지금 배터리가 얼마나 남았어 | 42% | 673.7ms |
| 11:10:43 / 21 | 지금 배터리 얼마인지 알려줘 | 42%, TTS 캐시 | 5.0ms |
| 11:12:46 / 22 | 위치 조회 | X 3.4m, Y 4.5m | 609.7ms |
| 11:14:50 / 23 | 위치 조회 | X 3.4m, Y 4.5m, 사용자 청취 확인 | 8.8ms |
| 11:16:13 / 24 | 토투스 부르고 조그만 거 고칠 때마다… | stop_speaking으로 분류 | 2.5ms |

11:14:50 위치 명령은 카메라 정지 구간에서도 처리됐다. 응답 WAV는 5.448초이고 스피커 완료 ACK는 11:14:56.532로, 명령 저장부터 약 6.257초이다. 이 간격에는 실제 음성 재생 시간이 들어 있다. 배터리 42% WAV 재생 길이는 3.576초이다.

비상 관리자 호출은 요청 후 약 30초에 미응답(missed) 처리됐다. 관리자 수신자가 응답하지 않은 기록이며 통신 전송 실패와 동일시하지 않는다. 화재 관련 모든 표현이 이번에 검증된 것은 아니다.

#### 4.3 발견한 논리 문제

1. **정지 명령 부분 문자열 오인:** ‘조그만’에 포함된 ‘그만’을 정지 명령으로 분류했다. 단어 경계·의도 확인 없이 부분 문자열로 찾는 로직을 수정해야 한다. 일반 대화가 경고 재생을 중단할 위험이 있다.
2. **비상 조건문 구분 부족:** ‘비상 상황이면’ 같은 조건 표현도 비상 키워드로 걸린다. 즉시 경보의 민감도를 유지하면서 인용·조건·부정 문장의 정책을 분리해야 한다.
3. **재생 중 마이크 억제:** 현재 AEC는 비활성화이며 스피커 재생 중 수집 음성을 버리는 경로가 있다. 이 시간에 외친 비상 발화가 서버까지 가지 못할 수 있다. 이번 기록에서 실제 누락이 입증된 것은 아니지만, 별도 시험이 필요하다.
4. **불필요한 STT 업로드:** 웨이크가 없는 주변 발화도 업로드되므로 비용·음성 큐·YOLO 우선순위에 영향을 준다.
5. **측정 부족:** 녹음 시작, STT 시작/완료, 웨이크 인정, 응답 생성, 첫 재생 시각을 하나의 request ID로 저장하지 않는다.

#### 4.4 인식 성공률을 계산할 수 없는 이유

전체 실제 호출 횟수와 실패한 발화의 원음·시각이 없다. HTTP 200은 업로드 성공이지 ‘투투스’ 인식 성공이 아니다. 따라서 기억에 따른 60~70%와 오늘 결과를 비교해 개선율을 숫자로 제시할 수 없다. 호출 20회·비상 20회 등 정해진 발화 시험에서 원음과 단계별 처리 결과를 대조해야 한다.

### 5. UWB·방향 데이터

#### 5.1 통신

- 영상 정지 중 58/58 API 샘플에서 UWB 갱신이 이어졌고, 샘플에서의 최대 데이터 나이는 약 0.669초였다.
- 별도 약 12초 태그 UART에서 POST 34건 모두 HTTP 200, 보고된 오류 0건.
- UART 시각 기준 갱신 약 2.78Hz, 간격 중앙값 0.313초, 최대 0.719초.
- mask=F로 4개 앵커 거리 입력이 관측됐다. 이는 태그가 4개 거리를 받았다는 근거이며 각 앵커의 직접 서버 heartbeat 검증은 아니다.
- DB 위치 행은 위치 변화 시에만 저장될 수 있으므로, 행 저장 간격을 업로드 주기로 사용하지 않았다.
- BNO 방향 로그도 영상 정지 중 계속됐다. 정확한 방위 오차·낙상 검출 성능을 이번 통신 관측만으로 보장하지 않는다.

#### 5.2 위치 계산 문제

| 앵커 | 서버 좌표(m) | 저장된 보정 거리 예시(m) |
|---|---|---:|
| 1 | (0, 0) | 4.03 |
| 2 | (5.8, 0) | 3.42 |
| 3 | (5.8, 8.2) | 2.41 |
| 4 | (0, 8.2) | 3.10 |

서버 배치에서 앵커 1↔3 거리는 약 10.04m다. 같은 기록의 태그↔1 및 태그↔3 거리 합은 6.44m다. 두 거리의 합이 앵커 사이 거리보다 작아 삼각 부등식을 만족하지 않는다. 이 배치와 거리를 동시에 정확하다고 볼 수 없다.

현재 confidence는 최소 0.371, 중앙값 0.4405, 최대 0.558이며 LOW_POSITION_CONFIDENCE가 표시됐다. 코드의 confidence는 거리 잔차 RMSE를 변환한 값으로, 정확도 44%라는 의미가 아니다. 중앙값에 대응하는 거리 잔차 RMSE는 약 1.68m이며 실제 위치 오차와도 다르다.

실제 앵커 간 가로·세로 거리, ID 대응, 거리 보정·단위, 장애물 영향을 확인해야 한다. 오늘 배치가 여전히 5.8×8.2m인지 사용자 확인을 요청한 상태이며 답변 전에는 원인을 확정하지 않는다. 좌표는 응답했지만 현재 좌표를 정밀한 안전 유도로 사용하기에는 검증이 부족하다.

### 6. 플래시·RAM·PSRAM 사용량

단위: MiB=1,048,576바이트, KiB=1,024바이트. 정적 빌드 사용량과 실행 중 여유 메모리를 구분한다.

#### 6.1 P4

| 항목 | 측정값 | 의미 |
|---|---:|---|
| 물리 플래시 | **16MiB** | esptool flash_id 직접 확인 |
| 물리 PSRAM | **32MiB** | 부팅 초기화·메모리 시험 로그 확인 |
| 앱 BIN | 1,890,048바이트, 약 1.802MiB | 실제 빌드 산출물 |
| 앱 파티션 | 4,194,304바이트, 4MiB | factory |
| 앱 사용 비율 | **45.06%** | 앱 파티션 대비 |
| 앱 남은 공간 | 2,304,256바이트, 약 2.197MiB | 54.94% |
| 정적 D/IRAM | 161,232 / 576,464바이트, 27.97% | 링커 map 영역 기준 |
| 정적 data / bss / text | 22,812 / 42,112 / 96,308바이트 | D/IRAM 구성 |
| map의 플래시 코드 / rodata | 1,402,244 / 367,892바이트 | BIN 전체 크기와 다른 집계 |
| bootloader / 파티션 테이블 BIN | 23,088 / 3,072바이트 | 별도 산출물 |
| 음성 model 파일 | **4바이트** | 로컬 WakeNet 모델 실사용 없음 |
| 실행 중 free heap / min free / largest block | **확인 불가** | 현재 텔레메트리 없음 |
| 실행 중 PSRAM 잔량 / 태스크 스택 여유 | **확인 불가** | 현재 텔레메트리 없음 |

| 파티션 | 시작 | 크기 |
|---|---|---|
| nvs | 0x9000 | 24KiB |
| phy | 0xF000 | 4KiB |
| factory | 0x10000 | 4MiB |
| model | 0x410000 | 6MiB 예약 |
| 마지막 파티션 이후 | 0xA10000~16MiB 끝 | 약 5.9375MiB 미배정 |

6MiB 모델 영역은 예약 공간이며 실제 모델이 6MiB를 소비하는 것이 아니다. 현 P4 파티션에는 ota_0/ota_1/otadata가 없어 그대로 OTA 업데이트 가능하다고 보장할 수 없다.

카메라 RGB565 버퍼 2개만 계산하면 800×640×2×2바이트, 약 1.953MiB다. 여기에 JPEG·전송·오디오·네트워크·드라이버·모델 버퍼가 추가된다. 이 예시는 전체 PSRAM 사용량이 아니다. 부팅 시 PSRAM 시험 성공이나 정적 RAM 여유만으로 실행 중 누수·단편화를 배제할 수 없다.

#### 6.2 UWB 태그와 내장 C6

| 항목 | 측정값 |
|---|---:|
| 태그 물리 플래시 | **16MiB**, flash_id 확인 |
| 태그 펌웨어 설정·기존 파티션 범위 | **4MiB** |
| PlatformIO 앱 플래시 사용 | 807,585 / 1,310,720바이트, **61.6%** |
| 앱 파티션 내 여유 | 503,135바이트 |
| 실제 앱 BIN | 814,160바이트 |
| 정적 RAM | 46,140 / 327,680바이트, **14.1%** |
| 정적 RAM 예산 잔여 | 281,540바이트; 실행 중 free heap과 다름 |

태그 파티션은 app0/app1 각 1.25MiB, NVS 20KiB, otadata 8KiB, SPIFFS 1,441,792바이트, coredump 64KiB로 4MiB 범위다. 물리 16MiB의 나머지를 현재 펌웨어가 자동으로 활용하는 것은 아니다.

내장 C6의 개별 플래시·동적 RAM은 이번에 직접 계측하지 않았다. P4의 map을 C6 사용량으로 해석하지 않는다.

#### 6.3 PC 자원·저장 공간

| 항목 | 관측 |
|---|---|
| PC RAM / 논리 CPU | 약 15.59GiB / 18 |
| 영상이 흐르던 최초 측정의 CPU | 중앙값 42.7%, 최대 56.4% |
| 최초 측정의 최소 가용 RAM | 약 2.26GiB |
| 영상 정지 측정의 CPU | 중앙값 10.35%, 최대 28% |
| 영상 정지 측정의 최소 가용 RAM | 약 2.53GiB |
| 백엔드 RSS | 약 181.5~191.1MiB |
| YOLO 워커 RSS | 약 592.5MiB |
| 프런트엔드 RSS | 약 91.1~93.5MiB |
| 영상 정지 중 YOLO CPU 증가 | 0초 |
| captures 전체 | 349파일, 약 22.11MiB |
| TTS 출력 | 19파일, 약 3.72MiB |

이번 구간에는 서버 메모리 부족·프로세스 크래시·대량의 분석 큐 적체 증거가 없다. PC의 여유 RAM이 무한한 것은 아니며 다른 프로그램과 장시간 실행에 대한 관측은 별도다.

### 7. 오류·병목 판정

| 항목 | 판정 | 근거/한계 |
|---|---|---|
| 카메라 장시간 진행 | **실패 확인** | 수신·분석·캡처 카운터 정지, 재부팅 후 복구 |
| 영상 정지 자동 복구 | **보완 필요** | 연결 표시 유지, 캡처 감시 없음 |
| 짧은 재부팅 후 영상 전송 | 성공 | 16.25 FPS, UART 보고 전송 실패 0 |
| YOLO 동시 실행 | 부분 확인 | 추론 진행 확인, 실제 PPE 정답 비교 없음 |
| 음성 배터리·위치 | 성공 기록 | 사용자 청취 확인, 위치 ACK 확인 |
| 웨이크 인식률 개선 | 확인 불가 | 로컬 WakeNet 비활성, 시험 분모 없음 |
| 비상 호출 | 이벤트/전달 확인 | 관리자 미응답, 모든 비상 표현 검증 아님 |
| UWB 전송 | 짧은 구간 성공 | 34 POST 200, 4개 거리 입력 |
| UWB 위치 정확도 | **보완 필요** | 거리·배치 불일치, 낮은 confidence |
| P4 플래시 용량 | 여유 확인 | 앱 45.06% |
| P4 실행 중 메모리 안정성 | 확인 불가 | 동적 계측 없음 |

P4 UART 동시 구간에 heartbeat 1회 `ESP_ERR_HTTP_INCOMPLETE_DATA`, status=0이 기록됐다. 이후 등록·heartbeat가 이어졌고 전체 연결 단절로 이어지지는 않았다. 서버의 최근 오류 목록만 보면 놓칠 수 있는 장치 측 오류다.

서버 전체 세션 로그의 시점별 집계는 음성 POST 348, UWB POST 6,600, heartbeat POST 297이 모두 2xx였다. 이 누적 수는 시험 창의 호출 수·정상 인식률을 의미하지 않는다. WebSocket accept 반복도 부팅·설정 변경을 포함하므로 그대로 장애 횟수로 계산하지 않는다. localhost의 일부 404/405는 진단 중 잘못된 GET 경로 조회였으며 장치 오류에서 제외했다.

### 8. 수정 우선순위와 대상

#### 1순위: 카메라 정지 감지·원인 기록·복구

- `firmware/helmet_p4/main/camera_source.c`: 캡처·DQBUF·JPEG 시작/완료·QBUF 시각, 반환 코드, 마지막 성공 프레임 시각 기록. 드라이버 API에 맞는 비차단/제한 시간 방법 검토. 진행 정지 시 안전하게 스트림·센서 재초기화.
- `firmware/helmet_p4/main/camera_transport.c`: 전송 시간·실패 원인·재연결 시간 기록. 캡처 정지와 소켓 정지를 구분.
- `firmware/helmet_p4/main/api_client.c`: heartbeat에 last_capture_age, last_send_age, 카운터 증가 여부, 메모리 정보 포함.
- `backend/app/routers/camera.py` 및 웹 상태 표시: 프레임 수신 나이로 정상/오래됨/정지 판정. connected나 capturing만으로 녹색 표시 금지.
- 자동 복구 검증: 최소 10~30분 연속 전송과 음성·UWB 동시 시험. 정지 재현 시 원인 로그 보존.

#### 2순위: 실행 중 메모리 계측

내부 RAM·PSRAM 각각 free/minimum/largest block, 태스크 스택 최저 여유, 버퍼 할당 실패 횟수를 일정 주기로 기록한다. 데이터가 증가하는지·메모리가 감소하는지 비교한 뒤 누수나 단편화 여부를 판단한다.

#### 3순위: 음성 intent·재생 중 비상 처리

- `backend/app/services/speech_service.py` 및 실제 intent/웨이크 판별 모듈: 부분 문자열 오인을 제거하고 명령 경계·조건/인용 정책 적용.
- `backend/app/routers/audio.py`: 요청 ID별 단계 시각, 처리 경로, 원래 STT 결과와 정규화 결과, 첫 재생/완료 ACK를 연결.
- P4 음성 수집 모듈: AEC·출력 기준 신호와 재생 중 비상 감지 가능성 검토. 무조건 마이크 차단하는 현재 경로를 실험으로 검증.
- 로컬 웨이크 모델은 실제 탑재 여부·한국어 호출 성능을 별도 확인. 이름만 설정한다고 동작하지 않는다.

#### 4순위: UWB 기준 배치 정정

- 실제 앵커 ID·좌표·거리부터 확인.
- `backend/app/services/location_service.py`와 UWB 거리 보정 설정: 원시 거리→보정 거리→잔차→confidence를 비교.
- 알려진 위치 3~5곳에서 실제 거리와 추정 좌표 오차 기록. 방향 보정도 같은 지도 축을 기준으로 재확인.

#### 5순위: YOLO 장면·성능 검증

전방 사람 1~2m, 일정한 조명, 렌즈 가림 없음 조건에서 보호구 착용/미착용 표본을 수집한다. 전송 FPS, 추론 FPS, 검출 정답을 별도로 비교한다. 입력 해상도만 올리는 것으로 시야 가림·흔들림·노출 문제를 해결할 수 없다.

### 9. 사용자에게 필요한 확인

1. 오늘 실제 앵커 배치가 가로 5.8m × 세로 8.2m인지, 앵커 1~4가 지도와 같은 위치인지 알려주기.
2. 전원을 끈 상태에서 카메라 FPC 삽입·잠금과 접촉 확인. 검증 중 USB 데이터 연결은 유지.
3. 카메라 앞 다른 사람이 보이게 하고 보호구 착용/미착용을 알려주기. 현재 저장 장면만으로는 인식률 판정 불가.
4. 단계별 계측과 카메라 자동 복구를 적용한 다음, 정해진 발화·연속 운전 시험으로 최종 판정하기.

이미 확인한 위치 안내와 스피커 청취를 같은 조건으로 계속 반복할 필요는 없다. 다음 시험은 정지 원인·실제 위치 오차·웨이크 누락을 구분할 수 있는 계측을 추가한 뒤 진행하는 것이 효율적이다.

### 10. 원본 증거 파일

원본 진단 자료 위치: `C:\dev\hanmir-runtime`.

- `integrated-20261010-raw.json`: 정지 발생 포함 최초 API/프로세스 샘플.
- `integrated-20261010-uart-raw.json`: 카메라 정지 중 약 60초 API/프로세스 샘플.
- `integrated-20261010-uart-serial.log`, `integrated-20261010-uart-serial-records.json`: 해당 P4 UART와 PC 시각.
- `integrated-20261010-after-reset-raw.json`: 재부팅 후 API/프로세스 샘플.
- `integrated-20261010-after-reset-serial.log`, `integrated-20261010-after-reset-serial-records.json`: 재부팅 후 P4 UART.
- `uwb-integrated-20261010.json`: 태그 UART 단기 기록.
- `p4-memory-20261010.json`: ESP-IDF map 정적 메모리 집계.
- `p4-flash-id-20261010.log`, `uwb-flash-id-20261010.log`: 물리 플래시 ID/용량.
- `integrated-after-reset-raw.jpg`, `integrated-after-reset-yolo.jpg`: 재부팅 후 실제 영상 장면.

보고서와 함께 제공하는 공유 ZIP에는 요약 계측·UART·메모리·이미지만 포함한다. Wi-Fi 설정 파일, API 키, 환경 파일, 전체 DB 덤프는 포함하지 않는다. 본 문서의 판단은 위 측정 구간에 한정되며 추가 코드 수정·장시간 시험 결과로 갱신해야 한다.


---

## 부록 9: HANMIR_CAMERA_RECHECK_AND_TUNING_2026-10-10.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## HANMIR 통합 재측정 및 카메라 개선안

작성: 2026-10-10, 한국 시각. 펌웨어·서버 설정 변경 없이 재측정했다.

### 1. 재측정 결과

| 항목 | 11:41:13~11:41:57 | 11:43:42~11:44:01 |
|---|---:|---:|
| 실제 경과 | 44.266초 | 19.265초 |
| API 샘플 | 43 | 18 |
| 영상 수신 | 546장 / 12.33 FPS | 231장 / 11.99 FPS |
| YOLO 분석 | 98장 / 2.21 FPS | 58장 / 3.01 FPS |
| 최근 추론 시간 샘플 중앙값 | 381.1ms | 98.05ms |
| 최근 추론 시간 샘플 최대 | 762.5ms | 439.1ms |
| 원시 프레임 나이 최대 | 1,609ms | 2,453ms |
| 음성 처리 활성 샘플 | 8/43 | 2/18 |

추론 시간은 API가 보관한 최근 값의 샘플 통계이며 전체 호출 p95가 아니다. 프레임 나이는 서버 수신 기준이며 센서 노출부터 웹 화면까지의 지연이 아니다. 측정 구간·장면이 달라 첫 구간과 두 번째 구간을 설정 개선 효과로 해석하면 안 된다.

첫 구간의 프레임 나이 중앙값은 32ms이고 500ms 초과 샘플은 5/43이었다. 대부분 빠르게 갱신됐지만 간헐적으로 1~2초 이상 갱신이 늦어졌다. 이번 구간에 앞서 발생했던 수 분의 지속 정지는 관측되지 않았으나, 이전 정지 원인이 해결된 것은 아니다.

첫 구간과 겹치는 약 50초 UART에서 전송 로그 32묶음, 총 640회 시도, 보고된 실패 0회였다. 묶음별 평균 전송 시간 중앙값 60.5ms, 최대 묶음 평균 237ms, 묶음별 평균 JPEG 크기의 평균 약 48,965바이트였다. 실패 없이 전송 완료됐어도 지연이 발생할 수 있다. API 창과 UART 창 길이가 달라 프레임 수를 직접 일치시키지 않는다.

서버 CPU 중앙값 52.5%, 최대 57.7%, 가용 RAM 최소 약 3.20GiB. 카메라 상태 API 응답 중앙값 8.78ms·최대 32.09ms, 위치 API 중앙값 10.69ms·최대 31.84ms. 측정 중 서버 전체 자원 고갈이나 모든 API 동시 지연 증거는 없다.

UWB 데이터 최대 나이는 약 0.317초였다. confidence는 0.281~0.55, 중앙값 0.382로 여전히 낮다. 전송 갱신과 위치 정확도는 구분해야 한다.

### 2. 실제 음성·보호구 확인

사용자는 조끼와 헬멧을 착용했고 배터리 질문에 답변이 들렸다고 확인했다. 서버 명령 ID 27, 11:43:22.229의 STT 결과는 ‘배터리와 잔량 알려줘.’이며 battery_query, confidence 0.97로 저장됐다. 이 명령은 최초 44초 측정 종료 후라서 최초 창에 명령이 없었다는 사실을 인식 실패로 해석하지 않는다.

초기 장면은 몸이 너무 크게 잡히고 머리가 화면 밖으로 잘렸다. 이후 11:44:05.490 분석에서는 다음이 검출됐다.

| 대상 | 검출 confidence | 경로 |
|---|---:|---|
| 사람 | 0.607 | 전체 영상 |
| 조끼 | 0.483 | 사람 ROI, sharp640 |
| 헬멧 | 0.549 | 사람 ROI, original960 |

최종 PPE 상태는 helmet=true, vest=true였다. 직전 분석에서는 조끼=true, 헬멧=null로 흔들림도 있었다. 따라서 검출 가능성은 확인했지만 안정적인 인식률·미착용 판단 정확도는 아직 계산하지 못했다. confidence는 정답 확률의 검증값이 아니다.

### 3. 현재 카메라 구조

- OV5647 센서 모드: RAW8 800×640, 모드 명칭 기준 50 FPS.
- P4 캡처 출력: RGB565 → 하드웨어 JPEG, YUV422, 품질 75.
- 전송 목표 15 FPS, 최신 프레임 큐 1, WebSocket → 내장 C6 Wi-Fi → 서버.
- YOLO 전체 입력 실제 설정 640. 코드의 기본값 320과 주석이 남아 있으나 실행 환경은 640이다.
- 일반 분석 목표 4 FPS, 음성 처리 활성 시 1 FPS.
- 사람 검출 시 최대 2초 ROI 유지. 상세 분석 간격 0.3초.
- 상세 분석은 선명화 ROI 640과 원본 ROI 960을 모두 추론한다. 전체 추론까지 합하면 해당 프레임당 최대 3회 모델 실행이다.

고해상도 상세 분석이 일부 보호구 검출에 도움이 된 증거는 있지만 CPU 비용도 있다. 전송 FPS를 높여도 현재 분석기가 모든 프레임을 추론하는 구조는 아니다.

### 4. 개선 순서

#### 1단계: 안정성·구도 기준 고정

카메라 정지 감시와 캡처/전송 단계별 시각을 먼저 추가한다. 순간 2.45초 정체가 센서 대기·인코더·전송·서버 어느 구간인지 구분해야 한다. 자동 복구는 이전 상세 진단 보고서의 우선순위를 따른다.

사람의 머리~허리가 화면에 들어오도록 1~2m에서 고정하고, 밝은 배경으로 인한 역광·렌즈 가림·초점·흔들림을 확인한다. 원본 JPEG와 분석 결과를 같은 프레임 ID로 비교한다. 잘린 머리는 JPEG 품질이나 FPS를 올려 복원할 수 없다.

#### 2단계: 800×640, 15 FPS 유지하고 JPEG 75→85 비교

가장 작은 변경으로 먼저 시험할 후보다. 동일 장면에서 보호구 경계의 압축 손상이 줄어드는지, JPEG 크기·전송 지연·누락이 얼마나 증가하는지 비교한다. 품질 85가 인식률을 몇 % 올린다고 사전 보장할 수 없다. 품질 90~100은 첫 변경 후보로 삼지 않는다.

현재 평균 약 49KB와 15 FPS를 가정하면 JPEG 페이로드만 약 5.9Mbps다. 동일 크기 20 FPS는 약 7.8Mbps다. 프로토콜 오버헤드·재전송·음성은 별도이며, JPEG 크기는 장면·품질에 따라 변한다.

#### 3단계: 상세 추론을 필요한 경우에만 실행

전체 영상 분석과 보호구 상세 분석 주기를 분리한다. 640 상세 1회로 충분히 판단되는 경우 960을 생략하고, 불확실하거나 대상이 작은 경우에만 960을 추가하는 방식을 비교한다. 상세 갱신 0.5~1초를 실험 후보로 두고 실제 보호구 판정 지연과 누락을 측정한다.

주의: 이번 헬멧은 original960에서 검출됐다. 960 경로를 무조건 제거하면 인식이 나빠질 수 있다. 전체 프레임 분석 4~5 FPS를 목표로 하되 실제 측정 후 확정한다. 안전 경보·음성 중에도 필요한 최소 분석률을 별도로 정한다.

#### 4단계: 원본 해상도 확대

먼 거리에서 보호구가 작은 경우, 센서 드라이버에 존재하는 1280×960 RAW10 binning 모드를 후보로 검토한다. 현재 비활성인 모드이며 ISP 형식·버퍼·JPEG 용량·Wi-Fi 지연을 확인한 후 적용해야 한다. 첫 시험은 10~12 FPS, JPEG 80~85를 후보로 한다. 특정 해상도와 속도가 바로 지원·안정화된다고 보장하지 않는다.

1280×960은 현 원본의 2.4배 픽셀이다. 그런데 전체 YOLO 입력을 640으로 유지하면 전체 영상이 다시 축소된다. 고해상도 원본을 보존한 ROI 추론 또는 전체 입력 768/960을 함께 비교해야 한다. 전체 입력 768은 640 대비 입력 픽셀 수 1.44배이며 실행 시간은 장비·모델에 따라 측정해야 한다.

#### 5단계: 모델·경보 검증

저장된 동일 P4 JPEG를 서버 모델에 오프라인 입력해 실시간 결과와 비교한다. P4 JPEG에서도 실패하면 전송 문제보다 입력 장면·모델 문제가 의심된다. 같은 JPEG의 오프라인 결과는 좋고 실시간만 나쁘다면 프레임 선택·ROI·후처리·상태 유지 로직을 확인한다.

헬멧 시점의 거리·흔들림·역광 표본으로 착용/미착용 정답 자료를 만들고 필요하면 재학습한다. confidence 임계값을 내리는 것만으로 정확도를 높였다고 평가하지 않는다. 보이지 않는 보호구는 ‘미착용’과 구분해 ‘확인 불가’로 처리하는 정책도 검증한다.

### 5. 권장 비교표

| 순서 | 원본 | JPEG 품질 | 전송 목표 | 분석 |
|---|---|---:|---:|---|
| 기준 | 800×640 | 75 | 15 FPS | 현재 전체640 + ROI640/960 |
| 1차 | 800×640 | 85 | 15 FPS | 현재와 동일, 화질 효과만 비교 |
| 2차 | 800×640 | 85 | 15 FPS | ROI 추가 추론 조건·주기 최적화 |
| 3차 | 1280×960 후보 | 80~85 | 10~12 FPS | 원본 ROI 유지, 전체768 후보 비교 |

매 조건에서 같은 사람·거리·조명·움직임으로 정답 대비 검출률, 잘못된 경보, 수신 FPS, 분석 FPS, 프레임 나이 p95/최대, 전송 지연, 동적 메모리, 음성 응답 지연을 기록한다. 이번에는 구간별 샘플만 있으므로 해당 p95를 확보했다고 주장하지 않는다.

### 6. 공식 참고 문서

- [Espressif JPEG 드라이버](https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-reference/peripherals/jpeg.html): JPEG 품질·입력 형식 설정. 로컬 설치 버전 헤더를 적용 기준으로 삼는다.
- [Ultralytics Predict](https://docs.ultralytics.com/modes/predict/): imgsz, conf 및 추론 입력 크기 설정.

이 문서는 개선 계획이며 아직 품질85·해상도 변경·추론 주기 변경을 적용한 결과가 아니다. 재측정 원본은 `C:\dev\hanmir-runtime\integrated-20261010-recheck-*`, `integrated-20261010-ppe-recheck-*`에 보관했다.


---

## 부록 10: UWB_AUTOMATIC_ANCHOR_SURVEY_2026-10-10.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## UWB 시작 시 10초 자동 지도 측량 — 중단 및 수동 방식 복원

> 2026-10-10 사용자 요청으로 자동 지도 생성을 철회했다. 자동 측량 서버 라우터·계산 서비스·웹 패널·앵커 코드를 제거했다. 아래 내용은 시행 당시 기록이며 현재 동작 설명이 아니다. 최신 상태는 `UWB_MANUAL_XY_ROLLBACK_2026-10-10.md` 참조.

### 최신 상태 — 10초 평균으로 X·Y 확정 후 고정 (2026-10-10)

사용자 요구: 모든 앵커가 준비되면 처음 10초간 실제 앵커 간 거리를 모아 이상값을 제거한 평균으로 X·Y를 확정하고, 이후 측정 흔들림은 지도 크기에 반영하지 않는다. 이동하는 안전모 태그 위치만 계속 갱신한다. 현재 재측량은 네 앵커 전체 재부팅이 필요하다. 아래 이전 단계 기록은 당시 상태이며 현재 상태는 이 절을 우선한다.

이 흐름의 펌웨어 수집과 서버 계산 코드는 반영돼 있다. 계산은 각 쌍의 이상값 제거 후 평균 → X=평균(1↔2,3↔4), Y=평균(1↔4,2↔3) → 두 대각선 및 맞은편 변 일치 검증 순서다. 네 앵커가 같은 높이의 직사각형 모서리에 설치된 경우를 전제로 한다. 부팅·네트워크 준비 시간을 포함한 전원 투입 순간부터 정확히 10초가 아니라, 모든 앵커의 준비 완료 후 10초 측정 창이다.

시계 오프셋 중복 부호 확장 수정본을 앵커 1·2·3 및 태그에 반영한 뒤, 사용자 확인 전체 재부팅으로 새 세션 `anchor-001-922116`이 수신됐다. 2026-10-10 13:11 KST 서버 접수, 10초 실제 측량 표본 총 46개. 1↔2 거리 변동으로 거부됐으며 자동 지도 적용은 성공하지 않았다. API started_at/finished_at은 완료 업로드의 서버 처리 시각이므로 실제 무선 측정 창 10초를 나타내지 않는다.

| 쌍 | 표본 수 | 중앙값(m) | 최솟값~최댓값(m) |
|---|---:|---:|---:|
| 1↔2 | 8 | 6.950 | 5.64~9.84 |
| 1↔3 | 9 | 6.960 | 6.30~7.06 |
| 1↔4 | 8 | 3.615 | 3.57~4.07 |
| 2↔3 | 6 | 3.380 | 3.31~3.41 |
| 2↔4 | 7 | 6.280 | 6.11~6.49 |
| 3↔4 | 8 | 4.920 | 4.82~5.06 |

중앙값은 진단용이며 확정된 X·Y가 아니다. 맞은편 가로 1↔2와 3↔4의 중앙값 차이도 2.03m로 커, 평균만 내고 강제 고정하면 잘못된 지도가 될 수 있다. 기존 수동 지도 5.2×3.2m를 유지한다. 1번 주변 가림·금속·높이·안테나 배치와 거리 측정 보정 등을 추가 확인해야 하며, 현재 로그만으로 SW/HW 원인을 확정하지 않는다.

남은 작업: 거리 불일치 원인 확인, 유효 측량 확보, 기존 출구·활성 위험 구역 좌표와 새 지도 경계 처리, 실제 지도 적용 및 웹 표시 확인. 기존 장애물/활성 구역이 있을 때 자동 적용을 보류하는 정책도 아직 남아 있으므로 평균 고정 기능 전체 완료로 표현하지 않는다. 근거 API 기록: `C:\dev\hanmir-runtime\anchor-survey-corrected-result-20261010.json`.


### 추가 진행: 앵커 2번 업데이트 완료

#### 고정 후 재측량 및 시계 보정 결함 확인

수정본 전체 반영: UWB 태그(COM6, 일련번호 02E4F879)도 수정본 업로드·플래시 해시 검증 성공. 기존 로컬 Wi-Fi 설정을 유지했다. UART에서 거리 수신과 서버 `POST 200`, 위치 최신 API HTTP 200 확인. 관측에는 `mask:7`, `mask:3`, `mask:0`도 있어 매 측정 주기의 네 거리 수신이 항상 성공한 것은 아니다. 한 API 스냅샷의 confidence=0.894는 정답 위치 정확도나 장시간 성능 개선율을 입증하지 않는다.

현재 시계 보정 수정본은 앵커 1·2·3 및 태그에 반영 완료, 4번은 이번 계산 수정 대상이 아니다. 수정본 전체 적용 후 앵커 네 개를 모서리에 고정해 모두 재부팅하도록 사용자에게 요청했다. 자동 지도 최신 API는 아직 수정 전 세션의 거부 결과이므로 새 측량 결과가 아니다. 태그 업로드 근거: `C:\dev\hanmir-runtime\tag-clock-fix-upload-20261010.log`, `tag-clock-fix-boot-20261010.log`.

수정본 추가 반영: 3번(COM9)도 중복 부호 확장 제거본 빌드·업로드·플래시 해시 검증 성공. UART의 `SURVEY_STATUS anchor=3 active=0 finished=0`과 태그 보고 수신 확인. 근거: `C:\dev\hanmir-runtime\anchor-03-clock-fix-upload-20261010.log`, `anchor-03-clock-fix-boot-20261010.log`. 거리 계산을 시작하는 앵커 1·2·3 수정본 반영 완료, 태그 수정본 업로드 및 전체 재측량이 남았다. 4번은 계산 시작 역할이 없어 이번 수정 재업로드 대상이 아니다.

수정본 반영 진행: 2번(COM8)도 시계 오프셋 중복 부호 확장을 제거한 펌웨어로 빌드·업로드 및 해시 검증 성공. UART에서 `SURVEY_STATUS anchor=2 active=0 finished=0` 확인. 태그 보고는 계속 들어오지만 관측 중 `mask:7`, `mask:B`도 있어 모든 개별 주기에 4개 거리 수신이 보장된 것은 아니다. 근거: `C:\dev\hanmir-runtime\anchor-02-clock-fix-upload-20261010.log`, `anchor-02-clock-fix-boot-20261010.log`. 수정본은 1·2번 완료, 3번과 태그 업로드가 남았다. 거리 정확도 개선·지도 자동 적용은 수정본 전체 반영 뒤 재측정해야 한다.

사용자가 네 모서리 고정·전체 재부팅을 확인한 뒤 새 세션 `anchor-001-5373001`의 50개 표본이 서버에 저장됐다. 서버는 1↔2 이상값 비율로 거부했다. 쌍별 중앙값/범위: 1↔2 7.22m(6.29~7.40), 1↔3 7.36m(6.53~7.58), 1↔4 3.975m(3.88~4.10), 2↔3 3.455m(3.36~5.14), 2↔4 7.355m(7.20~7.39), 3↔4 4.78m(4.73~4.83). 모든 쌍에 8~9개 표본이 있으나 맞은편 가로 길이 등이 맞지 않아 실제 지도 크기를 확정할 수 없다.

사용 중인 DW3000 드라이버 `dw3000_device_api.cpp`의 `dwt_readclockoffset()`은 이미 부호 확장된 int16_t를 반환하며, 드라이버 예제는 이를 그대로 2^26으로 나눈다. 기존 태그에서 가져온 코드와 초기 survey 코드에는 bit 10(0x400)을 검사해 0xFFFFF800으로 다시 확장하는 잘못된 처리가 있었다. 특정 값에서 시계 보정 오차를 만들 수 있는 확정 코드 결함이므로 제거했다. 해당 세션에는 원시 시계 오프셋 기록이 없어 이 결함이 위 거리 오차 전체를 설명한다고 단정하지 않는다.

`anchor_survey.h`, 원본 `tag.cpp`에서 수정했다. 실제 거리 측정 시작 역할이 있는 1·2·3번과 태그의 새 펌웨어 반영이 필요하다. 4번은 현재 프로토콜에서 응답만 하므로 이 계산 수정만을 위해 다시 업로드할 필요는 없다. 수정한 1번 업로드 이후 2·3번과 태그는 USB 연결·업로드가 추가로 필요하다. 전체 자동 지도 적용은 아직 성공하지 않았다.

재측량 원본: `backend/captures/_surveys/c887ef8f9d0a5665aca2c124fe9e4c75b925c13960c16e625bf116ec3b03f7b8.json`. 진단 결과: `C:\dev\hanmir-runtime\anchor-survey-fixed-corners-20261010.json` 및 동명 `.log`.

최신 진행: 앵커 1번(COM7, 일련번호 02E4F754) `anchor-01` 빌드·업로드 및 플래시 해시 검증 완료. 따라서 1·2·3·4 모두 새 코드 업로드 완료. 1번 정적 RAM 47,948바이트(14.6%), 앱 플래시 집계 937,681바이트(71.5%). 1번은 Wi-Fi·HTTP 조정자 코드가 포함돼 다른 앵커보다 앱이 크다.

첫 실제 부팅 측량에서 `ready_mask=F`, `SURVEY_END samples=50` 확인. 측량 결과 서버 접수도 확인했으나 `anchor-002 ↔ anchor-004 거리 변동이 커 지도 생성 불가`로 거부됐다. 즉 앵커 간 무선 표본 수집은 진행됐지만 자동 지도 확정은 성공하지 않았다. 기존 지도 유지. 원래 네 모서리에 앵커를 고정하고 네 앵커 전체 재부팅 후 재측정하도록 사용자에게 요청했다.

서버 반영을 위해 재시작했을 때 SQLAlchemy QueuePool(5+10 연결) 대기 시간 초과가 발생해 측량 HTTP 전송도 타임아웃됐다. DB에 직접 짧게 쓰기 잠금 요청을 했을 때 약 27ms로 획득돼 지속적인 외부 쓰기 잠금 증거는 없었다. 파일 SQLite에 NullPool을 적용해 연결 풀 슬롯을 기다리는 경로를 제거하고 다시 실행한 뒤 새 측량 API HTTP 200과 결과 접수를 확인했다. 이것이 모든 DB/통신 병목 해결을 입증하는 것은 아니며 동시 부하 관측은 계속 필요하다.

측량 거부 원인을 추적하도록 API에 6쌍별 표본 개수·중앙값·최솟값·최댓값을 추가했다. 이후 completed 업로드의 실제 원본은 `backend/captures/_surveys/<session_id의 SHA256>.json`에 보관한다. 첫 세션의 전체 원본은 이 보관 기능 추가 전이라 해당 위치에 없다. 근거: `C:\dev\hanmir-runtime\anchor-01-survey-upload-20261010.log`, `anchor-01-survey-20261010.log`, `anchor-01-survey-after-server-fix-20261010.log`. 새 서버 실행 로그는 `backend-survey-audit-20261010.*.log`.

후속 작업: 네 모서리 고정 후 재부팅 측량, 각 쌍의 변동 원인 확인, 현재 활성 위험 구역의 좌표 검토, 자동 지도 실제 적용·웹 표시 검증. 앵커 개별 업데이트는 완료됐지만 이 후속 작업은 미완료다.

추가: 앵커 4번(COM10, USB 일련번호 02E4F8EE)도 `anchor-04` 빌드·업로드 및 플래시 해시 검증 완료. UART에서 `SURVEY_STATUS anchor=4 active=0 finished=0`과 기존 태그 보고 `mask:F`, `fail:0`을 확인했다. 현재 2·3·4번 완료, 1번 업로드가 남았다. 근거: `C:\dev\hanmir-runtime\anchor-04-survey-upload-20261010.log`, `anchor-04-survey-20261010.log`. 자동 지도 적용 및 6쌍 실측 검증은 아직 완료 전이다.

추가: 앵커 3번(COM9, USB 일련번호 02E4F8D0)도 `anchor-03` 빌드·업로드 및 플래시 해시 검증 완료. UART에서 `SURVEY_STATUS anchor=3 active=0 finished=0`과 기존 태그 보고 `mask:F`, `fail:0`을 확인했다. 현재 2·3번 완료, 4번과 1번이 남았다. 증거: `C:\dev\hanmir-runtime\anchor-03-survey-upload-20261010.log`, `anchor-03-survey-20261010.log`. 전체 앵커 간 측량 검증은 아직 수행 전이다.

2026-10-10 앵커 간 측량 프로토콜 코드를 `firmware/uwb_multi_test - 복사본/src/anchor_survey.h`에 추가하고 `anchor.cpp`에 연결했다. 네 앵커의 준비 확인, 200ms 슬롯별 6쌍 SS-TWR, 10초 수집, 결과 중복 제거, 1번 앵커의 비동기 HTTP 결과 업로드를 구현했다. `POST /api/anchors/survey/completed`와 웹 지도 설계 페이지의 측량 상태 표시도 추가했다. 전체 무선 측량의 정확성과 동시 동작은 아직 검증하지 않았다.

앵커 2번(COM8, ESP32-D0WD-V3)에 `anchor-02` 빌드·업로드 성공, 플래시 해시 검증 성공. 정적 RAM 21,792바이트(6.7%), 앱 플래시 집계 287,929바이트(22.0%). 업로드 후 UART에서 `SURVEY_STATUS anchor=2 active=0 finished=0`을 확인했다. 이는 새 코드 실행과 준비 대기 확인이며 6쌍 측량 성공이 아니다.

남은 업로드 순서는 3번 → 4번 → 1번이다. 1번도 아직 새 코드 업로드 전이다. 모두 업데이트한 뒤 원래 모서리에 고정하고 함께 전원을 다시 켜야 시작 측량을 확인할 수 있다. 결과는 최초 준비 완료 뒤 10초 창에서 한 번 수집하고 고정한다. 개별 장치 재부팅만으로 재측량할 때의 복구 정책은 아직 별도 검증하지 않았다.

실행 서버에는 새 API를 반영하기 위한 재시작이 남아 있다. 현재 저장 작업장 5.2×3.2m에 기존 활성 위험 구역이 남아 있어, 서버 초기 정책은 측량 proposal까지만 반환하고 자동 적용을 보류한다. 측량값과 위험 구역/출구 기준 좌표를 함께 확인해야 한다. 이전 단계 기록의 ‘펌웨어 작업이 남음’은 아래 최초 준비 시점 상태이며, 현재는 코드 추가·2번 업로드까지 진행됐다.

현장 연결 대기 중인 남은 장치의 펌웨어 빌드·업로드, 서버 반영, 웹 빌드, 6쌍 실측 검증과 위험 구역 처리 연결은 완료되지 않았다. 비밀 Wi-Fi 헤더는 로컬 staging에서 공급하며 공유·커밋하지 않는다. UART 근거는 `C:\dev\hanmir-runtime\anchor-02-survey-20261010.log`에 보관했다.

### 요청과 현재 진행 상태

앵커 1~4를 기존 지도 순서로 작업장의 네 모서리에 배치한다. 전원을 켠 뒤 앵커들이 준비되면 10초간 앵커끼리 거리를 측정하고, 이상값을 제거해 가로·세로를 계산한다. 확정 이후 거리가 조금씩 변해도 지도는 움직이지 않는다. 앵커를 옮겼을 때는 새 측량 세션을 시작한다.

**현재는 서버 수집·통계·좌표 계산 코드를 준비한 단계다. 자동 측량이 장치에서 동작하거나 현장 지도에 적용된 상태는 아니다.** 앵커 1번이 COM7에 연결된 것을 UART로 확인했다. 해당 펌웨어는 태그 보고를 출력하며 앵커 간 측량 기능은 없다. 앵커 2·3·4의 연결 및 펌웨어 작업이 남아 있다. 기존 정상 위치 지도를 가짜 추정값으로 덮어쓰지 않았다. 실행 중 서버는 재시작하지 않았다.

### 태그 거리와 앵커 거리 구분

지금 `T0,mask:F,range:(...)`는 안전모 태그에서 네 앵커까지의 거리다. 이 값을 앵커끼리 거리로 사용하면 지도 크기가 잘못 계산된다. 자동 측량은 1↔2, 1↔3, 1↔4, 2↔3, 2↔4, 3↔4의 **6개 실제 앵커 쌍**을 별도로 측정해야 한다.

앵커들이 벽 모서리에 있을 때 계산 결과가 작업장 크기에 해당한다. 앵커가 벽에서 떨어져 있거나 높이가 서로 다르면 앵커 사이 거리와 실제 바닥 외곽 크기는 다르다. 같은 높이의 직사각형 배치를 기준으로 첫 버전을 준비했다. 대각선 거리도 검증하므로 사각형이 크게 뒤틀리면 적용을 거부한다.

### 준비한 서버 코드

- `backend/app/services/anchor_geometry_service.py`: 6개 쌍 표본 → 중앙값/MAD로 이상값 제거 → 남은 값 평균 → 직사각형 검증.
- `backend/app/routers/anchor_survey.py`: 10초 수집 세션, 중복 제거, 제한 시간 종료 후 적용 또는 거부, 지도 변경 알림.
- `backend/app/routers/__init__.py`: 신규 라우터 등록.

#### 통계 기준 (초기 설정, 실제 앵커 측량 뒤 조정 필요)

- 쌍마다 유효 표본 최소 5개.
- 중앙값 기준 허용 오차 `max(0.10m, 3 × 1.4826 × MAD)`로 이상값 제거.
- 남은 표본 최소 5개 및 원래 표본의 70% 이상.
- 남은 값 범위가 `max(0.30m, 거리의 10%)`보다 크면 거부.
- 가로 = 평균(1↔2, 3↔4), 세로 = 평균(1↔4, 2↔3).
- 두 대각선은 `sqrt(가로² + 세로²)`와 비교. 각 변·대각선 오차가 `max(0.20m, 기대 거리의 5%)`보다 크면 거부.
- 앵커 좌표: 1=(0,0), 2=(가로,0), 3=(가로,세로), 4=(0,세로).
- 전송 재시도는 쌍+sequence로 중복 제거. 재시도 표본을 새 측정으로 세지 않는다.
- 10초 종료 뒤 들어온 값은 지도에 반영하지 않는다.
- 표본 부족·지오메트리 불일치·DB 적용 실패 시 기존 지도 유지.

기존 장애물이나 활성 위험 구역이 있으면 자동 적용은 보류하고 측량 proposal을 반환한다. 지도 크기만 바뀐 채 기존 위험 구역이나 출구가 잘못 표시되는 것을 막기 위한 현재 정책이다. 장애물·구역을 유지하는 현장에서 자동 적용하려면 해당 데이터의 기준 좌표·경계 검증 정책도 연결해야 한다. 앵커 위치와 크기는 적용 전 LayoutVersion으로 저장한다.

### API 계약

1. 조정 장치/브리지가 `POST /api/anchors/survey/start`를 호출해 session_id를 받는다. 서버 수신 시점부터 정확히 10초 창을 시작한다. 펌웨어가 시작 준비를 끝낸 뒤 호출해야 하며 전원 투입 이전의 샘플은 섞지 않는다.
2. `POST /api/anchors/survey/ranges`로 아래 형태의 실제 측정값을 보내며, sequence는 같은 앵커 쌍의 새 측정마다 증가시킨다.

```json
{
  "session_id": "start 응답에서 받은 ID",
  "measurements": [
    {"from_anchor_id": "anchor-001", "to_anchor_id": "anchor-002", "distance_m": 3.25, "sequence": 1}
  ]
}
```

위 3.25는 API 형식 설명용 예시이며 실제 측정 결과가 아니다.

3. `GET /api/anchors/survey`로 awaiting_anchor_firmware, collecting, applied, rejected 상태를 확인한다. applied이면 결과 크기와 6쌍 통계를 반환한다.
4. 서버가 재시작되면 진행 중인 메모리 세션은 사라지고 기존 저장 지도를 유지한다. 이 버전은 현재 단일 FastAPI 워커 구조를 기준으로 준비했다. 여러 워커·프로세스 간 수집 상태 공유와 완료 상태 영속화는 추가 작업이다.

### 남은 장치·웹 작업

1. 앵커별 실제 ID/보드/현재 빌드 설정 확인.
2. 앵커 1번을 측량 조정자로 두고 준비 알림·측량 순서를 동기화. 각 앵커가 한 슬롯에서만 송신하도록 하고 정상 태그 위치 측정과 충돌하지 않게 한다.
3. 전용 앵커 간 TWR 측정과 응답 ID/sequence 검사·무응답 제한 시간 추가. 태그 거리 보정을 그대로 앵커 간 거리 보정에 사용하지 않는다.
4. 6개 쌍 표본을 서버 API로 전달하는 경로 구현. 서버 start 요청 성공 뒤 10초 측량을 수행하고 실패하면 기존 지도 사용.
5. 앵커 1~4 순차 빌드·업로드. 현재는 1번만 USB 확인했으므로 전체 측량 시험은 아직 불가.
6. 웹에 수집 진행·유효 표본 수·실패 원인·확정 크기를 표시하고 layout_changed 후 지도 데이터를 다시 읽게 한다.
7. 새 지도 적용 후 방향 기준·위치 필터·위험구역/출구를 확인. 현 코드는 위치 필터를 초기화하지만 방향 기준 재보정과 웹 상태 연결은 남아 있다.
8. 실제 줄자로 잰 값과 자동 지도 값 비교, 재부팅 반복, 한 앵커 누락, 장애물/NLOS, 앵커 이동 시 재측량을 검증.

‘전원 켠 후 10초’는 모든 앵커가 통신 준비를 마친 뒤 시작하는 측정 창이다. 늦게 켜진 앵커의 표본을 억지로 보충하거나 태그 거리로 대체하지 않는다. 완성 전에는 자동 지도 기능으로 기존 현장 지도를 변경하지 않는다.


---

## 부록 11: UWB_MANUAL_XY_ROLLBACK_2026-10-10.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## UWB 수동 X·Y 지도 방식 롤백 — 2026-10-10

### 요청 및 변경

사용자 요청으로 시작 시 10초 앵커 간 자동 측량과 지도 생성을 제거한다. 웹의 기존 작업장 설계에서 가로 X(m)·세로 Y(m)를 직접 입력하고 설계 저장 후 현장에 적용한다. 자동 측량 서버 API/계산 서비스, 웹 상태 패널/API 메서드, 앵커 survey 헤더와 연결 코드를 제거했다. anchor.cpp는 자동 측량 추가 전 HEAD 내용으로 복원하고 ASCII 빌드 staging에도 반영했다.

태그 거리 계산의 잘못된 시계 오프셋 부호 확장 제거, 파일 SQLite NullPool, P4·카메라·음성·방향 관련 개선은 유지했다. 자동 측량 원본 자료와 이전 진행 문서는 시행 기록으로 보관한다.

### 서버·웹

실행 서버를 재시작해 수동 지도 코드 반영. GET /api/layout 응답의 지도는 5.2×3.2m, 앵커 좌표는 1=(0,0), 2=(5.2,0), 3=(5.2,3.2), 4=(0,3.2), 높이 2.2m로 유지됐다. DB 지도/구역/출구/설계안을 임의 변경하지 않았다. 웹 기존 LayoutEditor의 가로 X·세로 Y 입력, 설계 저장, 현장에 적용 흐름을 복원했다. 실제 브라우저 화면 조작 검증이나 테스트 스위트는 실행하지 않았다.

### 장치 업데이트

자동 측량은 이미 네 앵커에 업로드됐으므로 서버 변경만으로 장치 측 측량을 없앨 수 없다. 앵커 1→2→3→4 순서로 USB를 연결해 일반 위치 측정 펌웨어를 재업로드해야 한다. 태그와 P4는 이번 롤백 재업로드 대상이 아니다. 1번 USB COM7/02E4F754 확인, 현재 롤백 펌웨어 빌드 및 업로드 진행 중. 완료 내역은 아래에 추가한다.

빌드 근거: C:\dev\hanmir-runtime\anchor-manual-rollback-build-20261010.log
서버 로그: C:\dev\hanmir-runtime\backend-manual-map-20261010.*.log

#### 앵커 1번 완료

COM7/02E4F754 확인 후 일반 anchor-01 앱(286032바이트)을 0x10000에 업로드했다. esptool 해시 검증 성공 및 하드 리셋 완료. 근거: C:/dev/hanmir-runtime/anchor-01-manual-rollback-upload-20261010.log. 2·3·4번 업로드는 아직 남아 있다.

#### 앵커 2번 완료

COM8/02E4F75D 확인 후 일반 anchor-02 앱(285776바이트)을 0x10000에 업로드했다. esptool 해시 검증 성공 및 하드 리셋 완료. UART 원본은 C:/dev/hanmir-runtime/anchor-02-manual-rollback-boot-20261010.log에 저장했다. 1·2번 완료, 3·4번 업로드가 남았다. 업로드 근거: C:/dev/hanmir-runtime/anchor-02-manual-rollback-upload-20261010.log.

#### 앵커 3번 완료

COM9/02E4F8D0 확인 후 일반 anchor-03 앱(285776바이트)을 0x10000에 업로드했다. esptool 해시 검증 성공 및 하드 리셋 완료. UART 기록: C:/dev/hanmir-runtime/anchor-03-manual-rollback-boot-20261010.log. 1·2·3번 완료, 4번 업로드가 남았다. 업로드 근거: C:/dev/hanmir-runtime/anchor-03-manual-rollback-upload-20261010.log. 네 앵커 롤백 펌웨어 전체 빌드 성공(빌드 로그 확인).

#### 앵커 4번 완료 및 롤백 완료

COM10/02E4F8EE 확인 후 일반 anchor-04 앱(285776바이트)을 0x10000에 업로드했다. esptool 해시 검증 성공 및 하드 리셋 완료. 1·2·3·4번 전체 일반 위치 측정 펌웨어 반영 완료. UART 원본: C:/dev/hanmir-runtime/anchor-04-manual-rollback-boot-20261010.log. 업로드 근거: C:/dev/hanmir-runtime/anchor-04-manual-rollback-upload-20261010.log. 서버·웹의 자동 측량 기능 제거와 네 앵커 재업로드까지 완료했다. 웹에서 가로 X·세로 Y 입력 → 설계 저장 → 현장에 적용으로 사용한다.

#### 웹 실행본 갱신 완료
사용자의 웹 롤백 요청 후 자동 측량 코드 참조가 없는 것을 재확인하고 npm run build(TypeScript 및 Vite) 성공. dist 실행 산출물 갱신. 기존 Vite PID 8616을 확인 후 종료하고 수동 지도 웹을 5174 포트에 재시작했다. HTTP 200 확인. 브라우저에서는 새로고침해 사용한다. 카메라/방향 등 자동 지도 추가 전에 진행한 기능은 유지했다.

#### 지도 값 불일치 제보 확인
사용자 제보 후 실제 Chrome의 /layout 및 /map 화면과 서버 layout/draft, layout, dashboard/snapshot을 비교했다. 현재 사용자 저장 설계는 4.8×2.5m(13:38:59 KST 저장)이며 세 API와 실시간 지도 상단 모두 동일했다. 이전 5.2×3.2m 기록은 당시 값이며 현재값이 아니다. 오른쪽 현재 위치 X4.3/Y2.5m는 작업자 태그 좌표로 지도 크기와 다른 값이다. 자동 측량 참조는 제거된 상태이며 LayoutEditor/layout.py는 HEAD 대비 변경 없음. 사용자 입력값을 임의로 이전 치수로 덮어쓰지 않았다.


---

## 부록 12: MAP_LIVE_HEADING_2026-10-10.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## 지도 방향 실시간 갱신 — 2026-10-10

### 변경 이유

BNO085 SH-2 rotation vector는 기존에도 10Hz(100000us)로 읽었다. 하지만 서버에 보내는 방향값은 5초 heartbeat에만 포함돼 있고, 웹은 heartbeat마다 전체 snapshot/history를 다시 조회했다. 센서 입력 속도와 화면 갱신 속도가 달랐다.

### 반영 내용

- P4 command_client.c: 기존 /ws/device/{device_id} 명령 WebSocket을 공유하는 독립 heading task 추가. 최신 yaw/pitch/roll을 100ms 간격으로 보내며, 연결이 끊기면 송신하지 않는다. 송신 대기 시간은 30ms로 제한하며 과거 표본을 큐에 쌓지 않는다. 기존 5초 heartbeat는 유지한다.
- main.py: 장치 socket에서 orientation JSON을 수신한다. 크기 512자 제한, 등록된 assistant_device만 처리, 숫자/유한값/각도 범위 검증, 최대 20Hz 처리 제한. 현재 기존 장치 socket의 인증 정책을 따른다.
- orientation_service.py: 최신 방향만 프로세스 메모리에 보관한다. 샘플별 DB 쓰기를 하지 않는다. 2초가 지난 live 표본은 미확인 처리하며 과거 heartbeat 방향으로 되돌리지 않는다. 단일 서버 워커를 전제로 한다. 여러 워커에서는 공유 캐시/메시지 전달이 추가로 필요하다.
- serializers.py/devices.py: snapshot과 방향 보정 시 최신 live 값을 사용한다. 보정 offset은 기존 서버 설정을 유지한다. 센서의 yaw만으로 임의 북쪽 방향을 만들지 않는다.
- useSafetyData.ts: orientation 이벤트에서 해당 장치의 방향만 직접 갱신한다. 10Hz마다 전체 snapshot/history를 재조회하지 않는다. 진행 중인 느린 snapshot 응답이 더 최신 방향을 덮어쓰지 않게 수신 시각을 비교한다.
- SiteMap.tsx: 화살표 회전에 requestAnimationFrame과 80ms 보간을 사용한다. 359↔0도는 최단 회전 경로로 연결한다. 기존 지도 가로/세로와 Y축 반전을 반영한 각도 변환을 유지한다. live 방향은 3초 이상 오래되면 숨긴다. 기존 5초 heartbeat 장치에는 기존 15초 기준을 사용한다.

자동 지도 생성 기능은 다시 추가하지 않았다. 사용자 수동 X·Y 설정과 기존 앵커 배치를 유지한다. 실시간 방향은 휴대폰 자체 나침반이 아니라 안전모 BNO085의 방향이다.

### 빌드·업로드 및 실제 관측

웹 npm run build(TypeScript/Vite) 성공. ESP-IDF 5.5.5 P4 빌드 성공. 앱 바이너리 1890400바이트, 4MiB 앱 파티션 중 약 55% 여유. 데이터 USB COM25(303A:1001, 30:ED:A0:EA:5C:E2)를 확인하고 앱만 0x10000에 업로드, esptool 해시 검증 및 하드 리셋 완료. 파티션/음성 모델 데이터는 변경하지 않았다. 서버 재시작으로 새 수신 경로 반영.

실제 dashboard WebSocket을 12초 동안 관측: orientation 95건, 수신율 7.95Hz, 간격 중앙값 109.5ms, 최대 219.0ms. 동시에 location 38건, camera_frame 10건, heartbeat 2건을 수신했다. 이는 짧은 구간에서의 이벤트 수신 관측으로 전체 센서→휴대폰 지연, 카메라 FPS 또는 장시간 병목 부재를 입증하지 않는다. 정지 상태 yaw 범위는 -152.177~-152.085도였다.

사용자에게 안전모/BNO를 함께 좌우로 돌려 지도 화살표 반응과 방향을 확인하도록 요청했고, 사용자가 “ㅇㅇ 잘된다”라고 답했다. 특정 휴대폰/브라우저 종류와 정량 회전 지연은 별도 확인되지 않았다. 단위 테스트나 테스트 스위트는 추가·실행하지 않았다.

### 근거

- C:/dev/hanmir-runtime/p4-live-heading-build-20261010.log
- C:/dev/hanmir-runtime/p4-live-heading-upload-20261010.log
- C:/dev/hanmir-runtime/p4-live-heading-observation-20261010.json
- C:/dev/hanmir-runtime/backend-live-heading-v2-20261010.*.log

### 제한 및 인수 사항

새 서버 코드와 새 P4 펌웨어를 함께 사용한다. 이전 펌웨어는 기존 heartbeat 방향 갱신을 계속 사용한다. 서버를 다시 켜면 transient 방향 캐시는 비워지고 새 표본으로 복구된다. BNO 센서 읽기 함수의 기존 신선도 기준은 2초라 센서 자체가 멈췄을 때 이를 판별하는 시간은 별도로 발생한다. 실제 자기장 간섭·장착 방향·센서 보정에 따른 각도 정확도는 갱신 속도와 별개다. ESP-IDF 활성화는 한글 TEMP 경로 문제를 피하려고 TEMP/TMP=C:/dev/tmp로 실행했다. staging 경로는 C:/dev/hanmir-p4/helmet_p4이며 이번 변경 command_client.c를 원본과 동기화했다.


---

## 부록 13: MOBILE_P4_INTEGRATION_2026-10-10.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## HANMIR P4 + 최신 모바일 앱 통합 인수인계

작성일: 2026-10-10. 실제 휴대폰 검증은 진행 중이며 완료된 항목과 구분한다.

최신 추가 작업: 웹·앱 통화 요청이 HTTP 409로 실패하는 원인을 확인하고 P4 통화 채널, 서버 인증 설정, 앱 WebSocket 주소를 수정했다. Android 최신 배포는 build13이다. 최종 build12와 인증서가 같으며 웹 마이크는 localhost/HTTPS 조건을 확인한다. 상세 내용과 실제 업로드·검증 범위는 [통화 수정 기록](P4_CALL_CONNECTION_FIX_2026-10-10.md)을 참조한다.

### 최신 추가 반영: PC 웹 디자인 및 build12

- 사용자가 추가로 지정한 최신 웹 브랜치 `codex/integrated-worker-app-v1.8-web-ui-20261010` (`51d555c`)를 통합했다. 병합 커밋 `a62f7a7`.
- PC 안전 현황 요약 `DesktopSafetyOverview`, 실시간 작업자 선택, 메뉴 아이콘, 최근 이벤트 정렬, PC 전용 CSS를 반영했다.
- 충돌 1건은 `safetyPresentation.ts`의 동일한 안전 요약 함수였다. 최신 웹 버전으로 해결했으며 P4·서버 코드의 추가 변경은 없었다.
- 이번 병합은 어제·오늘의 카메라 전송, BNO UART/방향, AI/STT/TTS, 수동 UWB 지도, 앱 이미지 로딩 및 작업자 실시간 방향 변경을 유지한다.
- Android versionCode 및 iOS build number를 **12**로 올리고 `npm run build:mobile`로 TypeScript/Vite 빌드 및 양 플랫폼 자산 동기화에 성공했다.
- 웹 개발 서버는 `http://localhost:5174`, 다른 PC/휴대폰 브라우저에서는 `http://192.168.0.40:5174`다. 앱의 API 서버 설정은 계속 `http://192.168.0.40:8000`이다.
- P4/앵커 펌웨어는 이번 웹 디자인 병합으로 바뀌지 않았다. 연결된 장치에 다시 업로드할 필요가 없다.
- 기존 build10 웹 UI ZIP은 원본 참고 자료다. 최신 통합 소스는 위 통합 브랜치에서 받는다.
- 아래 build11 진단·해시 기록은 당시 결과로 유지한다. 신규 배포용은 build12다. iOS 신규 서명 IPA와 실제 휴대폰 기능 확인은 여전히 별도다.
- 최종 build12 빌드: GitHub Actions `38029001268`, 성공. 파일 `releases/HanmirSafety-p4-mobile-v1.8-build12.apk`.
- 최종 APK SHA-256: `5c03e28e1232b747416d5597d05ac85aec399c6bcec4d36b69f67cdef0ce9a58`.
- 최종 인증서 SHA-256: `267e18f5d8ec2585c4b6a0b67abcd576f90635033ff9a0aba616960d6a49d974`. 기존 build10·build11과 다르므로 사용자 선택대로 기존 앱을 삭제하고 새로 설치한다.
- CI에서 서명 키 생성 위치를 명시하고 Gradle에 해당 경로를 전달하도록 수정했다. 이전 자동 생성 키는 캐시 경로와 달라 보관되지 않았다. 앞으로 같은 캐시 키가 유지되는 빌드는 동일 서명을 사용한다.

### 1. 소스 기준

- 통합 브랜치: `integration/p4-mobile-live-heading-20261010`
- 최신 앱 디자인/관리자·작업자 앱 원본: `codex/integrated-worker-app-v1.8-build10-20261010`, 커밋 `775d06f`.
- 로컬 P4 검증 변경 묶음: `8a62933`. 최신 앱과 병합: `43b7ebe`.
- 네이티브 카메라 로딩 및 작업자 실시간 방향 통합: `1a6c753`.
- 기존 저장소를 유지하고 모바일 변경을 병합했다. P4 펌웨어 충돌은 실제 장치에 검증한 로컬 버전을 유지했다.
- AI/STT/TTS, 최신 프레임만 남기는 YOLO 큐, UWB 수동 지도, 방향 보정 기능을 유지한다. 이 문서는 모든 AI 기능을 휴대폰에서 재검증했다는 의미가 아니다.

### 2. 현재 실행 환경

- PC 서버: `http://192.168.0.40:8000`, PC/휴대폰/P4/태그는 같은 WISET 네트워크.
- PC 주소는 DHCP로 바뀔 수 있다. 다른 컴퓨터로 이동하면 실제 IPv4를 확인하고 앱 서버 설정 및 장치 서버 주소를 변경해야 한다.
- FastAPI: 프로젝트 `.venv` Python으로 `backend`에서 `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- 개발 웹: frontend Vite, 현재 5174. 네이티브 앱은 빌드된 웹 자산을 사용하므로 Vite 서버가 없어도 된다.
- 로그: `C:\dev\hanmir-runtime\backend-mobile-build11.out.log`, `.err.log`.
- 병합 전 DB 백업: `C:\dev\hanmir-runtime\safety-before-mobile-integration-20261010.db`.
- API 키는 로컬 `.env`에 보관한다. DB·키·원본 진단 ZIP은 GitHub 공개 배포에 포함하지 않는다.
- 서버 세션은 메모리에 저장되어 서버 재시작 시 앱에서 다시 로그인해야 한다.

### 3. 유지한 실제 하드웨어 상태

- P4 펌웨어는 기존 검증 버전으로 이미 업로드했다. 이번 앱 업데이트에 P4 재업로드는 필요하지 않다.
- BNO 방향은 전용 WebSocket으로 약 100ms 간격 전송. heartbeat 5초와 분리했다.
- 관리자 지도 방향은 최단 각도 경로로 부드럽게 보간하며 새 데이터가 끊기면 표시를 무효화한다.
- UWB 자동 지도 측량은 사용자의 요청으로 제거했다. 앵커 1~4는 수동 지도 방식으로 재업로드 완료했다.
- 지도 크기는 설계 화면에서 사용자가 입력하고 적용한다. 현재 DB는 5.0 × 3.3m이며 자동 측량 값으로 덮어쓰지 않는다.
- 기존 하드웨어 배선 및 단위시험 상태는 하드웨어 문서와 `MAP_LIVE_HEADING_2026-10-10.md`, `UWB_MANUAL_XY_ROLLBACK_2026-10-10.md`를 함께 참조한다.

### 4. Android No Frame 진단 및 수정

사용자 실제 보고: Android 앱 카메라 화면에 `No Frame` 표시.

확인한 사실:

1. P4 원본 프레임과 YOLO 분석 결과가 서버에서 계속 갱신됐다.
2. LAN 주소로 이미지 API를 호출하면 HTTP 200, `image/jpeg`, JPEG 시작 바이트 `FFD8FF`, 약 82KB가 반환됐다.
3. 휴대폰 IP에서 카메라 `/latest` 상태 조회는 HTTP 200으로 기록되지만 실제 `/latest/image` 요청은 기록되지 않았다.
4. 따라서 영상이 서버에 없는 상태와 다르다. 앱의 이미지 로딩 단계가 실패하고 있다. WebView 콘솔 로그가 없어 혼합 콘텐츠 차단 등의 정확한 원인은 아직 확정하지 않았다.

수정:

- `services/cameraImage.ts`: Android/iOS에서는 Capacitor 네이티브 HTTP로 JPEG를 받아 base64를 바이트로 변환하고 Blob URL로 표시한다. HTTPS WebView에서 LAN HTTP 이미지를 직접 읽는 경로를 피한다.
- 기존 `CameraFrame`에도 동일 경로를 적용하여 카메라 관제·작업자 상세·긴급 카메라 표시를 함께 수정했다.
- `LiveCameraFrame`: 네이티브에서는 최근 원본 JPEG를 순차 조회한다. 완료 후 200ms 쉬며 요청을 중첩시키지 않는다. 목표 최대 약 5fps이며 실제 속도는 네이티브 브리지·Wi-Fi에 따라 낮아질 수 있다. P4 송신 FPS와 앱 표시 FPS는 별개다.
- PC 웹 원본 영상은 기존 MJPEG 스트림을 사용한다. 분석 화면은 별도로 유지한다.
- Blob URL은 교체/종료 시 해제한다. 이미지 데이터는 영구 저장하지 않는다.
- 이 수정의 Android 실제 표시 성공은 새 APK 설치 후 확인해야 한다.

### 5. 작업자 앱 실시간 방향

- 작업자 `/me` 응답에 장치 직렬화 결과를 포함하여 배터리·방향·보정값·최신 시각을 제공한다.
- `/ws/worker?token=...`는 로그인한 작업자의 현장 및 작업자 ID로 구독한다.
- 서버는 해당 작업자의 방향/위치/heartbeat 이벤트만 전송한다. 관리자 WebSocket과 분리했다.
- 작업자 지도에도 실시간 방향 화살표를 추가했다. 수동 보정값을 적용하고 오래된 방향은 표시하지 않는다.
- 2초 폴링은 연결이 끊겼을 때의 보조 수단으로 유지한다. 폴링 응답이 최신 방향을 덮어쓰지 않게 한다.
- 작업자 앱의 실제 전화기 회전 반응은 설치 후 별도 확인한다.

### 6. 빌드 및 배포

- `frontend`에서 `npm run build:mobile`: TypeScript/Vite 빌드 및 Android/iOS Capacitor 자산 동기화 성공.
- Android versionName 1.8, versionCode 11. iOS build number 11.
- Windows에는 Android SDK/Java 21 구성이 없어 `.github/workflows/android-p4-integration.yml`로 GitHub Actions APK를 빌드한다.
- CI에서 Linux용 esbuild optional lock 항목, SDK manager 설치, 폐기된 `tools` 패키지 요청을 수정했다.
- APK 서명 비교 정보를 함께 생성한다. 기존 APK와 새 APK 서명이 다르면 직접 덮어쓰기 설치가 안 된다. 기존 서명 키로 재빌드하거나 사용자가 기존 앱 삭제를 승인해야 한다. 임의로 기존 앱을 삭제하지 않는다.
- GitHub Actions 실행 `38027873833` 빌드 성공. APK: `releases/HanmirSafety-p4-mobile-v1.8-build11.apk`.
- APK SHA-256: `3ed94a14516954c86050c0a3de0a96e307aea93a90585760ea7b9606065ca2d3`.
- 현재 APK 인증서 SHA-256: `e653b766387b2e8670f7dbb5a585b9375cc9e5127d4f689106bb55fec87c6db4`.
- 기존 build10 인증서 SHA-256: `dcb416fbd939530d54660095ec6d1c1a00cf74b679ad340987756d5c484a9c00`.
- 사용자 선택 변경: **기존 앱을 직접 삭제하고 build11 APK를 새로 설치**한다. 기존 서명 키 확보 및 동일 서명 재빌드는 불필요하다. APK를 기존 앱 위에 덮어쓰기 설치할 수는 없다. 삭제 후 앱의 로그인·서버 설정을 다시 입력한다. 서버 DB의 작업자·지도 데이터는 앱 삭제로 삭제되지 않는다.
- iOS 프로젝트 자산은 동기화했지만 신규 서명 IPA는 아직 만들지 않았다. 기존 Mac/Xcode와 인증서·프로비저닝 환경이 필요하다. 기존 build10 IPA는 이번 변경을 포함하지 않는다.

### 7. 병합 후 실제 서버 관측

2026-10-10 서버 재시작 후 약 6초 관측:

| 항목 | 결과 |
| --- | --- |
| P4 및 UWB 태그 | 두 장치 online |
| 원본 프레임 | frame_id 35890, 조회 시 age_ms 62 |
| 방향 이벤트 | 46건 / 6초, 약 7.67Hz |
| 위치 이벤트 | 20건 / 6초 |
| 분석 프레임 이벤트 | 5건 / 6초 |
| heartbeat | 1건 / 6초 |
| 배터리 | 해당 순간 약 5.23%, 충전 필요 |

짧은 관측으로 장시간 병목이 없다고 단정하지 않는다. 이전 부하 측정 문서와 함께 판단한다.

### 8. 실제 휴대폰 검증 순서

1. Android 새 APK 설치 후 서버 `http://192.168.0.40:8000` 저장 및 관리자 로그인.
2. 카메라 원본 영상과 분석 화면 각각 표시 여부 확인. 실패하면 휴대폰 로그의 이미지 요청/오류를 확인한다.
3. 지도 5.0 × 3.3m 확인, 안전모/BNO를 함께 돌려 방향 반응 확인.
4. UWB 위치 이동·4개 앵커 상태 확인.
5. 배터리 값과 온라인 상태를 서버 값과 비교.
6. “투투스 배터리 알려줘”, “투투스 위치 알려줘” 발화와 스피커 응답 확인.
7. 비상 발화는 시험임을 공유하고 실제 이벤트 및 안내를 확인. 모든 기능을 동시에 실행하며 FPS/음성 지연/위치 갱신 기록.
8. 작업자 계정에서 본인 지도/방향/배터리 확인, 다른 현장·작업자 데이터가 섞이지 않는지 확인.
9. Android 확인 후 신규 IPA를 원래 iOS 서명 환경에서 생성하고 동일 항목 검증.

현재 미완료: 사용자의 기존 Android 앱 삭제 및 새 APK 설치, 휴대폰 카메라 성공 확인, 작업자 앱 실제 회전 확인, 신규 iOS IPA 빌드 및 iPhone 검증.


---

## 부록 14: P4_CALL_CONNECTION_FIX_2026-10-10.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## P4 웹·앱 통화 연결 오류 수정

### 실제 원인

사용자는 웹과 Android 앱 모두에서 통화 연결 시 “마이크 권한 또는 서버 연결을 확인하세요” 표시를 보고했다.

- 서버 로그에는 PC 및 휴대폰의 `/api/calls/helmet-001-av/ticket` 요청이 모두 HTTP 409로 기록됐다.
- 서버는 안전모 통화 WebSocket이 없으면 “안전모 통화 채널이 오프라인입니다”로 거절한다. 장치 heartbeat가 online인 것과 통화 채널 online은 별개다.
- 기존 P4 펌웨어에는 마이크 STT 업로드와 TTS 재생이 있었지만 S3의 `call_client.cpp`에 해당하는 양방향 통화 구현이 없었다.
- 로컬 서버의 `CALL_DEVICE_TOKEN`도 설정되지 않아 장치 통화 인증을 통과할 수 없었다.
- 앱 `HelmetCall`은 저장된 PC 서버 주소 대신 WebView의 `https://localhost`에서 통화 WebSocket 주소를 만들고 있었다. 따라서 장치 통화 채널을 추가해도 앱에서 추가 연결 실패가 발생할 수 있었다.

### 수정한 코드

#### P4

- `main/call_client.c` 신규: 인증된 전용 WebSocket `/ws/call/device/{device_id}`.
- 마이크의 기존 AFE 출력에서 16kHz mono PCM16을 공유한다. I2S RX 채널을 중복으로 열지 않는다.
- PCM을 최대 640바이트 단위로 전송하며 송수신 큐는 각각 6개로 제한한다. 오래된 PCM을 버려 통화 지연이 누적되지 않게 한다.
- 수신 PCM은 기존 MAX98357A I2S TX로 재생한다. 스피커 mutex로 TTS와 통화가 동시에 I2S를 조작하지 않게 한다.
- 통화 중 AI 발화 녹음·STT 업로드는 일시 중단한다. 종료하면 기존 AI 질문 경로로 돌아간다.
- 서버의 `call_start`/`call_stop` 및 연결 종료를 처리한다. `play_alert` 명령은 통화를 종료시킨 뒤 경고음을 출력한다.
- 마이크·스피커가 준비되지 않으면 통화 채널을 시작하지 않는다.
- `HANMIR_CALL_DEVICE_TOKEN`은 빈 기본값으로 정의했다. 실제 토큰은 로컬 sdkconfig에만 넣는다.

#### 서버

- 기존 장치 토큰 인증을 유지한다. P4는 URL 대신 Authorization 헤더로 토큰을 전달하고 서버가 읽도록 추가했다.
- 장치가 보내는 `call_stop`을 처리하여 관리자에게 종료 상태를 알린다.
- 로컬 `.env`의 `CALL_DEVICE_TOKEN`과 P4 staging sdkconfig에 동일한 값을 설정했다. 값은 문서·GitHub에 올리지 않는다.

#### 웹·앱

- `HelmetCall.tsx`: 공통 `getWsBaseUrl()`을 사용해 앱에 저장된 서버 주소로 통화한다.
- 통화 채널 오프라인, 로그인 만료, 마이크 권한 거부, 마이크 없음, 비보안 웹 주소를 구분해 표시한다.
- 통화에 실패하거나 상대가 바쁠 때 마이크 스트림과 AudioContext를 정리한다.
- 연결 확정 전에는 마이크 PCM을 보내지 않는다.
- HTTP LAN 주소로 접속한 일반 웹 브라우저에서는 마이크가 제한될 수 있다. PC 웹은 `http://localhost:5174`, 원격 웹의 마이크는 HTTPS 환경을 사용한다. 네이티브 앱은 앱 내부 WebView에서 마이크 권한을 사용한다.

### Android build13

- 파일: `releases/HanmirSafety-p4-mobile-v1.8-build13.apk`.
- GitHub Actions `38029735257`에서 빌드했다. TypeScript/Vite 및 Android/iOS 자산 동기화 완료.
- APK SHA-256: `47a0bba1c4b09cfc5b303a836d4e5ce560799eccf035a8b70d2768bc885ba1ab`.
- 인증서 SHA-256: `267e18f5d8ec2585c4b6a0b67abcd576f90635033ff9a0aba616960d6a49d974`.
- 최종 build12와 인증서가 같아 build12 위에 업데이트할 수 있다. 사용자는 직접 삭제 후 설치하는 방식을 선택했다.
- 앱 서버 설정: `http://192.168.0.40:8000`. 서버 재시작 후 로그인 세션은 다시 만들어야 한다.
- iOS 프로젝트는 build13으로 동기화했지만 신규 서명 IPA는 별도 Mac 환경에서 제작해야 한다.

### 실제 확인의 범위

P4 ESP-IDF 빌드 성공. 앱 크기 1,892,528바이트. COM25에서 앱 파티션 `0x10000`에 업로드하고 esptool 해시 일치 및 재부팅을 확인했다. 서버에 P4 `/ws/call/device/helmet-001-av`가 인증 후 등록됐다.

- `/api/calls/helmet-001-av/status`: HTTP 200, `channel_online=true`.
- `/api/calls/helmet-001-av/ticket`: 이전 HTTP 409에서 HTTP 200으로 변경, 통화 티켓 발급 확인.
- 동시에 원본 카메라 수신: frame_id 397, 조회 시 age_ms 31.
- 실제 두 방향 음성이 들리는지와 에코 상태는 사용자 확인 대기다. 컴파일 성공이나 연결 성공만으로 실제 양방향 음성이 검증됐다고 판단하지 않는다.
- 통화 상태 API의 `helmet_packets/bytes`, `operator_packets/bytes`는 해당 통화에서 서버에 도착한 PCM 계측이다. 패킷 수신만으로 스피커 재생 성공을 판단하지 않는다.
- 최종 서버 로그: `C:\dev\hanmir-runtime\backend-call-final.out.log`, `.err.log`; 펌웨어 빌드/업로드 로그: `p4-call-build.log`, `p4-call-upload.log`.

첫 실제 Android 통화 관측: 휴대폰 IP `192.168.0.41`의 통화 티켓 요청 HTTP 200. 통화 종료 후 누적 계측은 안전모→관리자 1,176패킷/602,112바이트, 관리자→안전모 936패킷/599,040바이트였다. PCM16 mono 16kHz 기준 각각 약 18.82초/18.72초다. 통화 종료 후 `operator_connected=false`, 장치 통화 채널은 `channel_online=true`로 유지됐다. 이는 양방향 PCM 수신 증거이며 실제 가청 음질·에코는 사용자 확인이 필요하다.

### 후속: 실제 스피커 출력 미확인

사용자 확인: 안전모 마이크 소리는 앱에서 들리지만 휴대폰 마이크 소리는 안전모에서 들리지 않았다. 블루투스/유선 이어폰 없이 휴대폰에 직접 발화했다.

- P4에 PCM 수신 peak와 스피커 쓰기 로그를 추가하고 업로드했다.
- 실제 로그: 약 2초마다 60,160~64,640바이트 수신, peak 10,818~32,768/32,768, `speaker_write=ok`.
- 따라서 휴대폰 PCM에 음성이 존재하며 P4까지 수신된다. 서버의 바이트 카운트뿐 아니라 P4 수신도 확인했다.
- 일반 확인음 명령도 P4가 `ok`로 응답했지만 사용자는 들리지 않는다고 답했다. 통화 연결 실패와 별도로 공통 스피커 출력 경로를 확인해야 한다.
- 배터리 보고값은 약 5.9%였다. 사용자는 배터리 전원 스위치를 켰다고 답했다. MAX98357A VIN–GND 실제 전압은 아직 확인하지 못했다. 배터리 잔량만으로 앰프 전원 차단을 확정하지 않는다.
- 컴파일 설정상 스피커 BCLK/WS/DIN은 GPIO20/21/22, 내장 C6 SDIO는 GPIO14~19다. 해당 GPIO의 중복 배정은 없다.
- 스피커 DMA를 기존 기본 511프레임에서 160프레임(10ms), 6개 버퍼로 조정했다. 짧은 통화 PCM 패킷에 맞추는 변경이다. 빌드·업로드 해시 일치 및 재부팅 완료. 이를 원인 해결로 단정하지 않는다.
- 버퍼 수정 후 확인음도 사용자는 안 들린다고 답했다. 사용자는 측정기가 없으며, 앰프 5V 공급 여부는 아직 확인할 수 없다. 배터리 충전 및 MAX98357A 전원/신호/스피커 배선 사진을 요청했다. 양방향 통화 전체가 해결됐다고 표시하지 않는다.

사용자는 앱/PC 마이크로 말한 내용이 안전모 스피커에서 들리는지, 안전모 마이크로 말한 내용이 앱/PC에서 들리는지를 각각 확인해야 한다. 통화 종료 후 AI 질문과 TTS가 복귀하는지도 확인한다.

현재 통화는 NS 처리된 마이크 PCM을 사용하지만 스피커 재생 신호를 참조하는 AEC는 구현하지 않았다. 실제 에코·하울링은 실물 배치와 음량 조건에서 확인해야 한다.

### 추가 비교: 충전 상태와 수정 전 코드

- 통화 기능을 잠시 끄고 수정 전 스피커 코드로 업로드하여 1.5초 확인음을 보냈으나 사용자에게 들리지 않았다.
- SW6106 충전용 USB-C 연결 후에도 확인음 3회가 들리지 않았다. 조회 시 배터리 보고값은 약 7.84%였다.
- 명령 `2defa9e8-614e-4fbb-ba15-17b937fdde40`은 전달되고 P4에서 `ok`로 응답했다. 이는 I2S 데이터 쓰기 결과이며 실제 앰프 전원이나 가청 출력을 증명하지 않는다.
- 통화 변경만을 원인으로 보기는 어렵지만, 앰프 고장으로 확정할 근거도 없다. VIN–GND 전압, 신호선과 SD 핀, 스피커 단자 확인이 필요하다. 사용자는 측정기가 없어 배선 사진을 요청했다.

통화 지원 버전으로 다시 빌드하여 COM25에 업로드했다. 앱 크기 1,892,864바이트, 해시 검증 및 재부팅 완료. 서버에서 channel_online=true를 확인했다. 임시 통화 비활성 비교 상태는 해제했다.

### 스피커 상세 I2S 진단

사용자는 통화 권한 이슈 수정 전까지 스피커가 정상 작동했다고 명확히 확인했다. 이 시간 관계를 원인 분석에서 유지하며, 하드웨어 고장으로 단정하지 않는다.

스피커 초기화 핀/형식, 재생 잠금 오류, I2S 활성화 오류, 톤 쓰기 바이트 및 명령 실행/완료 로그를 추가했다. COM25에 앱 1,893,696바이트 업로드 후 해시 일치 확인.

실제 명령 `98304974-d6f0-44ff-a505-025e85421143`: 1000Hz, 1500ms, 24,000샘플. P4 로그는 `tone complete ok=1 bytes=48000 expected=48000` 및 동일 명령 ID의 완료 `ok=1`을 기록했다. 서버도 해당 명령에 `ok` 응답을 받았다. 배터리 보고값 약 19.31%. 원시 로그는 로컬 `C:\dev\hanmir-runtime\p4-speaker-i2s-diagnostic.log`에 보관.

이 관측에서 재생 잠금 시간 초과, I2S 활성화 실패, 쓰기 오류는 나타나지 않았다. GPIO 실제 파형, MAX98357A 공급 전압 및 가청 출력은 증명되지 않았다. 사용자에게 실제 소리 여부를 다시 요청했다.

### 현재 물리 장치 버전 변경

사용자 요청으로 통화 수정 전 커밋 df52167의 펌웨어 전체를 다시 빌드·업로드했다. 현재 P4는 새 통화 기능이 없는 롤백 버전이다. 상세 범위와 결과는 `P4_FULL_PRECALL_ROLLBACK_2026-10-10.md` 참조. 최신 통화 코드가 저장소에 있다는 사실과 현재 장치 버전을 혼동하지 않는다.


---

## 부록 15: P4_FULL_PRECALL_ROLLBACK_2026-10-10.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## P4 통화 수정 전 전체 펌웨어 롤백 — 2026-10-10

### 목적
사용자는 통화 권한 문제 수정 전에는 스피커가 정상 작동했다고 확인했다. 스피커 일부 코드 비교만으로 판단하지 않고 당시 펌웨어 전체를 복원하여 가청 출력을 비교한다.

### 기준과 범위
- 기준 커밋: `df52167` (통화 수정 전 build12 통합 상태).
- `firmware/helmet_p4`의 Git 추적 파일 31개 전체를 빌드 스테이지에 복원했다. 이전 커밋과 바이트 단위 일치 31/31 확인.
- 이후 추가된 `call_client.c`는 스테이지에서 제거했다. 초기화, 음성, 명령, 스피커, CMake/Kconfig 모두 당시 소스다.
- 현재 소스와 장치 설정 백업: 로컬 `C:\dev\hanmir-runtime\p4-before-full-rollback-20261010.zip`. 비밀 설정을 포함할 수 있으므로 GitHub에 업로드하지 않는다.
- 현재 Wi-Fi/서버 주소 및 실제 하드웨어 GPIO 설정은 연결을 유지하기 위해 사용한다. 당시 장치 sdkconfig의 별도 스냅샷은 없어, 당시 바이너리와 비트 단위 동일하다고 주장하지 않는다.
- ESP-IDF 5.5.5와 당시 dependencies.lock으로 재빌드한다. 최신 앱/서버 및 Git 저장소 소스는 이 비교로 되돌리지 않는다.
- P4에서는 새 양방향 통화 기능이 빠진다. 스피커 테스트 후 다음 결정을 사용자와 한다.

### 결과
- 전체 빌드 성공. 앱 크기 1,890,400바이트, SHA-256 `135166fbc2d99b694fe0a704c220c37eb6f3c5f4871d5b7e695fd543128a0950`.
- COM25에서 부트로더 `0x2000`, 파티션 `0x8000`, 앱 `0x10000`, 빌드된 음성 모델 파티션 `0x410000` 업로드 및 해시 검증, 재부팅 완료.
- `/api/calls/helmet-001-av/status`의 `channel_online=false`: 새 통화 기능이 실행되지 않는 상태 확인.
- 명령 `93f17c5d-e575-4d60-96a3-879f605e42c4`: 1000Hz/1500ms 확인음, 연결 1개에 전달되고 해당 명령에 P4 `ok` 응답 확인. 배터리 보고값 약 33.84%.
- 사용자는 전체 롤백 후에도 확인음이 안 들린다고 답했다. 이 버전에는 새 상세 I2S 진단 로그도 포함되지 않는다. 소스 전체 복원 후 무음이 재현됐지만 당시 sdkconfig/바이너리와 동일한 비교는 아니므로 모든 소프트웨어 원인을 배제하지 않는다.
- 현재 P4는 이 롤백 버전으로 유지한다. 저장소 최신 코드와 빌드 스테이지가 다르므로 후속 작업자는 최신 펌웨어 업로드 전에 반드시 이 문서를 확인한다.
- 로컬 로그: `p4-full-precall-rollback-build.log`, `p4-full-precall-rollback-upload.log`, `p4-full-precall-rollback-serial.log` (C:/dev/hanmir-runtime).


### 후속 독립 진단

스피커 전용·GPIO 전용 진단에서 GPIO20/21 교차 레벨이 관측됐다. 자세한 내용은 `P4_SPEAKER_SIGNAL_DIAGNOSIS_2026-10-10.md` 참조. 진단 이후 P4는 다시 일반 통화 수정 전 버전으로 복구한다.


---

## 부록 16: P4_SPEAKER_SIGNAL_DIAGNOSIS_2026-10-10.md

> 당시 작업 기록입니다. 최신 상태는 본문 1절을 우선합니다.

## P4 스피커 무음: 출력 신호 분리 진단 — 2026-10-10

### 현재 결론
스피커 자체 고장으로 확정하지 않는다. GPIO20(BCLK)과 GPIO21(WS)이 독립적으로 동작하지 않는 현상을 실측 입력 및 펄스 카운터로 관측했다. 두 핀의 전기적 결합, 배선/납땜 연결, 앰프 쪽 영향, P4 쪽 문제를 구분하려면 앰프 연결을 분리한 상태의 비교가 필요하다. 본 계측은 멀티미터의 저항/전압 측정이나 외부 오실로스코프 파형 측정을 대신하지 않는다.

### 이전 비교
- 통화 수정 전 소스 df52167 전체 31개 파일 복원 후에도 무음. 당시 바이너리/설정과 비트 단위 동일한 비교는 아니다.
- 수정 후 상세 I2S 로그는 1000Hz/1500ms에 PCM 48,000바이트 전체 쓰기 성공. 실제 가청 출력은 없었다.
- 발견한 sdkconfig.before-wiset-20261010과 현재 설정의 HANMIR 마이크/스피커 항목 차이는 없다.
- 원래 플래시 백업에서 프로젝트 p4_record_play, 빌드 날짜 Oct 8 2026, ESP-IDF v5.5.5를 확인했다. 이는 별도 5초 큰 확인음 프로그램이므로 통합 펌웨어와 같은 것으로 취급하지 않았다.

### 전용 출력 비교
애플리케이션의 네트워크/카메라/마이크/IMU/배터리/통화 초기화를 호출하지 않고 직접 I2S를 구동했다. esp_hosted 라이브러리의 부팅 자동 초기화 로그는 존재한다. 이를 완전히 모든 라이브러리 작업이 없는 환경이라고 주장하지 않는다.

| 단계 | 출력 설정 | 기록된 PCM 쓰기 |
|---|---|---:|
| 1 | I2S1, 16bit mono left, 16kHz | 32,000 bytes |
| 2 | I2S1, 16bit mono right, 16kHz | 32,000 bytes |
| 3 | I2S1, 16bit stereo 같은 신호 양 채널, 16kHz | 64,000 bytes |
| 4 | I2S1, 32bit stereo 같은 신호 양 채널, 16kHz | 128,000 bytes |
| 5 | I2S0, 16bit stereo, 16kHz | 64,000 bytes |
| 6 | I2S1, 16bit stereo, 48kHz | 192,000 bytes |

사용자가 최초 하나 이상 들렸다고 응답한 후 바로 전부 안 들렸다고 정정했다. 최종 결과는 6개 모두 무음이다. 채널 선택이나 I2S 포트 변경으로 가청 출력이 복구됐다는 증거는 없다.

초기 진단 버퍼가 main task 스택을 초과하여 재부팅했다. static 버퍼로 수정한 뒤 위 6단계와 핀 교차 검사가 정상 완료됐다. 이 임시 진단 프로그램의 초기 오류를 기존 스피커 문제의 원인으로 혼동하지 않는다.

### 핀 교차 검사: 핵심 결과
I2S 채널을 삭제한 뒤 GPIO20/21/22를 reset하고, 시험하는 핀 하나만 INPUT_OUTPUT, 나머지는 INPUT+약한 pull-down으로 설정했다. LOW/HIGH를 20ms 유지하여 gpio_get_level로 읽었으며 각 핀에 100개 펄스를 생성했다. 펄스 카운터는 양의 에지 증가, 음의 에지 무시로 설정했다.

```text
DRIVE GPIO20 LOW=0,0,0 HIGH=1,1,0
DRIVE GPIO20 100 PULSES COUNTS=100,100,0
DRIVE GPIO21 LOW=0,0,0 HIGH=1,1,0
DRIVE GPIO21 100 PULSES COUNTS=100,100,0
DRIVE GPIO22 LOW=0,0,0 HIGH=0,0,1
DRIVE GPIO22 100 PULSES COUNTS=0,0,100
```

읽은 핀 순서는 항상 20,21,22다. GPIO20과21은 양방향으로 서로 따라갔고 GPIO22는 독립적이었다. 고속 I2S에서 WS 펄스가 설정상 예상과 다르게 관측된 것을 계기로 이 저속 검사를 실시했다. 출력 데이터가 두 핀에 분리되지 않는다면 앰프는 올바른 BCLK/WS를 얻지 못할 수 있다. 단락의 위치나 저항값은 아직 모른다.

### 필요한 다음 비교
1. 전체 전원을 끄고 MAX98357A BCLK/LRC 및 P4 GPIO20/21 연결부 사진 확인.
2. 앰프 쪽 BCLK와LRC 신호선을 분리 가능하면 분리한 뒤 동일 검사. 전원 상태에서 탈착하거나 임의로 공급 전원을 추가하지 않는다.
3. 분리 후 현상이 없어지면 앰프 또는 그 연결 쪽 영향. 유지되면 P4/남은 배선 쪽을 조사한다. 분리 위치에 따라 관측 범위가 달라진다.
4. MAX98357A VIN–GND 전압 및 SD_MODE 실제 상태는 아직 미측정이다. SPI/I2S 로그로 전압이나 앰프 활성화를 증명하지 않는다.

### 보관
- 진단 소스: firmware/diagnostics/p4_speaker_isolation/app_main.c 및 CMakeLists.txt. 평소 펌웨어에 자동 포함되지 않는다.
- 로컬 진단 바이너리: C:/dev/hanmir-runtime/p4-speaker-isolation-crosscheck.bin.
- 원시 로그: p4-speaker-isolation-crosscheck.log, p4-speaker-isolation-serial.log.
- 진단 후 통화 수정 전 일반 펌웨어로 복구 작업을 진행한다. 완료 여부는 후속 기록으로 확인한다.

### 참고
- MAX98357A 채널 및 데이터 형식: https://www.analog.com/en/products/max98357a.html
- ESP-IDF 5.5 ESP32-P4 I2S: https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32p4/api-reference/peripherals/i2s.html

### 독립 GPIO 검사 결과

I2S와 PCNT를 초기화하지 않는 gpio_only.c로 별도 빌드·업로드했다. 일반 GPIO 출력만 사용하고 핀 설정 덤프도 확인했다. 모든 핀의 GPIO Matrix SigOut ID는 256(simple GPIO output), 나머지 두 핀의 OutputEn은 0이었다. 두 차례 반복 모두 아래와 같았다.

```text
output=GPIO20 level=0 READ_20_21_22=0,0,0
output=GPIO20 level=1 READ_20_21_22=1,1,0
output=GPIO21 level=0 READ_20_21_22=0,0,0
output=GPIO21 level=1 READ_20_21_22=1,1,0
output=GPIO22 level=0 READ_20_21_22=0,0,0
output=GPIO22 level=1 READ_20_21_22=0,0,1
```

이 독립 비교는 I2S 형식/채널/PCNT 설정 때문에만 교차 현상이 생겼다는 설명을 지지하지 않는다. 연결된 상태의 디지털 레벨 관측이며, 저항 0옴의 단락으로 확정하지 않는다. 정확한 위치는 앰프 쪽 BCLK/LRC 분리 비교와 실제 전압·도통 측정이 필요하다. 사용자는 외관상 배선 문제가 없다고 답했으나 분리 비교나 사진은 아직 없다.

로그: C:/dev/hanmir-runtime/p4-pin-only-serial.log. 비교 바이너리도 로컬 보관했다. 진단 완료 후 통화 수정 전 일반 펌웨어 복구를 실행했다. 빌드 스테이지의 main/app_main.c 및 main/CMakeLists.txt도 일반 소스로 복원했다. build 폴더 바이너리는 마지막 진단 결과일 수 있으므로 후속 업로드 전에 반드시 정상 소스로 재빌드해야 한다.
