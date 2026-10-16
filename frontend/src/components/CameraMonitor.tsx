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
  const [performanceStats, setPerformanceStats] = useState<{receive: number | null; yolo: number | null; detail: number | null; ping: number; inference: number; detailMs: number} | null>(null);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let previous: Awaited<ReturnType<typeof api.cameraPerformance>> | null = null;
    const poll = async () => {
      const started = performance.now();
      try {
        const value = await api.cameraPerformance();
        if (!active) return;
        const seconds = previous ? value.sampled_at_seconds - previous.sampled_at_seconds : 0;
        const rate = (key: 'received_frames' | 'analysis_completed' | 'detail_completed') =>
          previous && seconds > 0 && value[key] >= previous[key] ? (value[key]-previous[key])/seconds : null;
        setPerformanceStats({receive: rate('received_frames'), yolo: rate('analysis_completed'), detail: rate('detail_completed'),
          ping: performance.now()-started, inference: value.last_inference_ms, detailMs: value.detail_last_ms});
        previous = value;
      } catch { if (active) { setPerformanceStats(null); previous = null; } }
      if (active) timer = setTimeout(() => void poll(), 2000);
    };
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, []);
  const formatMetric = (value: number | null | undefined, unit: string) => value != null && Number.isFinite(value) ? `${value.toFixed(1)} ${unit}` : '측정 중';
  const selected = avDevices.find(device => device.device_id === deviceId) ?? avDevices[0];
  const worker = useMemo(() => workers.find(item => item.worker_id === selected?.worker_id), [workers, selected]);

  useEffect(() => {
    if (!deviceId && avDevices[0]) setDeviceId(avDevices[0].device_id);
  }, [avDevices, deviceId]);
  useEffect(() => {
    if (!selected?.device_id) { setLatest(null); return; }
    setLatest(null);
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const load = () => api.latestCamera(selected.device_id).then(data => {
      if (!active) return;
      setLatest(data);
    }).catch(() => { if (active) setLatest(null); });
    const poll = async () => { await load(); if (active) timer = setTimeout(() => void poll(), 1000); };
    void poll();
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
  const detail = latest?.analysis?.detail_evidence;
  const analysisFresh = Boolean(latest?.received && latest.analyzed_at
    && Date.now() - Date.parse(latest.analyzed_at) < 3000
    && live?.received && (live.age_ms ?? Infinity) < 3000);
  const evidenceLabel = (item: string) => {
    if (!analysisFresh) return "";
    const fresh = [...(latest?.analysis?.detections ?? []), ...(detail?.valid ? detail.detections : [])]
      .filter(d => d.category === item && d.positive !== false && typeof d.confidence === "number")
      .sort((a,b) => (b.confidence ?? 0) - (a.confidence ?? 0))[0];
    if (!fresh) return " · 유효 검출 대기";
    const assisted = fresh.red_pixel_ratio != null || fresh.class?.includes("red");
    return ` · ${assisted ? "색상 보조 점수" : "검출 신뢰도"} ${Math.round((fresh.confidence ?? 0)*100)}%`;
  };
  const observedPpe = analysisFresh ? latest?.analysis?.ppe ?? {} : {};
  const ppeLabel = (item: "helmet" | "vest" | "glove") => {
    if (!analysisFresh) return "확인 불가";
    if (observedPpe[item] === true) return "착용 중";
    if (observedPpe[item] === false && judgement?.active) return "미착용";
    return "분석 대기";
  };
  const ppeClass = (item: "helmet" | "vest" | "glove") => observedPpe[item] === true ? "good"
    : observedPpe[item] === false && judgement?.active ? "bad" : "pending";

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
            <div className="camera-card-head"><b>실시간 영상</b><StatusPill active={Boolean(live?.received && (live.age_ms ?? Infinity) < 3000)} activeText="새 프레임 수신 중" inactiveText="영상 정지" /></div>
            {live?.received && (live.age_ms ?? Infinity) < 3000 ? <LiveCameraFrame deviceId={selected.device_id} /> : <div className="camera-placeholder"><strong>NO LIVE FRAME</strong><span>최근 3초 동안 새 원본 프레임이 없습니다.</span></div>}
            <small>원본 프레임 {live?.frame_id ?? "확인 불가"} · 수신 후 {live?.age_ms ?? "-"}ms</small>
          </article>
          <article className="camera-live-card">
            <div className="camera-card-head"><b>최근 분석 화면</b><StatusPill active={selected.online} activeText="카메라 온라인" inactiveText="카메라 오프라인" /></div>
            <CameraFrame deviceId={selected.device_id} detailed alt={`${worker?.worker_name ?? selected.worker_id} 보호구 검출 박스`} />
            <small>박스 색상: person 사람 초록 / helmet 안전모 노랑 / vest 조끼 파랑 / glove 장갑 보라 · 숫자: 검출 점수</small>
            <div className="camera-performance" aria-label="영상 처리 성능">
              <div><span>영상 수신</span><strong>{formatMetric(performanceStats?.receive, 'FPS')}</strong></div>
              <div><span>YOLO 분석</span><strong>{formatMetric(performanceStats?.yolo, 'FPS')}</strong></div>
              <div><span>보호구 상세 분석</span><strong>{formatMetric(performanceStats?.detail, 'FPS')}</strong></div>
              <div><span>서버 응답 (왕복)</span><strong>{formatMetric(performanceStats?.ping, 'ms')}</strong></div>
              <div><span>YOLO 처리 시간</span><strong>{formatMetric(performanceStats?.inference, 'ms')}</strong></div>
              <div><span>상세 처리 시간</span><strong>{formatMetric(performanceStats?.detailMs, 'ms')}</strong></div>
            </div>
            <small>서버 전체 · 최근 약 2초 구간 FPS · 응답 시간은 브라우저↔서버 HTTP 왕복 시간입니다.</small>
            <small>마지막 수신: {elapsedTime(selected.last_camera_at)}</small>
          </article>
          <article className="camera-analysis-card">
            <span className="eyebrow">WORKER DETECTION</span>
            <h3>안전모 착용자가 바라보는 전방 작업자</h3>
            <div className="detection-list">
              <div><span>PPE 판정</span><b className={judgement?.active ? "good" : ""}>{judgement?.active ? "전방 사람 추적 중" : latest?.analysis?.person_seen ? "사람 감지 · 상세 분석 대기" : "전방 사람 없음 · 판정 보류"}</b></div>
              <div><span>안전모</span><b className={ppeClass("helmet")}>{ppeLabel("helmet")}{evidenceLabel("helmet")}</b></div>
              <div><span>안전조끼</span><b className={ppeClass("vest")}>{ppeLabel("vest")}{evidenceLabel("vest")}</b></div>
              <div><span>장갑</span><b className={ppeClass("glove")}>{ppeLabel("glove")}{evidenceLabel("glove")}</b></div>
              <div><span>화재</span><b className={worker?.hazards.fire ? "bad" : "good"}>{worker?.hazards.fire ? "감지 · 관리자 경고" : `확인 중 ${Number(worker?.hazards.fire_confirm_frames ?? 0)}/3`}</b></div>
              <div><span>연기</span><b className={worker?.hazards.smoke ? "bad" : "good"}>{worker?.hazards.smoke ? "감지" : "없음"}</b></div>
            </div>
            <small>상세 결과 경과: {detail?.age_ms != null ? `${Math.round(detail.age_ms)}ms` : "확인 불가"} · 장비별 신뢰도 기준 적용. 신뢰도·색상 보조 점수는 실제 정확도가 아닙니다. 유효한 상세 분석에서 {judgement?.missing_frames_required ?? 3}회 연속 미검출되면 미착용으로 판정합니다.</small>
            <div className={`camera-risk level-${worker?.risk_level ?? "정상"}`}><span>통합 위험도</span><strong>{worker?.risk_score ?? 0}점 · {worker?.risk_level ?? "정상"}</strong></div>
          </article>
        </div>
      )}
    </section>
  );
}
