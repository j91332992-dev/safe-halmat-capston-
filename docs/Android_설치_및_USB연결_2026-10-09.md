# Android 설치·USB 백엔드 연결

2026-10-09 연결된 Galaxy S21에 v1.7 / build 8 debug APK를 `adb install -r`로 업데이트했습니다. 기존 앱 데이터는 유지했습니다. 이후 색상 대비 수정 APK도 다시 설치했습니다.

## 빌드

이 PC에서는 Android Studio 내장 최신 Java가 Gradle과 맞지 않아 설치된 Java 21을 사용했습니다. PowerShell에서 `frontend/android`로 이동 후 실행합니다. 경로는 각 PC 설치 위치에 맞게 바꾸세요.

```powershell
$env:JAVA_HOME='C:\Users\Sewon\.jdks\jbr-21.0.11'
$env:ANDROID_HOME='C:\Users\Sewon\AppData\Local\Android\Sdk'
.\gradlew.bat '-Pandroid.overridePathCheck=true' assembleDebug
```

한글 프로젝트 경로 때문에 Windows Android 경로 검사를 명시적으로 설정했습니다. 안정적인 빌드를 위해 영문 경로의 체크아웃을 사용할 수도 있습니다.

먼저 `frontend`에서 웹 빌드와 Android 동기화를 완료해야 합니다.

```powershell
npm.cmd run build
npx.cmd cap sync android
```

APK: `frontend/android/app/build/outputs/apk/debug/app-debug.apk`.

AndroidManifest의 중복 `usesCleartextTraffic` 속성을 제거했습니다. 로컬 의존성에 있던 ‘복사본’ 파일들은 `node_modules` 안의 별도 백업 폴더로 옮겼습니다. Windows 재분석 지점 속성 때문에 일반 파일로 인식되지 않던 소스 4개는 내용을 유지하며 다시 저장했습니다. 이러한 로컬 의존성 및 빌드 산출물은 Git에 포함하지 않습니다. 팀원은 정상 패키지 설치로 의존성을 준비하세요.

## USB 연결

백엔드가 PC의 8000 포트에서 실행되고 있어야 합니다. USB 디버깅을 허용한 후 Android SDK의 adb로 연결을 설정합니다.

```powershell
adb devices
adb reverse tcp:8000 tcp:8000
adb reverse --list
```

앱 서버 설정에 `http://127.0.0.1:8000` 입력 → 연결 테스트 → 저장 및 적용.

USB 재연결 때 reverse 설정이 사라져 연결 테스트가 실패한 사례가 있었습니다. 위 명령으로 복구한 뒤 PC의 `/api/health`와 회원가입 확인 API가 모두 HTTP 200 응답임을 확인했습니다. USB 재연결·재부팅 시 다시 설정해야 할 수 있습니다.

USB 없이 사용하려면 폰과 PC를 같은 Wi-Fi에 연결하고 앱 서버 주소를 `http://<PC의 현재 IPv4>:8000`으로 지정하세요. 네이티브 앱은 백엔드 8000을 사용하며 프론트엔드 개발 서버 5174와 구분합니다.

## 이번 업데이트

- 공통 `contrast.css`와 관리자/근로자 화면 색상 대비 수정.
- 알림 등급·처리 상태 한글 표시.
- 웹 빌드·Android APK 빌드 성공, 연결 기기에 업데이트 설치 성공.
- [색상 대비 검사 내용](앱_색상대비_점검_2026-10-09.md).
