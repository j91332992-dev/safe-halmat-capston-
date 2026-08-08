"""기존 로컬 DB를 5.80m x 8.20m UWB 테스트 공간으로 맞춥니다."""
from pathlib import Path
import json
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.database import init_database, session_scope  # noqa: E402
from app.models.entities import Anchor, WorkerState, Zone  # noqa: E402
from app.site_profile import clamp_position, default_anchor_positions  # noqa: E402


def main() -> None:
    init_database()
    with session_scope() as db:
        for index, (anchor_id, (x, y)) in enumerate(default_anchor_positions().items(), start=1):
            anchor = db.get(Anchor, anchor_id)
            if anchor is None:
                anchor = Anchor(
                    anchor_id=anchor_id,
                    name=f"UWB Anchor A{index}",
                    x=x,
                    y=y,
                    z=2.2,
                    online=True,
                )
                db.add(anchor)
            else:
                anchor.name = f"UWB Anchor A{index}"
                anchor.x = x
                anchor.y = y
                anchor.online = True

        worker = db.get(WorkerState, "worker-001")
        if worker is not None:
            worker.x, worker.y = clamp_position(worker.x, worker.y)

        zone = db.get(Zone, "zone-hot-work")
        if zone is not None:
            zone.coordinates_json = json.dumps(
                {"x": 4.0, "y": 5.5, "width": 1.5, "height": 2.0}
            )

    print("[완료] UWB 테스트 공간을 설정했습니다.")
    print(f"  공간: {settings.site_width_m:.2f}m x {settings.site_height_m:.2f}m")
    for anchor_id, (x, y) in default_anchor_positions().items():
        print(f"  {anchor_id}: ({x:.2f}, {y:.2f})m")
    print("  좌표 원점: 테스트 공간 왼쪽 아래")


if __name__ == "__main__":
    main()
