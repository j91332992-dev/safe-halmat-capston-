import {useEffect, useState} from "react";
import {workerApi} from "../../services/api";
import type {WorkerAppData, WorkerMapData} from "../../services/api";

export function WorkerMap({data}: {data: WorkerAppData}) {
  const [map, setMap] = useState<WorkerMapData | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = async () => {try {const value = await workerApi.map(); if (active) {setMap(value); setError("");}} catch {if (active) setError("현장 지도를 불러오지 못했습니다.");}};
    void load(); const timer = window.setInterval(() => void load(), 30000);
    return () => {active = false; window.clearInterval(timer);};
  }, [data.worker.site_name]);
  const tag = data.devices.find(d => d.device_type === "position_device");
  const fresh = !!tag?.online && !!tag.last_uwb_at && Date.now() - Date.parse(tag.last_uwb_at) < 15000 && data.worker.confidence > 0;
  const width = map?.site.width || 1, height = map?.site.height || 1;
  const sx = (x: number) => 35 + x / width * 630;
  const sy = (y: number) => 445 - y / height * 410;
  const c = map?.zones ?? [];
  return <section className="worker-card worker-map"><h3>내 실시간 위치</h3><p>{data.worker.site_name} · {fresh ? "위치 수신 중 · 약 2초마다 갱신" : "위치 수신 대기 · 표시된 위치는 마지막 수신값입니다."}</p>{error && <p role="alert">{error}</p>}
    {map && <svg viewBox="0 0 700 490" role="img" aria-label={`${data.worker.site_name}에서의 내 위치 지도`}><defs><pattern id="worker-map-grid" width="35" height="35" patternUnits="userSpaceOnUse"><path d="M35 0H0V35" fill="none" stroke="#dce6ec"/></pattern></defs><rect x="35" y="35" width="630" height="410" fill="url(#worker-map-grid)" stroke="#b4c9d6"/>
      {c.filter(z => z.active).map((z, i) => {const p = z.coordinates; const fill = z.zone_category === "restricted" ? "#e2b2f080" : "#ffc09b80";
        return <g key={i}>{z.zone_type === "rectangle" && p.width !== undefined && p.height !== undefined && <rect x={sx(p.x)} y={sy(p.y + p.height)} width={p.width / width * 630} height={p.height / height * 410} fill={fill}/>} {z.zone_type === "circle" && <ellipse cx={sx(p.x)} cy={sy(p.y)} rx={(p.radius ?? 0) / width * 630} ry={(p.radius ?? 0) / height * 410} fill={fill}/>} {z.zone_type === "polygon" && <polygon points={(p.points ?? []).map(point => `${sx(point.x)},${sy(point.y)}`).join(" ")} fill={fill}/>}</g>;})}
      {map.obstacles.map((o, i) => <g key={i}><rect x={sx(o.x)} y={sy(o.y + o.height)} width={o.width / width * 630} height={o.height / height * 410} fill={o.object_type === "emergency_exit" ? "#bce9d2" : "#c4d2da"}/><text x={sx(o.x + o.width / 2)} y={sy(o.y + o.height / 2)} textAnchor="middle" fontSize="12">{o.name}</text></g>)}
      {tag?.last_uwb_at && <g opacity={fresh ? 1 : .45}><circle cx={sx(data.worker.x)} cy={sy(data.worker.y)} r="20" fill="#3289f333"/><circle cx={sx(data.worker.x)} cy={sy(data.worker.y)} r="9" fill="#2679dc" stroke="white" strokeWidth="3"/><text x={Math.min(620, Math.max(80, sx(data.worker.x)))} y={Math.max(20, sy(data.worker.y) - 27)} textAnchor="middle" fill="#175da9" fontWeight="700">내 위치</text></g>}
      <text x="35" y="474" fontSize="13">0m</text><text x="665" y="474" textAnchor="end" fontSize="13">가로 {width}m · 세로 {height}m</text></svg>}
    <p>{tag?.last_uwb_at ? `${data.worker.current_zone ?? "현장 내부"} · X ${data.worker.x.toFixed(2)} / Y ${data.worker.y.toFixed(2)}m · 신뢰도 ${Math.round(data.worker.confidence * 100)}%` : "배정된 위치 태그의 실제 신호를 기다리고 있습니다."}</p>
    {tag?.last_uwb_at && <small>위치 마지막 수신 {new Date(tag.last_uwb_at).toLocaleTimeString("ko-KR")}</small>}
  </section>;
}
