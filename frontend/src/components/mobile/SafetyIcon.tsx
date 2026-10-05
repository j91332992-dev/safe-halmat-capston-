import type {ReactNode} from "react";

export type SafetyIconName = "shield" | "alert" | "bell" | "map" | "camera" | "worker" | "battery" | "signal" | "voice" | "history" | "settings" | "grid";
export function SafetyIcon({name}: {name: SafetyIconName}) {
  const paths: Record<SafetyIconName, ReactNode> = {
    shield: <><path d="m12 3 8 3v5c0 5-4 8-8 10-4-2-8-5-8-10V6Z"/><path d="m8 12 3 3 5-6"/></>,
    alert: <><path d="m12 3 10 18H2Z"/><path d="M12 9v5m0 3v1"/></>,
    bell: <><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10 21h4"/></>,
    map: <><path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2ZM9 3v16M15 5v16"/></>,
    camera: <><path d="m8 7 2-3h4l2 3h5v13H3V7Z"/><circle cx="12" cy="13" r="3"/></>,
    worker: <><circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></>,
    battery: <><rect x="2" y="6" width="18" height="12" rx="3"/><path d="M23 10v4M6 10v4M10 10v4M14 10v4"/></>,
    signal: <><path d="M3 8a15 15 0 0 1 18 0M6 12a10 10 0 0 1 12 0M9 16a5 5 0 0 1 6 0"/><circle cx="12" cy="20" r="1"/></>,
    voice: <><rect x="9" y="2" width="6" height="13" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8"/></>,
    history: <><path d="M3 11a9 9 0 1 1 2 7M3 3v8h8M12 7v5l3 2"/></>,
    settings: <><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 1v3M12 20v3M1 12h3M20 12h3"/></>,
    grid: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>
  };
  return <svg className="safety-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
