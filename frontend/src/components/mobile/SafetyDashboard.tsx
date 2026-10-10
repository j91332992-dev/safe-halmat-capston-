import {useNavigate} from "react-router-dom";
import {useEffect, useRef, useState} from "react";
import type {Snapshot, Worker} from "../../types";
import {api} from "../../services/api";
import {SafetyIcon} from "./SafetyIcon";
import {pendingEvents, priority, priorityLabels, siteCondition, workerTone} from "./safetyPresentation";
import {elapsedTime} from "../../utils/elapsedTime";

interface Props {
  data: Snapshot; selectedWorker?: Worker; critical: number; serverReachable: boolean;
  onAlerts: () => void; busy: boolean; onAction: (cb: () => Promise<unknown>) => void;
}
export function MobileDashboard({data, selectedWorker, serverReachable, onAlerts, busy, onAction}: Props) {
  const navigate = useNavigate();
  const condition = siteCondition(data, serverReachable);
  const events = pendingEvents(data.events);
  const focused = data.workers.find(w => workerTone(w) === "danger") ?? data.workers.find(w => workerTone(w) === "warning") ?? selectedWorker;
  const helmet = data.devices.find(d => d.worker_id === focused?.worker_id && d.device_type === "assistant_device");
  const disconnected = data.devices.filter(d => !d.online);
  const batteries = data.devices.filter(d => d.device_type === "assistant_device");
  const isEmergency = condition.tone === "danger";
  const conditionTitle = isEmergency ? `${focused?.worker_name ?? "작업자"} SOS 발생` : condition.title;
  const conditionDetail = isEmergency
    ? `${focused?.current_zone ?? "현재 위치 확인"} · 알림에서 즉시 대응하세요`
    : condition.detail;
  const summaryItems = [
    {tone: "danger", label: "긴급", value: Math.max(data.workers.filter(w => workerTone(w) === "danger").length, events.filter(e => priority(e) < 2).length), icon: "alert" as const},
    {tone: "warning", label: "주의", value: data.workers.filter(w => workerTone(w) === "warning").length, icon: "alert" as const},
    {tone: "safe", label: "안전", value: data.workers.filter(w => workerTone(w) === "safe").length, icon: "shield" as const},
    {tone: "info", label: "장치", value: data.devices.filter(d => d.online).length, icon: "signal" as const}
  ];
  const previousOffline = useRef<string[]>([]);
  const [restored, setRestored] = useState(false);
  const [now, setNow] = useState(Date.now());
  const offlineKey = disconnected.map(d => d.device_id).join('|');
  useEffect(() => {
    const offlineIds = offlineKey ? offlineKey.split('|') : [];
    if (previousOffline.current.some(id => data.devices.some(d => d.device_id === id && d.online))) setRestored(true);
    previousOffline.current = offlineIds;
  }, [offlineKey, data.devices]);
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  return <section className="ops-home" aria-label="현장 안전 대시보드">
    <section className="ops-card"><header><h3>작업자 근무 현황</h3><button onClick={() => navigate('/workers')}>배정·작업 조건 관리</button></header><div className="admin-work-roster">{data.workers.map(worker => <div key={worker.worker_id}><span><b>{worker.worker_name}</b><small> · 작업 {Math.floor((worker.work?.today_seconds ?? 0) / 3600)}시간 {Math.floor((worker.work?.today_seconds ?? 0) % 3600 / 60)}분 · 휴게 {Math.floor((worker.work?.today_break_seconds ?? 0) / 3600)}시간 {Math.floor((worker.work?.today_break_seconds ?? 0) % 3600 / 60)}분</small></span><span className={`work-status state-${worker.work?.state ?? 'off'}`}>{{working: '작업 중', break: '휴게 중', off: '작업 전·종료'}[worker.work?.state ?? 'off']}</span></div>)}</div></section>
    <div className="ops-counts" aria-label="현장 안전 요약">
      {summaryItems.map(item =>
        <button key={item.tone} className={`tone-${item.tone}`} onClick={() => item.tone === "info" ? navigate('/device') : navigate('/workers')}><SafetyIcon name={item.icon}/><span>{item.label}</span><strong>{item.value}<small>{item.tone === "info" ? "대" : item.tone === "danger" ? "건" : "명"}</small></strong></button>)}
    </div>
    <section className={`ops-condition tone-${condition.tone}`} aria-label="현장 안전도">
      <button className="ops-condition-main" onClick={onAlerts}>
        {isEmergency ? <span className="ops-sos-mark" aria-hidden="true">SOS</span> : <SafetyIcon name={condition.tone === "safe" ? "shield" : "alert"}/>}
        <span className="ops-condition-copy"><small>{isEmergency ? "CRITICAL · 긴급 신고" : "현장 안전도"}</small><strong>{conditionTitle}</strong><em>{conditionDetail}</em></span><b>알림 확인 ›</b>
      </button>
    </section>
    {!serverReachable && condition.tone === "danger" && <p className="ops-stale">연결 끊김 · 마지막 수신된 위험 상태입니다</p>}
    <div className="ops-heading ops-section-heading"><div><small>현장 안전 요약</small><h2>지금 확인할 정보</h2></div><span>{data.workers.length}명 등록</span></div>
    <div className="ops-grid">
      <section className="ops-card"><header><h3><SafetyIcon name="signal"/>장치 연결</h3><button onClick={() => navigate('/device')}>상세 ›</button></header><div className="ops-device-count"><strong>{data.devices.filter(d => d.online).length}<small> / {data.devices.length}</small></strong><span>{disconnected.length ? `${disconnected.length}대 확인 필요` : data.devices.length ? '연결됨' : '등록 대기'}</span></div>
        <button className="ops-offline" onClick={() => navigate('/hardware')}><span><b>UWB 앵커</b><small>{data.anchors.filter(a => a.online).length} / {data.anchors.length}개 연결 · 진단 보기</small></span><SafetyIcon name="signal"/></button>
        {restored && <button className="ops-offline" onClick={() => setRestored(false)}><span role="status">장치 연결이 복구되었습니다</span><span>닫기</span></button>}
        {disconnected.slice(0, 2).map(d => {
          const person = data.workers.find(w => w.worker_id === d.worker_id);
          const last = d.last_uwb_at ?? d.last_seen;
          return <button className="ops-offline" key={d.device_id} onClick={() => navigate('/map')}><span><b>{person?.worker_name ?? d.device_id}</b><small>마지막 수신 {elapsedTime(last, now)}</small>{person && <small>마지막 위치 {person.current_zone ?? `X ${person.x.toFixed(1)} · Y ${person.y.toFixed(1)}m`}</small>}</span><SafetyIcon name="map"/></button>;
        })}
      </section>
      <section className="ops-card"><header><h3><SafetyIcon name="battery"/>안전모 배터리</h3><button onClick={() => navigate('/hardware')}>진단 ›</button></header>
        {batteries.length ? batteries.slice(0, 3).map(d => <div className="ops-battery" key={d.device_id}><span>{data.workers.find(w => w.worker_id === d.worker_id)?.worker_name ?? d.device_id}<small>{!d.online ? '오프라인 · 마지막 값' : '연결됨'}</small></span><b className={d.battery !== null && d.battery <= 20 ? 'ops-low' : ''}>{d.battery === null ? '측정 대기' : `${Math.round(d.battery)}%`}</b></div>) : <p className="ops-empty">안전모 연결 대기</p>}
      </section>
    </div>
    <section className="ops-card ops-priority"><header><h3><SafetyIcon name="bell"/>우선 확인</h3><button onClick={onAlerts}>알림 {events.length}건 ›</button></header>
      {events.length ? events.slice(0, 3).map(e => <button className="ops-event" key={e.event_id} onClick={onAlerts}><span className={`ops-tag priority-${priority(e)}`}>{priorityLabels[priority(e)]}</span><span><b>{e.message || e.event_type}</b><small>{data.workers.find(w => w.worker_id === e.worker_id)?.worker_name ?? '현장'} · {new Date(e.created_at).toLocaleTimeString('ko-KR', {hour:'2-digit', minute:'2-digit'})}</small></span><b aria-hidden="true">›</b></button>) : <p className="ops-empty">미처리 알림이 없습니다</p>}
    </section>
    {focused && <section className="ops-card"><header><h3><SafetyIcon name="worker"/>{focused.worker_name}</h3><span className={`ops-tag tone-${workerTone(focused)}`}>{focused.risk_level}</span></header><div className="ops-location"><SafetyIcon name="map"/><span>{focused.current_zone ?? `X ${focused.x.toFixed(1)} · Y ${focused.y.toFixed(1)}m`}<small>마지막 위치 · 신뢰도 {Math.round(focused.confidence * 100)}%</small></span></div><div className="ops-actions"><button onClick={() => navigate('/camera')}><SafetyIcon name="camera"/>영상 확인</button><button disabled={busy || !serverReachable || !helmet?.online} onClick={() => onAction(() => api.sendAlert(helmet?.device_id))}><SafetyIcon name="voice"/>경고 전송</button></div></section>}
  </section>;
}
