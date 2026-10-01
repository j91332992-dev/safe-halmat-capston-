import {Haptics, ImpactStyle} from "@capacitor/haptics";
import type {ConnectionState} from "../../hooks/useSafetyData";

interface NetworkStatusBarProps {
  connectionState: ConnectionState;
  serverReachable: boolean;
  reconnectAttempts: number;
  onRetry: () => void;
  onOpenSettings: () => void;
}

export function NetworkStatusBar({
  connectionState,
  serverReachable,
  reconnectAttempts,
  onRetry,
  onOpenSettings
}: NetworkStatusBarProps) {
  // The dashboard is still safely usable when periodic API snapshots arrive,
  // even if Safari has not restored its WebSocket status event yet.
  if (connectionState === "connected" || serverReachable) return null;

  const handleRetry = () => {
    void Haptics.impact({style: ImpactStyle.Medium}).catch(() => {});
    onRetry();
  };

  const isOffline = connectionState === "offline";
  const isReconnecting = connectionState === "reconnecting";

  return (
    <aside className="mobile-network-bar" role="alert" aria-live="assertive">
      <div className="mobile-network-info">
        <span className="mobile-network-dot" />
        <span className="mobile-network-text">
          {isOffline
            ? "오프라인 상태입니다 (인터넷 연결 끊김)"
            : isReconnecting
            ? `서버 재연결 중... (시도 ${reconnectAttempts}회)`
            : "관제 서버와 통신할 수 없습니다"}
        </span>
      </div>
      <div className="mobile-network-actions">
        <button type="button" className="btn-retry" onClick={handleRetry}>
          재시도
        </button>
        <button type="button" className="btn-config" onClick={onOpenSettings} title="서버 IP 설정">
          IP 변경
        </button>
      </div>
    </aside>
  );
}
