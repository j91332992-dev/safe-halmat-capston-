import {useEffect, useState} from "react";
import {api} from "../services/api";
import type {Worker, Zone} from "../types";

interface Props {
  workers: Worker[];
  zones: Zone[];
  onSaved: () => Promise<void>;
}

interface DraftProfile {
  worker_name: string;
  worker_role: Worker["worker_role"];
  notes: string;
}

export function WorkerManagement({workers, zones, onSaved}: Props) {
  const [drafts, setDrafts] = useState<Record<string, DraftProfile>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    setDrafts(current => Object.fromEntries(workers.map(worker => [
      worker.worker_id,
      current[worker.worker_id] ?? {worker_name: worker.worker_name, worker_role: worker.worker_role, notes: worker.notes ?? ""}
    ])));
  }, [workers]);

  const save = async (worker: Worker) => {
    const draft = drafts[worker.worker_id];
    const name = draft?.worker_name.trim();
    if (!name) {
      setMessage("작업자 이름을 입력하세요.");
      return;
    }
    setSavingId(worker.worker_id);
    try {
      await api.updateWorkerProfile(worker.worker_id, name, draft.worker_role, draft.notes);
      await onSaved();
      setMessage(name + " 작업자 정보를 저장했습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "작업자 정보 저장에 실패했습니다.");
    } finally {
      setSavingId(null);
    }
  };

  const change = (workerId: string, patch: Partial<DraftProfile>) =>
    setDrafts(current => ({...current, [workerId]: {...current[workerId], ...patch}}));

  return (
    <section className="page-panel worker-management">
      <header><div><span className="eyebrow">WORKER & HELMET</span><h2>작업자·안전모 관리</h2></div><span>등록 작업자 {workers.length}명</span></header>
      <p className="page-intro">작업자 ID는 TAG 통신 연결에 사용하므로 유지하고, 표시 이름과 현장 특이사항을 관리합니다.</p>
      <div className="worker-manage-list">
        {workers.map(worker => {
          const draft = drafts[worker.worker_id] ?? {worker_name: worker.worker_name, worker_role: worker.worker_role, notes: worker.notes ?? ""};
          const allowedZones = zones.filter(zone => zone.allowed_worker_ids?.includes(worker.worker_id));
          const changed = draft.worker_name.trim() !== worker.worker_name || draft.worker_role !== worker.worker_role || draft.notes.trim() !== (worker.notes ?? "");
          return (
            <article key={worker.worker_id}>
              <header className="worker-card-head">
                <div className="worker-avatar">{worker.worker_name.slice(0, 1)}</div>
                <div className="worker-identifiers"><b>{worker.worker_id}</b><span>안전모 {worker.helmet_id}</span></div>
                <span className={"level level-" + worker.risk_level}>{worker.risk_level} · {worker.risk_score}점</span>
              </header>
              <div className="worker-live-summary">
                <span>현재 위치 <b>{worker.x.toFixed(2)}, {worker.y.toFixed(2)}m</b></span>
                <span>위치 신뢰도 <b>{Math.round(worker.confidence * 100)}%</b></span>
                <span>마지막 갱신 <b>{new Date(worker.updated_at).toLocaleTimeString("ko-KR")}</b></span>
              </div>
              <div className="worker-profile-form">
                <label>표시 이름<input value={draft.worker_name} onChange={event => change(worker.worker_id, {worker_name: event.target.value})} /></label>
                <label>작업 역할<select value={draft.worker_role} onChange={event => change(worker.worker_id, {worker_role: event.target.value as Worker["worker_role"]})}><option value="general_worker">일반작업자</option><option value="manager">관리자</option><option value="hot_work_authorized">화기인가자</option><option value="heavy_equipment_operator">중장비운전자</option><option value="unauthorized">비인가자</option></select></label>
                <label>특이사항·주의사항<textarea rows={4} placeholder="예: 고소 작업 교육 이수, 특정 구역 접근 시 관리자 동행 필요" value={draft.notes} onChange={event => change(worker.worker_id, {notes: event.target.value})} /></label>
              </div>
              <div className="worker-zone-access"><b>출입 허용 제한구역</b>{allowedZones.length ? allowedZones.map(zone => <span key={zone.zone_id}>{zone.zone_name}</span>) : <em>지정된 구역 없음</em>}</div>
              <button className="worker-save" disabled={savingId === worker.worker_id || !changed} onClick={() => void save(worker)}>{savingId === worker.worker_id ? "저장 중…" : "작업자 정보 저장"}</button>
            </article>
          );
        })}
      </div>
      {message && <div className="editor-message">{message}</div>}
      <div className="worker-hardware-note"><b>새 작업자 추가 준비</b><span>새 안전모 TAG가 생기면 고유 TAG ID와 worker/helmet/device ID를 설정해 펌웨어를 최초 한 번 업로드합니다.</span></div>
    </section>
  );
}






