import {useState} from "react";
import type {Worker} from "../types";
import {TeamChat} from "./TeamChat";
import {WorkerOperations} from "./WorkerOperations";

export function AdminTeamPage({workers, mode}: {workers: Worker[]; mode: "chat" | "permissions"}) {
  const [workerId, setWorkerId] = useState(workers[0]?.worker_id ?? "");
  const selected = workers.find(worker => worker.worker_id === workerId) ?? workers[0];
  return <section className="page-panel admin-team-page"><header><div><span className="eyebrow">TEAM OPERATIONS</span><h2>{mode === "chat" ? "팀 채팅" : "교육·작업 허가"}</h2></div></header>
    <p>{mode === "chat" ? "작업자를 선택하면 해당 작업자의 배정 팀 대화에 참여합니다." : "작업자를 선택해 교육 이수·작업 승인·유효기간과 필수 조건을 관리하세요."}</p>
    <label className="admin-worker-selector">작업자 선택<select value={selected?.worker_id ?? ""} onChange={event => setWorkerId(event.target.value)}>{workers.map(worker => <option value={worker.worker_id} key={worker.worker_id}>{worker.worker_name} · {worker.worker_id}</option>)}</select></label>
    {selected ? mode === "chat" ? <TeamChat key={selected.worker_id} workerId={selected.worker_id}/> : <WorkerOperations key={selected.worker_id} workerId={selected.worker_id} showChat={false}/> : <p>등록된 작업자가 없습니다.</p>}
  </section>;
}
