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
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
        <span>대시보드</span>
      </button>

      {/* 2. Map */}
      <button
        type="button"
        className={`bottom-tab ${currentPath === "/map" && !isMenuOpen ? "is-active" : ""}`}
        onClick={() => handleNav("/map")}
      >
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Z" />
          <path d="M9 3v15M15 6v15" />
        </svg>
        <span>실시간지도</span>
      </button>

      {/* 3. Camera */}
      <button
        type="button"
        className={`bottom-tab ${currentPath === "/camera" && !isMenuOpen ? "is-active" : ""}`}
        onClick={() => handleNav("/camera")}
      >
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14.5 4 16 7h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h3l1.5-3Z" />
          <circle cx="12" cy="13" r="3.5" />
        </svg>
        <span>카메라</span>
      </button>

      {/* 4. Workers */}
      <button
        type="button"
        className={`bottom-tab ${currentPath === "/workers" && !isMenuOpen ? "is-active" : ""}`}
        onClick={() => handleNav("/workers")}
      >
        <div className="tab-icon-wrapper">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="8" r="4" />
            <path d="M4 21a8 8 0 0 1 16 0" />
          </svg>
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
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="4" y1="12" x2="20" y2="12" />
            <line x1="4" y1="18" x2="20" y2="18" />
          </svg>
          {unresolvedCount > 0 && <span className="tab-badge">{unresolvedCount}</span>}
        </div>
        <span>메뉴</span>
      </button>
    </nav>
  );
}
