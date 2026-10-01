import {useEffect, useRef, useState} from "react";
import {useNavigate} from "react-router-dom";
import {Haptics, ImpactStyle} from "@capacitor/haptics";
import {api} from "../../services/api";
import type {Snapshot, Worker} from "../../types";

interface MobileDashboardProps {
  data: Snapshot;
  selectedWorker: Worker | undefined;
  critical: number;
  onAlerts: () => void;
  busy: boolean;
  onAction: (cb: () => Promise<unknown>) => void;
}

const riskTone: Record<string, "safe" | "info" | "warning" | "danger"> = {
  "정상": "safe", "관심": "info", "주의": "warning", "위험": "danger", "비상": "danger"
};

function elapsedSince(timestamp: string | null | undefined): string {
  if (!timestamp) return "수신 기록 없음";
  const elapsed = Math.max(0, Math.floor((Date.now() - new Date(timestamp).getTime()) / 1000));
  if (!Number.isFinite(elapsed)) return "수신 기록 없음";
  if (elapsed < 60) return `${elapsed}초 전`;
  if (elapsed < 3600) return `${Math.floor(elapsed / 60)}분 ${elapsed % 60}초 전`;
  return `${Math.floor(elapsed / 3600)}시간 ${Math.floor((elapsed % 3600) / 60)}분 전`;
}

function communicationTime(timestamp: string | null | undefined): string {
  if (!timestamp || Number.isNaN(new Date(timestamp).getTime())) return "기록 없음";
  return new Date(timestamp).toLocaleTimeString("ko-KR", {hour: "2-digit", minute: "2-digit", second: "2-digit"});
}

