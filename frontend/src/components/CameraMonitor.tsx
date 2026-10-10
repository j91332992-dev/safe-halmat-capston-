import {CameraFrame} from "./CameraFrame";
import {LiveCameraFrame} from "./LiveCameraFrame";
import {useEffect, useMemo, useState} from "react";
import {api} from "../services/api";
import type {Device, Worker} from "../types";
import {StatusPill} from "./StatusPill";
import {elapsedTime} from "../utils/elapsedTime";

interface Props {workers: Worker[]; devices: Device[]}

export function CameraMonitor({workers, devices}: Props) {
  const avDevices = devices.filter(device => device.device_type === "assistant_device");
  const [deviceId, setDeviceId] = useState(avDevices[0]?.device_id ?? "");
  const [latest, setLatest] = useState<import("../types").CameraLatest | null>(null);
  const [live, setLive] = useState<{received: boolean; frame_id?: number; age_ms?: number} | null>(null);
  const selected = avDevices.find(device => device.device_id === deviceId) ?? avDevices[0];
  const worker = useMemo(() => workers.find(item => item.worker_id === selected?.worker_id), [workers, selected]);

  useEffect(() => {
    if (!deviceId && avDevices[0]) setDeviceId(avDevices[0].device_id);
  }, [avDevices, deviceId]);
  useEffect(() => {
    if (!selected?.device_id) { setLatest(null); return; }
    let active = true;
    const load = () => api.latestCamera(selected.device_id).then(data => {
      if (!active) return;
      setLatest(data);
    }).catch(() => { if (active) setLatest(null); });
    load();
    const timer = window.setInterval(load, 1000);
    return () => { active = false; window.clearInterval(timer); };
  }, [selected?.device_id]);
  useEffect(() => {
    setLive(null);
    if (!selected?.device_id) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { const value = await api.liveCamera(selected.device_id); if (active) setLive(value); }
      catch { if (active) setLive(null); }
      if (active) timer = setTimeout(() => void poll(), 500);
    };
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [selected?.device_id]);
  const judgement = latest?.analysis?.ppe_judgement;
  const observedPpe = latest?.analysis?.ppe ?? worker?.hazards.observed_person_ppe ?? {};
  const ppeLabel = (item: "helmet" | "vest" | "glove") => {
    if (!judgement || !judgement.active) return "판정 보류";
    if (observedPpe[item] === false) return "미착용";
    if (observedPpe[item] === true) return "착용";
    return "판정 중";
  };
  const ppeClass = (item: "helmet" | "vest" | "glove") => observedPpe[item] === false && judgement?.active ? "bad" : "good";

  return (
    <section className="page-panel camera-page">
      <header>
        <div><span className="eyebrow">YOLO CAMERA</span><h2>안전모 카메라 관제</h2></div>
        <div className="camera-toolbar">
          <select value={selected?.device_id ?? ""} onChange={event => setDeviceId(event.target.value)}>
            {avDevices.map(device => <option key={device.device_id} value={device.device_id}>{device.worker_id} · {device.device_id}</option>)}
          </select>
          <button onClick={() => { if (selected) void api.latestCamera(selected.device_id).then(setLatest); }}>분석 새로고침</button>
        </div>
      </header>
      {!selected ? <p className="empty">등록된 AV 장치가 없습니다.</p> : (
        <div className="camera-monitor-grid">
          <article className="camera-live-card">
            <div className="camera-card-head"><b>실시간 원본 영상</b><StatusPill active={Boolean(live?.received && (live.age_ms ?? Infinity) < 3000)} activeText="새 프레임 수신 중" inactiveText="영상 정지" /></div>
            {live?.received && (live.age_ms ?? Infinity) < 3000 ? <LiveCameraFrame deviceId={selected.device_id} /> : <div className="camera-placeholder"><strong>NO LIVE FRAME</strong><span>최근 3초 동안 새 원본 프레임이 없습니다.</span></div>}
            <small>원본 프레임 {live?.frame_id ?? "확인 불가"} · 수신 후 {live?.age_ms ?? "-"}ms</small>
          </article>
          <article className="camera-live-card">
            <div className="camera-card-head"><b>최근 분석 화면</b><StatusPill active={selected.online} activeText="카메라 온라인" inactiveText="카메라 오프라인" /></div>
            <CameraFrame deviceId={selected.device_id} alt={`${worker?.worker_name ?? selected.worker_id} 카메라 최신 프레임`} />
            <small>마지막 수신: {elapsedTime(selected.last_camera_at)}</small>
          </article>
          <article className="camera-analysis-card">
            <span className="eyebrow">WORKER DETECTION</span>
            <h3>안전모 착용자가 바라보는 전방 작업자</h3>
            <div className="detection-list">
              <div><span>PPE 판정</span><b className={judgement?.active ? "good" : ""}>{judgement?.active ? "전방 사람 추적 중" : "전방 사람 없음 · 판정 보류"}</b></div>
              <div><span>안전모</span><b className={ppeClass("helmet")}>{ppeLabel("helmet")}</b></div>
              <div><span>안전조끼</span><b className={ppeClass("vest")}>{ppeLabel("vest")}</b></div>
              <div><span>장갑</span><b className={ppeClass("glove")}>{ppeLabel("glove")}</b></div>
              <div><span>화재</span><b className={worker?.hazards.fire ? "bad" : "good"}>{worker?.hazards.fire ? "감지 · 관리자 경고" : `확인 중 ${Number(worker?.hazards.fire_confirm_frames ?? 0)}/3`}</b></div>
              <div><span>연기</span><b className={worker?.hazards.smoke ? "bad" : "good"}>{worker?.hazards.smoke ? "감지" : "없음"}</b></div>
            </div>
            <small>기준: 실제 YOLO 처리 프레임에서 사람이 검출되고 같은 장비가 {judgement?.missing_frames_required ?? 3}프레임 연속 보이지 않을 때 전방 작업자 미착용 확정 · PPE confidence 45% 이상</small>
            <div className={`camera-risk level-${worker?.risk_level ?? "정상"}`}><span>통합 위험도</span><strong>{worker?.risk_score ?? 0}점 · {worker?.risk_level ?? "정상"}</strong></div>
          </article>
        </div>
      )}
    </section>
  );
}
