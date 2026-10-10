import {useCallback, useEffect, useRef, useState} from "react";
import {workerApi} from "../../services/api";
import type {WorkerAppData} from "../../services/api";
import {WorkCalendar, duration} from "./WorkCalendar";
import {WorkerMap} from "./WorkerMap";
import {TeamChat} from "../TeamChat";
import {SafetyIcon} from "./SafetyIcon";
import "./worker-app.css";

type Tab = "home" | "map" | "work" | "chat" | "alerts" | "me";
const tabs: {id: Tab; icon: string; label: string}[] = [
  {id: "home", icon: "⌂", label: "홈"}, {id: "map", icon: "◎", label: "내 위치"},
  {id: "work", icon: "◷", label: "내 작업"}, {id: "chat", icon: "☏", label: "팀 채팅"},
  {id: "alerts", icon: "♧", label: "알림"}, {id: "me", icon: "♙", label: "내 정보"}
];
function WorkerMenuIcon({tab}: {tab: Tab}) {
  if (tab === "chat") return <svg className="safety-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 4h18v13H9l-6 4Z"/><path d="M7 9h10M7 13h6"/></svg>;
  return <SafetyIcon name={({home: "grid", map: "map", work: "history", alerts: "bell", me: "worker"} as const)[tab]}/>;
}
const dateText = (value: string) => new Date(value).toLocaleString("ko-KR", {timeZone: "Asia/Seoul", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit"});
const batteryStage = (battery: number | null | undefined) => typeof battery !== "number" ? 0 : battery <= 5 ? 5 : battery <= 10 ? 10 : battery <= 20 ? 20 : 0;
const batteryMessage = (stage: number) => stage === 5 ? "긴급: 배터리 5% 이하입니다. 즉시 충전하거나 안전모를 교체하세요." : stage === 10 ? "경고: 배터리 10% 이하입니다. 충전을 준비하고 관리자에게 알려주세요." : "주의: 배터리 20% 이하입니다. 안전모를 충전하세요.";

export function WorkerApp({onLogout}: {onLogout: () => Promise<void>}) {
  const [tab, setTab] = useState<Tab>("home");
  const [data, setData] = useState<WorkerAppData | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [checklist, setChecklist] = useState(false);
  const [checks, setChecks] = useState({helmet: false, vest: false, glove: false});
  const [revision, setRevision] = useState(0);
  const [now, setNow] = useState(Date.now());
  const fetchedAt = useRef(Date.now());
  const [batteryNotice, setBatteryNotice] = useState(0);
  const lastStage = useRef(0);
  const [sosState, setSosState] = useState<"idle" | "sending" | "received" | "failed">("idle");
  const refresh = useCallback(async () => {
    try {const value = await workerApi.me(); fetchedAt.current = Date.now(); setData(value); setError("");}
    catch {setError("서버에 연결할 수 없습니다. 표시된 정보는 마지막 수신값입니다.");}
  }, []);
  useEffect(() => {
    void refresh(); const poll = window.setInterval(() => void refresh(), 2000);
    const clock = window.setInterval(() => setNow(Date.now()), 1000);
    return () => {window.clearInterval(poll); window.clearInterval(clock);};
  }, [refresh]);
  useEffect(() => {
    if (!checklist) return;
    const escape = (e: KeyboardEvent) => {if (e.key === "Escape" && !busy) setChecklist(false);};
    window.addEventListener("keydown", escape); return () => window.removeEventListener("keydown", escape);
  }, [checklist, busy]);
  const helmet = data?.devices.find(device => device.device_type === "assistant_device");
  const freshBattery = !!helmet?.online && now - Date.parse(helmet.last_seen) < 60000;
  const stage = freshBattery ? batteryStage(helmet?.battery) : 0;
  useEffect(() => {
    if (!freshBattery) return;
    if (stage && stage !== lastStage.current) setBatteryNotice(stage);
    if (!stage) setBatteryNotice(0);
    lastStage.current = stage;
  }, [stage, freshBattery]);
  const state = data?.work.state ?? "off";
  const seconds = (data?.work.today_seconds ?? 0) + (state === "working" ? Math.max(0, Math.floor((now - fetchedAt.current) / 1000)) : 0);
  const workAction = async (kind: "start" | "break_start" | "break_end" | "end") => {
    setBusy(true);
    try {await workerApi.work(kind, kind === "start" ? checks : undefined); setChecklist(false); setRevision(n => n + 1); await refresh();}
    catch (e) {setError(e instanceof Error ? e.message : "작업 기록을 저장하지 못했습니다.");}
    finally {setBusy(false);}
  };
  const sendSos = async () => {
    if (!window.confirm("관리자에게 SOS 요청을 보내시겠습니까?")) return;
    setSosState("sending");
    try {await workerApi.sos(); setSosState("received"); await refresh();} catch {setSosState("failed");}
  };
  const latestSos = data?.events.find(event => event.event_type === "WORKER_SOS");
  const emergency = !!data?.worker.emergency || data?.worker.risk_level === "비상";
  const safetyLevel = emergency || data?.worker.risk_level === "위험" ? "danger" : ["주의", "관심"].includes(data?.worker.risk_level ?? "") ? "warning" : "safe";
  const workLabel = state === "working" ? "현재 작업 중" : state === "break" ? "현재 휴게 중" : "작업 전·종료";
  const actions = <div className="worker-actions">{state === "off" ? <button disabled={busy || !data?.eligibility.can_work} onClick={() => {setChecks({helmet: false, vest: false, glove: false}); setChecklist(true);}}>작업 시작</button> : <>{state === "working" ? <button disabled={busy} onClick={() => void workAction("break_start")}>휴게 시작</button> : <button disabled={busy || !data?.eligibility.can_work} onClick={() => void workAction("break_end")}>작업 재개</button>}<button disabled={busy} onClick={() => void workAction("end")}>작업 종료</button></>}</div>;
  const eligibility = data && <section className="worker-card"><h3>교육·작업 허가</h3><strong className={data.eligibility.can_work ? "eligible" : "ineligible"}>{data.eligibility.can_work ? "등록된 조건 충족 · 작업 가능" : "작업 조건 확인 필요"}</strong>{!data.eligibility.items.length && <p>관리자가 등록한 교육·허가 조건이 없습니다.</p>}{data.eligibility.reasons.map(reason => <p className="ineligible" key={reason}>{reason}</p>)}<ul className="worker-list">{data.eligibility.items.map((q, i) => <li key={q.qualification_id ?? i}><span><b>{q.kind === "education" ? "교육" : "작업 허가"} · {q.name}</b><small>{q.required ? "필수" : "선택"} · {q.expires_on ? `유효기간 ${q.expires_on}` : "기한 없음"}</small></span><b className={q.valid ? "eligible" : "ineligible"}>{q.valid ? q.kind === "education" ? "이수 완료" : "승인 완료" : !q.completed ? q.kind === "education" ? "미이수" : "미승인" : "만료"}</b></li>)}</ul><p>이수·승인 정보 변경은 현장 관리자에게 요청하세요.</p></section>;
  return <div className={`worker-app state-${state} safety-${safetyLevel}`} data-tab={tab}>
    <aside className="worker-sidebar">
    <header className="worker-header"><div className="worker-brand">H</div><div><strong>HANMIR</strong><small>MY SAFETY</small></div><span className="worker-role">근로자</span></header>
    <nav className="worker-nav" aria-label="근로자 메뉴">{tabs.map(item => <button key={item.id} aria-current={tab === item.id ? "page" : undefined} className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}><span><WorkerMenuIcon tab={item.id}/></span>{item.label}</button>)}</nav>
    </aside>
    <div className="worker-body">
    {data && <div className={`worker-work-banner state-${state}`} role="status"><b>{emergency ? "⚠ 비상상황 · 즉시 안전 확인" : safetyLevel === "danger" ? "⚠ 위험 · 안전한 곳으로 이동" : workLabel}</b><span>작업시간: {duration(seconds)}{error ? " · 연결 확인 필요" : ""}</span></div>}
    <main className="worker-content">
      {error && <div className="worker-error" role="alert">{error} <button onClick={() => void refresh()}>재시도</button></div>}
      {emergency && <div className="worker-emergency-notice" role="alert"><b>⚠ 비상상황입니다</b><p>작업을 멈추고 안전한 장소로 이동하세요. 도움이 필요하면 SOS 또는 관리자 통화를 이용하세요.</p></div>}
      {!!stage && <div className={`battery-warning stage-${stage}`} role={batteryNotice ? "alert" : "status"}>{batteryMessage(stage)} 현재 {Math.round(helmet?.battery ?? 0)}%{batteryNotice !== 0 && <button onClick={() => setBatteryNotice(0)}>확인</button>}</div>}
      {!data ? <section className="worker-card"><h1>내 안전 정보를 불러오는 중입니다</h1><button onClick={() => void refresh()}>새로고침</button></section> : <>
        {tab === "home" && <>
          <div className="worker-intro"><span>MY SAFETY DASHBOARD</span><h1>{data.worker.worker_name}님, 안녕하세요</h1><p>{data.worker.site_name} · {data.worker.team} · {data.worker.job_title}</p></div>
          <section className={`worker-hero ${safetyLevel}`}><span className="worker-hero-icon">{safetyLevel === "safe" ? "✓" : "!"}</span><div><small>내 안전 상태</small><h2>{emergency ? "비상상황 · 긴급 확인 필요" : data.worker.risk_level}</h2><p>마지막 확인 {dateText(data.worker.updated_at)}</p></div></section>
          <div className="worker-grid"><button className="worker-card" onClick={() => setTab("work")}><small>오늘 일한 시간</small><strong>{duration(seconds)}</strong><span>{workLabel} · 달력 보기 ›</span></button><button className="worker-card" onClick={() => setTab("me")}><small>안전모 연결</small><strong>{helmet?.online ? "연결됨" : "확인 필요"}</strong><span>배터리 {typeof helmet?.battery === "number" ? `${Math.round(helmet.battery)}%` : "확인 불가"} ›</span></button></div>
          <section className="worker-card"><h3>작업 상태</h3>{actions}{!data.eligibility.can_work && <p className="ineligible">교육·허가 조건을 내 정보에서 확인하세요.</p>}</section>
          <button className="worker-card" onClick={() => setTab("map")}><h3>내 실시간 위치 지도 ›</h3><p>{data.worker.current_zone ?? "현재 위치 확인"}</p></button>
          <section className="worker-card"><div className="worker-section-head"><h3>내 알림</h3><button onClick={() => setTab("alerts")}>전체 보기 ›</button></div><p>{data.events[0]?.message ?? "새로운 알림이 없습니다."}</p></section>
        </>}
        {tab === "map" && <WorkerMap data={data}/>}
        {tab === "work" && <><div className="worker-intro"><span>MY WORK</span><h1>내 작업</h1><p>달력에서 날짜를 선택해 전체 작업 기록을 확인하세요.</p></div><section className="worker-card"><h2>{workLabel}</h2><strong className="worker-duration">{duration(seconds)}</strong>{actions}{!data.eligibility.can_work && <p className="ineligible">{data.eligibility.reasons.join(" · ")}</p>}</section><WorkCalendar revision={revision}/></>}
        {tab === "chat" && <TeamChat/>}
        {tab === "alerts" && <><div className="worker-intro"><h1>내 알림</h1></div><section className="worker-card">{data.events.length ? <ul className="worker-list">{data.events.map(event => <li key={event.event_id}><span><b>{event.message}</b><small>{event.status === "open" ? "확인 대기" : event.status === "acknowledged" ? "관리자 확인" : "처리 완료"}</small></span><time>{dateText(event.created_at)}</time></li>)}</ul> : <p>새로운 알림이 없습니다.</p>}</section></>}
        {tab === "me" && <><div className="worker-intro"><span>MY PROFILE</span><h1>내 정보</h1></div><section className="worker-card"><h3>{data.worker.worker_name}</h3><dl className="assignment-info"><dt>배정 현장</dt><dd>{data.worker.site_name}</dd><dt>소속</dt><dd>{data.worker.organization || "미등록"}</dd><dt>배정 팀</dt><dd>{data.worker.team}</dd><dt>직책</dt><dd>{data.worker.job_title}</dd><dt>작업자 ID</dt><dd>{data.worker.worker_id}</dd></dl></section>{eligibility}<section className="worker-card"><h3>내 장치</h3><ul className="worker-list">{data.devices.map(device => <li key={device.device_id}><span><b>{device.device_type === "assistant_device" ? "안전모" : "위치 태그"}</b><small>{device.device_id} · {device.online ? "연결됨" : "연결 확인 필요"}</small></span><span>{typeof device.battery === "number" ? `${Math.round(device.battery)}%` : "잔량 확인 불가"}</span></li>)}</ul></section><button className="worker-logout" onClick={() => void onLogout()}>로그아웃</button></>}
      </>}
    </main>
    <div className="worker-sos"><button onClick={() => void sendSos()} disabled={sosState === "sending"}>SOS <span>긴급 도움 요청</span></button>{sosState !== "idle" && <p role="status">{sosState === "sending" ? "전송 중…" : sosState === "failed" ? "전송 실패 · 관리자에게 전화하거나 다시 시도하세요." : latestSos?.status === "resolved" ? "관리자가 상황을 종료했습니다." : latestSos?.status === "acknowledged" ? "관리자가 확인했습니다." : "서버 접수 완료 · 관리자 확인 대기"}</p>}</div>
    </div>
    {checklist && <div className="worker-modal-backdrop"><section className="worker-checklist" role="dialog" aria-modal="true" aria-labelledby="checklist-title"><h2 id="checklist-title">⚠ 잠깐! 안전장비를 확인하세요</h2><p>작업 시작 전 모두 착용하셨나요?</p>{([['helmet', '안전모 착용·고정 확인'], ['vest', '작업 조끼 착용'], ['glove', '장갑 착용']] as const).map(([key, label], i) => <label key={key}><input autoFocus={i === 0} type="checkbox" checked={checks[key]} onChange={e => setChecks({...checks, [key]: e.target.checked})}/>{label}</label>)}{error && <p role="alert">{error}</p>}<div className="worker-actions"><button disabled={busy || !checks.helmet || !checks.vest || !checks.glove} onClick={() => void workAction("start")}>{busy ? "저장 중" : "확인하고 작업 시작"}</button><button disabled={busy} onClick={() => setChecklist(false)}>취소</button></div></section></div>}
  </div>;
}
