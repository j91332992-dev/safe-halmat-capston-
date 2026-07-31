import type {Device} from "../types";
import {StatusPill} from "./StatusPill";

interface Props {devices: Device[]; mode: string}

function time(value: string | null) {
  return value ? new Date(value).toLocaleTimeString("ko-KR") : "수신 없음";
}

export function DiagnosticPanel({devices, mode}: Props) {
  return (
    <div className="diagnostic-grid">
      {devices.map(device => (
        <article className="diag-card" key={device.device_id}>
          <header>
            <div>
              <span className="eyebrow">{device.device_type === "assistant_device" ? "AV CONTROLLER" : "POSITION TAG"}</span>
              <h3>{device.device_id}</h3>
            </div>
            <StatusPill active={device.online} activeText="ONLINE" inactiveText="OFFLINE" />
          </header>
          <div className="diag-metrics">
            <div><span>Wi-Fi RSSI</span><strong>{device.rssi ?? "-"} dBm</strong></div>
            <div><span>배터리</span><strong>{device.battery != null ? `${Math.round(device.battery)}%` : "-"}</strong></div>
            <div><span>마지막 heartbeat</span><strong>{time(device.last_seen)}</strong></div>
            <div><span>서버 모드</span><strong>{mode.toUpperCase()}</strong></div>
          </div>
          <div className="component-list">
            {Object.entries(device.component_status).map(([name, status]) => (
              <div key={name}><span>{name.toUpperCase()}</span><StatusPill active={status === "ready" || status === "ok"} activeText={status} inactiveText={status} /></div>
            ))}
          </div>
          <footer>
            <span>카메라 {time(device.last_camera_at)}</span>
            <span>음성 {time(device.last_audio_at)}</span>
            <span>버튼 {time(device.last_button_at)}</span>
            <span>UWB {time(device.last_uwb_at)}</span>
          </footer>
          {device.last_error && <p className="error-box">{device.last_error}</p>}
        </article>
      ))}
    </div>
  );
}

