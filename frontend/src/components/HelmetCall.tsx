import {useEffect, useRef, useState} from "react";
import {api} from "../services/api";

type CallStatus = "idle" | "requesting" | "connecting" | "connected" | "offline" | "busy" | "error";

interface Props {
  deviceId: string;
  workerName: string;
  disabled?: boolean;
}

const statusText: Record<CallStatus, string> = {
  idle: "통화 연결",
  requesting: "연결 준비 중",
  connecting: "안전모 연결 중",
  connected: "통화 종료",
  offline: "안전모 오프라인",
  busy: "다른 관리자 통화 중",
  error: "연결 다시 시도"
};

type CallTone = "connected" | "ended";

function playCallTone(context: AudioContext, tone: CallTone) {
  if (context.state === "closed") return;
  const notes = tone === "connected"
    ? [{frequency: 1480, start: 0, duration: 0.18}]
    : [{frequency: 1100, start: 0, duration: 0.12}, {frequency: 650, start: 0.17, duration: 0.22}];
  const now = context.currentTime + 0.02;
  for (const note of notes) {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    const startsAt = now + note.start;
    const endsAt = startsAt + note.duration;
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(note.frequency, startsAt);
    gain.gain.setValueAtTime(0.0001, startsAt);
    gain.gain.exponentialRampToValueAtTime(0.12, startsAt + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, endsAt);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start(startsAt);
    oscillator.stop(endsAt + 0.01);
  }
}

function resample(input: Float32Array, inputRate: number, outputRate = 16000): Int16Array {
  const outputLength = Math.max(1, Math.round(input.length * outputRate / inputRate));
  const output = new Int16Array(outputLength);
  for (let index = 0; index < outputLength; index += 1) {
    const position = index * inputRate / outputRate;
    const left = Math.floor(position);
    const right = Math.min(input.length - 1, left + 1);
    const mix = position - left;
    const value = Math.max(-1, Math.min(1, input[left] * (1 - mix) + input[right] * mix));
    output[index] = value < 0 ? value * 32768 : value * 32767;
  }
  return output;
}

