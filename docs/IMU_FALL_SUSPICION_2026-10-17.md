# BNO085 수집·낙상 의심 감지 초기 구현

기준: `integration/hanmir-final-prd-20261016`, `9519ce6`.
2026-10-17 GitHub fetch에서 최신 커밋과 같음을 확인했다. 업로드된 장치도 이 버전이라는 작업 가정으로 개발한다. 실제 실행 이미지 일치를 측정한 결과는 아니다.

## 이번 범위

P4 펌웨어에서 IMU를 수집하고 낙상 의심 이벤트를 만든다. 감지 계산은 서버·카메라·음성·UWB와 독립적으로 수행하며, 후속 안내·응답·관리자 알림 연결은 [서버·펌웨어 처리 흐름](FALL_RESPONSE_FLOW_2026-10-17.md)에 정리했다.
기존 Rotation Vector 요청 주기 100,000us(10Hz), yaw/pitch/roll 계산 및 공개 API는 유지한다.
음성·STT prompt·WakeNet·NS·카메라·UWB 설정은 변경하지 않는다.
실제 업로드·서버 실행·실물 데이터 수집은 하지 않았다.

## 장착 조건 — 사용자 설명 기준

- 위치: 착용자 머리의 가장 오른쪽 측면.
- 보드 바닥면: 머리 쪽(안쪽)을 향함.
- 보드 위쪽 변: 착용자의 앞통수 쪽을 향함.
- 보드 아래쪽 변: 착용자의 뒤통수 쪽을 향함.
- 센서 칩/보드 실크의 X·Y·Z 방향, 고정 방식과 유격, 머리 회전 중심에서의 거리는 아직 확인하지 않았다.

여기서 위/아래는 보드 외형의 변을 뜻하며 착용자의 수직 방향이나 센서 Y축이라고 가정하지 않는다. 칩 축과 보드 외형 방향의 대응이 확인되기 전에는 몸 기준 축 변환이나 기존 지도 heading 보정값을 바꾸지 않는다.
현재 감지기는 벡터 크기와 기준 중력 방향 대비 기울기를 사용하므로 고정된 축 회전에 대한 별도 변환은 필요하지 않지만, 오른쪽 측면 장착에서 발생하는 회전 가속도·충격 전달·장착 유격의 영향은 그대로 받는다. 이 장착 조건에서 고개 끄덕임·좌우 회전·걷기·쪼그리기·탈착·보호된 헬멧 낙하 데이터를 수집해 임계값을 검증해야 한다.

기존 `9519ce6` 소스는 Rotation Vector로 yaw/pitch/roll을 출력한다. 사용자가 이를 자이로 값이라고 표현하더라도 각속도(rad/s) 원시 출력이 이미 있다고 단정하지 않는다. P4 연결 시 먼저 기존 로그 항목만 확인할 수 있으며, 새 가속도·각속도·ADC 수집에는 수정 펌웨어 적용이 필요하다. 연결 제안 자체를 업로드·설정 변경 승인으로 취급하지 않는다.

## 수집

`HANMIR_ENABLE_BNO_SH2`가 활성화된 빌드에서 `HANMIR_IMU_CAPTURE` 기본값은 ON이다. 이 옵션을 끄면 기존 방향 보고만 요청한다.

| SH-2 ID | 보고 | 요청 주기 | 단위 |
|---|---|---|---|
| 1 | Accelerometer | 20,000us / 50Hz | m/s², 중력 포함 |
| 2 | Gyroscope calibrated | 20,000us / 50Hz | rad/s |
| 5 | Rotation Vector | 기존 100,000us / 10Hz | quaternion xyzw |
| 20 | Raw accelerometer | 20,000us / 50Hz | ADC counts |
| 21 | Raw gyroscope | 20,000us / 50Hz | ADC counts, 온도 ADC 포함 |

진짜 원시 ADC와 SI 단위 보고를 구분한다. 감지에는 SI 보고와 quaternion만 사용한다. 원시 ADC 보고는 `HANMIR_IMU_RAW_ADC`로 별도 제어한다(기본 ON). ADC에서 g 또는 rad/s로 임의 변환하지 않는다.

