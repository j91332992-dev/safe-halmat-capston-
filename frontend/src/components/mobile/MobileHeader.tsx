import {Haptics, ImpactStyle} from "@capacitor/haptics";
import type {ConnectionState} from "../../hooks/useSafetyData";

interface MobileHeaderProps {
  siteName: string;
  connectionState: ConnectionState;
  serverReachable: boolean;
  unresolvedCount: number;
  hasEmergency: boolean;
  onOpenAlerts: () => void;
  onOpenSettings: () => void;
}

export function MobileHeader({
  siteName,
  connectionState,
  serverReachable,
  unresolvedCount,
  hasEmergency,
  onOpenAlerts,
  onOpenSettings
}: MobileHeaderProps) {
  const handleAlertClick = () => {
    void Haptics.impact({style: ImpactStyle.Medium}).catch(() => {});
    onOpenAlerts();
  };

  const handleSettingsClick = () => {
    void Haptics.impact({style: ImpactStyle.Light}).catch(() => {});
    onOpenSettings();
  };

  const statusLabel = serverReachable && connectionState !== "connected" ? "서버 연결됨" : {
    connected: "실시간",
    connecting: "연결 중",
    reconnecting: "재연결 중",
    offline: "오프라인",
    error: "연결 오류"
  }[connectionState];
  const statusClass = serverReachable && connectionState !== "connected" ? "connected" : connectionState;

  return (
    <header className="mobile-header ops-header">
      <div className="mobile-header-brand">
        <div className="brand-mark small">
          <span>H</span>
        </div>
        <div className="mobile-header-titles">
          <h1>한미르 안전관제</h1>
          <span className="mobile-site-name">{siteName}</span>
        </div>
      </div>

      <div className="mobile-header-actions">
        {/* Connection status pill */}
        <div className={`mobile-status-badge state-${statusClass}`} aria-label={`관제 서버 ${statusLabel}`} title={`관제 서버 ${statusLabel}`}>
          <span className="badge-dot" />
          <span className="badge-text">{statusLabel}</span>
        </div>

        {/* Emergency Alert Button */}
        <button
          type="button"
          className={`mobile-header-btn btn-alert ${hasEmergency ? "is-emergency" : ""}`}
          onClick={handleAlertClick}
          aria-label="알림 목록"
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          {unresolvedCount > 0 && <span className="alert-count-pill">{unresolvedCount}</span>}
        </button>

        {/* Server IP Settings Button */}
        <button
          type="button"
          className="mobile-header-btn btn-settings"
          onClick={handleSettingsClick}
          aria-label="서버 설정"
          title="서버 IP 설정"
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      </div>
      <button className={`ops-notification-strip ${hasEmergency ? "has-danger" : ""}`} onClick={handleAlertClick}>
        <span>{hasEmergency ? "긴급 상황 · 우선 확인" : "현장 알림"}</span><b>{unresolvedCount ? `${unresolvedCount}건 확인하기` : "미처리 알림 없음"} <span aria-hidden="true">›</span></b>
      </button>
    </header>
  );
}
