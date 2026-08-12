import {useEffect, useState} from "react";
import {api} from "../services/api";
import type {Device, Worker} from "../types";
import {StatusPill} from "./StatusPill";

interface Props {worker: Worker; devices: Device[]; onRefresh: () => void}

export function WorkerDetail({worker, devices, onRefresh}: Props) {
  const av = devices.find(device => device.device_type === "assistant_device");
  const [cameraVersion, setCameraVersion] = useState(Date.now());
  useEffect(() => {
    if (!av?.device_id) return;
    const timer = window.setInterval(() => setCameraVersion(Date.now()), 1000 / 6);
    return () => window.clearInterval(timer);
  }, [av?.device_id]);
  const uwb = devices.find(device => device.device_type === "position_device");
  const sendAlert = async () => {await api.sendAlert(av?.device_id); await onRefresh();};
  return (
    <aside className="worker-detail">
      <div className="detail-head">
        <div><span className="eyebrow">WORKER STATUS</span><h2>{worker.worker_name}</h2><p>{worker.worker_id} · {worker.helmet_id}</p></div>
        <div className={`risk-orb risk-${worker.risk_level}`}><strong>{worker.risk_score}</strong><span>{worker.risk_level}</span></div>
      </div>
      <div className="detail-grid">
        <div><span>현재 위치</span><strong>X {worker.x.toFixed(1)} · Y {worker.y.toFixed(1)}m</strong></div>
        <div><span>위치 신뢰도</span><strong>{Math.round(worker.confidence * 100)}%</strong></div>
        <div><span>현재 구역</span><strong>{worker.current_zone ?? "안전구역"}</strong></div>
        <div><span>보호구</span><strong>안전모 {worker.ppe.helmet === false ? "미착용" : worker.ppe.helmet === true ? "착용" : "판정 보류"} · 조끼 {worker.ppe.vest === false ? "미착용" : worker.ppe.vest === true ? "착용" : "판정 보류"} · 장갑 {worker.ppe.glove === false ? "미착용" : worker.ppe.glove === true ? "착용" : "판정 보류"}</strong></div>
      </div>
      {av?.last_camera_at && <section className="worker-camera-mini"><div className="section-title"><h3>안전모 카메라</h3><span>{new Date(av.last_camera_at).toLocaleTimeString("ko-KR")}</span></div><img src={api.cameraImageUrl(av.device_id, cameraVersion)} alt={`${worker.worker_name} 최신 카메라 프레임`} /></section>}
      <section>
        <div className="section-title"><h3>위험도 근거</h3><span>{worker.risk_reasons.length}개</span></div>
        <div className="reason-list">{worker.risk_reasons.length ? worker.risk_reasons.map(item => <div key={item.reason}><span>{item.reason}</span><b>+{item.points}</b></div>) : <p className="empty">감지된 위험 요인이 없습니다.</p>}</div>
      </section>
      <section>
        <div className="section-title"><h3>장치 연결</h3></div>
        <div className="device-mini">
          <div><span>AV 장치</span><StatusPill active={Boolean(av?.online)} activeText="온라인" inactiveText="오프라인" /></div>
          <div><span>UWB 태그</span><StatusPill active={Boolean(uwb?.online)} activeText="온라인" inactiveText="오프라인" /></div>
        </div>
      </section>
      <button className="alert-button" onClick={() => void sendAlert()}><span>!</span> 안전모에 경고 보내기</button>
    </aside>
  );
}
