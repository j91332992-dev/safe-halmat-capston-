import {SafetyIcon} from "./SafetyIcon";
import {useEffect, useRef} from "react";
import {useLocation, useNavigate} from "react-router-dom";
import {Haptics, ImpactStyle} from "@capacitor/haptics";

interface MobileBottomNavProps {
  unresolvedCount: number;
  hasEmergency: boolean;
  onOpenMenu: () => void;
  isMenuOpen: boolean;
}

export function MobileBottomNav({
  unresolvedCount,
  hasEmergency,
  onOpenMenu,
  isMenuOpen
}: MobileBottomNavProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const navRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;

    const keepNavFixed = (event: TouchEvent) => {
      event.preventDefault();
    };

    nav.addEventListener("touchmove", keepNavFixed, {passive: false});
    return () => nav.removeEventListener("touchmove", keepNavFixed);
  }, []);

  const handleNav = (path: string) => {
    void Haptics.impact({style: ImpactStyle.Light}).catch(() => {});
    navigate(path);
  };

  const handleMenuClick = () => {
    void Haptics.impact({style: ImpactStyle.Medium}).catch(() => {});
    onOpenMenu();
  };

  const currentPath = location.pathname;

  return (
    <nav ref={navRef} className="mobile-bottom-nav">
      {/* 1. Dashboard */}
      <button
        type="button"
        className={`bottom-tab ${currentPath === "/dashboard" && !isMenuOpen ? "is-active" : ""}`}
        onClick={() => handleNav("/dashboard")}
      >
        <SafetyIcon name="grid" />
        <span>대시보드</span>
      </button>

      {/* 2. Map */}
      <button
        type="button"
        className={`bottom-tab ${currentPath === "/map" && !isMenuOpen ? "is-active" : ""}`}
        onClick={() => handleNav("/map")}
      >
        <SafetyIcon name="map" />
        <span>실시간지도</span>
      </button>

      {/* 3. Camera */}
      <button
        type="button"
        className={`bottom-tab ${currentPath === "/camera" && !isMenuOpen ? "is-active" : ""}`}
        onClick={() => handleNav("/camera")}
      >
        <SafetyIcon name="camera" />
        <span>카메라</span>
      </button>

      {/* 4. Workers */}
      <button
        type="button"
        className={`bottom-tab ${currentPath === "/workers" && !isMenuOpen ? "is-active" : ""}`}
        onClick={() => handleNav("/workers")}
      >
        <div className="tab-icon-wrapper">
          <SafetyIcon name="worker" />
          {hasEmergency && <span className="tab-pulse-badge" />}
        </div>
        <span>작업자</span>
      </button>

      {/* 5. More Menu */}
      <button
        type="button"
        className={`bottom-tab ${isMenuOpen ? "is-active" : ""}`}
        onClick={handleMenuClick}
      >
        <div className="tab-icon-wrapper">
          <SafetyIcon name="menu" />
          {unresolvedCount > 0 && <span className="tab-badge">{unresolvedCount}</span>}
        </div>
        <span>메뉴</span>
      </button>
    </nav>
  );
}
