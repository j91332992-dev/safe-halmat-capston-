import {useState} from "react";
import {Haptics, ImpactStyle, NotificationType} from "@capacitor/haptics";
import {getStoredServerUrl, setStoredServerUrl, isCapacitorNative} from "../../services/config";

interface ServerSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export function ServerSettingsModal({isOpen, onClose, onSaved}: ServerSettingsModalProps) {
  const [url, setUrl] = useState(getStoredServerUrl() || (isCapacitorNative() ? "" : window.location.origin));
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ok: boolean; message: string} | null>(null);

  if (!isOpen) return null;

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    const targetUrl = url.trim().replace(/\/+$/, "");
    try {
      const res = await fetch(`${targetUrl}/api/dashboard/snapshot`, {
        method: "GET",
        headers: {"Accept": "application/json"}
      });
      if (res.ok) {
        setTestResult({ok: true, message: "연결 성공! 관제 서버가 정상 응답했습니다."});
        void Haptics.notification({type: NotificationType.Success}).catch(() => {});
      } else {
        setTestResult({ok: false, message: `서버 응답 오류 (상태 코드: ${res.status})`});
        void Haptics.notification({type: NotificationType.Warning}).catch(() => {});
      }
    } catch {
      setTestResult({
        ok: false,
        message: "연결 실패: IP 주소 및 포트(예: 8000)가 맞는지, 동일 Wi-Fi망인지 확인하세요."
      });
      void Haptics.notification({type: NotificationType.Error}).catch(() => {});
    } finally {
      setTesting(false);
    }
  };

  const handleSave = () => {
    void Haptics.impact({style: ImpactStyle.Medium}).catch(() => {});
    setStoredServerUrl(url.trim());
    onSaved();
    onClose();
    // Reload page to reinitialize all sockets and API base paths
    window.location.reload();
  };

  return (
    <div className="mobile-modal-overlay" onClick={onClose}>
      <div className="mobile-modal-card" onClick={e => e.stopPropagation()}>
        <header className="mobile-modal-header">
          <h3>관제 서버 IP / 주소 설정</h3>
          <button type="button" className="mobile-modal-close" onClick={onClose} aria-label="닫기">
            ✕
          </button>
        </header>

        <div className="mobile-modal-body">
          <p className="mobile-modal-desc">
            설치형 관리자 앱은 처음 한 번만 관제 서버 주소를 설정하면 됩니다. 백엔드가 실행 중인 PC의 Wi-Fi IP와 포트(기본 8000)를 입력하세요.
          </p>

          <label className="mobile-input-label">
            서버 URL (HTTP/HTTPS)
            <input
              type="text"
              className="mobile-input"
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="예: http://192.168.0.18:8000"
              autoCapitalize="none"
              autoCorrect="off"
            />
          </label>

          <div className="mobile-quick-ips">
            <span>빠른 설정:</span>
            <button
              type="button"
              className="btn-quick-ip"
              onClick={() => setUrl("http://localhost:8000")}
            >
              localhost:8000
            </button>
          </div>

          {testResult && (
            <div className={`mobile-test-alert ${testResult.ok ? "is-success" : "is-error"}`}>
              {testResult.message}
            </div>
          )}
        </div>

        <footer className="mobile-modal-footer">
          <button
            type="button"
            className="btn-test-conn"
            onClick={handleTest}
            disabled={testing}
          >
            {testing ? "연결 확인 중..." : "연결 테스트"}
          </button>
          <button
            type="button"
            className="btn-save-conn"
            onClick={handleSave}
          >
            저장 및 적용
          </button>
        </footer>
      </div>
    </div>
  );
}
