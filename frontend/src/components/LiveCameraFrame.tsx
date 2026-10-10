import {useEffect, useState} from "react";
import {api} from "../services/api";
import {isCapacitorNative} from "../services/config";
import {loadCameraImage, releaseCameraImage} from "../services/cameraImage";

export function LiveCameraFrame({deviceId}: {deviceId: string}) {
  const [frame, setFrame] = useState<{deviceId: string; src: string} | null>(null);
  useEffect(() => {
    if (!isCapacitorNative()) return;
    let active = true;
    let visible = "";
    let lastFrame = -1;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const latest = await api.liveCamera(deviceId);
        if (latest.received && (latest.age_ms ?? Infinity) < 3000 && latest.frame_id !== lastFrame) {
          const src = await loadCameraImage(api.liveCameraImageUrl(deviceId, latest.frame_id));
          if (!active) { releaseCameraImage(src); return; }
          const old = visible;
          visible = src;
          lastFrame = latest.frame_id ?? -1;
          setFrame({deviceId, src});
          releaseCameraImage(old);
        } else if (!latest.received || (latest.age_ms ?? Infinity) >= 3000) {
          setFrame(null);
        }
      } catch { if (active) setFrame(null); }
      // One request at a time, with no growing queue on slow mobile Wi-Fi.
      if (active) timer = setTimeout(() => void poll(), 200);
    };
    void poll();
    return () => { active = false; clearTimeout(timer); releaseCameraImage(visible); };
  }, [deviceId]);
  if (!isCapacitorNative()) return <img src={api.liveCameraStreamUrl(deviceId)} alt="안전모 카메라 원본 영상" />;
  return frame?.deviceId === deviceId ? <img src={frame.src} alt="안전모 카메라 원본 영상" />
    : <div className="camera-placeholder"><strong>영상 수신 대기</strong><span>안전모 카메라 이미지를 불러오는 중입니다.</span></div>;
}
