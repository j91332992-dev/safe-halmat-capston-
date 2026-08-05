import type {Anchor, CameraLatest, LayoutDraft, LayoutVersion, LocationPoint, Obstacle, Snapshot, VoiceResponse, Worker, Zone} from "../types";

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
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  updateWorkerProfile: (workerId: string, worker_name: string, notes: string) => request<Worker>("/api/workers/" + encodeURIComponent(workerId), {method: "PUT", body: JSON.stringify({worker_name, notes})}),
  snapshot: () => request<Snapshot>("/api/dashboard/snapshot"),
  locationHistory: (workerId: string, limit = 300) =>
    request<LocationPoint[]>(`/api/locations/${workerId}/history?limit=${limit}`),
  layoutDraft: () => request<LayoutDraft>("/api/layout/draft"),
  layoutVersions: () => request<LayoutVersion[]>("/api/layout/versions"),
  createLayoutVersion: (name: string) => request<LayoutVersion>("/api/layout/versions", {method: "POST", body: JSON.stringify({name})}),
  loadLayoutVersion: (versionId: string) => request<LayoutDraft>("/api/layout/versions/" + encodeURIComponent(versionId) + "/load", {method: "POST"}),
  deleteLayoutVersion: (versionId: string) => request<void>("/api/layout/versions/" + encodeURIComponent(versionId), {method: "DELETE"}),
  saveLayoutDraft: (draft: Omit<LayoutDraft, "saved_at">) =>
    request<{saved: boolean; saved_at: string}>("/api/layout/draft", {method: "PUT", body: JSON.stringify(draft)}),
  applyLayoutDraft: () =>
    request<{applied: boolean}>("/api/layout/apply", {method: "POST"}),
  createZone: (zone: Zone) =>
    request<Zone>("/api/zones", {method: "POST", body: JSON.stringify(zone)}),
  updateZone: (zone: Zone) =>
    request<Zone>("/api/zones/" + encodeURIComponent(zone.zone_id), {method: "PUT", body: JSON.stringify(zone)}),
  deleteZone: (zoneId: string) =>
    request<void>("/api/zones/" + encodeURIComponent(zoneId), {method: "DELETE"}),
  updateSite: (site: {name: string; width: number; height: number}) =>
    request("/api/layout/site", {method: "PUT", body: JSON.stringify(site)}),
  updateAnchor: (anchor: Anchor) =>
    request<Anchor>("/api/anchors/" + encodeURIComponent(anchor.anchor_id), {method: "PUT", body: JSON.stringify(anchor)}),
  createObstacle: (obstacle: Obstacle) =>
    request<Obstacle>("/api/layout/obstacles", {method: "POST", body: JSON.stringify(obstacle)}),
  updateObstacle: (obstacle: Obstacle) =>
    request<Obstacle>("/api/layout/obstacles/" + encodeURIComponent(obstacle.obstacle_id), {method: "PUT", body: JSON.stringify(obstacle)}),
  deleteObstacle: (obstacleId: string) =>
    request<void>("/api/layout/obstacles/" + encodeURIComponent(obstacleId), {method: "DELETE"}),
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
  mockVoice: (text: string, workerId = "worker-001", deviceId = "helmet-001-av") =>
    request<VoiceResponse>("/api/audio/mock-command", {
      method: "POST",
      body: JSON.stringify({worker_id: workerId, device_id: deviceId, text})
    }),
  latestCamera: (deviceId: string) => request<CameraLatest>(`/api/camera/${encodeURIComponent(deviceId)}/latest`),
  cameraImageUrl: (deviceId: string, version: string | number = Date.now()) =>
    `${API_URL}/api/camera/${encodeURIComponent(deviceId)}/latest/image?v=${encodeURIComponent(String(version))}`,
  assetUrl: (path: string) => `${API_URL}${path}`,
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

