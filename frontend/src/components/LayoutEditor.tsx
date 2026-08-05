import {memo, useEffect, useRef, useState} from "react";
import type {PointerEvent as ReactPointerEvent} from "react";
import {api} from "../services/api";
import type {Anchor, LayoutDraft, LayoutVersion, Obstacle, Snapshot, Worker, Zone} from "../types";

interface Props {
  site: Snapshot["site"];
  anchors: Anchor[];
  obstacles: Obstacle[];
  zones: Zone[];
  workers: Worker[];
  onSaved: () => Promise<void>;
}

type Selection = {kind: "anchor" | "obstacle" | "zone"; id: string} | null;
type RectKind = "obstacle" | "zone";
type Handle = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";
interface EditorSnapshot {
  site: {name: string; width: number; height: number};
  anchors: Anchor[];
  obstacles: Obstacle[];
  zones: Zone[];
}
type Interaction =
  | {kind: "anchor"; id: string; dx: number; dy: number}
  | {kind: "move"; target: RectKind; id: string; dx: number; dy: number}
  | {kind: "resize"; target: RectKind; id: string; handle: Handle; start: {x: number; y: number; width: number; height: number}};

const PAD_X = 70;
const MAP_TOP = 50;
const MAP_RIGHT = 930;
const MAP_BOTTOM = 590;
const MAP_W = MAP_RIGHT - PAD_X;
const MAP_H = MAP_BOTTOM - MAP_TOP;
const HANDLES: Handle[] = ["n", "s", "e", "w", "ne", "nw", "se", "sw"];

const clamp = (value: number, low: number, high: number) => Math.min(Math.max(value, low), high);
const clean = (value: number) => Math.round(value * 100) / 100;

