import {useEffect, useMemo, useState} from "react";
import {CameraMonitor} from "./components/CameraMonitor";
import {DiagnosticPanel} from "./components/DiagnosticPanel";
import {EventLog} from "./components/EventLog";
import {HistoryReplay} from "./components/HistoryReplay";
import {LayoutEditor} from "./components/LayoutEditor";
import {SiteMap} from "./components/SiteMap";
import {StatusPill} from "./components/StatusPill";
import {WorkerDetail} from "./components/WorkerDetail";
import {VoiceAssistant} from "./components/VoiceAssistant";
import {WorkerManagement} from "./components/WorkerManagement";
import {useSafetyData} from "./hooks/useSafetyData";
import {api} from "./services/api";

type Page = "dashboard" | "map" | "camera" | "assistant" | "layout" | "history" | "workers" | "devices" | "events" | "zones" | "diagnostics";

const navigation: {id: Page; label: string; mark: string}[] = [
  {id: "dashboard", label: "통합 대시보드", mark: "⌂"},
  {id: "map", label: "실시간 지도", mark: "◇"},
  {id: "camera", label: "카메라 관제", mark: "▤"},
  {id: "assistant", label: "음성·AI", mark: "◉"},
  {id: "layout", label: "지도 설계", mark: "⌗"},
  {id: "history", label: "위치 기록 재생", mark: "▶"},
  {id: "workers", label: "작업자 관리", mark: "♙"},
  {id: "devices", label: "장치 관리", mark: "▣"},
  {id: "events", label: "이벤트 로그", mark: "≡"},
  {id: "zones", label: "위험구역 관리", mark: "△"},
  {id: "diagnostics", label: "하드웨어 진단", mark: "⊙"}
];

const scenarios = [
  ["normal", "정상 복귀"],
  ["danger_zone", "위험구역 진입"],
  ["ppe_missing", "보호구 미착용"],
  ["fire", "화재 감지"],
  ["smoke", "연기 감지"],
  ["emergency", "비상 상황"],
  ["device_offline", "장치 오프라인"]
];

