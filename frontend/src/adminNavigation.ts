export type Page = "dashboard" | "map" | "camera" | "assistant" | "layout" | "history" | "workers" | "devices" | "events" | "zones" | "diagnostics" | "chat" | "permissions";
export type NavigationGroupId = "location" | "media" | "safety" | "system";

// All administrator clients use this list. Screen size only changes layout.
export const navigation: {id: Page; path: string; label: string}[] = [
  {id: "dashboard", path: "/dashboard", label: "통합 대시보드"},
  {id: "map", path: "/map", label: "실시간 지도"},
  {id: "layout", path: "/layout", label: "지도 설계"},
  {id: "history", path: "/history", label: "위치 기록 재생"},
  {id: "camera", path: "/camera", label: "카메라 관제"},
  {id: "workers", path: "/workers", label: "작업자 관리"},
  {id: "chat", path: "/team-chat", label: "팀 채팅"},
  {id: "permissions", path: "/permissions", label: "교육·작업 허가"},
  {id: "devices", path: "/device", label: "장치 관리"},
  {id: "events", path: "/event", label: "이벤트 로그"},
  {id: "zones", path: "/danger", label: "위험구역 관리"},
  {id: "diagnostics", path: "/hardware", label: "하드웨어 진단"},
  {id: "assistant", path: "/assistant", label: "음성·AI"}
];
export const navigationGroups: {id: NavigationGroupId; label: string; pages: Page[]; icon: "map" | "voice" | "shield" | "settings"}[] = [
  {id: "location", label: "위치 관제", pages: ["map", "history", "layout"], icon: "map"},
  {id: "media", label: "영상·AI 관제", pages: ["camera", "assistant"], icon: "voice"},
  {id: "safety", label: "안전 관리", pages: ["workers", "chat", "permissions", "zones", "events"], icon: "shield"},
  {id: "system", label: "장치·시스템", pages: ["devices", "diagnostics"], icon: "settings"}
];
