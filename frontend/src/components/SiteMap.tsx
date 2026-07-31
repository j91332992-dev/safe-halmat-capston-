import type {Anchor, Worker, Zone} from "../types";

interface Props {
  width: number;
  height: number;
  anchors: Anchor[];
  zones: Zone[];
  workers: Worker[];
  selectedId?: string;
  onSelect: (worker: Worker) => void;
}

const riskColor: Record<string, string> = {
  정상: "#37d49f",
  관심: "#73d7ff",
  주의: "#ffc857",
  위험: "#ff8a47",
  비상: "#ff4d65"
};

export function SiteMap({width, height, anchors, zones, workers, selectedId, onSelect}: Props) {
  const scaleX = (x: number) => 50 + (x / width) * 900;
  const scaleY = (y: number) => 40 + (y / height) * 520;
  return (
    <div className="map-shell">
      <div className="map-toolbar">
        <span><i className="legend worker" /> 작업자</span>
        <span><i className="legend anchor" /> UWB 앵커</span>
        <span><i className="legend zone" /> 위험구역</span>
        <strong>{width}m × {height}m</strong>
      </div>
      <svg className="site-map" viewBox="0 0 1000 600" role="img" aria-label="작업 현장 실시간 위치 지도">
        <defs>
          <pattern id="grid" width="75" height="65" patternUnits="userSpaceOnUse">
            <path d="M 75 0 L 0 0 0 65" fill="none" stroke="rgba(116,166,196,.11)" strokeWidth="1" />
          </pattern>
          <filter id="glow"><feGaussianBlur stdDeviation="5" result="blur" /><feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        <rect x="35" y="25" width="930" height="550" rx="18" fill="#091827" stroke="#1c3a51" strokeWidth="2" />
        <rect x="35" y="25" width="930" height="550" rx="18" fill="url(#grid)" />
        <g className="map-labels">
          <text x="55" y="55">A 구역 · 조립/이동 통로</text>
          <text x="730" y="550">화기 작업 구역</text>
        </g>
        {zones.filter(zone => zone.active && zone.zone_type === "rectangle").map(zone => (
          <g key={zone.zone_id}>
            <rect
              x={scaleX(zone.coordinates.x)}
              y={scaleY(zone.coordinates.y)}
              width={(zone.coordinates.width! / width) * 900}
              height={(zone.coordinates.height! / height) * 520}
              rx="12"
              className="danger-zone"
            />
            <text x={scaleX(zone.coordinates.x) + 16} y={scaleY(zone.coordinates.y) + 28} className="zone-name">{zone.zone_name}</text>
          </g>
        ))}
        {anchors.map(anchor => (
          <g key={anchor.anchor_id} transform={`translate(${scaleX(anchor.x)}, ${scaleY(anchor.y)})`} className="anchor-node">
            <circle r="19" className={anchor.online ? "online" : "offline"} />
            <path d="M-7 5 L0-8 L7 5 Z M0-7 V10" />
            <text y="36" textAnchor="middle">{anchor.anchor_id.replace("anchor-", "A")}</text>
          </g>
        ))}
        {workers.map(worker => {
          const color = riskColor[worker.risk_level] ?? "#37d49f";
          const selected = selectedId === worker.worker_id;
          return (
            <g
              key={worker.worker_id}
              transform={`translate(${scaleX(worker.x)}, ${scaleY(worker.y)})`}
              className={`worker-node ${selected ? "selected" : ""}`}
              onClick={() => onSelect(worker)}
              role="button"
              tabIndex={0}
              onKeyDown={event => event.key === "Enter" && onSelect(worker)}
            >
              <circle r={38 + (1 - worker.confidence) * 25} fill="none" stroke={color} opacity=".16" strokeWidth="12" />
              <circle r="25" fill={color} filter="url(#glow)" />
              <path d="M-8-4 A8 8 0 1 1 8-4 M-13 15 C-11 4 11 4 13 15" fill="none" stroke="#06101a" strokeWidth="4" strokeLinecap="round" />
              <g transform="translate(32,-29)">
                <rect x="0" y="0" width="128" height="52" rx="11" className="worker-label-bg" />
                <text x="12" y="20" className="worker-label-name">{worker.worker_name}</text>
                <text x="12" y="39" className="worker-label-risk">{worker.risk_score}점 · {worker.risk_level}</text>
              </g>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

