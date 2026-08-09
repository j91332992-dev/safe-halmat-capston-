import {useEffect, useMemo, useState} from "react";
import {useLocation, useNavigate} from "react-router-dom";
import {CameraMonitor} from "./components/CameraMonitor";
import {DiagnosticPanel} from "./components/DiagnosticPanel";
import {EventLog} from "./components/EventLog";
import {FireEvacuationModal} from "./components/FireEvacuationModal";
import {HistoryReplay} from "./components/HistoryReplay";
import {HelmetCall} from "./components/HelmetCall";
import {LayoutEditor} from "./components/LayoutEditor";
import {SiteMap} from "./components/SiteMap";
import {StatusPill} from "./components/StatusPill";
import {WorkerDetail} from "./components/WorkerDetail";
import {VoiceAssistant} from "./components/VoiceAssistant";
import {WorkerManagement} from "./components/WorkerManagement";
import {useSafetyData} from "./hooks/useSafetyData";
import {api} from "./services/api";

type Page = "dashboard" | "map" | "camera" | "assistant" | "layout" | "history" | "workers" | "devices" | "events" | "zones" | "diagnostics";

const navigation: {id: Page; path: string; label: string}[] = [
  {id: "dashboard", path: "/dashboard", label: "통합 대시보드"},
  {id: "map", path: "/map", label: "실시간 지도"},
  {id: "layout", path: "/layout", label: "지도 설계"},
  {id: "history", path: "/history", label: "위치 기록 재생"},
  {id: "camera", path: "/camera", label: "카메라 관제"},
  {id: "workers", path: "/workers", label: "작업자 관리"},
  {id: "devices", path: "/device", label: "장치 관리"},
  {id: "events", path: "/event", label: "이벤트 로그"},
  {id: "zones", path: "/danger", label: "위험구역 관리"},
  {id: "diagnostics", path: "/hardware", label: "하드웨어 진단"},
  {id: "assistant", path: "/assistant", label: "음성·AI"}
];

type NavigationGroupId = "location" | "media" | "safety" | "system";

const navigationGroups: {id: NavigationGroupId; label: string; pages: Page[]}[] = [
  {id: "location", label: "위치 관제", pages: ["map", "history", "layout"]},
  {id: "media", label: "영상·AI 관제", pages: ["camera", "assistant"]},
  {id: "safety", label: "안전 관리", pages: ["workers", "zones", "events"]},
  {id: "system", label: "장치·시스템", pages: ["devices", "diagnostics"]}
];

function MenuIcon({page}: {page: Page}) {
  const paths: Record<Page, React.ReactNode> = {
    dashboard: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    map: <><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Z"/><path d="M9 3v15M15 6v15"/></>,
    camera: <><path d="M14.5 4 16 7h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h3l1.5-3Z"/><circle cx="12" cy="13" r="3.5"/></>,
    assistant: <><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5M8 22h8"/></>,
    layout: <><path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4z"/><path d="M17 14v6M14 17h6"/></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
    workers: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    devices: <><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M9 6h6M10 18h4"/></>,
    events: <><path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3" cy="6" r="1"/><circle cx="3" cy="12" r="1"/><circle cx="3" cy="18" r="1"/></>,
    zones: <><path d="M12 3 2.8 20h18.4Z"/><path d="M12 9v5M12 17h.01"/></>,
    diagnostics: <><path d="M14.7 6.3a4 4 0 0 0-5 5L3 18l3 3 6.7-6.7a4 4 0 0 0 5-5l-3 3-3-3Z"/></>
  };
  return <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true">{paths[page]}</svg>;
}

function KpiIcon({type}: {type: "workers" | "location" | "risk" | "zone"}) {
  const paths = {
    workers: <><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M16 6a3 3 0 0 1 0 6M17 15a5 5 0 0 1 4 5"/></>,
    location: <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/></>,
    risk: <><path d="M12 3 4 6v5c0 5 3.4 8.4 8 10 4.6-1.6 8-5 8-10V6Z"/><path d="M12 8v5M12 16h.01"/></>,
    zone: <><path d="M12 3 2.8 20h18.4Z"/><path d="M12 9v5M12 17h.01"/></>
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[type]}</svg>;
}


