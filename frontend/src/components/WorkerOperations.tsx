import {useEffect, useState} from "react";
import {operationsApi} from "../services/api";
import type {Operations, Qualification} from "../services/api";
import {TeamChat} from "./TeamChat";

export function WorkerOperations({workerId, showChat = true}: {workerId: string; showChat?: boolean}) {
  const [data, setData] = useState<Operations | null>(null);
  const [items, setItems] = useState<Qualification[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {let active = true; void operationsApi.get(workerId).then(value => {if (active) {setData(value); setItems(value.eligibility.items);}}).catch(() => {if (active) setMessage("배정 정보를 불러오지 못했습니다.");}); return () => {active = false;};}, [workerId]);
  const save = async () => {
    if (!data) return; setBusy(true);
    try {const value = await operationsApi.save(workerId, {...data, qualifications: items.map(q => ({...q, expires_on: q.expires_on || null}))}); setData(value); setItems(value.eligibility.items); setMessage("소속·배정·교육·허가 조건을 저장했습니다.");}
    catch (e) {setMessage(e instanceof Error ? e.message : "저장 실패");} finally {setBusy(false);}
  };
  const change = (index: number, patch: Partial<Qualification>) => setItems(current => current.map((q, i) => i === index ? {...q, ...patch} : q));
  return <div className="worker-operations-editor">{message && <p role="status">{message}</p>}{data && <><div className="worker-profile-form">{([['organization', '소속 회사'], ['team', '배정 팀'], ['job_title', '직책 (예: 현장반장)']] as const).map(([key, label]) => <label key={key}>{label}<input maxLength={key === 'organization' ? 100 : 80} value={data[key]} onChange={e => setData({...data, [key]: e.target.value})}/></label>)}</div>
    <h3>교육 이수·작업 허가 조건</h3><p>필수 항목이 미이수·미승인 또는 만료이면 작업 시작과 재개가 제한됩니다.</p>
    {items.map((q, i) => <fieldset key={i} className="qualification-editor"><legend>{i + 1}. 교육 / 허가</legend><label>구분<select value={q.kind} onChange={e => change(i, {kind: e.target.value as Qualification['kind']})}><option value="education">교육</option><option value="permit">작업 허가</option></select></label><label>이름<input maxLength={100} value={q.name} onChange={e => change(i, {name: e.target.value})}/></label><label>유효기간 (비우면 기한 없음)<input type="date" value={q.expires_on ?? ''} onChange={e => change(i, {expires_on: e.target.value || null})}/></label><label><input type="checkbox" checked={q.required} onChange={e => change(i, {required: e.target.checked})}/>작업에 필수</label><label><input type="checkbox" checked={q.completed} onChange={e => change(i, {completed: e.target.checked})}/>교육 이수 / 작업 승인 완료</label><button onClick={() => setItems(rows => rows.filter((_, j) => j !== i))}>항목 삭제</button></fieldset>)}
    <button onClick={() => setItems(rows => [...rows, {kind: 'education', name: '', required: true, completed: false, expires_on: null}])} disabled={items.length >= 50}>교육·허가 항목 추가</button><button className="worker-save" disabled={busy} onClick={() => void save()}>{busy ? '저장 중' : '배정·작업 조건 저장'}</button>
    {showChat && <TeamChat workerId={workerId}/>}</>}</div>;
}
