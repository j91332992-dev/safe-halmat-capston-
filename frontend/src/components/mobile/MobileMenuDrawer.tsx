import {useNavigate} from "react-router-dom";
import {Haptics, ImpactStyle} from "@capacitor/haptics";

interface MobileMenuDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenSettings: () => void;
  onLogout: () => void;
  isHardware: boolean;
  onToggleHardware: () => void;
}

const extraMenuItems = [
  {path: "/layout", label: "지도 설계", icon: "📐", desc: "앵커 및 장애물 배치 편집"},
  {path: "/history", label: "위치 기록 재생", icon: "⏪", desc: "작업자 과거 동선 타임라인"},
  {path: "/device", label: "장치 관리", icon: "📟", desc: "ESP32 헬멧 및 UWB 태그 상태"},
  {path: "/event", label: "이벤트 로그", icon: "📋", desc: "SOS 및 시스템 감지 이력"},
  {path: "/danger", label: "위험구역 관리", icon: "⚠️", desc: "출입금지/경고 구역 설정"},
  {path: "/hardware", label: "하드웨어 진단", icon: "🛠️", desc: "스피커 테스트 및 센서 점검"},
  {path: "/assistant", label: "음성·AI 어시스턴트", icon: "🎙️", desc: "무전 명령 및 AI 안내"}
];

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

        <div className="mobile-drawer-grid">
          {extraMenuItems.map(item => (
            <button
              key={item.path}
              type="button"
              className="drawer-nav-item"
              onClick={() => handleItemClick(item.path)}
            >
              <span className="drawer-item-icon">{item.icon}</span>
              <div className="drawer-item-text">
                <strong>{item.label}</strong>
                <small>{item.desc}</small>
              </div>
              <span className="drawer-item-arrow">›</span>
            </button>
          ))}
        </div>

        <footer className="mobile-drawer-footer">
          <button
            type="button"
            className="btn-drawer-action"
            onClick={() => {
              onClose();
              onOpenSettings();
            }}
          >
            ⚙️ 관제 서버 IP 주소 설정
          </button>
          <button type="button" className="btn-drawer-logout" onClick={onLogout}>↪ 관리자 로그아웃</button>
          <div className="mobile-version-tag">
            <span>HANMIR Mobile v1.0.0</span>
            <span>PWA / Capacitor Cross-Platform</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
