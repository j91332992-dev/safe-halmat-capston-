import type {Anchor, CameraLatest, EvacuationSnapshot, FireZone, LayoutDraft, LayoutVersion, LocationPoint, Obstacle, Snapshot, VoiceResponse, Worker, Zone} from "../types";

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
  updateWorkerProfile: (workerId: string, worker_name: string, worker_role: Worker["worker_role"], notes: string) => request<Worker>("/api/workers/" + encodeURIComponent(workerId), {method: "PUT", body: JSON.stringify({worker_name, worker_role, notes})}),
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
  confirmFireZone: (incidentId: string, zone: FireZone) =>
    request<EvacuationSnapshot>("/api/evacuation/" + encodeURIComponent(incidentId) + "/confirm-zone", {method: "POST", body: JSON.stringify(zone)}),
  cancelFire: (incidentId: string, reason: "false_alarm" | "no_fire" | "resolved") =>
    request<EvacuationSnapshot>("/api/evacuation/" + encodeURIComponent(incidentId) + "/cancel", {method: "POST", body: JSON.stringify({reason})}),
  triggerFire: (workerId: string, source: "manager" | "voice" | "yolo" = "manager") =>
    request<EvacuationSnapshot>("/api/evacuation/trigger", {method: "POST", body: JSON.stringify({worker_id: workerId, source, details: {manual: source === "manager"}})}),
  callTicket: (deviceId: string) => request<{device_id: string; ticket: string; expires_in: number}>(`/api/calls/${encodeURIComponent(deviceId)}/ticket`, {method: "POST"}),
  sendAlert: (deviceId = "helmet-001-av") =>
    request(`/api/devices/${deviceId}/command`, {
      method: "POST",
      body: JSON.stringify({command_type: "play_alert", payload: {message: "관리자 경고"}})
    }),
  speakerTest: (deviceId: string) =>
    request<{ok: boolean}>(`/api/diagnostics/${encodeURIComponent(deviceId)}/speaker-test`, {method: "POST"}),
  sendTextCommand: (text: string, workerId = "worker-001", deviceId = "helmet-001-av") =>
    request<VoiceResponse>("/api/audio/command", {
      method: "POST",
      body: JSON.stringify({worker_id: workerId, device_id: deviceId, text})
    }),
  latestCamera: (deviceId: string) => request<CameraLatest>(`/api/camera/${encodeURIComponent(deviceId)}/latest`),
  cameraImageUrl: (deviceId: string, version: string | number = Date.now()) =>
    `${API_URL}/api/camera/${encodeURIComponent(deviceId)}/latest/image?v=${encodeURIComponent(String(version))}`,
  assetUrl: (path: string) => `${API_URL}${path}`,
  acknowledge: (eventId: string) => request(`/api/events/${eventId}/acknowledge`, {method: "POST"}),
  resolve: (eventId: string) => request(`/api/events/${eventId}/resolve`, {method: "POST"})
};


