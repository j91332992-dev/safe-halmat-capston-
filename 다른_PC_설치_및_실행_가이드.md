# 다른 Windows PC 설치 및 실행 가이드

이 문서는 새 컴퓨터에서 저장소를 내려받아 웹 서버, YOLO, ESP32-S3 안전모를 동일하게 실행하기 위한 최소 절차입니다.

## 1. 준비 프로그램

- Git for Windows
- Python 3.12 64-bit
- Node.js 20 이상
- ESP32-S3 펌웨어를 올릴 경우 USB 데이터 케이블과 장치의 COM 번호

프로젝트 경로에는 한글과 공백이 있어도 되지만, 도구 호환성을 위해 가능하면 `C:\projects\safe-halmat-capston-`처럼 짧은 영문 경로를 권장합니다.

## 2. 저장소 내려받기

```bat
cd /d C:\projects
git clone https://github.com/j91332992-dev/safe-halmat-capston-.git
cd safe-halmat-capston-
```

## 3. 서버와 웹 설치

```bat
install_windows.bat
install_ai_windows.bat
copy backend\.env.example backend\.env
```

`install_windows.bat`은 Python 가상환경과 웹 패키지를 설치합니다. `install_ai_windows.bat`은 실제 `best.pt` YOLO 실행에 필요한 OpenCV·Ultralytics를 설치합니다. `backend\best.pt`는 저장소에 포함돼 있습니다.

OpenAI 음성인식을 사용한다면 `backend\.env`의 아래 항목에 개인 키를 입력합니다. 키가 없는 상태로 Git에 커밋하지 마세요.

```env
OPENAI_API_KEY=개인_API_키
```

## 4. 서버 PC 주소와 안전모 설정

안전모와 서버 PC를 같은 Wi-Fi에 연결합니다. 서버 PC에서 `ipconfig`를 실행해 Wi-Fi의 IPv4 주소를 확인한 뒤 다음 명령을 실행합니다.

```bat
.\.venv\Scripts\python.exe configure_av_device.py
```

질문에 다음 값을 입력합니다.

- Wi-Fi SSID
- Wi-Fi 비밀번호
- 서버 PC IPv4 주소(예: `192.168.0.49`)

이 명령은 다음 두 로컬 파일을 만듭니다.

- `firmware\helmet_av_device\include\device_secrets.h`
- `backend\.env`의 `CALL_DEVICE_TOKEN`

두 파일에는 비밀번호나 인증값이 있으므로 `.gitignore`로 제외되며 다른 PC에서는 다시 생성해야 합니다.

Windows 방화벽이 묻는 경우 Python과 Node.js의 사설 네트워크 접근을 허용합니다. 같은 Wi-Fi의 안전모가 서버의 TCP 8000 포트에 접근할 수 있어야 합니다.

## 5. ESP32-S3 펌웨어 업로드

처음 한 번 PlatformIO를 설치합니다.

```bat
.\.venv\Scripts\python.exe -m pip install platformio
```

ESP32-S3를 USB로 연결하고 장치 관리자에서 COM 번호를 확인합니다. 아래 `COM13`은 실제 번호로 바꿉니다.

```bat
cd firmware\helmet_av_device
..\..\.venv\Scripts\python.exe -m platformio run --target upload --upload-port COM13
cd ..\..
```

업로드가 끝난 후 안전모 자체 전원을 사용할 경우 USB 케이블을 분리해도 됩니다.

## 6. 서버와 웹 실행

```bat
run_integrated_hardware.bat
```

정상 실행 주소:

- 관리자 웹: `http://localhost:5173`
- 백엔드 API 문서: `http://localhost:8000/docs`
- 같은 Wi-Fi의 다른 기기: `http://서버_PC_IP:5173`

백엔드와 프런트엔드 명령창은 사용하는 동안 닫지 않습니다.

UWB TAG가 별도 COM 포트로 연결돼 있다면 새 명령창에서 실행합니다. `COM18`은 실제 번호로 바꿉니다.

```bat
run_hardware_map.bat COM18
```

## 7. 개발 전 검증

```bat
cd backend
..\.venv\Scripts\python.exe -m pytest
cd ..\frontend
npm.cmd run build
cd ..
```

## 8. 새 PC에서 꼭 다시 확인할 항목

- `backend\.env`가 존재하는지
- `OPENAI_API_KEY`가 필요한 환경이면 입력됐는지
- `device_secrets.h`의 Wi-Fi와 서버 IP가 새 장소에 맞는지
- Windows 방화벽에서 8000·5173 포트 통신이 가능한지
- ESP32와 서버 PC가 같은 네트워크인지
- 현재 COM 번호가 명령의 번호와 일치하는지
- `http://127.0.0.1:8000/api/camera/processor/status`에서 카메라 분석 작업이 실행 중인지

## 9. Git에 올리지 않는 로컬 파일

- `backend\.env`
- `firmware\helmet_av_device\include\device_secrets.h`
- `.venv`, `node_modules`, `.pio`
- SQLite DB와 캡처·음성·TTS 결과
- 생성된 YOLO 테스트 이미지

이 파일들은 새 PC마다 설치 또는 생성해야 하며 저장소에 push하지 않습니다.
