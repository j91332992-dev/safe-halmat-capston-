import {useState} from "react";
import {api} from "../services/api";
import type {SafetyEvent} from "../types";

interface Props {events: SafetyEvent[]; onRefresh: () => void; expanded?: boolean}

export function EventLog({events, onRefresh, expanded = false}: Props) {
  const [photo, setPhoto] = useState<string | null>(null);
  const change = async (id: string, action: "ack" | "resolve") => {action === "ack" ? await api.acknowledge(id) : await api.resolve(id); await onRefresh();};
  const imageUrl = (event: SafetyEvent) => typeof event.details?.url === "string" ? api.assetUrl(event.details.url) : null;
  return <>
    <div className={`event-table ${expanded ? "expanded" : ""}`}>
      <div className="event-row event-head"><span>시간</span><span>등급</span><span>이벤트</span><span>작업자/장치</span><span>상태</span><span /></div>
      {events.map(event => {
        const image = imageUrl(event);
        return <div className="event-row" key={event.event_id}>
          <span className="event-time">{new Date(event.created_at).toLocaleTimeString("ko-KR")}</span>
          <span><i className={`severity severity-${event.severity}`} />{event.severity}</span>
          <span><b>{event.event_type}</b><small>{event.message}</small>{image && <button className="event-photo-link" onClick={() => setPhoto(image)}>사진 보기</button>}</span>
          <span>{event.worker_id ?? "-"}<small>{event.device_id ?? ""}</small></span>
          <span className={`event-status status-${event.status}`}>{event.status}</span>
          <span className="event-actions">{event.status === "open" && <button onClick={() => void change(event.event_id, "ack")}>확인</button>}{event.status !== "resolved" && <button onClick={() => void change(event.event_id, "resolve")}>종료</button>}</span>
        </div>;
      })}
      {!events.length && <div className="event-empty-state"><span aria-hidden="true">✓</span><b>현재 확인할 이벤트가 없습니다</b><p>새로운 안전 알림이 수신되면 시간과 처리 상태가 이곳에 표시됩니다.</p></div>}
    </div>
    {photo && <div className="photo-modal" role="dialog" aria-modal="true" aria-label="카메라 이벤트 사진" onClick={() => setPhoto(null)}><div onClick={event => event.stopPropagation()}><button onClick={() => setPhoto(null)}>닫기</button><img src={photo} alt="카메라 이벤트 감지 화면" /></div></div>}
  </>;
}
