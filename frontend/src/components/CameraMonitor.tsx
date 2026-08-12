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
  const [latest, setLatest] = useState<import("../types").CameraLatest | null>(null);
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
    }, 1000 / 8);
    return () => window.clearInterval(timer);
  }, [selected?.device_id]);
  useEffect(() => {
    if (!selected?.device_id) { setLatest(null); return; }
    let active = true;
    const load = () => api.latestCamera(selected.device_id).then(data => {
      if (active) setLatest(data);
    }).catch(() => { if (active) setLatest(null); });
    load();
    const timer = window.setInterval(load, 1000);
    return () => { active = false; window.clearInterval(timer); };
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
