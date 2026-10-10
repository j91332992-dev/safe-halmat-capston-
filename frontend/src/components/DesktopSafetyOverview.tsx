import {useState} from "react";
import {useNavigate} from "react-router-dom";
import type {Snapshot} from "../types";
import {SafetyIcon} from "./mobile/SafetyIcon";
import {pendingEvents, priority, safetySummary, siteCondition, workerTone} from "./mobile/safetyPresentation";

interface Props {
  data: Snapshot;
  serverReachable: boolean;
  selectedId: string;
  onSelect: (id: string) => void;
  onAlerts: () => void;
}
type Filter = "all" | "danger" | "warning" | "safe";
const stateLabels = {working: "작업 중", break: "휴게 중", off: "작업 전·종료"};

export function DesktopSafetyOverview({data, serverReachable, selectedId, onSelect, onAlerts}: Props) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>("all");
  const [workState, setWorkState] = useState("all");
  const summary = safetySummary(data);
  const condition = siteCondition(data, serverReachable);
  const urgent = pendingEvents(data.events).find(e => priority(e) < 2);
  const emergencyWorker = data.workers.find(w => w.emergency);
  const focused = emergencyWorker ?? data.workers.find(w => workerTone(w) === "danger");
  const fire = ["active", "pending_manager"].includes(data.evacuation.incident?.status ?? "");
  const incidentTitle = fire ? "화재·대피 상황 확인 필요" : emergencyWorker ? `${emergencyWorker.worker_name} SOS 발생` : focused ? `${focused.worker_name} 위험 상태 확인 필요` : urgent?.message || condition.title;
  const workers = data.workers.filter(w => (filter === "all" || workerTone(w) === filter) && (workState === "all" || (w.work?.state ?? "off") === workState));
  const total = data.workers.length;
  const dangerAngle = total ? summary.emergencyWorkers / total * 360 : 0;
  const warningAngle = dangerAngle + (total ? summary.warningWorkers / total * 360 : 0);
  const chartBackground = total ? `conic-gradient(#c33243 0deg ${dangerAngle}deg, #d18a19 ${dangerAngle}deg ${warningAngle}deg, #238558 ${warningAngle}deg 360deg)` : "#e5eae7";
  const cards = [
    {tone: "danger" as const, label: "긴급", value: summary.emergencyWorkers, icon: "alert" as const, detail: `미처리 긴급·위험 경보 ${summary.urgentEvents}건`},
    {tone: "warning" as const, label: "주의", value: summary.warningWorkers, icon: "alert" as const, detail: "관심·주의 상태 작업자"},
    {tone: "safe" as const, label: "안전", value: summary.safeWorkers, icon: "shield" as const, detail: "위험·SOS 미감지 작업자"},
  ];
  return <section className="energy-overview" aria-label="현장 안전 요약">
    <div className="energy-toolbar">
      <div><h2>현장 안전 현황</h2><p>{data.site.name} · 등록 작업자 {total}명</p></div>
      <div className="energy-toolbar-actions"><span className={`energy-live ${serverReachable ? "online" : "offline"}`}>{serverReachable ? "● 실시간 수신" : "마지막 수신 정보"}</span><button onClick={() => navigate("/team-chat")}>팀 채팅 →</button></div>
    </div>
    <div className="energy-counts">
      {cards.map(card => <button key={card.tone} className={`energy-count tone-${card.tone} ${filter === card.tone ? "selected" : ""}`} aria-pressed={filter === card.tone} onClick={() => setFilter(current => current === card.tone ? "all" : card.tone)}>
        <span className="energy-count-heading"><span>{card.label}</span><SafetyIcon name={card.icon}/></span>
        <strong>{card.value}<small>명</small></strong><span className="energy-count-detail">{card.detail}</span><span className="energy-count-link">작업자 보기 ↗</span>
      </button>)}
      <button className="energy-count tone-info" onClick={() => navigate("/device")}><span className="energy-count-heading"><span>장치</span><SafetyIcon name="signal"/></span><strong>{summary.totalDevices}<small>대 등록</small></strong><span className="energy-count-detail">연결 {summary.onlineDevices}대 · 오프라인 {summary.totalDevices - summary.onlineDevices}대</span><span className="energy-count-link">장치 관리 ↗</span></button>
    </div>
    <button className={`energy-incident tone-${condition.tone}`} onClick={onAlerts}>
      <span className="energy-incident-icon">{emergencyWorker ? "SOS" : <SafetyIcon name={condition.tone === "safe" ? "shield" : "alert"}/>}</span>
      <span><small>{condition.tone === "danger" ? "긴급 상황 · 즉시 확인" : "현장 안전 상태"}</small><strong>{condition.tone === "danger" ? incidentTitle : condition.title}</strong><em>{condition.tone === "danger" ? `${focused?.current_zone ?? "현재 위치 확인"} · 미처리 긴급·위험 경보 ${summary.urgentEvents}건` : condition.detail}</em></span><b>알림·영상 확인 →</b>
    </button>
    <div className="energy-panels">
      <section className="energy-panel"><header><div><h3>작업자 안전 분포</h3><p>전체 등록 작업자의 수신된 상태</p></div><span>{total}명</span></header><div className="energy-distribution"><div className="energy-donut" style={{background: chartBackground}} role="img" aria-label={`전체 ${total}명: 긴급 ${summary.emergencyWorkers}명, 주의 ${summary.warningWorkers}명, 안전 ${summary.safeWorkers}명`}><div><strong>{total}</strong><span>전체 작업자</span></div></div><div className="energy-legend">{cards.map(card => <button className={`tone-${card.tone}`} key={card.tone} onClick={() => setFilter(card.tone)}><i/><span>{card.label}</span><b>{card.value}명</b></button>)}<small>{serverReachable ? "위험·SOS 판정 기준" : "연결 끊김 · 마지막 수신 상태"}</small></div></div></section>
      <section className="energy-panel energy-roster"><header><div><h3>작업자 근무 현황</h3><p>현재 작업·휴게 상태와 오늘 근로시간</p></div><button onClick={() => navigate("/workers")}>전체 관리 →</button></header>
        <div className="energy-filters"><label>안전 상태<select value={filter} onChange={e => setFilter(e.target.value as Filter)}><option value="all">전체 상태</option><option value="danger">긴급</option><option value="warning">주의</option><option value="safe">안전</option></select></label><label>근무 상태<select value={workState} onChange={e => setWorkState(e.target.value)}><option value="all">전체 근무</option><option value="working">작업 중</option><option value="break">휴게 중</option><option value="off">작업 전·종료</option></select></label><span>{workers.length}명 표시</span></div>
        <div className="energy-roster-list">{workers.map(w => <button key={w.worker_id} className={selectedId === w.worker_id ? "selected" : ""} aria-pressed={selectedId === w.worker_id} onClick={() => onSelect(w.worker_id)}><span className={`energy-worker-dot tone-${workerTone(w)}`}/><span><b>{w.worker_name}</b><small>오늘 {Math.floor((w.work?.today_seconds ?? 0) / 3600)}시간 {Math.floor((w.work?.today_seconds ?? 0) % 3600 / 60)}분</small></span><span className={`energy-worker-risk tone-${workerTone(w)}`}>{w.emergency ? "SOS" : w.risk_level}</span><span className={`energy-work-state state-${w.work?.state ?? "off"}`}>{stateLabels[w.work?.state ?? "off"]}</span></button>)}{!workers.length && <p className="energy-empty">{total ? "선택한 조건에 해당하는 작업자가 없습니다." : "등록된 작업자가 없습니다."}</p>}</div>
      </section>
    </div>
  </section>;
}
