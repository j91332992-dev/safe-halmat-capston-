# HANMIR 2.0 음성 준비 상태 (2026-10-02)

## 기준과 목표

사용자가 기억하는 `투투스` 호출 성공률 약 60~70%는 **체감 추정**이다. 반복 측정 원자료가 없어 개선률로 발표하지 않는다. P4 수령 후 동일한 녹음·화자·소음 조건에서 현재 S3/STT 경로와 P4 로컬 감지 경로를 비교한다.

## 지금 구현한 것

| 구간 | 준비 상태 |
|---|---|
| S3 서버 경로 | 유지. STT → 텍스트 호출어/긴급어 판정 |
| P4 로컬 감지 후 서버 | `/api/audio/upload`에 `wake_detected=true` 입력 준비. STT는 명령문만 전사 |
| P4 마이크 실험 | 별도 ESP-IDF 프로젝트에서 I2S INMP441, WebRTC NS, VAD, WakeNet 모델 이벤트 로그, AFE PCM 덤프 준비 |
| 긴급어 | `살려주세요`, `비상상황`, `화재발생` 등 무호출어 서버 경로 유지. `불이야` 추가. 입력 음량 80 미만이라는 이유로 SOS를 취소하던 조건 제거 |
| LLM | 기본 후보 `gpt-6-luna`의 `none` reasoning, 5초 timeout, 재시도 0회. 일반 명령은 기존 규칙 응답을 사용 |
| STT | 기존 `gpt-4o-mini-transcribe`를 비교 기준으로 유지. `gpt-transcribe`와 WAV A/B 도구 준비 |

프로젝트별 실제 `.env`는 설정 기본값보다 우선한다. 두 모델의 실제 한국어 성능·지연시간은 아직 측정하지 않았다.

## API 선택 근거

`gpt-4o-mini-transcribe`는 현재 안내 가격이 약 **$0.003/분**으로 저렴하며 기존의 정상 동작 기준이다. 다만 2027-02-26 종료 예정이므로 `gpt-transcribe`(약 **$0.0045/분**)와 현장 녹음에서 CER, 명령 intent 성공률, 응답 지연 P50/P95를 비교해 전환해야 한다. Live transcription은 현재 발화 단위 WAV 업로드보다 비용이 높고 전송 구조 변경이 커 이번 단계에서 선택하지 않았다. 가격과 모델 종료 일정은 요청 시점의 OpenAI 공식 문서 기준이다.

일반 안전 질문은 고정 응답을 사용한다. 복합 설명에만 쓰는 기본 LLM 후보는 `gpt-6-luna`로 조정했다. 입력/출력 토큰 가격이 `gpt-5.6-sol`보다 낮다. 짧은 응답의 실제 속도와 한국어 답변 품질은 같은 질문 세트로 추후 측정한다.

공식 근거:

- [OpenAI 전사 모델 가격](https://developers.openai.com/api/docs/pricing)
- [OpenAI 전사 모델 종료 일정](https://developers.openai.com/api/docs/deprecations)
- [GPT-6 Luna 모델](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [ESP-SR P4 AFE](https://docs.espressif.com/projects/esp-sr/en/latest/esp32p4/audio_front_end/README.html)

## API A/B 실행

`backend/tools/compare_stt.py`는 API 키가 설정된 경우에만 호출한다. CSV는 `file,reference` 두 열을 갖고 WAV 파일 이름은 CSV 위치를 기준으로 쓴다.

```csv
file,reference
quiet_01.wav,배터리 얼마나 남았어
fan_01.wav,관리자 연결해줘
```

```powershell
$env:OPENAI_API_KEY = "실제키"
python backend/tools/compare_stt.py recordings/manifest.csv --out recordings/stt_result.csv
```

산출 CSV에는 전사문, CER, 요청 지연과 추정 비용이 기록된다. 같은 WAV를 두 모델에 보내므로 STT 모델 비교가 가능하다. `wake_detected` 경로의 실제 호출 성공률은 맞춤 로컬 모델이 준비된 뒤 별도 측정해야 한다. API 키와 원본 음성은 Git에 올리지 않는다.

## 실물 도착 후 합격 기준

1. 최소 화자 5명 이상, 조용한 환경·대화·팬·기계·바람에서 각 조건 100회 이상 호출 성공/미탐을 기록한다.
2. 호출하지 않는 대화와 작업 소음에서 시간당 오인 호출을 기록한다.
3. Wake 감지 시각, 발화 종료, 업로드 완료, STT 완료, 답변 생성, TTS 시작의 P50/P95를 별도로 기록한다.
4. NS 켬/끔의 STT CER와 intent 성공률을 비교한다. 음질 청감만으로 채택하지 않는다.
5. 카메라 및 C6 통신을 켠 상태에서도 오디오 underrun, heap 부족, watchdog reset이 없는지 측정한다.
6. 긴급어는 일반 호출어 없이 동작하는지, 네트워크가 끊겼을 때 로컬 경보·재전송이 가능한지 별도 검증한다.

현재 P4용 한국어 호출어·긴급어 모델은 준비되지 않았다. ESP-SR의 기본 영어/중국어 모델 감지를 실제 `투투스` 또는 SOS 성공으로 취급하지 않는다.
