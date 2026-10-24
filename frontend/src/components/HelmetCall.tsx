import {useEffect, useRef, useState} from "react";
import {api} from "../services/api";
import {getWsBaseUrl} from "../services/config";
import {CallWorkerSocket} from '../services/callWorker';

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

function makeResampler(inputRate: number) {
  let position=0,next=0,previous=0;
  return (input: Float32Array): Int16Array => {
    const output:number[]=[];
    for(let i=0;i<input.length;i++,position++) {
      while(next<=position) {
        const fraction=next-(position-1);
        const value=Math.max(-1,Math.min(1,previous+(input[i]-previous)*fraction));
        output.push(value<0?value*32768:value*32767);
        next+=inputRate/16000;
      }
      previous=input[i];
    }
    return Int16Array.from(output);
  };
}

export function HelmetCall({deviceId, workerName, disabled = false}: Props) {
  const [status, setStatus] = useState<CallStatus>("idle");
  const [listenOnly, setListenOnly] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");
  const socketRef = useRef<WebSocket | CallWorkerSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const contextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const filtersRef = useRef<BiquadFilterNode[]>([]);
  const [audioQuality, setAudioQuality] = useState("");
  const webDroppedSamples = useRef(0);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const muteRef = useRef<GainNode | null>(null);
  const pendingRef = useRef<Int16Array>(new Int16Array(0));
  const nextPlaybackRef = useRef(0);
  const closingRef = useRef(false);
  const callConnectedRef = useRef(false);
  const reconnectDeadlineRef = useRef<number | null>(null);

  const audioWatchRef = useRef<number | null>(null);
  const lastAudioRef = useRef(0);
  const audioStalledRef = useRef(false);

  const stop = (playEndTone = true) => {
    if (audioWatchRef.current !== null) window.clearInterval(audioWatchRef.current);
    audioWatchRef.current = null;
    lastAudioRef.current = 0;
    audioStalledRef.current = false;
    if (reconnectDeadlineRef.current !== null) window.clearTimeout(reconnectDeadlineRef.current);
    reconnectDeadlineRef.current = null;
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
    workletRef.current?.port.postMessage({type: 'enabled', value: false});
    if (workletRef.current) workletRef.current.port.onmessage = null;
    workletRef.current?.disconnect();
    workletRef.current = null;
    filtersRef.current.forEach(filter => filter.disconnect());
    filtersRef.current = [];
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
    setAudioQuality("");
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
    if (workletRef.current) {
      workletRef.current.port.postMessage({type: 'audio', pcm: payload}, [payload]);
      return;
    }
    const pcm = new Int16Array(payload);
    const audioBuffer = context.createBuffer(1, pcm.length, 16000);
    const channel = audioBuffer.getChannelData(0);
    for (let index = 0; index < pcm.length; index += 1) channel[index] = pcm[index] / 32768;
    const source = context.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(context.destination);
    // Never schedule a new buffer over speech already scheduled in the future.
    if (nextPlaybackRef.current > context.currentTime + 0.25) {
      webDroppedSamples.current += pcm.length;
      return;
    }
    const startAt = Math.max(context.currentTime + 0.06, nextPlaybackRef.current);
    const ramp=context.createGain();
    const gap=nextPlaybackRef.current<context.currentTime+.01;
    ramp.gain.setValueAtTime(gap?0:1,startAt);
    if(gap) ramp.gain.linearRampToValueAtTime(1,startAt+.002);
    source.disconnect();source.connect(ramp);ramp.connect(context.destination);
    source.start(startAt);
    nextPlaybackRef.current = startAt + audioBuffer.duration;
  };

  const start = async (receiveOnly = false) => {
    if (disabled || status === "requesting") return;
    if (status === "connecting" && socketRef.current) { stop(false); return; }
    if (status === "connected") {
      stop();
      return;
    }
    closingRef.current = false;
    setErrorMessage("");
    setListenOnly(receiveOnly);
    setStatus("requesting");
    try {
      if (!receiveOnly && !navigator.mediaDevices?.getUserMedia) throw new Error("MIC_INSECURE_CONTEXT");
      const stream = receiveOnly ? null : await navigator.mediaDevices.getUserMedia({
        audio: {echoCancellation: true, noiseSuppression: true, autoGainControl: true},
        video: false
      });
      streamRef.current = stream;
      const ticket = await api.callTicket(deviceId);
      const context = new AudioContext();
      contextRef.current = context;
      await context.resume();
      let worklet: AudioWorkletNode | null = null;
      webDroppedSamples.current = 0;
      if (context.audioWorklet && typeof AudioWorkletNode !== 'undefined') {
        try {
          await context.audioWorklet.addModule(`${import.meta.env.BASE_URL}hanmir-call-worklet.js`);
          worklet = new AudioWorkletNode(context,'hanmir-call',{numberOfInputs:1,numberOfOutputs:1,outputChannelCount:[1]});
          const rxHigh=context.createBiquadFilter(),rxLow=context.createBiquadFilter();
          rxHigh.type='highpass';rxHigh.frequency.value=80;rxHigh.Q.value=.707;
          rxLow.type='lowpass';rxLow.frequency.value=6000;rxLow.Q.value=.707;
          worklet.connect(rxHigh);rxHigh.connect(rxLow);rxLow.connect(context.destination);
          filtersRef.current.push(rxHigh,rxLow);
          workletRef.current = worklet;
        } catch (error) {console.warn('Call AudioWorklet unavailable; using short-block fallback',error);}
      }
      const processor = !worklet && stream ? context.createScriptProcessor(512, 1, 1) : null;
      if (stream && (processor || worklet)) {
        const source = context.createMediaStreamSource(stream);
        const highpass=context.createBiquadFilter(),lowpass=context.createBiquadFilter();
        highpass.type='highpass';highpass.frequency.value=80;highpass.Q.value=.707;
        lowpass.type='lowpass';lowpass.frequency.value=6500;lowpass.Q.value=.707;
        source.connect(highpass);highpass.connect(lowpass);
        filtersRef.current.push(highpass,lowpass);
        if(worklet) lowpass.connect(worklet);
        else if(processor) {
          const mute=context.createGain();mute.gain.value=0;
          lowpass.connect(processor);processor.connect(mute);mute.connect(context.destination);
          muteRef.current=mute;
        }
        sourceRef.current = source;
        processorRef.current = processor;
      }

      const wsBase = getWsBaseUrl();
      const url=`${wsBase}/ws/call/operator/${encodeURIComponent(deviceId)}?ticket=${encodeURIComponent(ticket.ticket)}`;
      const socket=worklet && typeof Worker!=='undefined' ? new CallWorkerSocket(url,worklet,n=>{webDroppedSamples.current=n;}) : new WebSocket(url);
      socket.binaryType = "arraybuffer";
      socketRef.current = socket;
      setStatus("connecting");
      const resampleMic=makeResampler(context.sampleRate);

      if(worklet) worklet.port.onmessage=event=>{
        if (closingRef.current || socketRef.current!==socket) return;
        if(event.data.type==='mic') {
          const pcm=event.data.pcm as ArrayBuffer;
          if(socket.readyState===WebSocket.OPEN && callConnectedRef.current) {
            if(socket.bufferedAmount<=640*4) socket.send(pcm);
            else webDroppedSamples.current+=pcm.byteLength/2;
          }
        } else if(event.data.type==='stats') {
          const stats={...event.data,webDroppedSamples:webDroppedSamples.current};
          setAudioQuality(`재생 버퍼 ${Math.round(stats.queueMs)}ms · 재생 큐 폐기 ${Math.round(stats.overflowSamples/16)}ms`);
          console.info('Hanmir call quality',stats);
          if(socket.readyState===WebSocket.OPEN) socket.send(JSON.stringify({type:'call_audio_metrics',metrics:stats}));
        }
      };

      if (processor) processor.onaudioprocess = event => {
        if (socket.readyState !== WebSocket.OPEN || closingRef.current || !callConnectedRef.current) return;
        if (socket.bufferedAmount > 640 * 4) {
          webDroppedSamples.current += pendingRef.current.length + Math.round(event.inputBuffer.length*16000/context.sampleRate);
          pendingRef.current = new Int16Array(0);
          return;
        }
        const current = resampleMic(event.inputBuffer.getChannelData(0));
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

      // PCM arrives even during silence; OPEN alone does not establish device health.
      lastAudioRef.current = performance.now();
      audioWatchRef.current = window.setInterval(() => {
        if (closingRef.current || socketRef.current !== socket) return;
        const gap = performance.now() - lastAudioRef.current;
        if (gap >= 3000 && !audioStalledRef.current) {
          audioStalledRef.current = true;
          setStatus("connecting");
          setErrorMessage("안전모 음성 수신이 3초 이상 멈췄습니다. 연결 복구 중 · 버튼을 누르면 종료");
          console.warn("Helmet audio stalled", {gapMs: Math.round(gap)});
        }
        if (gap >= 10000) {
          stop(false);
          setErrorMessage("안전모 음성이 10초 동안 수신되지 않아 통화를 종료했습니다.");
          setStatus("error");
        }
      }, 500);

      socket.onmessage = event => {
        if (socketRef.current !== socket || closingRef.current) return;
        if (typeof event.data !== "string") {
          if (!(event.data instanceof ArrayBuffer) || event.data.byteLength < 2 || event.data.byteLength % 2) return;
          lastAudioRef.current = performance.now();
          if (reconnectDeadlineRef.current !== null) window.clearTimeout(reconnectDeadlineRef.current);
          reconnectDeadlineRef.current = null;
          if (audioStalledRef.current) {
            audioStalledRef.current = false;
            callConnectedRef.current = true;
            setStatus("connected");
            setErrorMessage("");
            console.info("Helmet audio recovered");
          }
          playHelmetAudio(event.data as ArrayBuffer);
          return;
        }
        const message = JSON.parse(event.data) as {type?: string; status?: string};
        if(message.type==='call_audio_tick'){
          lastAudioRef.current=performance.now();
          if(audioStalledRef.current){audioStalledRef.current=false;callConnectedRef.current=true;setStatus('connected');setErrorMessage('');}
          return;
        }
        if (message.type !== "call_status") return;
        if (message.status === "connected") {
          if (reconnectDeadlineRef.current !== null) window.clearTimeout(reconnectDeadlineRef.current);
          reconnectDeadlineRef.current = null;
          pendingRef.current = new Int16Array(0);
          nextPlaybackRef.current = 0;
          if (!audioStalledRef.current) setErrorMessage("");
          if (!callConnectedRef.current && contextRef.current) playCallTone(contextRef.current, "connected");
          callConnectedRef.current = true;
          if(!(socket instanceof CallWorkerSocket))workletRef.current?.port.postMessage({type:'enabled',value:true});
          if (!audioStalledRef.current) setStatus("connected");
        }
        else if (message.status === "ended") stop();
        else if (message.status === "device_offline") {
          workletRef.current?.port.postMessage({type:'enabled',value:false});
          callConnectedRef.current = false;
          pendingRef.current = new Int16Array(0);
          setStatus("connecting");
          setErrorMessage("안전모 통화 채널 재연결을 기다립니다. 최대 10초");
          if (reconnectDeadlineRef.current === null) reconnectDeadlineRef.current = window.setTimeout(() => {
            stop(false);
            setStatus("offline");
          }, 10000);
        }
        else if (message.status === "busy") { stop(false); setStatus("busy"); }
        else if (message.status === "unauthorized") { stop(false); setErrorMessage("통화 인증이 만료됐습니다. 다시 연결하세요."); setStatus("error"); }
      };
      socket.onerror = () => { stop(false); setErrorMessage("통화 서버에 연결하지 못했습니다. 앱의 서버 주소와 Wi-Fi를 확인하세요."); setStatus("error"); };
      socket.onclose = () => {
        if (!closingRef.current) { stop(false); setErrorMessage("통화 연결이 끊겼습니다. 다시 연결하세요."); setStatus("error"); }
      };
    } catch (error) {
      console.error("Helmet call failed", error);
      stop();
      const message = error instanceof Error ? error.message : "";
      if (message.includes("통화 채널이 오프라인")) setStatus("offline");
      else {
        setErrorMessage(message === "MIC_INSECURE_CONTEXT" ? "웹 마이크는 HTTPS 또는 localhost에서 사용할 수 있습니다. PC는 localhost:5174로 접속하세요."
          : error instanceof DOMException && error.name === "NotAllowedError" ? "마이크 권한을 허용한 뒤 다시 연결하세요."
          : error instanceof DOMException && error.name === "NotFoundError" ? "사용할 마이크가 없습니다. 마이크 연결을 확인하세요."
          : message.includes("로그인") ? "로그인이 만료됐습니다. 다시 로그인하세요."
          : "통화 준비에 실패했습니다. 서버 연결과 마이크 상태를 확인하세요.");
        setStatus("error");
      }
    }
  };

  const elapsed = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  return (
    <div className={`helmet-call helmet-call-${status}`}>
      <button type="button" disabled={disabled} onClick={() => void start()}>
        <span>{status === "connected" ? "■" : "☎"}</span>
        {statusText[status]}
      </button>
      {status === "connected" && <small>{workerName} · {elapsed} · {listenOnly ? "듣기 전용 · 내 목소리는 전송되지 않음" : "양방향"}</small>}
      {status === 'connected' && audioQuality && <small>{audioQuality}</small>}
      {status === "error" && errorMessage.includes("마이크") && <button type="button" disabled={disabled} onClick={() => void start(true)}>안전모 소리만 듣기</button>}
      {status === "connecting" && errorMessage && <small>{errorMessage}</small>}
      {status === "offline" && <small>안전모 통화 채널이 끊겼습니다. 전원·Wi-Fi를 확인한 뒤 다시 연결하세요.</small>}
      {status === "busy" && <small>현재 다른 관리자와 연결되어 있습니다.</small>}
      {status === "error" && <small>{errorMessage || "통화 연결에 실패했습니다. 다시 연결하세요."}</small>}
    </div>
  );
}