function LayoutEditorComponent({site, anchors, obstacles, zones, workers, onSaved}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const loaded = useRef(false);
  const anchorsRef = useRef(anchors);
  const obstaclesRef = useRef(obstacles);
  const zonesRef = useRef(zones);
  const undoRef = useRef<EditorSnapshot[]>([]);
  const redoRef = useRef<EditorSnapshot[]>([]);
  const [draftSite, setDraftSite] = useState({name: site.name, width: site.width, height: site.height});
  const [localAnchors, setLocalAnchors] = useState(anchors);
  const [localObstacles, setLocalObstacles] = useState(obstacles);
  const [localZones, setLocalZones] = useState(zones);
  const [selection, setSelection] = useState<Selection>(null);
  const [interaction, setInteraction] = useState<Interaction | null>(null);
  const [dirty, setDirty] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("저장된 설계안을 불러오는 중입니다.");
  const [historyRevision, setHistoryRevision] = useState(0);
  const [versions, setVersions] = useState<LayoutVersion[]>([]);
  const [versionName, setVersionName] = useState("");
  const [showVersions, setShowVersions] = useState(false);

  const width = Math.max(0.5, Number(draftSite.width) || 0.5);
  const height = Math.max(0.5, Number(draftSite.height) || 0.5);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    void api.layoutDraft().then(draft => {
      setDraftSite(draft.site);
      anchorsRef.current = draft.anchors;
      obstaclesRef.current = draft.obstacles;
      zonesRef.current = draft.zones.map(zone => ({...zone, allowed_worker_ids: zone.allowed_worker_ids ?? []}));
      setLocalAnchors(anchorsRef.current);
      setLocalObstacles(obstaclesRef.current);
      setLocalZones(zonesRef.current);
      setSavedAt(draft.saved_at ?? null);
      setMessage(draft.saved_at ? "저장된 설계안을 불러왔습니다. 적용 전까지 실시간 지도는 바뀌지 않습니다." : "현재 현장 설정을 새 설계안으로 불러왔습니다.");
      undoRef.current = [];
      redoRef.current = [];
      setHistoryRevision(value => value + 1);
    }).catch(error => setMessage(error instanceof Error ? error.message : "설계안을 불러오지 못했습니다."));
    void api.layoutVersions().then(setVersions);
  }, []);

  const sx = (x: number) => PAD_X + (x / width) * MAP_W;
  const sy = (y: number) => MAP_BOTTOM - (y / height) * MAP_H;
  const toMap = (clientX: number, clientY: number) => {
    const rect = svgRef.current!.getBoundingClientRect();
    const vx = ((clientX - rect.left) / rect.width) * 1000;
    const vy = ((clientY - rect.top) / rect.height) * 640;
    return {
      x: clean(clamp(((vx - PAD_X) / MAP_W) * width, 0, width)),
      y: clean(clamp(((MAP_BOTTOM - vy) / MAP_H) * height, 0, height))
    };
  };

  const replaceAnchors = (next: Anchor[]) => {
    anchorsRef.current = next;
    setLocalAnchors(next);
    setDirty(true);
  };
  const replaceObstacles = (next: Obstacle[]) => {
    obstaclesRef.current = next;
    setLocalObstacles(next);
    setDirty(true);
  };
  const replaceZones = (next: Zone[]) => {
    zonesRef.current = next;
    setLocalZones(next);
    setDirty(true);
  };

  const capture = (): EditorSnapshot => ({
    site: {...draftSite},
    anchors: structuredClone(anchorsRef.current),
    obstacles: structuredClone(obstaclesRef.current),
    zones: structuredClone(zonesRef.current)
  });
  const restore = (snapshot: EditorSnapshot) => {
    setDraftSite(snapshot.site);
    anchorsRef.current = structuredClone(snapshot.anchors);
    obstaclesRef.current = structuredClone(snapshot.obstacles);
    zonesRef.current = structuredClone(snapshot.zones);
    setLocalAnchors(anchorsRef.current);
    setLocalObstacles(obstaclesRef.current);
    setLocalZones(zonesRef.current);
    setSelection(null);
    setDirty(true);
  };
  const checkpoint = () => {
    undoRef.current = [...undoRef.current.slice(-49), capture()];
    redoRef.current = [];
    setHistoryRevision(value => value + 1);
  };
  const undo = () => {
    const previous = undoRef.current.pop();
    if (!previous) return;
    redoRef.current.push(capture());
    restore(previous);
    setHistoryRevision(value => value + 1);
    setMessage("이전 편집 상태로 되돌렸습니다.");
  };
  const redo = () => {
    const next = redoRef.current.pop();
    if (!next) return;
    undoRef.current.push(capture());
    restore(next);
    setHistoryRevision(value => value + 1);
    setMessage("되돌린 편집을 다시 적용했습니다.");
  };
  const rectForZone = (zone: Zone) => ({
    x: Number(zone.coordinates.x),
    y: Number(zone.coordinates.y),
    width: Number(zone.coordinates.width ?? 1),
    height: Number(zone.coordinates.height ?? 1)
  });
  const withZoneRect = (zone: Zone, rect: {x: number; y: number; width: number; height: number}): Zone => ({
    ...zone,
    coordinates: {...zone.coordinates, ...rect}
  });

  const updateRect = (target: RectKind, id: string, updater: (rect: {x: number; y: number; width: number; height: number}) => {x: number; y: number; width: number; height: number}) => {
    if (target === "obstacle") {
      replaceObstacles(obstaclesRef.current.map(item => item.obstacle_id === id ? {...item, ...updater(item)} : item));
    } else {
      replaceZones(zonesRef.current.map(item => item.zone_id === id ? withZoneRect(item, updater(rectForZone(item))) : item));
    }
  };

  const onPointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!interaction) return;
    const point = toMap(event.clientX, event.clientY);
    if (interaction.kind === "anchor") {
      replaceAnchors(anchorsRef.current.map(anchor => anchor.anchor_id === interaction.id
        ? {...anchor, x: clean(clamp(point.x - interaction.dx, 0, width)), y: clean(clamp(point.y - interaction.dy, 0, height))}
        : anchor));
      return;
    }
    if (interaction.kind === "move") {
      updateRect(interaction.target, interaction.id, rect => ({
        ...rect,
        x: clean(clamp(point.x - interaction.dx, 0, width - rect.width)),
        y: clean(clamp(point.y - interaction.dy, 0, height - rect.height))
      }));
      return;
    }
    const start = interaction.start;
    const right = start.x + start.width;
    const top = start.y + start.height;
    let next = {...start};
    if (interaction.handle.includes("w")) {
      next.x = clean(clamp(point.x, 0, right - 0.1));
      next.width = clean(right - next.x);
    }
    if (interaction.handle.includes("e")) next.width = clean(clamp(point.x - start.x, 0.1, width - start.x));
    if (interaction.handle.includes("s")) {
      next.y = clean(clamp(point.y, 0, top - 0.1));
      next.height = clean(top - next.y);
    }
    if (interaction.handle.includes("n")) next.height = clean(clamp(point.y - start.y, 0.1, height - start.y));
    updateRect(interaction.target, interaction.id, () => next);
  };

  const beginAnchor = (event: ReactPointerEvent, anchor: Anchor) => {
    event.stopPropagation();
    checkpoint();
    const point = toMap(event.clientX, event.clientY);
    svgRef.current?.setPointerCapture(event.pointerId);
    setSelection({kind: "anchor", id: anchor.anchor_id});
    setInteraction({kind: "anchor", id: anchor.anchor_id, dx: point.x - anchor.x, dy: point.y - anchor.y});
  };

  const beginRect = (event: ReactPointerEvent, target: RectKind, id: string, rect: {x: number; y: number; width: number; height: number}) => {
    event.stopPropagation();
    checkpoint();
    const point = toMap(event.clientX, event.clientY);
    svgRef.current?.setPointerCapture(event.pointerId);
    setSelection({kind: target, id});
    setInteraction({kind: "move", target, id, dx: point.x - rect.x, dy: point.y - rect.y});
  };

  const beginResize = (event: ReactPointerEvent, target: RectKind, id: string, handle: Handle, rect: {x: number; y: number; width: number; height: number}) => {
    event.stopPropagation();
    checkpoint();
    svgRef.current?.setPointerCapture(event.pointerId);
    setInteraction({kind: "resize", target, id, handle, start: {...rect}});
  };

  const handlePosition = (rect: {x: number; y: number; width: number; height: number}, handle: Handle) => {
    const x = handle.includes("w") ? rect.x : handle.includes("e") ? rect.x + rect.width : rect.x + rect.width / 2;
    const y = handle.includes("s") ? rect.y : handle.includes("n") ? rect.y + rect.height : rect.y + rect.height / 2;
    return {x: sx(x), y: sy(y)};
  };

  const renderHandles = (target: RectKind, id: string, rect: {x: number; y: number; width: number; height: number}) => (
    <g className="resize-handles">
      {HANDLES.map(handle => {
        const point = handlePosition(rect, handle);
        return <rect key={handle} className={"resize-handle handle-" + handle} x={point.x - 7} y={point.y - 7} width="14" height="14" onPointerDown={event => beginResize(event, target, id, handle, rect)} />;
      })}
    </g>
  );

  const selectedAnchor = selection?.kind === "anchor" ? localAnchors.find(item => item.anchor_id === selection.id) : undefined;
  const selectedObstacle = selection?.kind === "obstacle" ? localObstacles.find(item => item.obstacle_id === selection.id) : undefined;
  const selectedZone = selection?.kind === "zone" ? localZones.find(item => item.zone_id === selection.id) : undefined;

  const addObstacle = () => {
    checkpoint();
    const item: Obstacle = {
      obstacle_id: "obstacle-" + Date.now(),
      name: "새 장애물 " + (localObstacles.length + 1),
      x: clean(Math.max(0, width / 2 - 0.5)),
      y: clean(Math.max(0, height / 2 - 0.5)),
      width: Math.min(1, width),
      height: Math.min(1, height)
    };
    replaceObstacles([...obstaclesRef.current, item]);
    setSelection({kind: "obstacle", id: item.obstacle_id});
    setMessage("장애물을 설계안에 추가했습니다. 아직 현장에는 적용되지 않았습니다.");
  };

  const addZone = () => {
    checkpoint();
    const item: Zone = {
      zone_id: "zone-" + Date.now(),
      zone_name: "새 제한구역 " + (localZones.length + 1),
      zone_type: "rectangle",
      coordinates: {x: clean(Math.max(0, width / 2 - 0.75)), y: clean(Math.max(0, height / 2 - 0.75)), width: Math.min(1.5, width), height: Math.min(1.5, height)},
      required_ppe: [],
      allowed_worker_ids: [],
      risk_weight: 30,
      warning_message: "허가되지 않은 작업자가 제한구역에 진입했습니다.",
      max_stay_seconds: 0,
      active: true
    };
    replaceZones([...zonesRef.current, item]);
    setSelection({kind: "zone", id: item.zone_id});
    setMessage("제한구역을 설계안에 추가했습니다. 허용 작업자를 선택하세요.");
  };

  const arrangeCorners = () => {
    checkpoint();
    const positions = [[0, 0], [width, 0], [width, height], [0, height]];
    const arranged = [...anchorsRef.current].sort((a, b) => a.anchor_id.localeCompare(b.anchor_id))
      .map((anchor, index) => index < 4 ? {...anchor, x: positions[index][0], y: positions[index][1]} : anchor);
    replaceAnchors(arranged);
    setMessage("A1 왼쪽 아래 → A2 오른쪽 아래 → A3 오른쪽 위 → A4 왼쪽 위로 설계했습니다.");
  };

  const saveDraft = async () => {
    if (!(draftSite.width > 0.5 && draftSite.height > 0.5)) {
      setMessage("작업장 가로와 세로는 0.5m보다 크게 입력하세요.");
      return;
    }
    setBusy(true);
    try {
      const draft: Omit<LayoutDraft, "saved_at"> = {
        site: draftSite,
        anchors: anchorsRef.current,
        obstacles: obstaclesRef.current,
        zones: zonesRef.current
      };
      const result = await api.saveLayoutDraft(draft);
      setSavedAt(result.saved_at);
      setDirty(false);
      setMessage("설계안을 저장했습니다. 실제 지도에는 아직 적용되지 않았습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "설계안 저장에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  };

  const applyDraft = async () => {
    if (dirty) {
      setMessage("변경 내용을 먼저 ‘설계 저장’한 뒤 적용하세요.");
      return;
    }
    if (!savedAt) {
      setMessage("먼저 설계안을 저장하세요.");
      return;
    }
    setBusy(true);
    try {
      await api.applyLayoutDraft();
      await onSaved();
      setMessage("저장된 설계안을 실제 현장 지도와 UWB 계산에 적용했습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "현장 적용에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  };

  const refreshVersions = async () => setVersions(await api.layoutVersions());
  const createVersion = async () => {
    if (dirty || !savedAt) {
      setMessage("설계안을 먼저 저장한 뒤 버전으로 보관하세요.");
      return;
    }
    const name = versionName.trim() || "설계 " + new Date().toLocaleString("ko-KR");
    setBusy(true);
    try {
      await api.createLayoutVersion(name);
      setVersionName("");
      await refreshVersions();
      setMessage("‘" + name + "’ 버전을 보관했습니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "버전 저장에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  };
  const loadVersion = async (versionId: string) => {
    checkpoint();
    setBusy(true);
    try {
      const draft = await api.loadLayoutVersion(versionId);
      setDraftSite(draft.site);
      anchorsRef.current = draft.anchors;
      obstaclesRef.current = draft.obstacles;
      zonesRef.current = draft.zones;
      setLocalAnchors(draft.anchors);
      setLocalObstacles(draft.obstacles);
      setLocalZones(draft.zones);
      setSavedAt(draft.saved_at ?? new Date().toISOString());
      setDirty(false);
      setSelection(null);
      setMessage("선택한 버전을 설계안으로 불러왔습니다. ‘현장에 적용’을 눌러야 실제 반영됩니다.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "버전을 불러오지 못했습니다.");
    } finally {
      setBusy(false);
    }
  };
  const deleteVersion = async (versionId: string) => {
    setBusy(true);
    try {
      await api.deleteLayoutVersion(versionId);
      await refreshVersions();
      setMessage("설계 버전을 삭제했습니다.");
    } finally {
      setBusy(false);
    }
  };
  const updateAnchor = (field: "name" | "x" | "y" | "z", value: string) => {
    if (!selectedAnchor) return;
    replaceAnchors(anchorsRef.current.map(item => item.anchor_id === selectedAnchor.anchor_id ? {...item, [field]: field === "name" ? value : Number(value)} : item));
  };
  const updateObstacle = (field: keyof Obstacle, value: string) => {
    if (!selectedObstacle) return;
    replaceObstacles(obstaclesRef.current.map(item => item.obstacle_id === selectedObstacle.obstacle_id ? {...item, [field]: field === "name" ? value : Number(value)} : item));
  };
  const updateZone = (updater: (zone: Zone) => Zone) => {
    if (!selectedZone) return;
    replaceZones(zonesRef.current.map(item => item.zone_id === selectedZone.zone_id ? updater(item) : item));
  };

  return (
    <section className="layout-editor">
      <header className="layout-editor-head">
        <div><span className="eyebrow">SITE BLUEPRINT EDITOR</span><h2>작업장 설계도 편집</h2><p>편집 → 설계 저장 → 현장 적용 순서로 진행합니다.</p></div>
        <div className="editor-actions" data-history-revision={historyRevision}>
          <button className="history-action" onClick={undo} disabled={busy || undoRef.current.length === 0}>↶ 실행취소</button>
          <button className="history-action" onClick={redo} disabled={busy || redoRef.current.length === 0}>↷ 다시실행</button>
          <button className="version-action" onClick={() => setShowVersions(value => !value)}>버전 관리</button>
          <button onClick={arrangeCorners} disabled={busy || localAnchors.length < 4}>앵커 꼭짓점 배치</button>
          <button onClick={addObstacle} disabled={busy}>+ 장애물</button>
          <button className="danger-action" onClick={addZone} disabled={busy}>+ 제한구역</button>
          <button className="save-draft" onClick={() => void saveDraft()} disabled={busy || !dirty}>설계 저장</button>
          <button className="apply-draft" onClick={() => void applyDraft()} disabled={busy || dirty || !savedAt}>현장에 적용</button>
        </div>
      </header>

      <div className="draft-status">
        <span className={dirty ? "dirty" : "saved"}>{dirty ? "● 저장되지 않은 변경 있음" : "✓ 설계안 저장됨"}</span>
        <small>{savedAt ? "마지막 저장 " + new Date(savedAt).toLocaleString("ko-KR") : "아직 저장된 설계안 없음"}</small>
        <b>현장 적용 전까지 실시간 UWB 지도는 변경되지 않습니다.</b>
      </div>

      {showVersions && (
        <div className="version-panel">
          <div className="version-create">
            <label>새 버전 이름<input placeholder="예: 1차 앵커 배치 완료" value={versionName} onChange={event => setVersionName(event.target.value)} /></label>
            <button onClick={() => void createVersion()} disabled={busy || dirty || !savedAt}>현재 저장안을 버전으로 보관</button>
          </div>
          <div className="version-list">
            {versions.length === 0 && <span>저장된 버전이 없습니다.</span>}
            {versions.map(version => (
              <article key={version.version_id}>
                <div><b>{version.name}</b><small>{new Date(version.created_at).toLocaleString("ko-KR")}</small></div>
                <button onClick={() => void loadVersion(version.version_id)} disabled={busy}>불러오기</button>
                <button className="delete-version" onClick={() => void deleteVersion(version.version_id)} disabled={busy}>삭제</button>
              </article>
            ))}
          </div>
        </div>
      )}

      <div className="site-size-form">
        <label>작업장 이름<input value={draftSite.name} onChange={event => {checkpoint(); setDraftSite({...draftSite, name: event.target.value}); setDirty(true);}} /></label>
        <label>가로 X (m)<input type="number" min=".5" step=".1" value={draftSite.width} onChange={event => {checkpoint(); setDraftSite({...draftSite, width: Number(event.target.value)}); setDirty(true);}} /></label>
        <label>세로 Y (m)<input type="number" min=".5" step=".1" value={draftSite.height} onChange={event => {checkpoint(); setDraftSite({...draftSite, height: Number(event.target.value)}); setDirty(true);}} /></label>
      </div>

      <div className="editor-workspace">
        <div className="blueprint-wrap">
          <svg ref={svgRef} className="blueprint" viewBox="0 0 1000 640" onPointerMove={onPointerMove} onPointerUp={() => setInteraction(null)} onPointerCancel={() => setInteraction(null)}>
            <defs><pattern id="blueprint-grid" width="43" height="27" patternUnits="userSpaceOnUse"><path d="M43 0H0V27" fill="none" stroke="rgba(95,202,243,.12)" /></pattern></defs>
            <rect x={PAD_X} y={MAP_TOP} width={MAP_W} height={MAP_H} rx="4" className="blueprint-floor" onPointerDown={() => setSelection(null)} />
            <rect x={PAD_X} y={MAP_TOP} width={MAP_W} height={MAP_H} rx="4" fill="url(#blueprint-grid)" pointerEvents="none" />
            <text x={PAD_X} y="35" className="dimension-label">가로 X = {width.toFixed(2)}m</text>
            <text x="17" y={(MAP_TOP + MAP_BOTTOM) / 2} className="dimension-label vertical">세로 Y = {height.toFixed(2)}m</text>

            {localObstacles.map(item => {
              const selected = selection?.kind === "obstacle" && selection.id === item.obstacle_id;
              return <g key={item.obstacle_id} className={"blueprint-obstacle " + (selected ? "selected" : "")}>
                <rect x={sx(item.x)} y={sy(item.y + item.height)} width={(item.width / width) * MAP_W} height={(item.height / height) * MAP_H} onPointerDown={event => beginRect(event, "obstacle", item.obstacle_id, item)} />
                <text className="center-label" x={sx(item.x + item.width / 2)} y={sy(item.y + item.height / 2) - 4} textAnchor="middle">{item.name}</text>
                <text className="center-size" x={sx(item.x + item.width / 2)} y={sy(item.y + item.height / 2) + 14} textAnchor="middle">{item.width.toFixed(2)} × {item.height.toFixed(2)}m</text>
                {selected && renderHandles("obstacle", item.obstacle_id, item)}
              </g>;
            })}

            {localZones.filter(zone => zone.zone_type === "rectangle").map(zone => {
              const rect = rectForZone(zone);
              const selected = selection?.kind === "zone" && selection.id === zone.zone_id;
              return <g key={zone.zone_id} className={"blueprint-zone " + (selected ? "selected" : "")}>
                <rect x={sx(rect.x)} y={sy(rect.y + rect.height)} width={(rect.width / width) * MAP_W} height={(rect.height / height) * MAP_H} onPointerDown={event => beginRect(event, "zone", zone.zone_id, rect)} />
                <text className="center-label" x={sx(rect.x + rect.width / 2)} y={sy(rect.y + rect.height / 2) - 4} textAnchor="middle">{zone.zone_name}</text>
                <text className="center-size" x={sx(rect.x + rect.width / 2)} y={sy(rect.y + rect.height / 2) + 14} textAnchor="middle">허용 {zone.allowed_worker_ids?.length ?? 0}명</text>
                {selected && renderHandles("zone", zone.zone_id, rect)}
              </g>;
            })}

            {localAnchors.map((anchor, index) => {
              const selected = selection?.kind === "anchor" && selection.id === anchor.anchor_id;
              return <g key={anchor.anchor_id} className={"blueprint-anchor " + (selected ? "selected" : "")} transform={"translate(" + sx(anchor.x) + "," + sy(anchor.y) + ")"} onPointerDown={event => beginAnchor(event, anchor)}>
                <circle r="18" /><text textAnchor="middle" y="4">A{index + 1}</text><text className="anchor-coordinate" textAnchor="middle" y="37">({anchor.x.toFixed(2)}, {anchor.y.toFixed(2)})</text>
              </g>;
            })}
          </svg>
          <div className="editor-message">{busy ? "처리 중…" : message}</div>
        </div>

        <aside className="property-panel">
          <div className="property-title"><span>선택 객체</span><b>{selectedAnchor?.name ?? selectedObstacle?.name ?? selectedZone?.zone_name ?? "선택 안 됨"}</b></div>
          {!selection && <p className="property-empty">지도에서 앵커, 장애물 또는 제한구역을 선택하세요.</p>}
          {selectedAnchor && <div className="property-form">
            <label>앵커 이름<input value={selectedAnchor.name} onChange={event => updateAnchor("name", event.target.value)} /></label>
            <div className="property-pair"><label>X (m)<input type="number" step=".01" value={selectedAnchor.x} onChange={event => updateAnchor("x", event.target.value)} /></label><label>Y (m)<input type="number" step=".01" value={selectedAnchor.y} onChange={event => updateAnchor("y", event.target.value)} /></label></div>
            <label>설치 높이 Z (m)<input type="number" step=".01" value={selectedAnchor.z} onChange={event => updateAnchor("z", event.target.value)} /></label>
          </div>}
          {selectedObstacle && <div className="property-form">
            <label>장애물 이름<input value={selectedObstacle.name} onChange={event => updateObstacle("name", event.target.value)} /></label>
            <div className="property-pair"><label>X (m)<input type="number" step=".01" value={selectedObstacle.x} onChange={event => updateObstacle("x", event.target.value)} /></label><label>Y (m)<input type="number" step=".01" value={selectedObstacle.y} onChange={event => updateObstacle("y", event.target.value)} /></label></div>
            <div className="property-pair"><label>가로 (m)<input type="number" min=".1" step=".01" value={selectedObstacle.width} onChange={event => updateObstacle("width", event.target.value)} /></label><label>세로 (m)<input type="number" min=".1" step=".01" value={selectedObstacle.height} onChange={event => updateObstacle("height", event.target.value)} /></label></div>
            <button className="delete-property" onClick={() => {checkpoint(); replaceObstacles(obstaclesRef.current.filter(item => item.obstacle_id !== selectedObstacle.obstacle_id)); setSelection(null);}}>장애물 삭제</button>
          </div>}
          {selectedZone && <div className="property-form">
            <label>제한구역 이름<input value={selectedZone.zone_name} onChange={event => updateZone(zone => ({...zone, zone_name: event.target.value}))} /></label>
            <div className="property-pair"><label>X (m)<input type="number" step=".01" value={selectedZone.coordinates.x} onChange={event => updateZone(zone => ({...zone, coordinates: {...zone.coordinates, x: Number(event.target.value)}}))} /></label><label>Y (m)<input type="number" step=".01" value={selectedZone.coordinates.y} onChange={event => updateZone(zone => ({...zone, coordinates: {...zone.coordinates, y: Number(event.target.value)}}))} /></label></div>
            <div className="property-pair"><label>가로 (m)<input type="number" min=".1" step=".01" value={selectedZone.coordinates.width} onChange={event => updateZone(zone => ({...zone, coordinates: {...zone.coordinates, width: Number(event.target.value)}}))} /></label><label>세로 (m)<input type="number" min=".1" step=".01" value={selectedZone.coordinates.height} onChange={event => updateZone(zone => ({...zone, coordinates: {...zone.coordinates, height: Number(event.target.value)}}))} /></label></div>
            <label>진입 경고문<input value={selectedZone.warning_message} onChange={event => updateZone(zone => ({...zone, warning_message: event.target.value}))} /></label>
            <div className="worker-permission"><b>출입 허용 작업자</b><small>선택되지 않은 작업자가 들어오면 경보가 발생합니다.</small>
              {workers.map(worker => <label key={worker.worker_id}><input type="checkbox" checked={selectedZone.allowed_worker_ids?.includes(worker.worker_id) ?? false} onChange={event => updateZone(zone => ({...zone, allowed_worker_ids: event.target.checked ? [...(zone.allowed_worker_ids ?? []), worker.worker_id] : (zone.allowed_worker_ids ?? []).filter(id => id !== worker.worker_id)}))} /><span>{worker.worker_name}</span><em>{worker.worker_id}</em></label>)}
            </div>
            <button className="delete-property" onClick={() => {checkpoint(); replaceZones(zonesRef.current.filter(item => item.zone_id !== selectedZone.zone_id)); setSelection(null);}}>제한구역 삭제</button>
          </div>}
          <div className="object-summary"><span>앵커 <b>{localAnchors.length}</b></span><span>장애물 <b>{localObstacles.length}</b></span><span>제한구역 <b>{localZones.length}</b></span></div>
        </aside>
      </div>
    </section>
  );
}

const sameDesign = (left: Props, right: Props) =>
  JSON.stringify([left.site, left.anchors, left.obstacles, left.zones, left.workers.map(worker => [worker.worker_id, worker.worker_name])])
  === JSON.stringify([right.site, right.anchors, right.obstacles, right.zones, right.workers.map(worker => [worker.worker_id, worker.worker_name])]);

export const LayoutEditor = memo(LayoutEditorComponent, sameDesign);
