export type RiskLevel = "정상" | "관심" | "주의" | "위험" | "비상";

export interface Worker {
  worker_id: string;
  worker_name: string;
  helmet_id: string;
  x: number;
  y: number;
  confidence: number;
  current_zone: string | null;
  risk_score: number;
  risk_level: RiskLevel;
  risk_reasons: {reason: string; points: number}[];
  ppe: {vest?: boolean; glove?: boolean};
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

export interface Zone {
  zone_id: string;
  zone_name: string;
  zone_type: string;
  coordinates: {x: number; y: number; width?: number; height?: number; radius?: number};
  required_ppe: string[];
  risk_weight: number;
  warning_message: string;
  active: boolean;
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
  zones: Zone[];
  events: SafetyEvent[];
}

