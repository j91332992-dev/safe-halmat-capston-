# HANMIR 모바일 통합판 v1.8 / build 10

## 최신 설치 파일

- iOS: `releases/HanmirSafety-integrated-worker-app-v1.8-build10.ipa`
- Android: `releases/HanmirSafety-integrated-worker-app-v1.8-build10.apk`

두 파일은 같은 프런트엔드 빌드를 사용하므로 관리자·근로자 통합 로그인과 최신 작업자 기능이 동일하게 들어 있습니다.

## 주요 변경 사항

- 로그인 화면 안에서 `관리자 로그인`과 `근로자 로그인`을 작은 탭으로 선택
- 관리자·근로자 계정과 권한을 구분해 로그인 및 회원가입 처리
- 계정·회사·현장에 따라 분리된 관제 데이터 표시
- 근로자의 휴게 시작/작업 재개를 여러 번 반복해도 누적 휴게시간 유지
- 작업 중에는 현재 작업시간과 누적 휴게시간을 실시간 표시
- 작업 종료 후 총 작업시간과 총 휴게시간을 기록에 표시
- 관리자 화면과 근로자 달력에서도 작업·휴게 합계를 확인
- iOS와 Android 앱 버전을 모두 `1.8 (10)`으로 통일

## 설치 참고

- IPA는 현재 개발 인증서로 서명된 개발·시연용 파일입니다. 허용된 iPhone에서 사용할 수 있습니다.
- APK는 디버그 서명된 설치·시연용 파일입니다. Android에서 출처가 확인되지 않은 앱 설치를 허용하면 직접 설치할 수 있습니다.
- App Store 또는 Google Play 정식 배포 시에는 각 스토어용 배포 인증서로 다시 서명해야 합니다.

## 확인 결과

- 백엔드 자동 테스트: 96개 통과
- 프런트엔드 빌드 및 Capacitor iOS/Android 동기화: 완료
- IPA 생성 및 실제 iPhone 설치: 완료
- APK 생성 및 압축 무결성 확인: 완료
- Android 패키지: `com.hanmir.safesmarthelmet`
- Android 최소 버전: Android 7.0(API 24)
