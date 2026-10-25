# HANMIR iPhone 앱 — Mac 설치 인수인계

작성일: 2026-10-25. 브랜치: `integration/hanmir-final-prd-20261016`.

## 지금 어디까지 준비됐나

최신 Android build26에서 사용한 관리자·근로자 React 화면을 iOS도 그대로 빌드한다. iOS 전용으로 화면을 다시 작성하거나 예전 build10 화면을 복사하지 않는다. `frontend/src`가 두 플랫폼의 공통 원본이다. 기존 카메라 밝기·YOLO 기준·음성·UWB·P4 펌웨어 설정은 이번 작업에서 변경하지 않았다.

- iPhone 실기기용 arm64 **v1.8 / build27** 컴파일 성공. [최초 성공한 GitHub Actions 실행](https://github.com/j91332992-dev/safe-halmat-capston-/actions/runs/40175631911).
- 컴파일된 앱의 웹 파일 **15개**가 같은 실행에서 만든 production 웹 빌드와 SHA-256으로 일치했다. 이는 번들 내용 검증이며 아이폰에서 모든 기능이 동작했다는 뜻은 아니다.
- 저장소의 Android build26 APK 내부 `assets/public/`와 iOS 번들을 직접 비교해도 **15/15개가 동일**했다. 운영체제별 실행 차이는 아래 실기기 시험에서 확인한다.
- 기존 `armv7` 필수 장치 설정을 `arm64`로 수정했다. 최소 iOS 버전은 15.0이다.
- 예전 제작자의 Apple Team 고정값을 제거하고 Xcode 자동 서명 설정을 유지했다. Mac에서 실제 설치할 계정의 Team을 한 번 선택해야 한다.
- iOS 네이티브 바탕색을 공통 다크 UI의 RGB(12,14,18)로 맞췄다. Debug에서 WKWebView 검사도 가능하도록 했다.
- 마이크·카메라·로컬 네트워크 권한 설명과 현장 HTTP 서버 연결 설정을 포함한다.
- Windows 개인 서명은 사용자의 요청으로 중단했다. **이번 iPhone 설치·로그인·양방향 통화 실기기 시험은 아직 하지 않았다.**

## Mac에서 가장 짧은 설치 순서

1. Mac에 **Xcode 26 이상**, Node.js 22 이상, Git, Python 3를 준비한다. Xcode를 처음 실행해 필요한 구성 요소 설치를 끝낸다. Xcode → Settings → Locations → Command Line Tools에서 사용할 Xcode를 선택한다. 프로젝트는 Swift Package Manager를 사용하므로 이 경로에 CocoaPods 설치는 필요 없다.
2. 새 폴더에서 아래 명령을 실행한다. 이미 저장소가 있으면 현재 작업을 보존한 뒤 해당 브랜치의 최신 코드를 받는다.

```bash
git clone --branch integration/hanmir-final-prd-20261016 \
  https://github.com/j91332992-dev/safe-halmat-capston-.git hanmir
cd hanmir
bash frontend/scripts/prepare-ios-mac.sh
```

스크립트는 환경 확인 → `npm ci` → 공통 UI production 빌드 → `cap sync ios` → iOS 번들 파일 일치 검사 → Xcode 열기를 실행한다. 서버 주소를 임의로 고정하거나 Apple 계정에 로그인하지 않는다. 최초 실행에는 npm·Swift 패키지 다운로드 인터넷 연결이 필요하다.

3. Xcode → Settings → Accounts에서 **설치할 사람의 Apple 계정**으로 로그인한다. 비밀번호·인증번호·인증서 개인키는 GitHub에 올리지 않는다.
4. Xcode의 **App 프로젝트 → App 타깃 → Signing & Capabilities**에서 Automatically manage signing을 사용하고 본인의 Team/Personal Team을 선택한다. Bundle Identifier는 기본 `com.hanmir.safesmarthelmet`이다. Apple이 이 식별자를 본인 팀에서 사용할 수 없다고 실제 오류를 내면 본인 소유의 고유 식별자로 바꾼다. 변경할 경우 `frontend/capacitor.config.ts`의 appId와 Xcode Debug/Release의 Bundle Identifier를 함께 맞추고 준비 스크립트를 다시 실행한다. 이 값은 서버의 `helmet-001-av` 장치 ID와 별개다.
5. 아이폰을 Mac에 USB로 연결하고 신뢰·잠금을 해제한다. 필요한 경우 아이폰 설정 → 개인정보 보호 및 보안 → 개발자 모드를 켜고 재시동 안내를 따른다.
6. Xcode 상단 실행 대상에서 실제 아이폰을 선택하고 **Run(▶)** 한다. 패키지 해결·서명·설치가 진행된다. 개발자를 신뢰하라는 안내가 실제로 나오면 아이폰 설정 → 일반 → VPN 및 기기 관리에서 본인 프로파일을 확인한다.
7. 앱 최초 실행에서 로컬 네트워크를 허용한다. 마이크 권한은 통화 기능을 실행할 때 허용한다. 최신 서버를 켜고 같은 LAN에서 아래 서버 주소 설정을 마친다.

무료 Personal Team은 프로파일 유효기간이 7일이므로 이후 Mac에서 다시 Run하여 갱신해야 한다. 한 번 설치하면 영구 사용하는 IPA 배포 방식은 아니다. TestFlight/App Store 배포는 유료 개발자 계정과 별도 배포 설정이 필요하다.

## IPA 파일과 Xcode 프로젝트의 차이

- [`releases/HanmirSafety-ios-v1.8-build27-unsigned.ipa`](../releases/HanmirSafety-ios-v1.8-build27-unsigned.ipa)는 최신 화면을 포함한 **서명 전 실기기 바이너리**다. 파일을 아이폰에 복사하거나 Finder로 옮기는 것만으로 실행되지 않는다.
- **이번 Mac 설치의 권장 경로는 위 소스 준비 → Xcode Run이다.** Xcode가 해당 아이폰/Apple Team에 맞게 서명하고 설치한다. 기존 unsigned IPA를 Xcode에서 자동으로 재서명해 주는 절차로 설명하지 않는다.
- 과거 `build8/9/10.ipa`는 당시 프로비저닝이 2026-10-17에 만료됐고 최신 Android 화면·수정 전체를 담고 있지 않다. 최신 설치 원본으로 사용하지 않는다.
- 빌드 증거: [`evidence/2026-10-25/ios-build27/`](evidence/2026-10-25/ios-build27/). manifest의 source_commit은 실제 컴파일 원본이며 후속 문서 커밋과 다를 수 있다.
- CI artifact는 보관 기간이 있으므로 다운로드 가능한 unsigned IPA도 위 releases 경로에 보존한다. Apple 서명 인증서·프로비저닝·개인 계정 정보는 포함하지 않는다.

## 서버는 계속 필요하다

앱에는 관리자·근로자 화면이 들어 있고 FastAPI·YOLO·DB는 별도 서버 PC에서 실행된다. Mac으로 앱을 설치하더라도 기존 Windows 서버를 계속 사용할 수 있다. 앱 설치가 P4/UWB 펌웨어 설치나 AI 서버 설치를 대신하지 않는다.

로그인 화면의 **관제 서버 설정**에서 현재 서버 PC의 LAN 주소를 입력하고 연결 테스트 → 저장한다. 작업 당시 예시는 `http://192.168.0.40:8000`이며 고정 보장값이 아니다. 아이폰의 `localhost`는 서버 PC가 아니라 아이폰 자신이다. 개발용 프런트 포트 5174 대신 **백엔드 포트 8000**을 입력한다.

- 아이폰·서버 PC·안전모가 서로 접근 가능한 같은 LAN에 있어야 한다. 서버 PC는 5GHz, P4/C6·UWB는 2.4GHz여도 같은 LAN이면 가능하다. 게스트 격리망은 별도 확인한다.
- 서버가 다른 PC/IP로 이동하면 앱의 서버 주소뿐 아니라 장치의 서버 대상도 맞춰야 한다. 앱 설정만 바꿔서는 장치 송신 주소가 바뀌지 않는다.
- 앱은 저장한 주소로 HTTP API와 WS/WSS를 함께 구성한다. 개발용 원격 `server.url`을 지정해 번들 UI를 과거 웹 화면으로 대체하지 않는다.
- HTTP 허용은 현장 LAN 시연 환경을 위한 현재 설정이다. 인터넷 공개 배포에서는 HTTPS/WSS, 인증·권한 및 배포 설정을 별도로 검토한다.

## Android와 공유하는 기능·UI

| 항목 | iOS에 들어가는 구현 | Mac 설치 후 확인 |
| --- | --- | --- |
| 관리자/근로자 | 공통 로그인·권한별 라우팅·현장 데이터 분리 | 실제 각 계정으로 로그인/로그아웃 |
| UI/UX | 공통 다크 배경·폰트 선언·SVG 아이콘·근로자 테마·44px 버튼·이벤트 카드/페이지 구분 | 노치·홈 인디케이터·키보드·회전 시 잘림 |
| 카메라/YOLO | 동일 native 이미지 전송 경로·원본/분석 화면·색상별 검출 박스·FPS/ms 표시 | 장치 영상 새로 수신되는지 |
| 지도/UWB/방향 | 동일 지도·작업자 아이콘·실시간 갱신·마지막 위치 구분 | 새 UWB/방향값과 표시 시각 |
| 통화 | 동일 PCM 중계·AudioWorklet·전송 Worker·필터·버퍼 통계·fallback | 아이폰↔안전모 양쪽 청취·3분 유지 |
| AI/호출/음성 | 기존 안전모→서버 STT/규칙/LLM→TTS 경로 유지 | 실제 호출·명령·TTS 청취 |
| 낙상/대피/금지구역 | 기존 서버 이벤트·지도·관리자 화면 공유 | 현장 설정/기준 자세·모의 이벤트 |
| 작업/채팅/교육·허가/알림 | 최신 공통 관리자·근로자 코드 | 권한별 메뉴·입력·저장 |

같은 CSS라도 iOS 시스템 폰트·WebKit·오디오 권한/출력 경로는 Android와 다르다. 특히 아이폰에서 통화 지연·지지직·수화부/스피커 경로·화면 잠금은 실기기 확인 전 보장하지 않는다. 백그라운드 상시 통화, CallKit, 네이티브 푸시까지 새로 구현한 것은 아니다. 현재 범위는 앱을 열어 사용하는 현장 관제 시연이다.

## 설치 후 시험 순서와 기록

1. 서버 연결 테스트와 관리자 로그인 → 장치 온라인/배터리 갱신 → 카메라 새 원본/분석/FPS → 지도/방향.
2. 근로자 로그인 → 내 작업·근무 달력·채팅·교육/허가·알림 → 키보드 열고 닫기, 하단 버튼/노치 확인.
3. 아이폰에서 통화 시작 → 양쪽 번갈아 발화 → 통화 3분 유지. 실제 들리는지 사용자 확인과 서버의 양방향 bytes/큐 폐기/끊김·카메라 FPS를 함께 기록한다. 화면에서 연결됐다는 표시만으로 음질 합격 처리하지 않는다.
4. 통화 종료 → 안전모 ‘투투스’와 배터리 질문 → 안내/응답이 회복되는지 확인한다.
5. 시연할 때 낙상 확인·무응답 관리자 알림, 화재 종료/대피 종료, 금지구역 알림을 별도 시험한다. 기존 현장 구역을 임의 변경하거나 실제 낙상 동작을 요구하지 않는다.

기록할 값: 소스 커밋, 앱 build, iPhone/iOS 버전, 서버 주소, 권한 허용 여부, 영상/YOLO/상세 FPS, 서버 RTT, 통화 연결 시간·재연결 횟수·양방향 bytes·폐기량, UWB 마지막 수신 경과와 유효 앵커 수. 기준은 Android의 실제 시험 결과와 비교하되 그 결과를 iPhone 측정값으로 재사용하지 않는다.

## 현재 검증 범위

- **완료:** 최신 공유 소스의 iOS 실기기용 컴파일, 번들 파일 일치, 권한 설명, arm64, iOS build27 패키지 생성.
- **완료:** Android Galaxy S24+에서 관리자 13개·근로자 6개 화면 점검. [상세 보고서](HANMIR_2.0_FULL_MOBILE_UI_AUDIT_2026-10-25.md).
- **미완료:** 새 IPA의 iPhone 설치/서명, iOS 전체 화면·양방향 통화·모든 센서 연동 실기기 검증. Mac 연결 후 위 순서로 진행한다.

## 공식 참고

- [Capacitor iOS — 지원 버전·Xcode·실행](https://capacitorjs.com/docs/ios)
- [Apple — 실기기/시뮬레이터 실행](https://developer.apple.com/documentation/xcode/running-your-app-on-simulated-or-physical-devices)
- [Apple — Personal Team 및 무료 계정 제한](https://developer.apple.com/help/account/basics/about-your-developer-account/)
- [Apple — 개발자 모드](https://developer.apple.com/documentation/xcode/enabling-developer-mode-on-a-device)
