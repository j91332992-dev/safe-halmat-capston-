from app.services.risk_service import risk_level


def test_risk_level_boundaries():
    assert risk_level(0) == "정상"
    assert risk_level(20) == "관심"
    assert risk_level(40) == "주의"
    assert risk_level(60) == "위험"
    assert risk_level(80) == "비상"

