# GitHub 팀 공유 및 다른 PC 실행 가이드

## 이 저장소에 포함되는 것

- 관리자 웹(PC / 휴대폰 / iPad UI)
- FastAPI 관제 백엔드
- 가상 안전모 시뮬레이터
- ESP32 펌웨어와 하드웨어 연동 문서
- YOLO 모델 파일(`backend/best.pt`)과 배터리·음성 AI Agent 연동 코드
- 팀원용 최초 설치/실행 배치 파일

## GitHub에 올리면 안 되는 것

`.gitignore`가 아래 파일을 자동으로 제외한다.

- `node_modules`, Python 가상환경(`.venv`)
- 로컬 관제 DB(`backend/safety.db`)와 캡처/녹음/TTS 결과물
- `backend/.env`의 API 키, 통화 토큰
- Wi-Fi와 장치 비밀키가 들어갈 수 있는 펌웨어 헤더
- 개인 PC에서 생성한 로그와 복사본 파일

**API 키나 실제 Wi-Fi 비밀번호를 GitHub에 올리지 않는다.** 팀원은 각자 `backend/.env.example`을 `backend/.env`로 복사한 뒤 본인 개발용 값을 넣는다.

## 최초 1회: 저장소를 GitHub에 올리는 사람

프로젝트 최상위 폴더에서 PowerShell을 열고 아래 순서로 실행한다.

```powershell
git init
git add .
git status
git commit -m "Initial team share - smart helmet safety control"
```

그 다음 GitHub 웹사이트에서 빈 저장소를 만든다. README나 `.gitignore`를 새로 만들지 않은 빈 저장소가 편하다. GitHub가 보여 주는 주소를 아래의 `저장소주소` 자리에 넣는다.

```powershell
git branch -M main
git remote add origin 저장소주소
git push -u origin main
```

`git status`에서 `backend/.env`, `backend/safety.db`, `.venv`, `node_modules`가 보이면 업로드 전에 중지하고 `.gitignore`를 다시 확인한다.

## 팀원의 다른 Windows PC에서 실행

### 1. 준비물

- Git
- Python 3.10 이상
- Node.js LTS
- 동일 Wi-Fi에서 휴대폰/iPad 테스트를 하려면 Windows 방화벽의 Node.js 및 Python 네트워크 접근 허용

### 2. 내려받기와 최초 설치

```powershell
git clone 저장소주소
cd safe-halmat-capston--main
.\TEAM_SETUP_WINDOWS.bat
```

`TEAM_SETUP_WINDOWS.bat`은 다음을 자동으로 수행한다.

1. `backend/.venv` 생성
2. 백엔드 Python 패키지 설치
3. `frontend` Node 패키지 설치
4. `backend/.env.example`을 기반으로 개발용 `.env` 생성

### 3. 실행

```powershell
.\TEAM_RUN_ALL.bat
```

두 개의 창이 열린다.

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5174`

가상 안전모 데이터도 필요하면 세 번째 PowerShell 창에서 실행한다.

```powershell
.\TEAM_RUN_SIMULATOR.bat
```

### 4. 휴대폰/iPad 접속

프론트엔드 창에 나타나는 `Network` 주소(예: `http://192.168.x.x:5174`)를 휴대폰/iPad Safari 또는 Chrome에 입력한다. PC와 모바일 기기는 같은 Wi-Fi여야 한다.

로그인 계정은 현재 시연용으로 다음과 같다.

```text
ID: TUTUS
비밀번호: 0000
```

## 평소 업데이트 받기

```powershell
git pull
.\TEAM_SETUP_WINDOWS.bat
```

코드만 변경되었다면 보통 다시 설치할 필요는 없지만, Python 또는 npm 의존성이 바뀔 수 있으므로 `TEAM_SETUP_WINDOWS.bat`을 한 번 실행하는 것이 안전하다.

## 실행 종료

각 Backend, Frontend, Simulator PowerShell 창에서 `Ctrl + C`를 누른다. 창의 `X`를 눌러도 종료된다.

## 실제 배포 전 확인할 항목

- `backend/.env`에 실제 OpenAI 키, 통화 토큰, 운영 설정을 넣을지 결정
- `TUTUS / 0000` 시연 계정을 실제 관리자 계정 체계로 교체
- MAX17048, 마이크, 스피커, 카메라, UWB 배선 및 ESP32 펌웨어 연결
- 실 장비로 SOS, 통화, 배터리, 통신 두절/재연결 시험
- iOS 네이티브 앱 빌드는 macOS의 Xcode에서 Capacitor 동기화 후 수행