기존 저장소의 Hillcrest SH-2 드라이버를 그대로 활용했다. [제조사 SH-2 소스](https://github.com/ceva-dsp/sh2/blob/main/sh2_SensorValue.h), [SH-2 설명서](https://www.ceva-ip.com/wp-content/uploads/2019/10/SH-2-Reference-Manual.pdf)의 보고 형식·단위를 참고했다. 손목·허리용 오픈소스 감지 모델이나 검증되지 않은 가중치는 가져오지 않았다. 감지기는 아래의 명시적 상태 기계로 직접 구현했다.

센서 콜백은 128개 고정 길이 큐에 대기 없이 기록을 넣고, 낮은 우선순위 태스크가 `IMU1` 행을 출력한다. 큐가 차면 기록만 버리고 `IMU_LOG_DROPPED total=...`을 남긴다. 감지는 기록 큐와 별도로 진행한다. 다만 콘솔 출력의 전체 시스템 부하는 실기 검증 대상이다. 기본값은 최대 약 210보고/초이며, UART 115200 콘솔에서는 대역폭이 부족할 수 있다. 기존 검증 설정은 USB Serial/JTAG다. 실측 보고 주기·시퀀스 누락·큐 폐기를 반드시 확인한다. 요청 주기는 실제 달성 주기를 보장하지 않는다.

형식:

```text
IMU1,received_us,sensor_us,sensor_id,sequence,status,x,y,z,w_or_temperature,raw_us
```

- `received_us`: P4 콜백 도착 시각(부팅 기준 단조 증가).
- `sensor_us`: SH-2가 재구성한 보고 시각. UTC가 아니며 raw clock과 같은 값으로 가정하지 않는다.
- `raw_us`: 원시 ADC 보고 내부 32비트 센서 시각. 다른 보고에서는 0.
- `sequence`: 보고 종류별 8비트 번호. 종류별로 modulo 256 차이를 비교한다.
- `status`: SH-2 정확도 0~3. 원시 ADC의 상태를 SI 보고의 정확도와 동일하게 해석하지 않는다.
- quaternion에서 roll/pitch를 도출할 수 있으며 기존 1Hz 방향 로그도 보존한다.
- 센서 재설정 시 감지 증거를 초기화하고 보고 요청을 다시 설정한다. 실패한 보고가 다른 보고 설정을 영구적으로 막지 않도록 순환 재시도한다.

PC 파일 저장 예시(서버·토큰 불필요):

```powershell
python scripts/capture_p4_imu.py --input monitor.txt --output walking.csv --label walking --mount "right side; underside inward; board top edge forward; bottom edge backward; sensor xyz unverified"
python scripts/capture_p4_imu.py --port COM5 --output helmet-drop.csv --label helmet_drop --mount "right side; underside inward; board top edge forward; bottom edge backward; sensor xyz unverified"
```

직접 COM 수집은 선택 의존성 `pyserial`이 필요하다. 기존 모니터와 같은 포트를 동시에 열지 않는다. 스크립트는 DTR/RTS를 낮게 열지만 USB 드라이버에 따라 포트 열기가 장치에 영향을 줄 수 있으므로 기존 monitor 로그 추출을 먼저 사용할 수 있다.
CSV, `.metadata.json`, `.monitor.log`를 새 파일로 보관한다. 같은 파일을 덮어쓰지 않는다. monitor 원본에는 감지 이벤트·리셋·누락 경고도 유지된다. 메타데이터의 활동 이름은 구간 전체 라벨이며 실제 이벤트 정답 시각은 별도 기록해야 한다.

## 검증용 낙상 의심 감지기

`main/fall_detector.c`는 ESP-IDF와 독립된 C 코드다. 50Hz 가속도 보고가 기준 입력이고 최근 각속도와 기존 10Hz quaternion을 연결한다. quaternion의 중력 방향 차이로 기울기 변화를 구하므로 단순 yaw 회전은 자세 변화로 세지 않는다.

초기 값은 데이터로 선정한 운영 임계값이 아니다. `fall_default_config()`에서 확인·변경할 수 있다.

1. 연속 유효 입력으로 1초 준비하고, 충격 전의 기준 중력 방향을 저속 추적한다.
2. 가속도 크기 2.5g 이상이면 후보를 만들고 그 시점의 기준 자세를 고정한다.
3. 충격 전 0.5초 또는 후보 구간에 각속도 크기 2rad/s 이상이 있어야 한다.
4. 충격 후 3초 안에 기준 대비 기울기 변화 45° 이상이며, 각속도 0.6rad/s 이하·가속도 0.8~1.2g가 연속 0.6초 유지되면 낙상 의심으로 출력한다. 충격 직후 최소 0.2초를 확보한다.
5. 0.5g 미만 구간이 충격 전 1초 안에 있었는지도 부가 증거로 남긴다. 낮은 g는 필수가 아니다.
6. 같은 움직임의 반복 출력을 줄이는 10초 쿨다운을 둔다. 이는 착용자 응답 대기시간이나 사건 해제 판정이 아니다.

각속도 16개·자세 4개 시간 정렬 버퍼에서 가속도 측정 시각보다 늦지 않은 최신 보고를 선택한다. 따라서 묶음 보고에서 미래 시각의 각속도가 먼저 도착해도 이전 유효 보고를 사용할 수 있다. 정확도 status=0, NaN/비정상 quaternion, 역순·중복 가속도 시각, 가속도 보고 공백 100ms 초과, 각속도·자세 보고 나이 200ms 초과 또는 해당 시각의 보조 보고가 없으면 증거를 버리고 다시 준비한다. 센서 오류를 안전 상태로 판정하지 않는다. 실제 보고 지연이 버퍼 범위를 넘는 경우도 실기 수집에서 확인해야 한다.

감지 시 `FALL_SUSPECTED` 로그에 부팅 내 사건 번호·시각·피크·기울기를 출력한다. `hanmir_imu_last_fall()`은 최근 사건과 누적 횟수를 반환한다. 최근 사건은 RAM에만 있고 전체 이력은 PC monitor 원본에 남긴다. 전원 차단 후 장치 내부 영속 보관은 구현하지 않았다.

낮은 충격, 자세 변화 없는 낙상, 낙상 후 계속 움직이는 경우는 놓칠 수 있다. 합성 데이터의 통과는 헬멧에서의 검출률·오탐률을 의미하지 않는다. 탈착·헬멧 낙하도 같은 조건을 만들 수 있으며 착용 여부를 판단하지 않는다.

## 네트워크 없이 수집할 때

기존 정상 설정을 복사·덮어쓰지 않는다. 별도 검증 빌드에서 ESP-IDF 5.5.5를 사용하고 `menuconfig`에서 확인된 BNO085 RX/TX, SH-2, IMU capture를 설정한다. 선택 옵션 `HANMIR_IMU_STANDALONE=y`는 센서 초기화 후 네트워크·카메라·음성 태스크 시작을 생략한다. 기본값 OFF여서 기존 통합 시작 순서는 유지한다. 전체 프로젝트 의존성은 기존대로 필요하며, 이 모드는 독립 최소 프로젝트가 아니다. 코드 작성만으로 현재 올라간 펌웨어에 수집 기능이 추가되지는 않는다. 추후 별도로 승인된 실기 시험 때 빌드·업로드해야 한다.

## 호스트 검증과 재생

C11 컴파일러로 P4와 동일한 감지기를 실행한다. 예시는 저장소 루트 기준이다.

```powershell
zig cc -std=c11 -Wall -Wextra -Werror -Ifirmware/helmet_p4/main firmware/helmet_p4/main/fall_detector.c firmware/helmet_p4/test/test_fall_detector.c -o test_fall.exe
.\test_fall.exe
zig cc -std=c11 -Wall -Wextra -Werror -Ifirmware/helmet_p4/main firmware/helmet_p4/main/fall_detector.c firmware/helmet_p4/test/replay_imu.c -o replay_imu.exe
.\replay_imu.exe walking.csv
$env:HANMIR_IMU_REPLAY_EXE = (Resolve-Path .\replay_imu.exe).Path
python -m unittest discover -s firmware/helmet_p4/test -p "test_*.py"
```

재생기는 추출 CSV의 도착 순서대로 동일 감지기를 구동한다. 입력 파일에서 `received_us`가 감소하면 재부팅으로 취급하고 캐시를 초기화한다. 실제 센서 리셋 정보는 monitor 원본과 함께 대조한다. PC 기록 큐에서 누락된 표본이 있으면 재생 결과와 장치 감지가 다를 수 있다.

이번 호스트 검증: Zig C11 `-Wall -Wextra -Werror`로 감지기·재생기를 컴파일하고 C 시나리오 검증을 통과했다. 정지·충격 없는 자세 변화·자세 변화 없는 충격·회전 없는 충격·저가속도 유무의 낙상 후보·중복 억제·시간 공백·오래된 보고·불량 상태·NaN·비정상 quaternion·계속 움직이는 후보·순서가 엇갈린 보고 선택·50Hz/10Hz 조합을 확인했다. Python 3개 시험은 monitor 추출/증거 보존과 CSV→실제 C 재생기의 의심 1건/0건을 확인한다. ESP-IDF P4 전체 빌드, 센서 실제 요청 수락·샘플링 속도·드라이버 버퍼·CPU·힙·기존 방향/음성 회귀는 아직 검증하지 않았다.

실기 비교 데이터는 고개 숙이기, 걷기, 쪼그려 앉기, 헬멧 탈착, 보호된 시험 지그에서의 헬멧 낙하를 각각 수집한다. 부착 위치·축·실제 펌웨어 식별값·정답 구간·센서 주기/시퀀스/상태·큐 폐기와 오탐/미탐/지연을 기록한다. 사람의 실제 낙상을 요구하지 않는다. 서로 다른 반복·사람을 조정용과 평가용으로 분리한다.

## 연결 구현과 남은 검증

후속 작업에서 서버 사건 저장·관리자 최초 알림·동일 사건 갱신·착용자 TTS·호출어 없는 응답 경로·재생 종료 후 8초·긴급/의심 해제 이력을 연결했다. 기존 `fallen/man_down` 분기는 유지하며 별도 낙상 의심 상태로 처리한다. 사용자의 추가 지시에 따라 통화 중 새 감지 이벤트는 안내·관리자 알림 없이 무시하고 원시 IMU 기록은 유지한다. 카메라와 UWB는 낙상 판정·응답 확인에서 사용하지 않는다. 실제 P4 빌드·청취·현장 종합 검증은 남아 있다.
