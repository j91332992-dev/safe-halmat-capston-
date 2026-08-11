import {useEffect, useRef, useState} from "react";
import {api} from "../services/api";
import type {Device, EvacuationIncident, FireZone, Obstacle, Worker} from "../types";

interface Props {
  incident: EvacuationIncident;
  site: {width: number; height: number};
  obstacles: Obstacle[];
  workers: Worker[];
  devices: Device[];
  onRefresh: () => Promise<unknown>;
}

const sourceLabel: Record<string, string> = {
  voice: "작업자 음성 신고",
  yolo: "YOLO 카메라 감지",
  manager: "관리자 수동 신고"
};

export function FireEvacuationModal({incident, site, obstacles, workers, devices, onRefresh}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragStart = useRef<{x: number; y: number} | null>(null);
  const [zone, setZone] = useState<FireZone>(() => ({
    name: "관리자 지정 화재구역",
    x: Math.max(0, site.width / 2 - 0.75),
    y: Math.max(0, site.height / 2 - 0.75),
    width: Math.min(1.5, site.width),
    height: Math.min(1.5, site.height)
  }));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("지도에서 화재구간을 드래그하거나 아래 수치를 입력하세요.");
  const [cameraVersion, setCameraVersion] = useState(Date.now());
  const reporter = workers.find(worker => worker.worker_id === incident.worker_id);
  const cameraDevice = devices.find(device => device.worker_id === incident.worker_id && device.device_type === "assistant_device");

  useEffect(() => {
    if (incident.fire_zone && Object.keys(incident.fire_zone).length) setZone(incident.fire_zone);
  }, [incident.incident_id, incident.fire_zone]);

  useEffect(() => {
    if (!cameraDevice?.device_id) return;
    const timer = window.setInterval(() => setCameraVersion(Date.now()), 500);
    return () => window.clearInterval(timer);
  }, [cameraDevice?.device_id]);

  const point = (event: React.PointerEvent<SVGSVGElement>) => {
    const rect = svgRef.current!.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(site.width, ((event.clientX - rect.left) / rect.width) * site.width)),
      y: Math.max(0, Math.min(site.height, (1 - (event.clientY - rect.top) / rect.height) * site.height))
    };
  };
  const sx = (x: number) => (x / site.width) * 800;
  const sy = (y: number) => 500 - (y / site.height) * 500;

  const startDrag = (event: React.PointerEvent<SVGSVGElement>) => {
    dragStart.current = point(event);
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const moveDrag = (event: React.PointerEvent<SVGSVGElement>) => {
    const start = dragStart.current;
    if (!start) return;
    const current = point(event);
    setZone(currentZone => ({
      name: currentZone.name,
      x: Math.min(start.x, current.x),
      y: Math.min(start.y, current.y),
      width: Math.max(0.2, Math.abs(current.x - start.x)),
      height: Math.max(0.2, Math.abs(current.y - start.y))
    }));
  };
  const endDrag = () => { dragStart.current = null; };
  const update = (key: "x" | "y" | "width" | "height", value: number) => {
    const next = {...zone, [key]: Math.max(0, value)};
    next.width = Math.min(Math.max(0.2, next.width), site.width);
    next.height = Math.min(Math.max(0.2, next.height), site.height);
    next.x = Math.min(next.x, site.width - next.width);
    next.y = Math.min(next.y, site.height - next.height);
    setZone(next);
  };
  const run = async (action: () => Promise<unknown>, success: string) => {
    setBusy(true);
    try {
      await action();
      setMessage(success);
      await onRefresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "처리에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="fire-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="fire-modal-title">
      <section className="fire-modal">
        <header>
          <div className="fire-pulse">!</div>
          <div>
            <span className="eyebrow">FIRE ALERT CONTROL</span>
            <h2 id="fire-modal-title">화재 감지 — 관리자 확인 필요</h2>
            <p>{sourceLabel[incident.source] ?? incident.source}{reporter ? " · " + reporter.worker_name : ""}</p>
          </div>
        </header>
        <div className="fire-default-route-notice">
          <b>현재 즉시 대피 안내 중</b>
          <span>화재 위치를 확인하는 동안에도 가장 가까운 비상구 거리와 비상 유도등을 따라 즉시 대피하라는 안내를 전송합니다.</span>
        </div>
        <section className="fire-camera-evidence">
          <header><div><span className="eyebrow">LIVE HELMET CAMERA</span><h3>화재 발생 카메라 영상</h3></div><b>{cameraDevice?.online ? "실시간 수신" : "카메라 오프라인"}</b></header>
          {cameraDevice?.last_camera_at
            ? <img src={api.cameraImageUrl(cameraDevice.device_id, cameraVersion)} alt="화재 발생 안전모 최신 카메라 영상" />
            : <div className="fire-camera-placeholder">수신된 안전모 카메라 영상이 없습니다.</div>}
        </section>
        <div className="fire-modal-grid">
          <div>
            <svg ref={svgRef} className="fire-zone-picker" viewBox="0 0 800 500" onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag}>
              <defs><pattern id="fire-grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="rgba(115,215,255,.12)" /></pattern></defs>
              <rect width="800" height="500" className="fire-map-floor" />
              <rect width="800" height="500" fill="url(#fire-grid)" />
              {obstacles.map(item => (
                <g key={item.obstacle_id} className={"fire-object " + (item.object_type ?? "obstacle")}>
                  <rect x={sx(item.x)} y={sy(item.y + item.height)} width={sx(item.width)} height={(item.height / site.height) * 500} />
                  <text x={sx(item.x + item.width / 2)} y={sy(item.y + item.height / 2)} textAnchor="middle" dominantBaseline="middle">{item.name}</text>
                </g>
              ))}
              {workers.map(worker => (
                <g key={worker.worker_id} transform={"translate(" + sx(worker.x) + "," + sy(worker.y) + ")"} className="fire-worker">
                  <circle r="10" /><text x="14" y="4">{worker.worker_name}</text>
                </g>
              ))}
              <g className="selected-fire-zone">
                <rect x={sx(zone.x)} y={sy(zone.y + zone.height)} width={sx(zone.width)} height={(zone.height / site.height) * 500} />
                <text x={sx(zone.x + zone.width / 2)} y={sy(zone.y + zone.height / 2)} textAnchor="middle" dominantBaseline="middle">화재구간</text>
              </g>
            </svg>
            <small className="fire-map-help">마우스로 화재 발생 영역의 한쪽 끝에서 반대쪽 끝까지 드래그하세요.</small>
          </div>
          <aside className="fire-zone-form">
            <h3>화재 발생 위치</h3>
            <label>위치 이름<input type="text" maxLength={80} value={zone.name} onChange={event => setZone(current => ({...current, name: event.target.value}))} placeholder="예: 용접 작업 구역" /></label>
            <div><label>X (m)<input type="number" step=".1" value={zone.x.toFixed(2)} onChange={event => update("x", Number(event.target.value))} /></label><label>Y (m)<input type="number" step=".1" value={zone.y.toFixed(2)} onChange={event => update("y", Number(event.target.value))} /></label></div>
            <div><label>가로 (m)<input type="number" min=".2" step=".1" value={zone.width.toFixed(2)} onChange={event => update("width", Number(event.target.value))} /></label><label>세로 (m)<input type="number" min=".2" step=".1" value={zone.height.toFixed(2)} onChange={event => update("height", Number(event.target.value))} /></label></div>
            <p>{message}</p>
            <button className="confirm-fire-zone" disabled={busy} onClick={() => void run(() => api.confirmFireZone(incident.incident_id, zone), "화재 위치와 비상구 거리를 안전모로 전송했습니다.")}>화재 위치 확정 · 안전모 알림 전송</button>
            <div className="false-alarm-actions">
              <button disabled={busy} onClick={() => void run(() => api.cancelFire(incident.incident_id, "false_alarm"), "오판단으로 취소했습니다.")}>오판단으로 취소</button>
              <button disabled={busy} onClick={() => void run(() => api.cancelFire(incident.incident_id, "no_fire"), "화재 없음으로 처리했습니다.")}>화재 없음</button>
            </div>
          </aside>
        </div>
      </section>
    </div>
  );
}

