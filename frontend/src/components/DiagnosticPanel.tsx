import type {Anchor, Device} from "../types";
import {StatusPill} from "./StatusPill";

interface Props {devices: Device[]; anchors: Anchor[]; mode: string}

function time(value: string | null) {
  return value ? new Date(value).toLocaleTimeString("ko-KR") : "수신 없음";
}

export function DiagnosticPanel({devices, anchors, mode}: Props) {
  const tag = devices.find(device => device.device_type === "position_device");
  const missing = anchors.filter(anchor => !anchor.online);
  const anchorMessage = !tag?.online
    ? "UWB 태그가 오프라인이므로 앵커 수신 여부를 확인할 수 없습니다."
    : missing.length
      ? `신호 미수신: ${missing.map(anchor => anchor.name).join(", ")}`
      : `앵커 ${anchors.length}개 신호가 모두 정상 수신 중입니다.`;

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
              <StatusPill
                active={Boolean(tag?.online && anchor.online)}
                activeText="신호 수신"
                inactiveText={tag?.online ? "미수신" : "확인 불가"}
              />
              <small>마지막 신호 {time(anchor.last_seen)}</small>
            </article>
          ))}
        </div>
      </section>

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
    </>
  );
}
