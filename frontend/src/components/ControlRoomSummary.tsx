import type {Anchor, Device, Worker} from "../types";
import {HorizonWidget} from "./HorizonWidget";
interface Props {
  workers: Worker[];
  devices: Device[];
  anchors: Anchor[];
  onNavigate: (path: string) => void;
}
function SummaryIcon({type}: {type: "workers" | "map" | "risk" | "battery" | "chat"}) {
  const paths = {
    workers: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
    map: "m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6M9 3v15M15 6v15",
    risk: "m12 3 10 18H2L12 3M12 9v5M12 17v1",
    battery: "M3 7h16v10H3V7M22 10v4M7 10v4M11 10v4",
    chat: "M21 11a8 8 0 0 1-8 8H7l-5 3 2-6a8 8 0 1 1 17-5M8 10h8M8 14h5",
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={paths[type]} /></svg>;
}
export function ControlRoomSummary({workers, devices, anchors, onNavigate}: Props) {
  const working = workers.filter(w => w.work?.state === "working").length;
  const resting = workers.filter(w => w.work?.state === "break").length;
  const onlineTags = devices.filter(d => d.device_type === "position_device" && d.online);
  const located = workers.filter(w => onlineTags.some(d => d.worker_id === w.worker_id));
  const confidence = located.length ? Math.round(located.reduce((sum, w) => sum + w.confidence, 0) / located.length * 100) : null;
  const highest = [...workers].sort((a, b) => b.risk_score - a.risk_score)[0];
  const batteries = devices.filter(d => d.device_type === "assistant_device" && typeof d.battery === "number");
  const average = batteries.length ? Math.round(batteries.reduce((sum, d) => sum + (d.battery ?? 0), 0) / batteries.length) : null;
  const minimum = batteries.length ? Math.min(...batteries.map(d => d.battery!)) : null;
  const liveBattery = batteries.filter(d => d.online).length;
  return <section className="control-kpis" aria-label="현장 핵심 상태 5개">
    <HorizonWidget icon={<SummaryIcon type="workers" />} title="실시간 작업자" value={<>{working}<small>명 작업 중</small></>} footer={<span>휴게 {resting}명 · 등록 {workers.length}명</span>} onClick={() => onNavigate("/workers")} />
    <HorizonWidget icon={<SummaryIcon type="map" />} title="위치 신뢰도" value={<>{confidence ?? "—"}<small>{confidence === null ? "수신 대기" : "%"}</small></>} footer={<span>{confidence === null ? "태그 오프라인" : "실시간 수신"} · 앵커 {anchors.filter(a => a.online).length}/{anchors.length}</span>} onClick={() => onNavigate("/map")} />
    <HorizonWidget className={`control-risk risk-${highest?.risk_level ?? "정상"}`} icon={<SummaryIcon type="risk" />} title="최고 위험도" value={<>{highest?.risk_level ?? "—"}<small>{highest ? `${highest.risk_score}점` : "작업자 없음"}</small></>} footer={<span>{highest?.worker_name ?? "등록 대기"} · {highest && highest.risk_score >= 60 ? "상태 확인 필요" : "현장 상태"}</span>} onClick={() => onNavigate("/workers")} />
    <HorizonWidget icon={<SummaryIcon type="battery" />} title="안전모 배터리" value={<>{average ?? "—"}<small>{average === null ? "측정 대기" : "%"}</small></>} footer={<span>{minimum === null ? "값 없음" : `최저 ${minimum}%`} · {liveBattery ? `${liveBattery}대 수신` : "마지막 수신값"}</span>} onClick={() => onNavigate("/device")} />
    <HorizonWidget className="control-chat" icon={<SummaryIcon type="chat" />} title="현장팀 채팅" value="팀 대화" footer={<span>팀 채팅 열기 →</span>} onClick={() => onNavigate("/team-chat")} />
  </section>;
}
