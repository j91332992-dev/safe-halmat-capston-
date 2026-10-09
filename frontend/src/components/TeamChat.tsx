import {useEffect, useId, useRef, useState} from "react";
import {operationsApi, workerApi} from "../services/api";
import type {ChatData} from "../services/api";

export function TeamChat({workerId}: {workerId?: string}) {
  const [data, setData] = useState<ChatData | null>(null);
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [older, setOlder] = useState<ChatData["messages"]>([]);
  const list = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const sending = useRef(false);
  const inputHelpId = useId();
  const [calling, setCalling] = useState(false);
  const [callNotice, setCallNotice] = useState("");
  const requestCall = async () => {
    if (calling) return;
    setCalling(true);
    try {await workerApi.callManager(); setCallNotice("관리자에게 통화를 요청했습니다. 관리자 연결 후 안전모로 통화하세요.");}
    catch (e) {setCallNotice(e instanceof Error ? e.message : "통화 요청 실패");}
    finally {setCalling(false);}
  };
  const load = async () => {
    try {setData(await (workerId ? operationsApi.chat(workerId) : workerApi.chat())); setError("");}
    catch {setError("팀 채팅 연결을 확인하세요.");}
  };
  useEffect(() => {
    let active = true; setOlder([]); setData(null);
    const poll = async () => {
      try {const value = await (workerId ? operationsApi.chat(workerId) : workerApi.chat()); if (active) {setData(value); setError("");}}
      catch {if (active) setError("팀 채팅 연결을 확인하세요.");}
    };
    void poll(); const timer = window.setInterval(() => void poll(), 2000);
    return () => {active = false; window.clearInterval(timer);};
  }, [workerId]);
  useEffect(() => {setOlder([]);}, [data?.team]);
  useEffect(() => {if (list.current && nearBottom.current) list.current.scrollTop = list.current.scrollHeight;}, [data?.messages.at(-1)?.message_id]);
  const send = async (event?: React.FormEvent) => {
    event?.preventDefault(); if (!content.trim() || sending.current) return;
    sending.current = true; setBusy(true);
    try {await (workerId ? operationsApi.sendChat(workerId, content) : workerApi.sendChat(content)); setContent(""); nearBottom.current = true; await load();}
    catch (e) {setError(e instanceof Error ? e.message : "전송 실패");} finally {sending.current = false; setBusy(false);}
  };
  const all = [...older, ...(data?.messages ?? [])].filter((r, i, rows) => rows.findIndex(m => m.message_id === r.message_id) === i);
  const earlier = async () => {
    try {const value = await (workerId ? operationsApi.chat(workerId, all[0]?.message_id) : workerApi.chat(all[0]?.message_id)); nearBottom.current = false; setOlder(rows => [...value.messages, ...rows]); if (!value.messages.length) setError("이전 메시지가 없습니다.");}
    catch {setError("이전 메시지를 불러오지 못했습니다.");}
  };
  return <section className="worker-card team-chat"><div className="team-chat-heading"><h3>{data?.team ?? "팀"} 채팅</h3>{!workerId && <button type="button" disabled={calling} onClick={() => void requestCall()}>☎ {calling ? "요청 중…" : "관리자 통화"}</button>}</div>{callNotice && <p role="status">{callNotice}</p>}<p>같은 현장·같은 팀의 근로자와 관리자가 함께 보는 대화입니다.</p>{error && <p role="alert">{error}</p>}<button type="button" onClick={() => void earlier()} disabled={!all.length}>이전 대화 보기</button>
    <div className="chat-messages" ref={list} aria-live="polite" onScroll={() => {if (list.current) nearBottom.current = list.current.scrollHeight - list.current.scrollTop - list.current.clientHeight < 60;}}>{all.map(row => <article key={row.message_id}><b>{row.sender_name}</b><time>{new Date(row.created_at).toLocaleString("ko-KR", {timeZone: "Asia/Seoul"})}</time><p>{row.content}</p></article>)}{!all.length && <p>첫 메시지를 보내보세요.</p>}</div>
    <form onSubmit={event => void send(event)}><label>메시지<textarea value={content} maxLength={2000} rows={2} readOnly={busy} enterKeyHint="send" aria-describedby={inputHelpId} onChange={e => setContent(e.target.value)} onKeyDown={event => {
      if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) return;
      event.preventDefault();
      if (!event.repeat) void send();
    }} placeholder="팀에 전달할 내용을 입력하세요."/></label><button disabled={busy || !content.trim()}>{busy ? "전송 중" : "보내기"}</button></form>
    <small id={inputHelpId}>Enter 전송 · Shift+Enter 줄바꿈</small>
  </section>;
}
