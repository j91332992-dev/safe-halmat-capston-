# 카메라 전송 개선 실물 결과

## 적용 내용

1. P4 카메라 WebSocket 버퍼 16KB. 기존에는 라이브러리 기본 버퍼 사용.
2. send timeout을 설정 항목으로 분리. 최종 실물 적용 1,500ms.
3. 실패한 JPEG 전송 이후 연결을 stop/start하여 불완전한 프레임이 다음 프레임에 이어지는 것을 방지. 연결 끊김이 10초 이상 지속되면 복구 시도. 호출은 WebSocket 이벤트 콜백이 아니라 별도 sender task에서 실행.
4. 평균 JPEG 크기, 전송 소요시간 및 20회 단위 실패 횟수 로그 추가.
5. 서버 명령으로 timeout 변경, 범위 100~5,000ms. NVS 저장으로 재부팅 후 유지. heartbeat에 실효 timeout과 버퍼 크기 보고.
6. 웹 원본 영상은 500ms 이미지 재요청에서 MJPEG 스트림으로 변경. 서버 메모리의 최신 프레임만 최대 15fps 전송하고 늦은 클라이언트용 프레임 큐는 쌓지 않는다. 상태 표시용 metadata polling은 500ms로 유지.

800×640, JPEG 품질 75, 촬영 목표 15fps, YOLO 기본 입력 640, 분석 상한 4fps 및 음성 우선 정책은 유지했다. 회전 보정은 이번 변경에 포함하지 않았다. 서버 프레임 디스크 저장 제거 및 음성/영상 전송률의 별도 제어는 아직 적용하지 않았다.

## 비교 결과

| 조건 | 서버 수신 FPS | YOLO 완료 FPS | 추론 ms 샘플 중앙값 |
| --- | ---: | ---: | ---: |
| 이전 15fps/640 | 2.57 | 1.98 | 80.1 |
| 16KB·600ms, 명시적 복구 추가 전 | 2.71 | 1.01 | 62.7 |
| 16KB·1,500ms, 복구 추가 후 | 6.93 | 2.90 | 70.95 |
| 같은 복구 코드·16KB·600ms 재비교 | 5.33 | 2.09 | 66.9 |

최종 선택: 16KB·1,500ms·명시적 복구. 기존 측정 대비 수신 약 2.7배. 단, 장면·음성 처리 상태가 완전히 통제된 실험은 아니며 개선을 특정 설정 하나의 효과로 단정하지 않는다.

최종 1,500ms 실험 카운터 구간은 약 36.50초, 직렬 로그 구간 약 35초. 해당 직렬 로그의 20회 단위 TX sample 12개는 모두 failures=0. 평균 전송 102~177ms, JPEG 약 68~69KB. 이 짧은 구간에서 전송 실패가 없었다는 의미이며 장시간 안정성을 보장하지 않는다.

600ms 재비교에서는 연결 끊김 복구 로그가 3회 기록됐다. 복구 처리가 있는 상태에서 전송을 다시 시작할 수 있었다. 마지막 카메라 분석은 person_seen=True였으나 이는 검출 사례 하나이며 정확도 검증 결과는 아니다.

## 검증

- P4 빌드·업로드·해시 검증 완료.
- 프런트엔드 TypeScript/Vite 빌드 성공.
- 실제 웹 img 소스 `/api/camera/helmet-001-av/live/mjpeg`, naturalWidth=800 / naturalHeight=640 확인.
- 최종 timeout 명령 전달 후 heartbeat camera_send_timeout_ms=1500, camera_ws_buffer_bytes=16384 확인.
- 측정 후 서버와 웹을 실행 상태로 유지.

## 설정·인수 방법

Kconfig: HANMIR_CAMERA_WS_BUFFER_BYTES / HANMIR_CAMERA_SEND_TIMEOUT_MS.
새 보드용 sdkconfig.dfr1172.example은 16KB·1,500ms로 설정했다.
실험용 업로드 바이너리는 최초 기본값 600ms로 빌드했고, 이후 명령으로 1,500ms를 NVS에 저장했다. NVS 값이 기본값보다 우선한다. NVS를 지우거나 새 보드에 올릴 때는 example의 1,500ms 설정으로 빌드한다.

명령: POST /api/devices/helmet-001-av/command

```json
{"command_type":"set_camera_timeout","payload":{"send_timeout_ms":1500}}
```

명령 delivered는 전달 여부다. 적용 완료는 `/api/diagnostics/devices`의 component_status.camera_send_timeout_ms로 확인한다. 다른 부품 배선·GPIO 변경은 없다.

## 증거 및 다음 단계

로컬 파일: C:\dev\hanmir-runtime\ws16k-600ms-measurement.json, ws16k-1500ms-recovery-measurement.json, ws16k-600ms-recovery-measurement.json 및 대응 serial.log.

아직 실제 15fps는 달성하지 못했다. 평균 전송 자체가 100~180ms로, 현재 구간에서는 연속 전송 가능한 속도에 한계가 있다. 후속은 동일 장면의 장시간 실험, 32KB 비교, 내장 C6 경로/음성 업로드 동시 부하 측정, JPEG 크기 최적화, 서버 수신 디스크 쓰기 제거 순서로 검토한다. 지금 개선만으로 통신 병목이 전부 해결됐다고 판단하지 않는다.
