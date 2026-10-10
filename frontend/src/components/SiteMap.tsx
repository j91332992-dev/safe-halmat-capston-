import {useEffect, useMemo, useRef, useState} from "react";
import type {Anchor, Device, EvacuationRoute, FireZone, LocationPoint, Obstacle, Worker, Zone} from "../types";
import {api} from "../services/api";
import {AnchorSymbol} from "./AnchorSymbol";

interface Props {
  width: number;
  height: number;
  anchors: Anchor[];
  obstacles: Obstacle[];
  zones: Zone[];
  workers: Worker[];
  devices: Device[];
  history: LocationPoint[];
  lastLocationAt: string | null;
  selectedId?: string;
  evacuationRoute?: EvacuationRoute;
  fireZone?: FireZone | null;
  onSelect: (worker: Worker) => void;
}

const riskColor: Record<string, string> = {
  정상: "#37d49f",
  관심: "#73d7ff",
  주의: "#ffc857",
  위험: "#ff8a47",
  비상: "#ff4d65"
};

function timestamp(value: string | null) {
  if (!value) return 0;
  const normalized = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : value + "Z";
  return new Date(normalized).getTime();
}

function HeadingArrow({angle, label}: {angle: number; label: string}) {
  const [display, setDisplay] = useState(angle);
  const current = useRef(angle);
  useEffect(() => {
    const start = current.current;
    const delta = (((angle - start + 180) % 360 + 360) % 360) - 180;
    const began = performance.now();
    let frame = 0;
    const animate = (now: number) => {
      const progress = Math.min(1, (now - began) / 80);
      current.current = start + delta * progress;
      setDisplay(current.current);
      if (progress < 1) frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [angle]);
  return <g transform={`rotate(${display})`} className="worker-heading">
    <title>{label}</title>
    <path d="M 0 0 L 82 -30 A 87 87 0 0 1 82 30 Z" fill="#38bdf8" opacity=".18" />
    <path d="M 28 0 L 68 0 M 55 -12 L 68 0 L 55 12" fill="none" stroke="#0284c7" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
  </g>;
}

export function SiteMap({width, height, anchors, obstacles, zones, workers, devices, history, lastLocationAt, selectedId, evacuationRoute, fireZone, onSelect}: Props) {
  const scaleX = (x: number) => 50 + (x / width) * 900;
  const scaleY = (y: number) => 560 - (y / height) * 520;
  const [showTrail, setShowTrail] = useState(true);
  const [trailWindow, setTrailWindow] = useState<"60" | "300" | "all">("300");
  const [now, setNow] = useState(Date.now());
  const [calibrating, setCalibrating] = useState(false);
  const [calibrationMessage, setCalibrationMessage] = useState("");
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const selectedWorker = workers.find(worker => worker.worker_id === selectedId) ?? workers[0];
  const headingDevice = (worker: Worker) => devices.find(device => device.worker_id === worker.worker_id && device.device_type === "assistant_device");
  const freshHeading = (device?: Device) => device?.online && device.heading_deg != null && Number.isFinite(device.heading_deg)
    && timestamp(device.heading_at ?? null) > 0 && now - timestamp(device.heading_at ?? null) < (device.component_status?.heading_transport === "websocket" ? 3000 : 15000);
  const selectedDevice = selectedWorker ? headingDevice(selectedWorker) : undefined;
  const calibrate = async () => {
    if (!selectedDevice) return;
    setCalibrating(true);
    try {
      await api.calibrateHeading(selectedDevice.device_id);
      setCalibrationMessage("앵커 1·4 벽면을 바라보는 방향으로 보정했습니다.");
    } catch (error) {
      setCalibrationMessage(error instanceof Error ? error.message : "방향 보정 실패");
    } finally { setCalibrating(false); }
  };
  const receivedAt = timestamp(lastLocationAt);
  const ageMs = receivedAt ? Math.max(0, now - receivedAt) : Number.POSITIVE_INFINITY;
  const offline = ageMs > 20000;
  const ageLabel = !Number.isFinite(ageMs) ? "수신 기록 없음" : ageMs < 2000 ? "방금 전" : ageMs < 60000 ? Math.floor(ageMs / 1000) + "초 전" : Math.floor(ageMs / 60000) + "분 전";
  const dangerZone = selectedWorker ? zones.find(zone => {
    if (!zone.active || zone.zone_type !== "rectangle") return false;
    const {x, y, width: w = 0, height: h = 0} = zone.coordinates;
    return selectedWorker.x >= x && selectedWorker.x <= x + w && selectedWorker.y >= y && selectedWorker.y <= y + h;
  }) : undefined;
  const trail = useMemo(() => {
    const cutoff = trailWindow === "all" ? 0 : now - Number(trailWindow) * 1000;
    const ordered = history.filter(point => timestamp(point.created_at) >= cutoff).sort((a, b) => timestamp(a.created_at) - timestamp(b.created_at));
    if (ordered.length <= 160) return ordered;
    const step = Math.ceil(ordered.length / 160);
    return ordered.filter((_, index) => index % step === 0 || index === ordered.length - 1);
  }, [history, now, trailWindow]);
  const trailPoints = trail.map(point => scaleX(point.x) + "," + scaleY(point.y)).join(" ");
  return (
    <div className="map-shell">
      <div className="map-toolbar">
        <div className="map-legend">
          <span><i className="legend worker" /> 작업자</span>
          <span><i className="legend anchor" /> UWB 앵커</span>
          <span><i className="legend zone" /> 위험구역</span>
        </div>
        <div className="map-toolbar-actions">
          <button className={showTrail ? "active" : ""} onClick={() => setShowTrail(value => !value)}>경로 {showTrail ? "켜짐" : "꺼짐"}</button>
          {(["60", "300", "all"] as const).map(value => (
            <button key={value} className={trailWindow === value ? "active" : ""} disabled={!showTrail} onClick={() => setTrailWindow(value)}>
              {value === "60" ? "1분" : value === "300" ? "5분" : "전체"}
            </button>
          ))}
        </div>
        <span className={"map-reception " + (offline ? "offline" : "live")}><i /> {offline ? "수신 끊김" : "실시간"} · {ageLabel}</span>
        <strong>{width}m × {height}m</strong>
      </div>
      <div className="map-heading-panel" role="status">
        <strong>바라보는 방향: {freshHeading(selectedDevice)
          ? `${["오른쪽", "오른쪽 위", "위쪽", "왼쪽 위", "왼쪽", "왼쪽 아래", "아래쪽", "오른쪽 아래"][Math.round(selectedDevice!.heading_deg! / 45) % 8]} · ${selectedDevice!.heading_deg!.toFixed(0)}°`
          : "확인 불가"}</strong>
        <span>지도 기준 · 파란 화살표는 시선 방향</span>
        <button disabled={calibrating || !selectedDevice?.online || selectedDevice.component_status?.imu !== "ready"}
          onClick={() => void calibrate()}>{calibrating ? "보정 중…" : "앵커 1·4 벽을 정면으로 보고 보정"}</button>
        {calibrationMessage && <span>{calibrationMessage}</span>}
      </div>
      {evacuationRoute && (
        <div className={"map-alert-strip evacuation " + (evacuationRoute.mode === "fire_confirmed" ? "avoidance" : "official")} role="alert">
          <b>{evacuationRoute.mode === "fire_confirmed" ? "화재 위치 확인됨" : "화재 위치 확인 중"}</b>
          <span>{evacuationRoute.message ?? evacuationRoute.instructions[0] ?? "비상 유도등을 확인하고 즉시 대피하세요."}</span>
          {evacuationRoute.distance_m != null && <em>비상구 {evacuationRoute.distance_m.toFixed(1)}m</em>}
        </div>
      )}      {dangerZone && !offline && (
        <div className="map-alert-strip danger" role="alert"><b>위험구역 진입</b><span>{selectedWorker?.worker_name} 작업자가 ‘{dangerZone.zone_name}’ 안에 있습니다.</span></div>
      )}
      {offline && (
        <div className="map-alert-strip offline" role="status"><b>위치 확인 필요</b><span>태그 전원과 Wi-Fi를 확인하세요. 마지막 수신 위치를 표시 중입니다.</span></div>
      )}
      <svg className="site-map" viewBox="0 0 1000 600" role="img" aria-label="작업 현장 실시간 위치 지도">
        <defs>
          <pattern id="grid" width="75" height="65" patternUnits="userSpaceOnUse">
            <path d="M 75 0 L 0 0 0 65" className="map-grid-line" fill="none" strokeWidth="1" />
          </pattern>
          <filter id="glow"><feGaussianBlur stdDeviation="5" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        <rect x="35" y="25" width="930" height="550" rx="18" className="map-floor" strokeWidth="2" />
        <rect x="35" y="25" width="930" height="550" rx="18" fill="url(#grid)" />
        <g className="map-labels">
          <text x="55" y="55">A 구역 · 조립/이동 통로</text>
          <text x="730" y="550">화기 작업 구역</text>
        </g>
        {obstacles.map(obstacle => (
          <g key={obstacle.obstacle_id} className={"map-obstacle " + (obstacle.object_type ?? "obstacle")}>
            <rect
              x={scaleX(obstacle.x)}
              y={scaleY(obstacle.y + obstacle.height)}
              width={(obstacle.width / width) * 900}
              height={(obstacle.height / height) * 520}
              rx="4"
            />
            <text x={scaleX(obstacle.x + obstacle.width / 2)} y={scaleY(obstacle.y + obstacle.height / 2)} textAnchor="middle" dominantBaseline="middle">{obstacle.name}</text>
          </g>
        ))}
        {fireZone && (
          <g className="map-fire-zone">
            <rect x={scaleX(fireZone.x)} y={scaleY(fireZone.y + fireZone.height)} width={(fireZone.width / width) * 900} height={(fireZone.height / height) * 520} rx="10" />
            <text x={scaleX(fireZone.x + fireZone.width / 2)} y={scaleY(fireZone.y + fireZone.height / 2)} textAnchor="middle" dominantBaseline="middle">{fireZone.name || "화재구간"} · 진입금지</text>
          </g>
        )}        {zones.filter(zone => zone.active && zone.zone_type === "rectangle").map(zone => (
          <g key={zone.zone_id} className={dangerZone?.zone_id === zone.zone_id ? "zone-active" : ""}>
            <rect
              x={scaleX(zone.coordinates.x)}
              y={scaleY(zone.coordinates.y + zone.coordinates.height!)}
              width={(zone.coordinates.width! / width) * 900}
              height={(zone.coordinates.height! / height) * 520}
              rx="12"
              className="danger-zone"
            />
            <text x={scaleX(zone.coordinates.x + zone.coordinates.width! / 2)} y={scaleY(zone.coordinates.y + zone.coordinates.height! / 2)} textAnchor="middle" dominantBaseline="middle" className="zone-name">{zone.zone_name}</text>
          </g>
        ))}        {showTrail && trailPoints && (
          <g className="worker-route">
            <polyline points={trailPoints} className="route-line route-glow" />
            <polyline points={trailPoints} className="route-line" />
            {trail.length > 1 && <circle cx={scaleX(trail[0].x)} cy={scaleY(trail[0].y)} r="6" className="route-start" />}
            {trail.length > 0 && <circle cx={scaleX(trail[trail.length - 1].x)} cy={scaleY(trail[trail.length - 1].y)} r="7" className="route-end" />}
          </g>
        )}
        {anchors.map(anchor => (
          <g key={anchor.anchor_id} transform={`translate(${scaleX(anchor.x)}, ${scaleY(anchor.y)})`} className="anchor-node">
            <circle r="19" className={anchor.online ? "online" : "offline"} />
            <AnchorSymbol />
            <text y="36" textAnchor="middle">{anchor.anchor_id.replace("anchor-", "A")}</text>
          </g>
        ))}
        {workers.map(worker => {
          const color = riskColor[worker.risk_level] ?? "#37d49f";
          const selected = selectedId === worker.worker_id;
          const device = headingDevice(worker);
          const hasHeading = freshHeading(device);
          const angle = (device?.heading_deg ?? 0) * Math.PI / 180;
          // Account for the map's unequal X/Y scale and inverted screen Y.
          const screenAngle = Math.atan2(-Math.sin(angle) * 520 / height, Math.cos(angle) * 900 / width) * 180 / Math.PI;
          return (
            <g
              key={worker.worker_id}
              transform={`translate(${scaleX(worker.x)}, ${scaleY(worker.y)})`}
              className={`worker-node ${selected ? "selected" : ""} ${worker.emergency ? "emergency" : ""}`}
              onClick={() => onSelect(worker)}
              role="button"
              tabIndex={0}
              onKeyDown={event => event.key === "Enter" && onSelect(worker)}
            >
              <circle r={38 + (1 - worker.confidence) * 25} fill="none" stroke={color} opacity=".16" strokeWidth="12" />
              {hasHeading && <HeadingArrow angle={screenAngle} label={`${worker.worker_name} 바라보는 방향 ${device!.heading_deg!.toFixed(0)}도`} />}
              <circle r="25" fill={color} filter="url(#glow)" />
              <path d="M-8-4 A8 8 0 1 1 8-4 M-13 15 C-11 4 11 4 13 15" fill="none" stroke="#06101a" strokeWidth="4" strokeLinecap="round" />
              {worker.emergency && <g className="worker-sos-badge" transform="translate(-28,-62)"><rect x="0" y="0" width="56" height="24" rx="12" /><text x="28" y="16" textAnchor="middle">SOS</text></g>}
              <g transform="translate(32,-29)">
                <rect x="0" y="0" width="128" height="52" rx="11" className="worker-label-bg" />
                <text x="12" y="20" className="worker-label-name">{worker.worker_name}</text>
                <text x="12" y="39" className="worker-label-risk">{worker.emergency ? "긴급 도움 요청" : `${worker.risk_score}점 · ${worker.risk_level}`}</text>
              </g>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
