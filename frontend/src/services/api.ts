import type {Snapshot} from "../types";

const API_URL = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: {"Content-Type": "application/json", ...options?.headers},
    ...options
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `요청 실패: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  snapshot: () => request<Snapshot>("/api/dashboard/snapshot"),
  setMode: (mode: "mock" | "hardware") =>
    request<{mode: string}>("/api/system/mode", {method: "POST", body: JSON.stringify({mode})}),
  runScenario: (scenario: string) =>
    request("/api/system/mock/scenario", {
      method: "POST",
      body: JSON.stringify({scenario, worker_id: "worker-001"})
    }),
  sendAlert: (deviceId = "helmet-001-av") =>
    request(`/api/devices/${deviceId}/command`, {
      method: "POST",
      body: JSON.stringify({command_type: "play_alert", payload: {message: "관리자 경고"}})
    }),
  mockVoice: (text: string) =>
    request("/api/audio/mock-command", {
      method: "POST",
      body: JSON.stringify({worker_id: "worker-001", device_id: "helmet-001-av", text})
    }),
  mockButton: (event_type: string) =>
    request("/api/button-event", {
      method: "POST",
      body: JSON.stringify({
        organization_id: "org-001",
        site_id: "site-001",
        worker_id: "worker-001",
        helmet_id: "helmet-001",
        device_id: "helmet-001-av",
        event_type
      })
    }),
  acknowledge: (eventId: string) => request(`/api/events/${eventId}/acknowledge`, {method: "POST"}),
  resolve: (eventId: string) => request(`/api/events/${eventId}/resolve`, {method: "POST"})
};

