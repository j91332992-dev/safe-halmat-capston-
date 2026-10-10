import type {Anchor, Device, CameraLatest, EvacuationSnapshot, FireZone, LayoutDraft, LayoutVersion, LocationPoint, Obstacle, Snapshot, VoiceResponse, Worker, Zone} from "../types";
import {getServerBaseUrl} from "./config";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const baseUrl = getServerBaseUrl();
  const token = sessionStorage.getItem(ADMIN_TOKEN_KEY);
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {"Content-Type": "application/json", ...(token ? {Authorization: `Bearer ${token}`} : {}), ...options?.headers},
    ...options
  });
  if (!response.ok) {
    if (response.status === 401 && token) {
      sessionStorage.removeItem(ADMIN_TOKEN_KEY);
      window.dispatchEvent(new Event("hanmir-auth-expired"));
    }
    const body = await response.text();
    let message = body;
    try {
      const parsed = JSON.parse(body) as {detail?: unknown};
      if (typeof parsed.detail === "string") message = parsed.detail;
    } catch { /* The server returned plain text. */ }
    throw new Error(message || `요청 실패: ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const ADMIN_TOKEN_KEY = "hanmir_admin_session";

export const auth = {
  hasSession: () => Boolean(sessionStorage.getItem(ADMIN_TOKEN_KEY)),
  getToken: () => sessionStorage.getItem(ADMIN_TOKEN_KEY),
  login: async (username: string, password: string) => {
    const response = await request<{token: string; username: string; role: string; site_id: string; worker_id?: string}>("/api/auth/login", {method: "POST", body: JSON.stringify({username, password})});
    sessionStorage.setItem(ADMIN_TOKEN_KEY, response.token);
    return response;
  },
  signup: (username: string, password: string, inviteCode: string) =>
    request<{username: string; worker_id: string; site_id: string}>("/api/auth/signup", {method: "POST", body: JSON.stringify({username, password, invite_code: inviteCode})}),
  createWorkerInvite: (workerId: string) =>
    request<{worker_id: string; invite_code: string; expires_in_hours: number}>(`/api/auth/worker-invites/${encodeURIComponent(workerId)}`, {method: "POST"}),
  usernameAvailable: (username: string) =>
    request<{username: string; available: boolean; reason?: string}>(`/api/auth/username-available?username=${encodeURIComponent(username)}`),
  register: async (username: string, password: string, siteName: string) => {
    const response = await request<{token: string; username: string; role: string; site_id: string}>("/api/auth/register", {method: "POST", body: JSON.stringify({username, password, site_name: siteName})});
    sessionStorage.setItem(ADMIN_TOKEN_KEY, response.token);
    return response;
  },
  session: () => request<{username: string; role: string; site_id: string; worker_id?: string}>("/api/auth/session", {headers: {Authorization: `Bearer ${sessionStorage.getItem(ADMIN_TOKEN_KEY) ?? ""}`}}),
  logout: async () => {
    const token = sessionStorage.getItem(ADMIN_TOKEN_KEY);
    sessionStorage.removeItem(ADMIN_TOKEN_KEY);
    if (token) await request("/api/auth/logout", {method: "POST", headers: {Authorization: `Bearer ${token}`}}).catch(() => {});
  }
};

export interface WorkSummary {state: "off" | "working" | "break"; today_seconds: number; today_break_seconds: number; server_now: string; history: {kind: string; created_at: string}[]}
export interface Qualification {qualification_id?: string; kind: "education" | "permit"; name: string; required: boolean; completed: boolean; expires_on: string | null; valid?: boolean}
export interface Eligibility {items: Qualification[]; can_work: boolean; reasons: string[]}
export interface Operations {organization: string; team: string; job_title: string; eligibility: Eligibility; work: WorkSummary}
export interface ChatMessage {message_id: number; sender_id: string; sender_name: string; content: string; created_at: string}
export interface ChatData {team: string; messages: ChatMessage[]}
export interface CalendarDay {date: string; seconds: number; break_seconds: number; records: {kind: string; created_at: string}[]; intervals: {start: string; end: string}[]; break_intervals: {start: string; end: string}[]}
export interface WorkerCalendar {month: string; timezone: string; days: CalendarDay[]}
export interface WorkerMapData {site: {name: string; width: number; height: number}; obstacles: {name: string; object_type: string; x: number; y: number; width: number; height: number}[]; zones: {zone_name: string; coordinates: {x: number; y: number; width?: number; height?: number; radius?: number; points?: {x: number; y: number}[]}; zone_category: string; zone_type: string; active: boolean}[]}
export interface WorkerAppData {
  worker: {worker_id: string; worker_name: string; site_name: string; organization: string; team: string; job_title: string; current_zone: string | null; x: number; y: number; confidence: number; risk_level: string; emergency: boolean; updated_at: string};
  devices: Device[];
  events: {event_id: string; event_type: string; message: string; severity: string; status: string; created_at: string}[];
  work: WorkSummary;
  eligibility: Eligibility;
}

export const workerApi = {
  callManager: () => request("/api/worker-app/call-manager", {method: "POST"}),
  me: () => request<WorkerAppData>("/api/worker-app/me"),
  work: (kind: "start" | "break_start" | "break_end" | "end", checklist?: {helmet: boolean; vest: boolean; glove: boolean}) => request<{ok: boolean; work: WorkSummary}>(`/api/worker-app/work/${kind}`, {method: "POST", body: JSON.stringify(checklist ?? null)}),
  calendar: (month: string) => request<WorkerCalendar>(`/api/worker-app/calendar?month=${encodeURIComponent(month)}`),
  map: () => request<WorkerMapData>("/api/worker-app/map"),
  chat: (before?: number) => request<ChatData>(`/api/worker-app/chat${before ? `?before=${before}` : ""}`),
  sendChat: (content: string) => request("/api/worker-app/chat", {method: "POST", body: JSON.stringify({content})}),
  sos: () => request<{event_id: string; status: string}>("/api/worker-app/sos", {method: "POST"})
};

export const operationsApi = {
  get: (id: string) => request<Operations>(`/api/workers/${encodeURIComponent(id)}/operations`),
  save: (id: string, data: {organization: string; team: string; job_title: string; qualifications: Qualification[]}) => request<Operations>(`/api/workers/${encodeURIComponent(id)}/operations`, {method: "PUT", body: JSON.stringify(data)}),
  chat: (id: string, before?: number) => request<ChatData>(`/api/workers/${encodeURIComponent(id)}/chat${before ? `?before=${before}` : ""}`),
  sendChat: (id: string, content: string) => request(`/api/workers/${encodeURIComponent(id)}/chat`, {method: "POST", body: JSON.stringify({content})})
};

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
  calibrateHeading: (deviceId: string) =>
    request<Device>(`/api/devices/${encodeURIComponent(deviceId)}/heading-calibration`, {method: "POST", body: JSON.stringify({anchor_ids: ["anchor-001", "anchor-004"]})}),
  sendTextCommand: (text: string, workerId = "worker-001", deviceId = "helmet-001-av") =>
    request<VoiceResponse>("/api/audio/command", {
      method: "POST",
      body: JSON.stringify({worker_id: workerId, device_id: deviceId, text})
    }),
  latestCamera: (deviceId: string) => request<CameraLatest>(`/api/camera/${encodeURIComponent(deviceId)}/latest`),
  liveCamera: (deviceId: string) => request<{device_id: string; received: boolean; frame_id?: number; age_ms?: number}>(`/api/camera/${encodeURIComponent(deviceId)}/live`),
  liveCameraStreamUrl: (deviceId: string) => `${getServerBaseUrl()}/api/camera/${encodeURIComponent(deviceId)}/live/mjpeg?token=${encodeURIComponent(auth.getToken() ?? "")}`,
  liveCameraImageUrl: (deviceId: string, version: string | number = Date.now()) =>
    `${getServerBaseUrl()}/api/camera/${encodeURIComponent(deviceId)}/live/image?v=${encodeURIComponent(String(version))}`,
  cameraImageUrl: (deviceId: string, version: string | number = Date.now()) =>
    `${getServerBaseUrl()}/api/camera/${encodeURIComponent(deviceId)}/latest/image?v=${encodeURIComponent(String(version))}`,
  assetUrl: (path: string) => `${getServerBaseUrl()}${path}`,
  acknowledge: (eventId: string) => request(`/api/events/${eventId}/acknowledge`, {method: "POST"}),
  resolve: (eventId: string) => request(`/api/events/${eventId}/resolve`, {method: "POST"}),
  resolveAllEvents: () => request<{resolved_count: number}>("/api/events/resolve-all", {method: "POST"})
};
