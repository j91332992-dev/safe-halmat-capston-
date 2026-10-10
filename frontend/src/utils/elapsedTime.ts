/** Human-readable elapsed time for device and safety-signal receipts. */
export function elapsedTime(timestamp: string | null | undefined, now = Date.now()): string {
  if (!timestamp) return "수신 기록 없음";
  let seconds = Math.max(0, Math.floor((now - new Date(timestamp).getTime()) / 1000));
  if (!Number.isFinite(seconds)) return "수신 기록 없음";

  const days = Math.floor(seconds / 86_400);
  seconds %= 86_400;
  const hours = Math.floor(seconds / 3_600);
  seconds %= 3_600;
  const minutes = Math.floor(seconds / 60);
  const parts: string[] = [];
  if (days) parts.push(`${days}일`);
  if (hours || days) parts.push(`${hours}시간`);
  if (minutes || hours || days) parts.push(`${minutes}분`);
  parts.push(`${seconds % 60}초`);
  return `${parts.join(" ")} 전`;
}
