def build_response(intent: str, worker: dict) -> tuple[str, str | None]:
    responses = {
        "call_manager": ("관리자에게 호출을 전송했습니다.", "play_tone"),
        "status_report": (f"현재 상태는 {worker['risk_level']}입니다.", "play_tone"),
        "location_query": (f"현재 위치는 X {worker['x']:.1f}, Y {worker['y']:.1f} 미터입니다.", "play_tone"),
        "risk_query": (f"현재 위험도는 {worker['risk_score']}점, {worker['risk_level']} 단계입니다.", "play_tone"),
        "help": ("도움 요청을 관제실에 전송했습니다.", "play_alert"),
        "emergency": ("비상 신고를 접수했습니다.", "play_alert"),
        "repeat_warning": ("최근 경고를 다시 재생합니다.", "play_alert"),
    }
    return responses.get(intent, ("명령을 이해하지 못했습니다.", None))

