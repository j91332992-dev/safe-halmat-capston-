import type {Anchor, Obstacle, Zone} from '../types';

export interface LayoutIssue {kind: 'anchor' | 'obstacle' | 'zone'; id: string; message: string}

/** Preview validation without silently moving safety objects when the room shrinks. */
export function layoutIssues(site: {width: number; height: number}, anchors: Anchor[], obstacles: Obstacle[], zones: Zone[]): LayoutIssue[] {
  const {width: w, height: h} = site;
  const issues: LayoutIssue[] = [];
  const outside = (x: number, y: number) => !Number.isFinite(x) || !Number.isFinite(y) || x < 0 || y < 0 || x > w + .001 || y > h + .001;
  for (const a of anchors) if (outside(a.x, a.y)) issues.push({kind: 'anchor', id: a.anchor_id, message: `${a.name}: 지도 경계 밖 — 좌표를 수정하거나 꼭짓점 배치를 눌러 주세요.`});
  for (const o of obstacles) {
    if (outside(o.x, o.y) || outside(o.x + o.width, o.y + o.height)) issues.push({kind: 'obstacle', id: o.obstacle_id, message: `${o.name}: 지도 경계 밖`});
    else if (o.object_type === 'emergency_exit' && Math.min(Math.abs(o.x), Math.abs(o.y), Math.abs(w-o.x-o.width), Math.abs(h-o.y-o.height)) > .3) issues.push({kind: 'obstacle', id: o.obstacle_id, message: `${o.name}: 출구가 벽면에서 떨어져 있음`});
  }
  for (const z of zones) {
    const c = z.coordinates as Zone['coordinates'] & {points?: {x: number; y: number}[]};
    const points = z.zone_type === 'polygon' ? (c.points ?? []) : z.zone_type === 'circle'
      ? [{x: c.x-(c.radius ?? 0), y: c.y-(c.radius ?? 0)}, {x: c.x+(c.radius ?? 0), y: c.y+(c.radius ?? 0)}]
      : [{x: c.x, y: c.y}, {x: c.x+(c.width ?? 0), y: c.y+(c.height ?? 0)}];
    if (points.some(p => outside(p.x, p.y))) issues.push({kind: 'zone', id: z.zone_id, message: `${z.zone_name}: 구역이 지도 경계 밖`});
  }
  return issues;
}
