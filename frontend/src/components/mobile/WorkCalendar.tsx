import {useEffect, useState} from "react";
import {workerApi} from "../../services/api";
import type {WorkerCalendar} from "../../services/api";

export const kstDate = () => new Intl.DateTimeFormat("en-CA", {timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit"}).format(new Date());
export const duration = (seconds: number) => `${Math.floor(seconds / 3600)}시간 ${Math.floor(seconds % 3600 / 60)}분`;
const labels: Record<string, string> = {start: "작업 시작", break_start: "휴게 시작", break_end: "작업 재개", end: "작업 종료"};
const clock = (date: string) => new Date(date).toLocaleTimeString("ko-KR", {timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit"});

export function WorkCalendar({revision}: {revision: number}) {
  const [month, setMonth] = useState(kstDate().slice(0, 7));
  const [selected, setSelected] = useState(kstDate());
  const [data, setData] = useState<WorkerCalendar | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setData(null);
    const load = async () => {
      try {const value = await workerApi.calendar(month); if (active) {setData(value); setError("");}}
      catch {if (active) setError("작업 기록을 불러오지 못했습니다.");}
    };
    void load(); const timer = window.setInterval(() => void load(), 30000);
    return () => {active = false; window.clearInterval(timer);};
  }, [month, revision]);
  const move = (delta: number) => {
    const [y, m] = month.split("-").map(Number); const d = new Date(y, m - 1 + delta, 1);
    const next = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    setMonth(next); setSelected(next + "-01");
  };
  const day = data?.days.find(row => row.date === selected);
  const [year, monthNumber] = month.split("-").map(Number);
  const offset = new Date(Date.UTC(year, monthNumber - 1, 1)).getUTCDay();
  return <section className="worker-card work-calendar"><h3>근로시간 달력</h3><div className="calendar-toolbar"><button onClick={() => move(-1)} aria-label="이전 달">‹</button><input aria-label="월 선택" type="month" value={month} onChange={e => {if (e.target.value) {setMonth(e.target.value); setSelected(e.target.value + "-01");}}}/><button onClick={() => move(1)} aria-label="다음 달">›</button></div>
    {error && <p role="alert">{error}</p>}
    <p>월 합계 · {duration(data?.days.reduce((sum, row) => sum + row.seconds, 0) ?? 0)} · 한국 시간</p>
    <div className="calendar-grid">{["일", "월", "화", "수", "목", "금", "토"].map(d => <b key={d}>{d}</b>)}{Array.from({length: offset}, (_, i) => <span key={`blank-${i}`}/>)}{data?.days.map(row => <button key={row.date} aria-pressed={selected === row.date} className={selected === row.date ? "selected" : ""} onClick={() => setSelected(row.date)}><b>{Number(row.date.slice(-2))}</b><small>{row.seconds ? `${Math.floor(row.seconds / 3600)}h ${Math.floor(row.seconds % 3600 / 60)}m` : "—"}</small></button>)}</div>
    <h3>{selected} · {duration(day?.seconds ?? 0)}</h3><ul className="worker-list">{day?.records.map((r, i) => <li key={i}><span>{labels[r.kind] ?? r.kind}</span><time>{clock(r.created_at)}</time></li>)}</ul>
    {!!day?.intervals.length && <><h4>실제 작업 구간 · 휴게 제외</h4>{day.intervals.map((r, i) => <p key={i}>{clock(r.start)} ~ {clock(r.end)} · {duration((Date.parse(r.end) - Date.parse(r.start)) / 1000)}</p>)}</>}
    {day && !day.records.length && !day.intervals.length && <p>이 날짜의 작업 기록이 없습니다.</p>}
  </section>;
}
