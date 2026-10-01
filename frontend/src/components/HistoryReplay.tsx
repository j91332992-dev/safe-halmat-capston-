import {useEffect, useMemo, useState} from "react";
import {api} from "../services/api";
import type {Anchor, LocationPoint, Obstacle, Snapshot, Worker, Zone} from "../types";
import {AnchorSymbol} from "./AnchorSymbol";

interface Props {
  site: Snapshot["site"];
  anchors: Anchor[];
  obstacles: Obstacle[];
  zones: Zone[];
  workers: Worker[];
}

export function HistoryReplay({site, anchors, obstacles, zones, workers}: Props) {
  const [workerId, setWorkerId] = useState(workers[0]?.worker_id ?? "");
  const [allPoints, setAllPoints] = useState<LocationPoint[]>([]);
  const [range, setRange] = useState<"300" | "1800" | "all">("1800");
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!workerId) return;
    setLoading(true);
    void api.locationHistory(workerId, 5000).then(points => {
      setAllPoints(points);
      setIndex(Math.max(0, points.length - 1));
    }).finally(() => setLoading(false));
  }, [workerId]);

  const points = useMemo(() => {
    if (range === "all") return allPoints;
    const cutoff = Date.now() - Number(range) * 1000;
    return allPoints.filter(point => new Date(point.created_at).getTime() >= cutoff);
  }, [allPoints, range]);

  useEffect(() => {
    setIndex(Math.max(0, points.length - 1));
    setPlaying(false);
  }, [points]);

  useEffect(() => {
    if (!playing || points.length < 2) return;
    const timer = window.setInterval(() => {
      setIndex(current => {
        if (current >= points.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, Math.max(80, 700 / speed));
    return () => window.clearInterval(timer);
  }, [playing, points.length, speed]);

  const sx = (x: number) => 50 + (x / site.width) * 900;
  const sy = (y: number) => 560 - (y / site.height) * 520;
  const visible = points.slice(0, index + 1);
  const route = visible.map(point => sx(point.x) + "," + sy(point.y)).join(" ");
  const current = points[index];
  const worker = workers.find(item => item.worker_id === workerId);

  return (
    <section className="replay-page">
      <header className="replay-head">
        <div><span className="eyebrow">LOCATION HISTORY REPLAY</span><h2>작업자 이동 기록 재생</h2><p>저장된 UWB 좌표를 시간 순서대로 재생합니다.</p></div>
        <div className="replay-filters">
          <label>작업자<select value={workerId} onChange={event => setWorkerId(event.target.value)}>{workers.map(item => <option key={item.worker_id} value={item.worker_id}>{item.worker_name}</option>)}</select></label>
          <label>기록 범위<select value={range} onChange={event => setRange(event.target.value as "300" | "1800" | "all")}><option value="300">최근 5분</option><option value="1800">최근 30분</option><option value="all">전체 기록</option></select></label>
        </div>
      </header>
      <div className="replay-map-wrap">
        <svg className="site-map replay-map" viewBox="0 0 1000 600">
          <rect x="35" y="25" width="930" height="550" rx="18" className="replay-floor" />
          {obstacles.map(item => <g key={item.obstacle_id} className="map-obstacle"><rect x={sx(item.x)} y={sy(item.y + item.height)} width={(item.width / site.width) * 900} height={(item.height / site.height) * 520} /><text x={sx(item.x + item.width / 2)} y={sy(item.y + item.height / 2)} textAnchor="middle" dominantBaseline="middle">{item.name}</text></g>)}
          {zones.filter(zone => zone.active && zone.zone_type === "rectangle").map(zone => <g key={zone.zone_id}><rect className="danger-zone" x={sx(zone.coordinates.x)} y={sy(zone.coordinates.y + zone.coordinates.height!)} width={(zone.coordinates.width! / site.width) * 900} height={(zone.coordinates.height! / site.height) * 520} /><text className="zone-name" x={sx(zone.coordinates.x + zone.coordinates.width! / 2)} y={sy(zone.coordinates.y + zone.coordinates.height! / 2)} textAnchor="middle">{zone.zone_name}</text></g>)}
          {route && <><polyline points={route} className="route-line route-glow" /><polyline points={route} className="route-line" /></>}
          {anchors.map((anchor, anchorIndex) => <g key={anchor.anchor_id} transform={"translate(" + sx(anchor.x) + "," + sy(anchor.y) + ")"} className="anchor-node"><circle r="18" className="online" /><AnchorSymbol /><text textAnchor="middle" y="34">A{anchorIndex + 1}</text></g>)}
          {current && <g transform={"translate(" + sx(current.x) + "," + sy(current.y) + ")"} className="replay-worker"><circle r="24" /><text x="32" y="4">{worker?.worker_name}</text></g>}
        </svg>
        {!loading && points.length === 0 && <div className="replay-empty">선택한 범위에 저장된 위치 기록이 없습니다.</div>}
      </div>
      <div className="replay-controls">
        <button onClick={() => setIndex(0)} disabled={!points.length}>처음</button>
        <button className="play-button" onClick={() => {if (index >= points.length - 1) setIndex(0); setPlaying(!playing);}} disabled={points.length < 2}>{playing ? "일시정지" : "재생"}</button>
        <input aria-label="재생 위치" type="range" min="0" max={Math.max(0, points.length - 1)} value={Math.min(index, Math.max(0, points.length - 1))} onChange={event => {setPlaying(false); setIndex(Number(event.target.value));}} />
        <div className="replay-time"><b>{current ? new Date(current.created_at).toLocaleString("ko-KR") : "-"}</b><span>{points.length ? index + 1 : 0} / {points.length}</span></div>
        <div className="speed-buttons">{[1, 2, 4].map(value => <button key={value} className={speed === value ? "active" : ""} onClick={() => setSpeed(value)}>{value}×</button>)}</div>
      </div>
    </section>
  );
}
