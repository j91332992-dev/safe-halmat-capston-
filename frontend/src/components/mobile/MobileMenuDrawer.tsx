import {navigation, navigationGroups} from "../../adminNavigation";
import {useNavigate} from "react-router-dom";
import {Haptics, ImpactStyle} from "@capacitor/haptics";
import {SafetyIcon, type SafetyIconName} from "./SafetyIcon";

interface MobileMenuDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenSettings: () => void;
  onLogout: () => void;
  isHardware: boolean;
  onToggleHardware: () => void;
}

export function MobileMenuDrawer({
  isOpen,
  onClose,
  onOpenSettings,
  onLogout,
  isHardware,
  onToggleHardware
}: MobileMenuDrawerProps) {
  const navigate = useNavigate();

  if (!isOpen) return null;

  const handleItemClick = (path: string) => {
    void Haptics.impact({style: ImpactStyle.Light}).catch(() => {});
    navigate(path);
    onClose();
  };

  return (
    <div className="mobile-drawer-overlay" onClick={onClose}>
      <div className="mobile-drawer-card" onClick={e => e.stopPropagation()}>
        <div className="mobile-drawer-handle" />

        <header className="mobile-drawer-header">
          <div>
            <h3>전체 관제 메뉴</h3>
            <span className="mobile-drawer-sub">한미르 스마트 안전모 시스템</span>
          </div>
          <button type="button" className="mobile-drawer-close" onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </header>

        <div className="mobile-drawer-section">
          <h4>현장 운영 모드</h4>
          <div className="mobile-mode-card">
            <div>
              <strong>{isHardware ? "실장비 연동 모드" : "모의 시뮬레이션 모드"}</strong>
              <p>{isHardware ? "ESP32 UWB 태그 및 카메라 실시간 수신" : "가상 작업자 시뮬레이션 구동"}</p>
            </div>
            <button
              type="button"
              className={`btn-mode-toggle ${isHardware ? "is-hw" : "is-sim"}`}
              onClick={onToggleHardware}
            >
              {isHardware ? "실장비" : "모의"}
            </button>
          </div>
        </div>

        {navigationGroups.map(group => <details className="ops-menu-group" key={group.label}>
          <summary><SafetyIcon name={group.icon as SafetyIconName}/>{group.label}<span>+</span></summary>
          <div className="mobile-drawer-grid">
          {navigation.filter(item => group.pages.includes(item.id)).map(item => (
            <button
              key={item.path}
              type="button"
              className="drawer-nav-item"
              onClick={() => handleItemClick(item.path)}
            >
              <span className="drawer-item-icon"><SafetyIcon name={group.icon as SafetyIconName}/></span>
              <div className="drawer-item-text">
                <strong>{item.label}</strong>
                <small>{item.label} 기능 열기</small>
              </div>
              <span className="drawer-item-arrow">›</span>
            </button>
          ))}
        </div></details>)}

        <footer className="mobile-drawer-footer">
          <button
            type="button"
            className="btn-drawer-action"
            onClick={() => {
              onClose();
              onOpenSettings();
            }}
          >
            연결 설정
          </button>
          <button type="button" className="btn-drawer-logout" onClick={onLogout}>↪ 관리자 로그아웃</button>
        </footer>
      </div>
    </div>
  );
}
