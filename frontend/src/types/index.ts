export type RiskLevel = "정상" | "관심" | "주의" | "위험" | "비상";

export interface Worker {
  worker_id: string;
  worker_name: string;
  worker_role: "general_worker" | "manager" | "hot_work_authorized" | "heavy_equipment_operator" | "unauthorized";
  notes: string;
  helmet_id: string;
  x: number;
  y: number;
  confidence: number;
  current_zone: string | null;
  risk_score: number;
  risk_level: RiskLevel;
  risk_reasons: {reason: string; points: number; priority?: number; code?: string; voice_message?: string; action?: string}[];
  decision: {reason: string; points: number; priority: number; code: string; voice_message: string; action: string} | null;
  ppe: {vest?: boolean | null; glove?: boolean | null; helmet?: boolean | null};
  hazards: {fire?: boolean; smoke?: boolean; fire_candidate_confidence?: number; fire_confirm_frames?: number; smoke_candidate_confidence?: number; smoke_confirm_frames?: number; ppe_subject_scope?: "observed_person"; observed_person_seen?: boolean; observed_person_ppe?: {vest?: boolean | null; glove?: boolean | null; helmet?: boolean | null}; observed_person_missing_ppe?: string[]};
  emergency: boolean;
  updated_at: string;
}

export interface Device {
  device_id: string;
  device_type: string;
  worker_id: string;
  ip: string | null;
  rssi: number | null;
  online: boolean;
  component_status: Record<string, string>;
  last_error: string | null;
  last_seen: string;
  last_camera_at: string | null;
  last_audio_at: string | null;
  last_uwb_at: string | null;
  last_speaker_status: string | null;
  last_speaker_at: string | null;
}

export interface Anchor {
  anchor_id: string;
  name: string;
  x: number;
  y: number;
  z: number;
  online: boolean;
  last_seen: string;
}

export interface Obstacle {
  obstacle_id: string;
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  object_type: "obstacle" | "wall" | "emergency_exit" | "door";
}

export interface FireZone {
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface EvacuationIncident {
  incident_id: string;
  worker_id: string | null;
  source: "voice" | "yolo" | "manager";
  status: "pending_manager" | "active" | "cancelled" | "resolved";
  fire_zone: FireZone | null;
  details: Record<string, unknown>;
  cancel_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvacuationRoute {
  worker_id: string;
  available: boolean;
  mode: "fire_unconfirmed" | "fire_confirmed";
  exit_id?: string;
  exit_name?: string;
  path: {x: number; y: number}[];
  distance_m?: number;
  instructions: string[];
  message?: string;
  fire_location_name?: string;
  fire_distance_m?: number | null;
  reason?: string;
  fire_zone?: FireZone | null;
  updated_at?: string;
}

export interface EvacuationSnapshot {
  incident: EvacuationIncident | null;
  routes: Record<string, EvacuationRoute>;
}

export interface Zone {
  zone_id: string;
  zone_name: string;
  zone_type: string;
  zone_category: "general" | "danger" | "controlled" | "confined" | "safe" | "rest" | "shadow";
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
  mode: "hardware";
  site: {site_id: string; map_id: string; name: string; width: number; height: number};
  workers: Worker[];
  devices: Device[];
  anchors: Anchor[];
  obstacles: Obstacle[];
  zones: Zone[];
  events: SafetyEvent[];
  evacuation: EvacuationSnapshot;
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
    ppe: Record<string, boolean | null>;
    hazards: Record<string, boolean | number>;
    detections: unknown[];
    ppe_judgement?: {
      active: boolean;
      status: "active" | "pending_person";
      person_frames: number;
      person_frames_required: number;
      ppe_frames: Record<string, number>;
      ppe_frames_required: number;
      missing_consecutive_frames: Record<string, number>;
      missing_frames_required: number;
      subject_scope: "observed_person";
      window_seconds: number;
    };
  };
}