export function MobileDashboard({data, selectedWorker: worker, critical, onAlerts, busy, onAction}: MobileDashboardProps) {
  const navigate = useNavigate();
  const previouslyDisconnected = useRef<Set<string>>(new Set());
  const [reconnectedWorkers, setReconnectedWorkers] = useState<string[]>([]);
  const workersByRisk = {
    safe: data.workers.filter(item => item.risk_level === "정상").length,
    warning: data.workers.filter(item => ["관심", "주의"].includes(item.risk_level)).length,
    danger: data.workers.filter(item => ["위험", "비상"].includes(item.risk_level)).length
  };
  const emergencyWorker = data.workers.find(item => item.emergency) ?? data.workers.find(item => riskTone[item.risk_level] === "danger");
  const focusedWorker = emergencyWorker ?? worker;
  const helmet = data.devices.find(device => device.worker_id === focusedWorker?.worker_id && device.device_type === "assistant_device");
  const focusedTag = data.devices.find(device => device.worker_id === focusedWorker?.worker_id && device.device_type === "position_device");
  const disconnectedWorkers = data.workers.flatMap(person => {
    const tag = data.devices.find(device => device.worker_id === person.worker_id && device.device_type === "position_device");
    return tag && !tag.online ? [{worker: person, tag}] : [];
  });
  const isDanger = Boolean(emergencyWorker || critical > 0);
  const disconnectedKey = disconnectedWorkers.map(({worker: disconnectedWorker}) => disconnectedWorker.worker_id).join("|");

  useEffect(() => {
    const current = new Set(disconnectedKey ? disconnectedKey.split("|") : []);
    const restored = [...previouslyDisconnected.current].filter(workerId => !current.has(workerId));
    if (restored.length) {
      setReconnectedWorkers(restored.map(workerId => data.workers.find(person => person.worker_id === workerId)?.worker_name ?? workerId));
    }
    previouslyDisconnected.current = current;
  }, [data.workers, disconnectedKey]);

  const tap = (callback: () => void, strong = false) => {
    void Haptics.impact({style: strong ? ImpactStyle.Medium : ImpactStyle.Light}).catch(() => {});
    callback();
  };

  const eventLabel = (workerId: string | null) => data.workers.find(item => item.worker_id === workerId)?.worker_name ?? "현장 시스템";

  return (
    <section className="safety-mobile-home" aria-label="모바일 안전관제 홈">
      <div className="mobile-home-intro">
        <div>
          <span className="mobile-home-eyebrow">LIVE SAFETY CONTROL</span>
          <h2>현장 안전 현황</h2>
          <p>{data.site.name} · {new Date().toLocaleDateString("ko-KR", {month: "long", day: "numeric", weekday: "short"})}</p>
        </div>
        <button className="mobile-refresh" onClick={() => tap(onAlerts)} aria-label="미처리 이벤트 확인"><span>{critical}</span> 알림</button>
      </div>

      {isDanger ? (
        <button className="mobile-emergency-card" onClick={() => tap(onAlerts, true)}>
          <span className="mobile-emergency-icon">🚨</span>
          <span className="mobile-emergency-copy"><b>{emergencyWorker ? `${emergencyWorker.worker_name} 작업자 위험 감지` : `즉시 확인이 필요한 경보 ${critical}건`}</b><small>{emergencyWorker ? `${emergencyWorker.current_zone ?? "위치 확인 중"} · 위험도 ${emergencyWorker.risk_score}점` : "이벤트 센터에서 상황을 확인하세요"}</small></span>
          <span className="mobile-emergency-arrow">›</span>
        </button>
      ) : (
        <div className="mobile-safe-card"><span className="mobile-safe-icon">✓</span><span><b>현재 긴급 상황이 없습니다</b><small>모든 안전 신호를 실시간으로 수신 중입니다</small></span><span className="mobile-live-dot">LIVE</span></div>
      )}

      <section className="mobile-overview-card" aria-label="현장 상태 요약">
        <div className="mobile-overview-title"><span>📊</span><b>현장 상태 요약</b><small>실시간</small></div>
        <div className="mobile-status-summary">
          <button onClick={() => tap(() => navigate("/workers"))} className="summary-safe"><strong>{workersByRisk.safe}</strong><span>🟢 정상</span></button>
          <button onClick={() => tap(() => navigate("/workers"))} className="summary-warning"><strong>{workersByRisk.warning}</strong><span>🟡 주의</span></button>
          <button onClick={() => tap(onAlerts, true)} className="summary-danger"><strong>{workersByRisk.danger || critical}</strong><span>🔴 위험</span></button>
        </div>
      </section>

      {disconnectedWorkers.length > 0 && (
        <section className="mobile-connection-watch" aria-label="통신 끊김 작업자">
          <header><span>📡</span><div><b>통신 확인 필요</b><small>UWB 위치 신호가 끊긴 작업자 {disconnectedWorkers.length}명</small></div></header>
          {disconnectedWorkers.slice(0, 3).map(({worker: disconnectedWorker, tag}) => {
            const lastContact = tag.last_uwb_at ?? tag.last_seen;
            return <button key={disconnectedWorker.worker_id} onClick={() => tap(() => navigate("/map"))}>
              <span className="connection-lost-dot" />
              <span><b>👷 {disconnectedWorker.worker_name}</b><small>마지막 통신 {elapsedSince(lastContact)} · {communicationTime(lastContact)}</small></span>
              <span className="connection-last-location">📍 {disconnectedWorker.current_zone ?? `X ${disconnectedWorker.x.toFixed(1)} · Y ${disconnectedWorker.y.toFixed(1)}m`}</span>
              <i>›</i>
            </button>;
          })}
        </section>
      )}

      {reconnectedWorkers.length > 0 && (
        <div className="mobile-reconnected-notice" role="status">
          <span>✓</span><div><b>안전모 통신이 복구되었습니다</b><small>{reconnectedWorkers.join(", ")} · 실시간 수신을 다시 시작했습니다</small></div><button onClick={() => setReconnectedWorkers([])} aria-label="통신 복구 알림 닫기">×</button>
        </div>
      )}

      {focusedWorker && (
        <section className={`mobile-worker-focus tone-${riskTone[focusedWorker.risk_level] ?? "safe"}`}>
          <header><div><span className="mobile-card-kicker">FOCUS WORKER</span><h3>👷 {focusedWorker.worker_name}</h3></div><span className="mobile-risk-chip">{focusedWorker.risk_level}</span></header>
          <div className="mobile-worker-location"><span>📍</span><div><small>현재 위치</small><b>{focusedWorker.current_zone ?? `UWB X ${focusedWorker.x.toFixed(1)}m · Y ${focusedWorker.y.toFixed(1)}m`}</b></div></div>
          {focusedTag && !focusedTag.online && (
            <div className="mobile-last-contact">
              <span>⚠️</span><div><b>안전모 위치 통신이 끊겼습니다</b><small>마지막 통신: {elapsedSince(focusedTag.last_uwb_at ?? focusedTag.last_seen)} ({communicationTime(focusedTag.last_uwb_at ?? focusedTag.last_seen)})</small><em>마지막 위치: {focusedWorker.current_zone ?? `X ${focusedWorker.x.toFixed(1)}m · Y ${focusedWorker.y.toFixed(1)}m`}</em></div>
            </div>
          )}
          <div className="mobile-worker-metrics">
            <span><small>📡 위치 신뢰도</small><b>{Math.round(focusedWorker.confidence * 100)}%</b></span>
            <span><small>🛡️ 위험 점수</small><b>{focusedWorker.risk_score}점</b></span>
            <span><small>📶 장치 상태</small><b>{helmet?.online ? "정상" : "확인 필요"}</b></span>
          </div>
          <div className="mobile-primary-actions">
            <button className="action-camera" onClick={() => tap(() => navigate("/camera"))}>📹 카메라 확인</button>
            <button className="action-call" disabled={busy || !helmet?.online} onClick={() => tap(() => onAction(() => api.sendAlert(helmet?.device_id)), true)}>🔊 경고 전송</button>
          </div>
        </section>
      )}

      <section className="mobile-shortcuts" aria-label="빠른 메뉴">
        <button onClick={() => tap(() => navigate("/map"))}><span>🗺️</span><b>실시간 지도</b><small>작업자 위치</small></button>
        <button onClick={() => tap(onAlerts)}><span>🚨</span><b>이벤트</b><small>{critical ? `${critical}건 확인 필요` : "전체 정상"}</small></button>
        <button onClick={() => tap(() => navigate("/camera"))}><span>📹</span><b>카메라</b><small>현장 영상</small></button>
        <button onClick={() => tap(() => navigate("/workers"))}><span>👥</span><b>작업자</b><small>{data.workers.length}명 연결</small></button>
      </section>

      <section className="mobile-events-preview">
        <header><div><span className="mobile-card-kicker">RECENT ACTIVITY</span><h3>최근 안전 이벤트</h3></div><button onClick={() => tap(onAlerts)}>전체 보기</button></header>
        {data.events.length === 0 ? <p className="mobile-empty-events">새로운 이벤트가 없습니다.</p> : data.events.slice(0, 3).map(event => (
          <button className={`mobile-event-item severity-${event.severity}`} key={event.event_id} onClick={() => tap(onAlerts)}>
            <span>{["danger", "emergency"].includes(event.severity) ? "🚨" : event.severity === "warning" ? "⚠️" : "ℹ️"}</span>
            <span><b>{event.message || event.event_type}</b><small>{eventLabel(event.worker_id)} · {new Date(event.created_at).toLocaleTimeString("ko-KR", {hour: "2-digit", minute: "2-digit"})}</small></span><i>›</i>
          </button>
        ))}
      </section>
    </section>
  );
}
