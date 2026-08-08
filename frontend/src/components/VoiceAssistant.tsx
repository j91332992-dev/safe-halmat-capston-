import {useMemo, useState} from "react";
import {api} from "../services/api";
import type {Device, VoiceResponse, Worker} from "../types";

interface Props {workers: Worker[]; devices: Device[]; onRefresh: () => void}
const suggestions = ["현재 위험도 알려줘", "내 위치 알려줘", "관리자 호출해줘", "도와줘"];

export function VoiceAssistant({workers, devices, onRefresh}: Props) {
  const [workerId, setWorkerId] = useState(workers[0]?.worker_id ?? "");
  const [text, setText] = useState(suggestions[0]);
  const [result, setResult] = useState<VoiceResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const worker = workers.find(item => item.worker_id === workerId) ?? workers[0];
  const device = useMemo(() => devices.find(item => item.worker_id === worker?.worker_id && item.device_type === "assistant_device"), [devices, worker]);

  const submit = async () => {
    if (!worker || !device || !text.trim()) return;
    setBusy(true); setError("");
    try {
      const response = await api.sendTextCommand(text.trim(), worker.worker_id, device.device_id);
      setResult(response);
      await onRefresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "음성 명령 처리에 실패했습니다.");
    } finally {setBusy(false);}
  };

  return (
    <section className="page-panel assistant-page">
      <header><div><span className="eyebrow">SAFETY VOICE AI</span><h2>음성·AI 어시스턴트</h2></div><span>실제 안전모 마이크 명령을 확인하고 관리자가 텍스트 명령을 전송할 수 있습니다.</span></header>
      <div className="assistant-grid">
        <article className="assistant-command-card">
          <label>작업자<select value={worker?.worker_id ?? ""} onChange={event => setWorkerId(event.target.value)}>{workers.map(item => <option key={item.worker_id} value={item.worker_id}>{item.worker_name}</option>)}</select></label>
          <label>관리자 텍스트 명령<textarea value={text} onChange={event => setText(event.target.value)} rows={4} placeholder="안전모로 전달할 명령을 입력하세요." /></label>
          <div className="assistant-suggestions">{suggestions.map(item => <button key={item} onClick={() => setText(item)}>{item}</button>)}</div>
          <button className="assistant-submit" disabled={busy || !device} onClick={() => void submit()}>{busy ? "처리 중..." : "명령 실행"}</button>
          {!device && <p className="assistant-error">선택 작업자에게 등록된 AV 장치가 없습니다.</p>}
          {error && <p className="assistant-error">{error}</p>}
        </article>
        <article className="assistant-response-card">
          <span className="eyebrow">RESPONSE</span>
          {result ? <>
            <h3>{result.response}</h3>
            <dl><div><dt>의도</dt><dd>{result.intent}</dd></div><div><dt>인식 신뢰도</dt><dd>{Math.round(result.confidence * 100)}%</dd></div><div><dt>안전모 명령</dt><dd>{result.speaker_command ?? "없음"}</dd></div><div><dt>실시간 전달</dt><dd>{result.delivered_connections}개 연결</dd></div></dl>
            {result.audio_url ? <p className="assistant-note">안전모용 음성이 생성되었습니다. 웹에서는 재생하지 않습니다.</p> : <p className="assistant-note">음성 생성이 불가능하면 안전모에 텍스트 명령 또는 기본 경고가 전달됩니다.</p>}
          </> : <div className="assistant-empty"><strong>투투스 대기 중</strong><span>명령을 실행하면 분류 결과, 응답, TTS가 여기에 표시됩니다.</span></div>}
        </article>
      </div>
    </section>
  );
}