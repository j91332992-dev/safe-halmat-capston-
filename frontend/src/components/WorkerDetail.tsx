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
  const quality = worker.position_status?.quality_status;
  const positionReason: Record<string, string> = {insufficient_anchors: "사용 가능한 앵커 부족", singular_geometry: "앵커 배치 불안정", nonconverged: "위치 계산 수렴 실패", high_residual: "거리와 위치 불일치", speed_exceeded: "속도 검사 초과", measurement_clock_unavailable: "측정 시각 없음", solve_failed: "위치 계산 실패"};
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
        <div><span>마지막 유효 위치</span><strong>{worker.position_status === undefined ? "정보 없음" : worker.position_status.last_valid_age_seconds == null ? "확인 전" : `${worker.position_status.last_valid_age_seconds.toFixed(1)}초 전`}</strong></div>
        {worker.position_status?.last_valid_position && <div><span>마지막 유효 좌표</span><strong>X {worker.position_status.last_valid_position.x.toFixed(1)} · Y {worker.position_status.last_valid_position.y.toFixed(1)}m</strong></div>}
        <div><span>위치 검사</span><strong>{worker.position_status?.accepted === true ? "통과" : worker.position_status?.accepted === false ? (worker.position_status.mode === "observe" ? "관찰 중 · 판정 보류" : "갱신 보류") : "확인 대기"}</strong></div>
        {quality && <div><span>UWB 거리 사용{quality.mode === "observe" ? " · 관찰 모드" : ""}</span><strong>{quality.used_anchor_count}개 사용 · {quality.excluded_anchor_ids.length}개 제외</strong></div>}
        {worker.position_status?.accepted === false && <div><span>위치 보류 사유</span><strong>{positionReason[worker.position_status.reason ?? ""] ?? "위치 확인 중"}</strong></div>}
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
