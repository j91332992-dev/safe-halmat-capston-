"""Bounded four-neighbour search: reach a clear wall-side lane, then follow it.

Only registered geometry is checked. A lane is a map preference, not proof that
an unobserved smoke-filled passage is usable. No LLM chooses coordinates.
"""
import heapq


def wall_first_path(start, goals, blocked, width, height, grid, *, budget=120000):
    max_x, max_y = int(width / grid), int(height / grid)
    lane_width = max(.45, grid * 2)
    blocked_cache = {}

    def clear(cell):
        if not (0 <= cell[0] <= max_x and 0 <= cell[1] <= max_y):
            return False
        if cell not in blocked_cache:
            blocked_cache[cell] = blocked(cell)
        return not blocked_cache[cell]

    def boundary_distance(cell):
        x, y = cell[0] * grid, cell[1] * grid
        return min(x, width - x, y, height - y)

    def lane(cell):
        x, y = cell[0] * grid, cell[1] * grid
        return min(x, width - x, y, height - y) <= lane_width

    # A worker already at the exit does not detour to a different wall.
    root = (*start, lane(start) or start in goals, -1)
    costs = {root: 0.}
    previous = {}
    queue = [(0., 0., root)]
    directions = ((1, 0), (0, 1), (-1, 0), (0, -1))
    visited = 0
    while queue and visited < budget:
        _, cost, state = heapq.heappop(queue)
        if cost != costs.get(state):
            continue
        visited += 1
        x, y, reached_wall, facing = state
        if (x, y) in goals and reached_wall:
            states = [state]
            while states[-1] != root:
                states.append(previous[states[-1]])
            states.reverse()
            cells = [(s[0], s[1]) for s in states]
            wall_index = next((i for i, c in enumerate(cells) if lane(c)), 0)
            return cells, {"style": "wall_first_orthogonal", "turn_angle_deg": 90,
                           "wall_approach_cell": cells[wall_index],
                           "wall_lane_m": lane_width, "search_states": visited,
                           "wall_lane_fraction": round(sum(lane(c) for c in cells) / len(cells), 3)}
        for direction, (dx, dy) in enumerate(directions):
            if facing != -1 and (direction-facing) % 4 == 2:
                continue  # no 180-degree route vertex
            cell = (x + dx, y + dy)
            if not clear(cell):
                continue
            # Body centre follows an offset lane, not the physical wall line.
            # A noisy start nearer a wall may only move toward the interior.
            exit_approach = any(abs(cell[0]-g[0]) + abs(cell[1]-g[1]) <= 1 for g in goals)
            if (not exit_approach and boundary_distance(cell) < .25
                    and boundary_distance(cell) <= boundary_distance((x, y))):
                continue
            next_wall = reached_wall or lane(cell)
            nxt = (*cell, next_wall, direction)
            # After reaching a wall, interior travel is allowed only at a higher
            # cost so a blocked wall lane can still be bypassed without crossing it.
            step = 1. if not reached_wall or lane(cell) else 4.
            turn = .35 if facing != -1 and facing != direction else 0.
            score = cost + step + turn
            if score >= costs.get(nxt, float("inf")):
                continue
            costs[nxt] = score
            previous[nxt] = state
            estimate = min(abs(cell[0]-g[0]) + abs(cell[1]-g[1]) for g in goals)
            heapq.heappush(queue, (score + estimate, score, nxt))
    return None, {"style": "wall_first_orthogonal", "search_states": visited,
                  "reason": "search_budget" if visited >= budget else "no_clear_route"}
