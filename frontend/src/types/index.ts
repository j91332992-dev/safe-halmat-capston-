export type RiskLevel = "정상" | "관심" | "주의" | "위험" | "비상";

export interface Worker {
  worker_id: string;
  worker_name: string;
  notes: string;
  helmet_id: string;
  x: number;
  y: number;
  confidence: number;
  current_zone: string | null;
  risk_score: number;
  risk_level: RiskLevel;
  risk_reasons: {reason: string; points: number}[];
  ppe: {vest?: boolean; glove?: boolean; helmet?: boolean};
  hazards: {fire?: boolean; smoke?: boolean};
  emergency: boolean;
  updated_at: string;
}

export interface Device {
  device_id: string;
  device_type: string;
  worker_id: string;
  ip: string | null;
  rssi: number | null;
  battery: number | null;
  online: boolean;
  component_status: Record<string, string>;
  last_error: string | null;
  last_seen: string;
  last_camera_at: string | null;
  last_audio_at: string | null;
  last_button_at: string | null;
  last_uwb_at: string | null;
  last_speaker_status: string | null;
}

export interface Anchor {
  anchor_id: string;
  name: string;
  x: number;
  y: number;
  z: number;
  online: boolean;
}

export interface Obstacle {
  obstacle_id: string;
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Zone {
  zone_id: string;
  zone_name: string;
  zone_type: string;
  coordinates: {x: number; y: number; width?: number; height?: number; radius?: number};
  required_ppe: string[];
  allowed_worker_ids: string[];
  risk_weight: number;
  warning_message: string;
  max_stay_seconds: number;
  active: boolean;
}


export interface LocationPoint {
  x: number;
  y: number;
  confidence: number;
  created_at: string;
}
export interface SafetyEvent {
  event_id: string;
  event_type: string;
  severity: string;
  message: string;
  worker_id: string | null;
  device_id: string | null;
  details: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface Snapshot {
  mode: "mock" | "hardware";
  site: {site_id: string; map_id: string; name: string; width: number; height: number};
  workers: Worker[];
  devices: Device[];
  anchors: Anchor[];
  obstacles: Obstacle[];
  zones: Zone[];
  events: SafetyEvent[];
}


export interface LayoutDraft {
  site: {name: string; width: number; height: number};
  anchors: Anchor[];
  obstacles: Obstacle[];
  zones: Zone[];
  saved_at?: string | null;
}
export interface LayoutVersion {
  version_id: string;
  name: string;
  created_at: string;
}
export interface VoiceResponse {
  command_id: number;
  text: string;
  intent: string;
  confidence: number;
  response: string;
  speaker_command: string | null;
  audio_url: string | null;
  delivered_connections: number;
  worker: Worker;
}

export interface CameraLatest {
  device_id: string;
  received: boolean;
  filename?: string;
  url?: string;
  analysis?: {
    mode: string;
    model: string;
    ppe: Record<string, boolean>;
    hazards: Record<string, boolean>;
    detections: unknown[];
  };
}