function App() {
  const {data, locationHistory, connected, error, refresh} = useSafetyData();
  const [page, setPage] = useState<Page>("dashboard");
  const [selectedId, setSelectedId] = useState("worker-001");
  const [busy, setBusy] = useState(false);
  const worker = useMemo(() => data?.workers.find(item => item.worker_id === selectedId) ?? data?.workers[0], [data, selectedId]);

  useEffect(() => {
    if (data?.workers[0] && !selectedId) setSelectedId(data.workers[0].worker_id);
  }, [data, selectedId]);

  const action = async (callback: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await callback();
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  if (!data) {
    return (
      <main className="loading-screen">
        <div className="brand-mark"><span>H</span></div>
        <h1>한미르 안전관제</h1>
        <p>{error ? "백엔드 연결을 확인하고 있습니다." : "통합 시스템을 불러오는 중입니다."}</p>
        {error && <code>{error}</code>}
      </main>
    );
  }

  const critical = data.events.filter(event => ["danger", "emergency"].includes(event.severity) && event.status !== "resolved").length;
  const online = data.devices.filter(device => device.online).length;

  return (
    <div className="app-frame">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><span>H</span></div>
          <div><strong>HANMIR</strong><small>SMART SAFETY</small></div>
        </div>
        <nav aria-label="주 메뉴">
          <span className="nav-caption">관제 메뉴</span>
          {navigation.map(item => (
            <button key={item.id} className={page === item.id ? "active" : ""} onClick={() => setPage(item.id)}>
              <i>{item.mark}</i>{item.label}
              {item.id === "events" && critical > 0 && <b>{critical}</b>}
            </button>
          ))}
        </nav>
        <div className="sidebar-system">
          <span className="nav-caption">시스템 상태</span>
          <div><StatusPill active={connected} activeText="실시간 연결" inactiveText="재연결 중" /></div>
          <div className="mode-switch">
            <span>운영 모드</span>
            <button
              disabled={busy}
              className={data.mode === "hardware" ? "hardware" : ""}
              onClick={() => void action(() => api.setMode(data.mode === "mock" ? "hardware" : "mock"))}
            >
              {data.mode.toUpperCase()}
            </button>
          </div>
        </div>
        <footer><span>v1.0.0-integrated</span><span>site-001</span></footer>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <span className="eyebrow">ESP32 SMART HELMET · REALTIME CONTROL</span>
            <h1>{navigation.find(item => item.id === page)?.label}</h1>
          </div>
          <div className="top-status">
            <div><span>현재 시각</span><strong>{new Date().toLocaleTimeString("ko-KR", {hour: "2-digit", minute: "2-digit"})}</strong></div>
            <div><span>장치 연결</span><strong>{online}/{data.devices.length}</strong></div>
            <div className={critical ? "critical" : ""}><span>미처리 경보</span><strong>{critical}</strong></div>
          </div>
        </header>

        {error && <div className="connection-banner">서버 갱신 지연: {error}</div>}

        {(page === "dashboard" || page === "map") && worker && (
          <>
            <section className="kpi-row">
              <article><span className="kpi-icon teal">◎</span><div><small>실시간 작업자</small><strong>{data.workers.length}<em>명</em></strong></div><StatusPill active /></article>
              <article><span className="kpi-icon blue">⌁</span><div><small>위치 신뢰도</small><strong>{Math.round(worker.confidence * 100)}<em>%</em></strong></div><span className="trend">UWB 4 anchor</span></article>
              <article><span className={`kpi-icon risk-${worker.risk_level}`}>!</span><div><small>최고 위험도</small><strong>{worker.risk_score}<em>점</em></strong></div><span className={`level level-${worker.risk_level}`}>{worker.risk_level}</span></article>
              <article><span className="kpi-icon orange">△</span><div><small>활성 위험구역</small><strong>{data.zones.filter(zone => zone.active).length}<em>곳</em></strong></div><span className="trend">{critical} alert</span></article>
            </section>
            <section className={`dashboard-grid ${page === "map" ? "map-focus" : ""}`}>
              <SiteMap
                width={data.site.width}
                height={data.site.height}
                anchors={data.anchors}
                obstacles={data.obstacles}
                zones={data.zones}
                workers={data.workers}
                history={locationHistory[worker.worker_id] ?? []}
                lastLocationAt={data.devices.find(device => device.worker_id === worker.worker_id && device.device_type === "position_device")?.last_uwb_at ?? null}
                selectedId={worker.worker_id}
                onSelect={item => setSelectedId(item.worker_id)}
              />
              <WorkerDetail worker={worker} devices={data.devices.filter(device => device.worker_id === worker.worker_id)} onRefresh={refresh} />
            </section>
            {page === "dashboard" && (
              <section className="lower-grid">
                <article className="panel events-panel">
                  <header><div><span className="eyebrow">RECENT EVENTS</span><h2>최근 이벤트</h2></div><button onClick={() => setPage("events")}>전체 보기 →</button></header>
                  <EventLog events={data.events.slice(0, 5)} onRefresh={refresh} />
                </article>
                <article className="panel scenario-panel">
                  <header><div><span className="eyebrow">INTEGRATED TEST</span><h2>Mock 시나리오</h2></div><StatusPill active={data.mode === "mock"} activeText="사용 가능" inactiveText="Hardware 모드" /></header>
                  <p>별도 테스트 파일 없이 최종 시스템 안에서 전체 흐름을 확인합니다.</p>
                  <div className="scenario-buttons">
                    {scenarios.map(([id, label]) => (
                      <button key={id} disabled={busy || data.mode !== "mock"} onClick={() => void action(() => api.runScenario(id))}>{label}</button>
                    ))}
                  </div>
                  <div className="quick-actions">
                    <button disabled={busy} onClick={() => void action(() => api.mockVoice("현재 위험도 알려줘"))}>음성 명령</button>
                    <button disabled={busy} onClick={() => void action(() => api.mockButton("triple_press"))}>버튼 비상</button>
                    <button disabled={busy} onClick={() => void action(() => api.sendAlert())}>스피커 경고</button>
                  </div>
                </article>
              </section>
            )}
          </>
        )}

        {page === "camera" && <CameraMonitor workers={data.workers} devices={data.devices} />}
        {page === "assistant" && <VoiceAssistant workers={data.workers} devices={data.devices} onRefresh={refresh} />}

        {page === "layout" && (
          <LayoutEditor site={data.site} anchors={data.anchors} obstacles={data.obstacles} zones={data.zones} workers={data.workers} onSaved={refresh} />
        )}
        {page === "history" && (
          <HistoryReplay site={data.site} anchors={data.anchors} obstacles={data.obstacles} zones={data.zones} workers={data.workers} />
        )}

        {page === "workers" && <WorkerManagement workers={data.workers} zones={data.zones} onSaved={refresh} />}
        {page === "devices" && (
          <section className="page-panel">
            <header><div><span className="eyebrow">DEVICE REGISTRY</span><h2>등록 장치 {data.devices.length}대</h2></div></header>
            <div className="device-table">
              <div className="device-row head"><span>장치 ID</span><span>종류</span><span>상태</span><span>IP / RSSI</span><span>배터리</span><span>마지막 수신</span></div>
              {data.devices.map(device => (
                <div className="device-row" key={device.device_id}>
                  <strong>{device.device_id}</strong><span>{device.device_type}</span><StatusPill active={device.online} activeText="온라인" inactiveText="오프라인" />
                  <span>{device.ip ?? "-"} / {device.rssi ?? "-"} dBm</span><span>{Math.round(device.battery ?? 0)}%</span><span>{new Date(device.last_seen).toLocaleString("ko-KR")}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {page === "events" && <section className="page-panel"><header><div><span className="eyebrow">EVENT CENTER</span><h2>이벤트 로그</h2></div><span>{data.events.length}건 표시</span></header><EventLog events={data.events} onRefresh={refresh} expanded /></section>}

        {page === "zones" && (
          <section className="page-panel">
            <header><div><span className="eyebrow">DANGER ZONE</span><h2>위험구역 관리</h2></div><span>초기 버전은 API로 좌표를 편집합니다.</span></header>
            <div className="zone-grid">
              {data.zones.map(zone => <article key={zone.zone_id}><span className="zone-chip">{zone.active ? "활성" : "비활성"}</span><h3>{zone.zone_name}</h3><p>{zone.warning_message}</p><dl><div><dt>ID</dt><dd>{zone.zone_id}</dd></div><div><dt>형태</dt><dd>{zone.zone_type}</dd></div><div><dt>가중치</dt><dd>+{zone.risk_weight}</dd></div><div><dt>필수 PPE</dt><dd>{zone.required_ppe.join(", ")}</dd></div></dl></article>)}
            </div>
          </section>
        )}

        {page === "diagnostics" && (
          <section className="page-panel diagnostic-page">
            <header><div><span className="eyebrow">HARDWARE DIAGNOSTIC</span><h2>통합 하드웨어 진단</h2></div><button onClick={() => void refresh()}>지금 새로고침</button></header>
            <p className="page-intro">카메라·마이크·스피커·버튼·UWB를 별도 스케치가 아닌 최종 펌웨어 heartbeat와 서버 수신 기록으로 확인합니다.</p>
            <DiagnosticPanel devices={data.devices} mode={data.mode} />
          </section>
        )}
      </main>
    </div>
  );
}

export default App;

