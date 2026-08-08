import {useEffect, useMemo, useState} from "react";
import {api} from "../services/api";
import type {Device, Worker} from "../types";
import {StatusPill} from "./StatusPill";

interface Props {workers: Worker[]; devices: Device[]}

export function CameraMonitor({workers, devices}: Props) {
  const avDevices = devices.filter(device => device.device_type === "assistant_device");
  const [deviceId, setDeviceId] = useState(avDevices[0]?.device_id ?? "");
  const [imageVersion, setImageVersion] = useState(Date.now());
  const [imageError, setImageError] = useState(false);
  const selected = avDevices.find(device => device.device_id === deviceId) ?? avDevices[0];
  const worker = useMemo(() => workers.find(item => item.worker_id === selected?.worker_id), [workers, selected]);

  useEffect(() => {
    if (!deviceId && avDevices[0]) setDeviceId(avDevices[0].device_id);
  }, [avDevices, deviceId]);
  useEffect(() => {
    setImageError(false);
    setImageVersion(Date.now());
  }, [selected?.last_camera_at, selected?.device_id]);
  useEffect(() => {
    if (!selected?.device_id) return;
    const timer = window.setInterval(() => {
      setImageError(false);
      setImageVersion(Date.now());
    }, 1000 / 3);
    return () => window.clearInterval(timer);
  }, [selected?.device_id]);

  return (
    <section className="page-panel camera-page">
      <header>
        <div><span className="eyebrow">YOLO CAMERA</span><h2>안전모 카메라 관제</h2></div>
        <div className="camera-toolbar">
          <select value={selected?.device_id ?? ""} onChange={event => setDeviceId(event.target.value)}>
            {avDevices.map(device => <option key={device.device_id} value={device.device_id}>{device.worker_id} · {device.device_id}</option>)}
          </select>
          <button onClick={() => {setImageError(false); setImageVersion(Date.now());}}>영상 새로고침</button>
        </div>
      </header>
      {!selected ? <p className="empty">등록된 AV 장치가 없습니다.</p> : (
        <div className="camera-monitor-grid">
          <article className="camera-live-card">
            <div className="camera-card-head"><b>최근 분석 화면</b><StatusPill active={selected.online} activeText="카메라 온라인" inactiveText="카메라 오프라인" /></div>
            {!imageError && selected.last_camera_at ? (
              <img src={api.cameraImageUrl(selected.device_id, imageVersion)} alt={`${worker?.worker_name ?? selected.worker_id} 카메라 최신 프레임`} onError={() => setImageError(true)} />
            ) : (
              <div className="camera-placeholder"><strong>NO FRAME</strong><span>ESP32 안전모 카메라에서 실제 프레임을 수신하면 표시됩니다.</span></div>
            )}
            <small>마지막 수신: {selected.last_camera_at ? new Date(selected.last_camera_at).toLocaleString("ko-KR") : "없음"}</small>
          </article>
          <article className="camera-analysis-card">
            <span className="eyebrow">WORKER DETECTION</span>
            <h3>{worker?.worker_name ?? selected.worker_id}</h3>
            <div className="detection-list">
              <div><span>안전모</span><b className={worker?.ppe.helmet === false ? "bad" : "good"}>{worker?.ppe.helmet === false ? "미착용" : "착용/정상"}</b></div>
              <div><span>안전조끼</span><b className={worker?.ppe.vest === false ? "bad" : "good"}>{worker?.ppe.vest === false ? "미착용" : "착용/정상"}</b></div>
              <div><span>장갑</span><b className={worker?.ppe.glove === false ? "bad" : "good"}>{worker?.ppe.glove === false ? "미착용" : "착용/정상"}</b></div>
              <div><span>화재</span><b className={worker?.hazards.fire ? "bad" : "good"}>{worker?.hazards.fire ? "감지" : "없음"}</b></div>
              <div><span>연기</span><b className={worker?.hazards.smoke ? "bad" : "good"}>{worker?.hazards.smoke ? "감지" : "없음"}</b></div>
            </div>
            <div className={`camera-risk level-${worker?.risk_level ?? "정상"}`}><span>통합 위험도</span><strong>{worker?.risk_score ?? 0}점 · {worker?.risk_level ?? "정상"}</strong></div>
          </article>
        </div>
      )}
    </section>
  );
}