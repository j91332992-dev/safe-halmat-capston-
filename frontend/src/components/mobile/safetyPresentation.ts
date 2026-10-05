import type {SafetyEvent, Snapshot, Worker} from "../../types";

export function priority(event: SafetyEvent): number {
  if (event.severity === "emergency") return 0;
  if (event.severity === "danger") return 1;
  if (event.severity === "warning") return 2;
  return 3;
}
export const priorityLabels = ["긴급", "위험", "주의", "안내"];
export function pendingEvents(events: SafetyEvent[]) {
  return events.filter(event => event.status !== "resolved").sort((a, b) =>
    priority(a) - priority(b) || Date.parse(b.created_at) - Date.parse(a.created_at));
}
export function workerTone(worker: Worker) {
  return worker.emergency || ["위험", "비상"].includes(worker.risk_level) ? "danger"
    : ["관심", "주의"].includes(worker.risk_level) ? "warning" : "safe";
}
export function siteCondition(data: Snapshot, reachable: boolean) {
  const events = pendingEvents(data.events);
  const danger = data.workers.some(w => workerTone(w) === "danger") || events.some(e => priority(e) < 2)
    || ["active", "pending_manager"].includes(data.evacuation?.incident?.status ?? "");
  const missing = data.devices.filter(d => !d.online).length;
  if (danger) return {tone: "danger", title: "위험 · 즉시 확인", detail: "긴급 알림과 작업자 위치를 확인하세요"};
  if (!reachable) return {tone: "unknown", title: "안전 상태 확인 필요", detail: "서버 연결 끊김 · 마지막 수신 정보입니다"};
  if (!data.workers.length || !data.devices.length) return {tone: "unknown", title: "안전 신호 대기", detail: "작업자와 안전모 연결을 확인하세요"};
  if (missing || data.anchors.some(a => !a.online)) return {tone: "warning", title: "주의 · 통신 확인", detail: "일부 장치의 실시간 상태를 확인할 수 없습니다"};
  if (data.workers.some(w => workerTone(w) === "warning") || events.some(e => priority(e) === 2))
    return {tone: "warning", title: "주의 · 현장 점검", detail: "주의 알림과 작업자 상태를 확인하세요"};
  return {tone: "safe", title: "안전 · 정상 관제", detail: "수신된 정보 기준 · 위험 알림 없음"};
}
