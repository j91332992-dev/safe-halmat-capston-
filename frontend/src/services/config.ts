import {Capacitor} from "@capacitor/core";

const STORAGE_KEY = "hanmir_server_url";

export function isCapacitorNative(): boolean {
  return Capacitor.isNativePlatform();
}

export function getStoredServerUrl(): string {
  if (typeof window === "undefined") return "";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored && stored.trim().length > 0) {
    return stored.trim();
  }

  // 1. Env configured URL
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl && envUrl.trim().length > 0) {
    return envUrl.trim();
  }

  // 2. A native app cannot infer the PC's LAN address safely.  The operator
  // chooses it once in the in-app server settings and it is then kept locally.
  if (isCapacitorNative()) {
    return "";
  }

  // 3. Browser environment: use relative or origin
  return "";
}

export function setStoredServerUrl(url: string): void {
  if (typeof window === "undefined") return;
  const cleaned = url.trim().replace(/\/+$/, "");
  localStorage.setItem(STORAGE_KEY, cleaned);
}

export function getServerBaseUrl(): string {
  const custom = getStoredServerUrl();
  if (custom) return custom.replace(/\/+$/, "");
  return "";
}

export function getWsBaseUrl(): string {
  const envWs = import.meta.env.VITE_WS_URL;
  if (envWs && envWs.trim().length > 0) {
    return envWs.trim().replace(/\/+$/, "");
  }

  const base = getServerBaseUrl();
  if (base) {
    // Convert http/https to ws/wss
    return base.replace(/^http:/i, "ws:").replace(/^https:/i, "wss:");
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}`;
}
