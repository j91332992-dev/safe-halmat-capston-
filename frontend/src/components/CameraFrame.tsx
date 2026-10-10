import {useEffect, useState} from "react";
import {api} from "../services/api";

// Metadata requests remain active while NO FRAME is displayed. Image requests
// only happen for a new frame, so a stopped helmet cannot cause a 404 loop.
export function CameraFrame({deviceId, alt}: {deviceId?: string; alt: string}) {
  const [frame, setFrame] = useState<{deviceId: string; src: string} | null>(null);
  useEffect(() => {
    setFrame(null);
    if (!deviceId) return;
    let active = true;
    let token = "";
    let misses = 0;
    let pending: HTMLImageElement | null = null;
    const miss = () => {
      if (++misses >= 3 && active) {
        setFrame(null);
        if (pending) { pending.onload = null; pending.onerror = null; pending = null; }
      }
    };
    const poll = async () => {
      try {
        const data = await api.latestCamera(deviceId);
        if (!active) return;
        const next = data.received ? `${data.filename ?? ""}:${data.analyzed_at ?? ""}:${data.frame_id ?? ""}` : "";
        if (!next || next === token) { miss(); return; }
        token = next;
        misses = 0;
        if (pending) { pending.onload = null; pending.onerror = null; }
        const image = new Image();
        pending = image;
        image.onload = () => { if (active && pending === image) setFrame({deviceId, src: image.src}); };
        image.onerror = () => { if (active && pending === image) setFrame(null); };
        image.src = api.cameraImageUrl(deviceId, next);
      } catch { if (active) miss(); }
    };
    // Schedule after completion to avoid overlapping requests on a slow server.
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => { await poll(); if (active) timer = setTimeout(() => void tick(), 1000); };
    void tick();
    return () => {
      active = false;
      clearTimeout(timer);
      if (pending) { pending.onload = null; pending.onerror = null; }
    };
  }, [deviceId]);
  return frame && frame.deviceId === deviceId
    ? <img src={frame.src} alt={alt} />
    : <div className="camera-placeholder"><strong>No Frame</strong><span>수신된 카메라 화면이 없습니다. 새 프레임 수신 시 자동으로 표시됩니다.</span></div>;
}
