import {useState} from "react";
import {api} from "../services/api";
import type {Anchor, Device} from "../types";
import {StatusPill} from "./StatusPill";

interface Props {devices: Device[]; anchors: Anchor[]; mode: string; onRefresh: () => Promise<unknown>}

function time(value: string | null) {
  return value ? new Date(value).toLocaleTimeString("ko-KR") : "수신 없음";
}

function recent(value: string | null, seconds: number) {
  return Boolean(value && Date.now() - new Date(value).getTime() <= seconds * 1000);
}

export function DiagnosticPanel({devices, anchors, mode, onRefresh}: Props) {
  const [testing, setTesting] = useState<string | null>(null);
  const tag = devices.find(device => device.device_type === "position_device");
  const missing = anchors.filter(anchor => !anchor.online);
  const anchorMessage = !tag?.online
    ? "UWB 태그가 오프라인이므로 앵커 수신 여부를 확인할 수 없습니다."
    : missing.length
      ? `신호 미수신: ${missing.map(anchor => anchor.name).join(", ")}`
      : `앵커 ${anchors.length}개 신호가 모두 정상 수신 중입니다.`;

  const speakerTest = async (deviceId: string) => {
    setTesting(deviceId);
    try {
      await api.speakerTest(deviceId);
      await new Promise(resolve => window.setTimeout(resolve, 700));
      await onRefresh();
    } finally {
      setTesting(null);
    }
  };

  return (
    <>
      <section className={`anchor-diagnostic-summary ${!tag?.online ? "unknown" : missing.length ? "warning" : "healthy"}`}>
        <header>
          <div><span className="eyebrow">UWB ANCHOR RECEPTION</span><h3>앵커 수신 상태</h3></div>
          <b>{anchorMessage}</b>
        </header>
        <div className="anchor-status-grid">
          {anchors.map((anchor, index) => (
            <article key={anchor.anchor_id} className={anchor.online ? "online" : "offline"}>
              <div><strong>A{index + 1}</strong><span>{anchor.name}</span></div>
              <StatusPill active={Boolean(tag?.online && anchor.online)} activeText="신호 수신" inactiveText={tag?.online ? "미수신" : "확인 불가"} />
              <small>마지막 신호 {time(anchor.last_seen)}</small>
            </article>
          ))}
        </div>
      </section>

      <div className="diagnostic-grid">
        {devices.map(device => {
          const isAv = device.device_type === "assistant_device";
          const cameraActive = device.online && recent(device.last_camera_at, 20);
          const micActive = device.online && recent(device.last_audio_at, 300);
          const speakerActive = device.online && recent(device.last_speaker_at, 300) && device.last_speaker_status?.startsWith("ok:");
          return <article className="diag-card" key={device.device_id}>
            <header>
              <div><span className="eyebrow">{isAv ? "AV CONTROLLER" : "POSITION TAG"}</span><h3>{device.device_id}</h3></div>
              <StatusPill active={device.online} activeText="ONLINE" inactiveText="OFFLINE" />
            </header>
            <div className="diag-metrics diag-metrics-no-battery">
              <div><span>Wi-Fi RSSI</span><strong>{device.online ? `${device.rssi ?? "-"} dBm` : "확인 불가"}</strong></div>
              <div><span>마지막 heartbeat</span><strong>{time(device.last_seen)}</strong></div>
              <div><span>서버 모드</span><strong>{mode.toUpperCase()}</strong></div>
            </div>
            {isAv && <>
              <div className="component-list verified-components">
                <div><span>CAMERA</span><StatusPill active={cameraActive} activeText="프레임 수신 중" inactiveText={device.online ? "신호 없음" : "확인 불가"} /></div>
                <div><span>MIC</span><StatusPill active={micActive} activeText="음성 수신 확인" inactiveText={device.online ? "검증 필요" : "확인 불가"} /></div>
                <div><span>SPEAKER</span><StatusPill active={Boolean(speakerActive)} activeText="재생 확인" inactiveText={device.online ? "테스트 필요" : "확인 불가"} /></div>
              </div>
              <button className="speaker-test-button" disabled={!device.online || testing === device.device_id} onClick={() => void speakerTest(device.device_id)}>
                {testing === device.device_id ? "재생 결과 확인 중…" : "스피커 실제 재생 테스트"}
              </button>
              <footer>
                <span>카메라 실제 수신 {time(device.last_camera_at)}</span>
                <span>마이크 실제 수신 {time(device.last_audio_at)}</span>
                <span>스피커 재생 응답 {time(device.last_speaker_at)}</span>
              </footer>
            </>}
            {!isAv && <footer><span>UWB 실제 수신 {time(device.last_uwb_at)}</span></footer>}
            {device.last_error && <p className="error-box">{device.last_error}</p>}
          </article>;
        })}
      </div>
    </>
  );
}