export function HelmetCall({deviceId, workerName, disabled = false}: Props) {
  const [status, setStatus] = useState<CallStatus>("idle");
  const [seconds, setSeconds] = useState(0);
  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const muteRef = useRef<GainNode | null>(null);
  const pendingRef = useRef<Int16Array>(new Int16Array(0));
  const nextPlaybackRef = useRef(0);
  const closingRef = useRef(false);
  const callConnectedRef = useRef(false);

  const stop = (playEndTone = true) => {
    const context = contextRef.current;
    const shouldPlayEndTone = playEndTone && callConnectedRef.current;
    callConnectedRef.current = false;
    closingRef.current = true;
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send('{"type":"call_stop"}');
    }
    socket?.close();
    socketRef.current = null;
    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    muteRef.current?.disconnect();
    streamRef.current?.getTracks().forEach(track => track.stop());
    if (context && context.state !== "closed") {
      if (shouldPlayEndTone) {
        playCallTone(context, "ended");
        window.setTimeout(() => {
          if (context.state !== "closed") void context.close();
        }, 550);
      } else {
        void context.close();
      }
    }
    processorRef.current = null;
    sourceRef.current = null;
    muteRef.current = null;
    streamRef.current = null;
    contextRef.current = null;
    pendingRef.current = new Int16Array(0);
    nextPlaybackRef.current = 0;
    setSeconds(0);
    setStatus("idle");
  };

  useEffect(() => () => stop(false), []);

  useEffect(() => {
    if (status !== "connected") return;
    const timer = window.setInterval(() => setSeconds(value => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [status]);

  const playHelmetAudio = (payload: ArrayBuffer) => {
    const context = contextRef.current;
    if (!context || payload.byteLength < 2) return;
    const pcm = new Int16Array(payload);
    const audioBuffer = context.createBuffer(1, pcm.length, 16000);
    const channel = audioBuffer.getChannelData(0);
    for (let index = 0; index < pcm.length; index += 1) channel[index] = pcm[index] / 32768;
    const source = context.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(context.destination);
    if (nextPlaybackRef.current > context.currentTime + 0.25) nextPlaybackRef.current = context.currentTime + 0.04;
    const startAt = Math.max(context.currentTime + 0.04, nextPlaybackRef.current);
    source.start(startAt);
    nextPlaybackRef.current = startAt + audioBuffer.duration;
  };

  const start = async () => {
    if (disabled || status === "requesting" || status === "connecting") return;
    if (status === "connected") {
      stop();
      return;
    }
    closingRef.current = false;
    setStatus("requesting");
    try {
      const ticket = await api.callTicket(deviceId);
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true},
        video: false
      });
      const context = new AudioContext();
      await context.resume();
      const source = context.createMediaStreamSource(stream);
      const processor = context.createScriptProcessor(2048, 1, 1);
      const mute = context.createGain();
      mute.gain.value = 0;
      source.connect(processor);
      processor.connect(mute);
      mute.connect(context.destination);

      streamRef.current = stream;
      contextRef.current = context;
      sourceRef.current = source;
      processorRef.current = processor;
      muteRef.current = mute;

      const configured = import.meta.env.VITE_WS_URL;
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const wsBase = configured ?? `${protocol}://${window.location.host}`;
      const socket = new WebSocket(`${wsBase}/ws/call/operator/${encodeURIComponent(deviceId)}?ticket=${encodeURIComponent(ticket.ticket)}`);
      socket.binaryType = "arraybuffer";
      socketRef.current = socket;
      setStatus("connecting");

      processor.onaudioprocess = event => {
        if (socket.readyState !== WebSocket.OPEN || closingRef.current) return;
        if (socket.bufferedAmount > 640 * 4) {
          pendingRef.current = new Int16Array(0);
          return;
        }
        const current = resample(event.inputBuffer.getChannelData(0), context.sampleRate);
        const combined = new Int16Array(pendingRef.current.length + current.length);
        combined.set(pendingRef.current);
        combined.set(current, pendingRef.current.length);
        let offset = 0;
        while (combined.length - offset >= 320) {
          const frame = combined.slice(offset, offset + 320);
          socket.send(frame.buffer);
          offset += 320;
        }
        pendingRef.current = combined.slice(offset);
      };

      socket.onmessage = event => {
        if (typeof event.data !== "string") {
          playHelmetAudio(event.data as ArrayBuffer);
          return;
        }
        const message = JSON.parse(event.data) as {type?: string; status?: string};
        if (message.type !== "call_status") return;
        if (message.status === "connected") {
          if (!callConnectedRef.current && contextRef.current) playCallTone(contextRef.current, "connected");
          callConnectedRef.current = true;
          setStatus("connected");
        }
        else if (message.status === "ended") stop();
        else if (message.status === "device_offline") setStatus("offline");
        else if (message.status === "busy") setStatus("busy");
        else if (message.status === "unauthorized") setStatus("error");
      };
      socket.onerror = () => setStatus("error");
      socket.onclose = () => {
        if (!closingRef.current) setStatus(current => current === "busy" || current === "offline" ? current : "error");
      };
    } catch (error) {
      console.error("Helmet call failed", error);
      stop();
      setStatus("error");
    }
  };

  const elapsed = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  return (
    <div className={`helmet-call helmet-call-${status}`}>
      <button type="button" disabled={disabled} onClick={() => void start()}>
        <span>{status === "connected" ? "■" : "☎"}</span>
        {statusText[status]}
      </button>
      {status === "connected" && <small>{workerName} · {elapsed} · 양방향</small>}
      {status === "offline" && <small>안전모 전원과 Wi-Fi를 확인하세요.</small>}
      {status === "busy" && <small>현재 다른 관리자와 연결되어 있습니다.</small>}
      {status === "error" && <small>마이크 권한 또는 서버 연결을 확인하세요.</small>}
    </div>
  );
}
