import {SafetyIcon} from "./SafetyIcon";
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
          <SafetyIcon name="bell" />
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
          <SafetyIcon name="settings" />
        </button>
      </div>
    </header>
  );
}
