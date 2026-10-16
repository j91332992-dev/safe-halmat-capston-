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
