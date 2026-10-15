# DW3000 진단 계산과 측정 식별자

현재 처리·실행 방법은 [인수인계](UWB_HANDOFF_2026-10-15.md)를 따른다.

## 식별자와 시간

- `session_id`: ESP32 MAC + NVS 부팅 카운터 + 128비트 난수 nonce. NVS 초기화/실패에도
  nonce를 사용한다. `cycle_id`는 부팅 내 64비트 증가 카운터다.
- `measurement_id = session_id:cycle_id`. `sequence`는 실제 Poll의 uint8 값을 그대로
  기록한다. 255→0 순환은 새 세션이 아니다. 재부팅은 새 세션이다.
- `tag_hw_id`는 Poll의 TAG_ID, `anchor_hw_id`는 0xA0~0xA3이며 소프트웨어 ID도 함께 기록한다.
- 회차 `measured_uptime_us`는 Poll 준비 시작, 앵커별 값은 RXFCG를 관찰한 직후의
  `esp_timer_get_time()`이다. 32비트 millis 순환에 의존하지 않는다.
- `rx_timestamp_dtu`는 DW3000 수신 하드웨어 40비트 timestamp이다. 회차별 원시 진단에는
  Poll TX 및 앵커 Poll RX/Response TX의 low32 timestamp도 있다. DTU는 MCU uptime/UTC와
  별도 시계이고 약 17.2초마다 순환한다. low32 차이를 사용하는 기존 SS-TWR 산식을 보존한다.
- 현재 UTC 동기화를 하지 않으므로 `measured_at=null`, `time_basis=device_monotonic_us`이다.
  USB의 `bridge_received_at`와 서버의 `server_received_at`은 UTC다. 서버 수신 시각을
  실제 측정 UTC로 대신 쓰지 않는다. 두 호스트 시각도 정확한 무선 수신 시각은 아니다.
- 기존 클라이언트에는 session/측정 시각이 없으므로 null로 남긴다. 기존 serial 줄만으로는
  sequence 순환과 재부팅을 확실하게 구분할 수 없다. bridge의 `capture_id`는 로컬 로그 연결용이고,
  서버에도 `bridge_capture_id`로 전달해 legacy 클라이언트의 로그를 연결한다.

## 진단 획득과 계산 근거

이번에는 **앵커 Response → 태그 수신 방향의 Ipatov**만 수집한다. STS는 OFF다.
앵커의 Poll 진단은 수집하지 않는다. 역방향 품질은 이 로그로 추정하지 않는다.
앵커는 가장 빠르면 2000 UUS 후 delayed Response를 보내므로 추가 SPI 읽기/출력은
예약 실패 위험이 있다. 향후 역방향 수집은 TX 예약 직후/완료 후 읽기의 유효 기간과
delayed TX 실패율을 실측한 뒤 결정해야 한다.

포함 드라이버는 `DW3000 C0 Device Driver Version 04.00.00`이다.
`dwt_configciadiag(DW_CIA_DIAG_LOG_ALL)`로 MINDIAG를 끄고, 단일 RX 버퍼를 사용한다.
다음 RX enable 전에 `dwt_readdiagnostics()`와 DGC/clock 원시값을 복사한다.
최신 API의 `dwt_calculate_rssi`/`dwt_calculate_first_path_power`는 이 라이브러리에 없으므로
직접 계산한다. 수신 경로에서는 로그 출력, HTTP, JSON 구성, log10을 실행하지 않는다.

계산은 [Decawave/Qorvo DW3000 User Manual v1.1 §4.7.1–4.7.2, 레지스터 설명, §8.2.13](https://manuals.plus/m/d7a25b05c0c68d4de68137529f9ece5bd34dbf96c4ca611715e06b86733c0a94.pdf)
(제조사 문서의 공개 미러)와 저장소 드라이버의 비트 마스크를 대조했다.

```
F1, F2, F3 = raw / 4                 # unsigned Q20.2
N = ipatovAccumCount                 # 12-bit accumulated symbols
C = ipatovPower                      # 17-bit channel area
D = (DGC_DBG >> 28) & 7              # register 0x03:60
G = RX_TUNE_EN ? 6*D : 0             # register 0x03:18, bit 0
A = rxCode 1..8 ? 113.8 : 121.7       # Ipatov PRF 16/64 MHz; current code 9
RX_dBm = 10*log10(C*2^21/N^2) + G - A
FP_dBm = 10*log10((F1^2+F2^2+F3^2)/N^2) + G - A
power_difference_db = RX_dBm - FP_dBm
peak_minus_first_path_samples = ((ipatovPeak >> 21) & 1023) - ipatovFpIndex/64
clock_offset_ppm = signed_driver_clock_offset * 10^6 / 2^26
```

first path index는 unsigned Q10.6, peak index는 정수 CIR sample이다. 차이는 부호를 유지한다.
이 값은 경로 인덱스 차이이며 두 노드 간 거리 차이로 해석하지 않는다.
계산 전에 double로 변환해 정수 제곱의 overflow와 fractional truncation을 피한다.
현재 채널 5, preamble code 9, PLEN 128, STS OFF가 raw에 기록된다.
DGC 설정을 변경하거나 외부 LNA별 절대 전력 보정을 새로 추가하지 않는다.

근거 보완:
[Qorvo DW3xxx API Guide §5.4.2–5.4.3 및 §5.4.13](https://forum.qorvo.com/uploads/short-url/xD3TlXKvkujjdUaJWXv2b4E7GQN.pdf)는
진단 수준 설정, 마지막 수신 프레임에 대한 진단/clock 읽기를 설명한다.
[Qorvo의 고정소수점 설명](https://forum.qorvo.com/t/dw3000-rx-timestamp-quality/10453/6)은
F1/F2/F3의 소수 2비트를 확인한다. 전력 추정값은 절대 전력계로 교정한 값이 아니다.

`diagnostics.status`는 `valid`, `missing`, `invalid` 중 하나다.
Response 없음은 `missing/no_response`, CIA 미완료/오류, N=0, C=0, 모든 F=0,
레지스터 한계값, 지원하지 않는 채널/PRF는 `invalid`와 이유를 기록한다.
무효 전력 및 경로 차이는 null이며 원시값은 유지한다. N/C/F 문제만 있는 경우 독립적으로
유효한 clock 값은 남을 수 있다. `valid`는 식을 계산할 수 있다는 뜻이며 LOS/정확한 거리 보장이 아니다.
raw에는 F1/F2/F3/C/N, packed peak, FP index, 전체 DGC 설정/디버그 값, clock,
SYS_STATUS, Ipatov RX status, 타임스탬프, 진단 복사 소요 `capture_us`를 남긴다.