function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const currentNavigation = navigation.find(item => item.path === location.pathname);
  const page = currentNavigation?.id ?? "dashboard";
  const {data, locationHistory, connected, error, refresh} = useSafetyData();
  const [selectedId, setSelectedId] = useState("worker-001");
  const [busy, setBusy] = useState(false);
  const [openGroups, setOpenGroups] = useState<Record<NavigationGroupId, boolean>>({location: false, media: false, safety: false, system: false});
  const worker = useMemo(() => data?.workers.find(item => item.worker_id === selectedId) ?? data?.workers[0], [data, selectedId]);
  const evacuationIncident = data?.evacuation?.incident ?? null;
  const emergencyWorker = data?.workers.find(item => item.emergency) ?? null;
  const emergencyEvent = data?.events.find(item =>
    item.worker_id === emergencyWorker?.worker_id &&
    item.event_type === "VOICE_COMMAND" &&
    ["help", "emergency"].includes(String(item.details?.intent ?? "")) &&
    item.status !== "resolved"
  ) ?? null;
  const callRequestEvent = data?.events.find(item =>
    item.event_type === "VOICE_COMMAND" &&
    String(item.details?.intent ?? "") === "call_manager" &&
    item.status !== "resolved"
  ) ?? null;
  const callRequestWorker = data?.workers.find(item => item.worker_id === callRequestEvent?.worker_id) ?? null;
  const activeCallWorker = callRequestWorker ?? emergencyWorker ?? worker ?? null;
  const callDevice = data?.devices.find(device =>
    device.worker_id === activeCallWorker?.worker_id && device.device_type === "assistant_device"
  ) ?? null;

  useEffect(() => {
    if (data?.workers[0] && !selectedId) setSelectedId(data.workers[0].worker_id);
  }, [data, selectedId]);

  useEffect(() => {
    if (!currentNavigation) navigate("/dashboard", {replace: true});
  }, [currentNavigation, navigate]);

  useEffect(() => {
    const currentGroup = navigationGroups.find(group => group.pages.includes(page));
    if (currentGroup) setOpenGroups(current => ({...current, [currentGroup.id]: true}));
  }, [page]);

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
  const uwbTag = data.devices.find(device => device.device_type === "position_device");
  const missingAnchors = data.anchors.filter(anchor => !anchor.online);
  const showAnchorStatus = page === "dashboard" || page === "map" || page === "diagnostics";
  const overviewItems: {page: Page; value: string; detail: string}[] = [
    {page: "map", value: `${data.workers.length}명 표시`, detail: `작업자 X ${worker?.x.toFixed(1) ?? "-"} · Y ${worker?.y.toFixed(1) ?? "-"}m`},
    {page: "layout", value: `${data.anchors.length}개 앵커`, detail: `현장 ${data.site.width}m × ${data.site.height}m`},
    {page: "history", value: `${worker ? locationHistory[worker.worker_id]?.length ?? 0 : 0}개 좌표`, detail: "최근 위치 기록 재생"},
    {page: "camera", value: `${data.devices.filter(device => device.device_type === "assistant_device" && device.online).length}대 온라인`, detail: "안전모 카메라 관제"},
    {page: "workers", value: `${data.workers.length}명 등록`, detail: "작업자 상태와 권한"},
    {page: "devices", value: `${online}/${data.devices.length} 연결`, detail: "AV · UWB 장치 상태"},
    {page: "events", value: `${critical}건 미처리`, detail: `최근 이벤트 ${data.events.length}건`},
    {page: "zones", value: `${data.zones.filter(zone => zone.active).length}곳 활성`, detail: "위험구역과 PPE 요건"},
    {page: "diagnostics", value: `${data.anchors.length - missingAnchors.length}/${data.anchors.length} 수신`, detail: "하드웨어 통합 진단"},
    {page: "assistant", value: data.devices.some(device => device.device_type === "assistant_device" && device.online) ? "사용 가능" : "오프라인", detail: "음성 · AI 명령 전송"}
  ];

  return (
    <div className="app-frame">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><span>H</span></div>
          <div><strong>HANMIR</strong><small>SMART SAFETY</small></div>
        </div>
        <nav aria-label="주 메뉴">
          <span className="nav-caption">관제 메뉴</span>
          <button className={page === "dashboard" ? "active" : ""} onClick={() => navigate("/dashboard")}>
            <i><MenuIcon page="dashboard" /></i>통합 대시보드
          </button>
          {navigationGroups.map(group => (
            <div className={`nav-group ${group.pages.includes(page) ? "current" : ""}`} key={group.id}>
              <button className="nav-group-toggle" aria-expanded={openGroups[group.id]} onClick={() => setOpenGroups(current => ({...current, [group.id]: !current[group.id]}))}>
                <span>{group.label}</span><i className="nav-chevron">{openGroups[group.id] ? "−" : "+"}</i>
              </button>
              {openGroups[group.id] && <div className="nav-group-items">
                {group.pages.map(pageId => {
                  const item = navigation.find(entry => entry.id === pageId)!;
                  return <button key={item.id} className={`group-item ${page === item.id ? "active" : ""}`} onClick={() => navigate(item.path)}>
                    <i><MenuIcon page={item.id} /></i>{item.label}
                    {item.id === "events" && critical > 0 && <b>{critical}</b>}
                  </button>;
                })}
              </div>}
            </div>
          ))}
        </nav>
        <div className="sidebar-system">
          <span className="nav-caption">시스템 상태</span>
          <div><StatusPill active={connected} activeText="실시간 연결" inactiveText="재연결 중" /></div>
          <div className="mode-switch">
            <span>운영 모드</span>
            <button disabled className="hardware">HARDWARE</button>
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
        {showAnchorStatus && (
          <div className={`anchor-status-banner ${!uwbTag?.online ? "unknown" : missingAnchors.length ? "warning" : "healthy"}`}>
            <div>
              <b>{!uwbTag?.online ? "UWB 태그 오프라인" : missingAnchors.length ? "앵커 신호 미수신" : "UWB 수신 정상"}</b>
              <span>{!uwbTag?.online ? "태그 전원을 켜야 앵커 수신 여부를 확인할 수 있습니다." : missingAnchors.length ? `${missingAnchors.map(anchor => anchor.name).join(", ")} 신호가 20초 이상 수신되지 않았습니다.` : `앵커 ${data.anchors.length}개가 모두 수신되고 있습니다.`}</span>
            </div>
            <div className="anchor-status-chips">
              {data.anchors.map((anchor, index) => <span key={anchor.anchor_id} className={uwbTag?.online && anchor.online ? "online" : "offline"}>A{index + 1} {uwbTag?.online ? anchor.online ? "정상" : "미수신" : "확인 불가"}</span>)}
            </div>
          </div>
        )}
        {evacuationIncident?.status === "active" && (
          <div className="active-fire-banner" role="alert">
            <div><b>화재 경보 활성</b><span>확인된 화재 위치와 가장 가까운 비상구 거리를 작업자 안전모로 안내 중입니다.</span></div>
            <button disabled={busy} onClick={() => void action(() => api.cancelFire(evacuationIncident.incident_id, "resolved"))}>화재 종료</button>
          </div>
        )}
        {emergencyWorker && (
          <div className="active-sos-banner" role="alert">
            <div><b>긴급 도움 요청 · {emergencyWorker.worker_name}</b><span>현재 위치 X {emergencyWorker.x.toFixed(1)}m · Y {emergencyWorker.y.toFixed(1)}m</span></div>
            <div className="sos-banner-actions">
              {callDevice && <HelmetCall deviceId={callDevice.device_id} workerName={emergencyWorker.worker_name} />}
              {emergencyEvent?.status === "open" && <button disabled={busy} onClick={() => void action(() => api.acknowledge(emergencyEvent.event_id))}>신고 확인</button>}
              {emergencyEvent && <button className="resolve" disabled={busy} onClick={() => void action(() => api.resolve(emergencyEvent.event_id))}>상황 종료</button>}
            </div>
          </div>
        )}
        {callRequestEvent && callRequestWorker && callDevice && (
          <div className="active-call-request-banner" role="alert">
            <div><b>관리자 통화 요청 · {callRequestWorker.worker_name}</b><span>안전모에서 관리자 연결을 요청했습니다.</span></div>
            <div className="call-request-actions">
              <HelmetCall deviceId={callDevice.device_id} workerName={callRequestWorker.worker_name} />
              <button disabled={busy} onClick={() => void action(() => api.resolve(callRequestEvent.event_id))}>요청 닫기</button>
            </div>
          </div>
        )}

        {page === "dashboard" && worker && (
          <>
            <section className="kpi-row">
              <article><span className="kpi-icon teal"><KpiIcon type="workers" /></span><div><small>실시간 작업자</small><strong>{data.workers.length}<em>명</em></strong></div><StatusPill active /></article>
              <article><span className="kpi-icon blue"><KpiIcon type="location" /></span><div><small>위치 신뢰도</small><strong>{Math.round(worker.confidence * 100)}<em>%</em></strong></div><span className="trend">UWB 4 anchor</span></article>
              <article><span className={`kpi-icon risk-${worker.risk_level}`}><KpiIcon type="risk" /></span><div><small>최고 위험도</small><strong>{worker.risk_score}<em>점</em></strong></div><span className={`level level-${worker.risk_level}`}>{worker.risk_level}</span></article>
              <article><span className="kpi-icon orange"><KpiIcon type="zone" /></span><div><small>활성 위험구역</small><strong>{data.zones.filter(zone => zone.active).length}<em>곳</em></strong></div><span className="trend">{critical} alert</span></article>
            </section>
            <section className="system-overview-grid" aria-label="주요 관제 기능 요약">
              {overviewItems.map(item => {
                const navigationItem = navigation.find(entry => entry.id === item.page)!;
                return <button key={item.page} onClick={() => navigate(navigationItem.path)}><i><MenuIcon page={item.page} /></i><span><small>{navigationItem.label}</small><strong>{item.value}</strong><em>{item.detail}</em></span><b>→</b></button>;
              })}
            </section>
            <section className="dashboard-overview-grid">
              <WorkerDetail worker={worker} devices={data.devices.filter(device => device.worker_id === worker.worker_id)} onRefresh={refresh} />
              <div className="dashboard-side-stack">
                <article className="panel events-panel">
                  <header><div><span className="eyebrow">RECENT EVENTS</span><h2>최근 이벤트</h2></div><button onClick={() => navigate("/event")}>전체 보기 →</button></header>
                  <EventLog events={data.events.slice(0, 5)} onRefresh={refresh} />
                </article>
                <article className="panel scenario-panel">
                  <header><div><span className="eyebrow">OPERATOR CONTROL</span><h2>관리자 빠른 제어</h2></div><StatusPill active activeText="실제 장치" inactiveText="오프라인" /></header>
                  <p>등록된 안전모 장치에 경고를 보내거나 실제 화재 상황을 수동 발령합니다.</p>
                  <div className="quick-actions">
                    {!callRequestEvent && !emergencyWorker && callDevice && <HelmetCall deviceId={callDevice.device_id} workerName={worker.worker_name} />}
                    <button disabled={busy || !data.devices.some(device => device.worker_id === worker.worker_id && device.device_type === "assistant_device" && device.online)} onClick={() => void action(() => api.sendAlert(data.devices.find(device => device.worker_id === worker.worker_id && device.device_type === "assistant_device")?.device_id))}>스피커 경고</button>
                    <button className="fire-manual-button" disabled={busy || !!evacuationIncident} onClick={() => void action(() => api.triggerFire(worker.worker_id))}>화재 수동발령</button>
                  </div>
                </article>
              </div>
            </section>
          </>
        )}

        {page === "map" && worker && (
          <section className="map-page-grid">
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
              evacuationRoute={data.evacuation.routes[worker.worker_id]}
              fireZone={evacuationIncident?.fire_zone ?? null}
              onSelect={item => setSelectedId(item.worker_id)}
            />
            <WorkerDetail worker={worker} devices={data.devices.filter(device => device.worker_id === worker.worker_id)} onRefresh={refresh} />
          </section>
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

        {page === "events" && <section className="page-panel management-page event-management-page">
          <header><div><span className="eyebrow">EVENT CENTER</span><h2>이벤트 로그</h2><p>현장에서 수신된 안전 알림의 처리 상태를 한눈에 확인합니다.</p></div><span>{data.events.length}건 표시</span></header>
          <div className="management-overview">
            <article><i><MenuIcon page="events" /></i><span><small>전체 이벤트</small><strong>{data.events.length}<em>건</em></strong></span></article>
            <article><i className="warning"><MenuIcon page="zones" /></i><span><small>미처리 경보</small><strong>{critical}<em>건</em></strong></span></article>
            <article><i className="success"><MenuIcon page="workers" /></i><span><small>처리 완료</small><strong>{data.events.filter(event => event.status === "resolved").length}<em>건</em></strong></span></article>
          </div>
          <EventLog events={data.events} onRefresh={refresh} expanded />
        </section>}

        {page === "zones" && (
          <section className="page-panel management-page zone-management-page">
            <header><div><span className="eyebrow">DANGER ZONE</span><h2>위험구역 관리</h2><p>현장 위험구역의 상태와 작업자 보호구 요건을 관리합니다.</p></div><span>좌표 변경은 지도 설계에서 진행합니다.</span></header>
            <div className="management-overview">
              <article><i><MenuIcon page="zones" /></i><span><small>등록 구역</small><strong>{data.zones.length}<em>곳</em></strong></span></article>
              <article><i className="warning"><MenuIcon page="zones" /></i><span><small>활성 구역</small><strong>{data.zones.filter(zone => zone.active).length}<em>곳</em></strong></span></article>
              <article><i className="success"><MenuIcon page="workers" /></i><span><small>등록 작업자</small><strong>{data.workers.length}<em>명</em></strong></span></article>
            </div>
            <div className="zone-grid">
              {data.zones.map(zone => <article key={zone.zone_id}><span className="zone-chip">{zone.active ? "활성" : "비활성"}</span><h3>{zone.zone_name}</h3><p>{zone.warning_message}</p><dl><div><dt>ID</dt><dd>{zone.zone_id}</dd></div><div><dt>형태</dt><dd>{zone.zone_type}</dd></div><div><dt>가중치</dt><dd>+{zone.risk_weight}</dd></div><div><dt>필수 PPE</dt><dd>{zone.required_ppe.join(", ")}</dd></div></dl></article>)}
            </div>
          </section>
        )}

        {page === "diagnostics" && (
          <section className="page-panel diagnostic-page">
            <header><div><span className="eyebrow">HARDWARE DIAGNOSTIC</span><h2>통합 하드웨어 진단</h2></div><button onClick={() => void refresh()}>지금 새로고침</button></header>
            <p className="page-intro">카메라·마이크·스피커·버튼·UWB를 별도 스케치가 아닌 최종 펌웨어 heartbeat와 서버 수신 기록으로 확인합니다.</p>
            <DiagnosticPanel devices={data.devices} anchors={data.anchors} mode={data.mode} />
          </section>
        )}
      </main>
      {emergencyWorker && emergencyEvent?.status === "open" && (
        <div className="sos-modal-backdrop">
          <section className="sos-modal" role="alertdialog" aria-modal="true" aria-labelledby="sos-modal-title">
            <span className="sos-pulse">SOS</span>
            <div><small>WORKER EMERGENCY</small><h2 id="sos-modal-title">긴급 도움 요청이 발생했습니다</h2></div>
            <dl><div><dt>작업자</dt><dd>{emergencyWorker.worker_name}</dd></div><div><dt>현재 위치</dt><dd>X {emergencyWorker.x.toFixed(1)}m · Y {emergencyWorker.y.toFixed(1)}m</dd></div></dl>
            <p>작업자의 안전을 확인하고 즉시 대응하세요.</p>
            <div className="sos-modal-actions"><button disabled={busy} onClick={() => void action(() => api.acknowledge(emergencyEvent.event_id))}>신고 확인</button><button className="resolve" disabled={busy} onClick={() => void action(() => api.resolve(emergencyEvent.event_id))}>상황 종료</button></div>
          </section>
        </div>
      )}
      {evacuationIncident?.status === "pending_manager" && (
        <FireEvacuationModal incident={evacuationIncident} site={data.site} obstacles={data.obstacles} workers={data.workers} onRefresh={refresh} />
      )}
    </div>
  );
}

export default App;
