import {api} from "../services/api";
import type {SafetyEvent} from "../types";

interface Props {events: SafetyEvent[]; onRefresh: () => void; expanded?: boolean}

export function EventLog({events, onRefresh, expanded = false}: Props) {
  const change = async (id: string, action: "ack" | "resolve") => {
    action === "ack" ? await api.acknowledge(id) : await api.resolve(id);
    await onRefresh();
  };
  return (
    <div className={`event-table ${expanded ? "expanded" : ""}`}>
      <div className="event-row event-head">
        <span>시간</span><span>등급</span><span>이벤트</span><span>작업자/장치</span><span>상태</span><span />
      </div>
      {events.map(event => (
        <div className="event-row" key={event.event_id}>
          <span className="event-time">{new Date(event.created_at).toLocaleTimeString("ko-KR")}</span>
          <span><i className={`severity severity-${event.severity}`} />{event.severity}</span>
          <span><b>{event.event_type}</b><small>{event.message}</small></span>
          <span>{event.worker_id ?? "-"}<small>{event.device_id ?? ""}</small></span>
          <span className={`event-status status-${event.status}`}>{event.status}</span>
          <span className="event-actions">
            {event.status === "open" && <button onClick={() => void change(event.event_id, "ack")}>확인</button>}
            {event.status !== "resolved" && <button onClick={() => void change(event.event_id, "resolve")}>종료</button>}
          </span>
        </div>
      ))}
      {!events.length && <p className="empty">표시할 이벤트가 없습니다.</p>}
    </div>
  );
}

