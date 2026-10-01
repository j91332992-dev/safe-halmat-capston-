from .config import settings


def default_anchor_positions() -> dict[str, tuple[float, float]]:
    """테스트 공간 네 모서리의 기본 Anchor 좌표를 반환합니다."""
    return {
        "anchor-001": (0.0, 0.0),
        "anchor-002": (settings.site_width_m, 0.0),
        "anchor-003": (settings.site_width_m, settings.site_height_m),
        "anchor-004": (0.0, settings.site_height_m),
    }


def clamp_position(x: float, y: float, width: float | None = None, height: float | None = None) -> tuple[float, float]:
    """계산 오차로 좌표가 테스트 공간 밖으로 벗어나지 않게 제한합니다."""
    return (
        max(0.0, min(width if width is not None else settings.site_width_m, x)),
        max(0.0, min(height if height is not None else settings.site_height_m, y)),
    )
