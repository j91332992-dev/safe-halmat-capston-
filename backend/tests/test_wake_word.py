from app.services.wake_word_service import WakeWordGate


def test_ordinary_conversation_is_ignored():
    gate = WakeWordGate()
    decision = gate.evaluate("helmet-test", "오늘 작업장 많이 덥네요")
    assert decision.status == "ignored"
    assert decision.reason == "wake_word_missing"


def test_wake_word_and_command_are_accepted():
    gate = WakeWordGate()
    decision = gate.evaluate("helmet-test", "투투스 현재 위험도 알려줘")
    assert decision.status == "command"
    assert decision.command_text == "현재위험도알려줘"


def test_wake_word_only_arms_one_followup():
    gate = WakeWordGate()
    armed = gate.evaluate("helmet-test", "투투스")
    followup = gate.evaluate("helmet-test", "현재 위치 알려줘")
    assert armed.status == "armed"
    assert followup.status == "command"
    assert followup.reason == "armed_followup"


def test_common_stt_variant_is_accepted():
    gate = WakeWordGate()
    decision = gate.evaluate("helmet-test", "투투 쓰 현재 위험도 알려줘")
    assert decision.status == "command"
    assert decision.command_text == "현재위험도알려줘"


def test_fuzzy_prefix_is_accepted_but_mid_sentence_is_not():
    gate = WakeWordGate()
    fuzzy = gate.evaluate("helmet-fuzzy", "투투")
    ordinary = gate.evaluate("helmet-ordinary", "오늘 작업에서 투투스 점검")
    assert fuzzy.status == "armed"
    assert fuzzy.reason in {"wake_word_only", "wake_word_fuzzy_only"}
    assert ordinary.status == "ignored"


def test_life_critical_phrase_bypasses_wake_word():
    gate = WakeWordGate()
    decision = gate.evaluate("helmet-test", "화재 발생")
    assert decision.status == "command"
    assert decision.reason == "life_critical_bypass"


def test_fire_phrase_variants_bypass_wake_word():
    gate = WakeWordGate()
    for phrase in ("화재 발생", "화재가 발생했습니다", "화제 발생", "불이 났습니다"):
        decision = gate.evaluate("helmet-fire", phrase)
        assert decision.status == "command"
        assert decision.reason == "life_critical_bypass"


def test_fire_discussion_does_not_trigger_emergency():
    gate = WakeWordGate()
    decision = gate.evaluate("helmet-fire-talk", "오늘 화재 예방 교육이 있습니다")
    assert decision.status == "ignored"


def test_empty_stt_is_ignored():
    gate = WakeWordGate()
    decision = gate.evaluate("helmet-test", "")
    assert decision.status == "ignored"
    assert decision.reason == "stt_empty"


def test_stt_prompt_echo_is_ignored():
    gate = WakeWordGate()
    for phrase in (
        "산업 안전모 음성 명령입니다. 호출어는 '투투스'입니다. 긴급 명령은 '화재 발생', '비상 상황', '도와줘'입니다.",
        "한국어 산업 안전 현장 대화입니다. 호출어 투투스와 작업자의 짧은 명령을 정확히 받아쓰고, 들리지 않는 내용은 추측하지 마세요.",
    ):
        decision = gate.evaluate("helmet-prompt-echo", phrase)
        assert decision.status == "ignored"
        assert decision.reason == "stt_prompt_echo"

def test_empty_stt_after_wake_requests_retry():
    gate = WakeWordGate()
    assert gate.evaluate("helmet-empty-followup", "투투스").status == "armed"
    decision = gate.evaluate("helmet-empty-followup", "")
    assert decision.status == "command"
    assert decision.command_text == ""
    assert decision.reason == "armed_followup_empty"


def test_retry_rearms_one_followup():
    gate = WakeWordGate()
    gate.arm("helmet-retry")
    decision = gate.evaluate("helmet-retry", "location command")
    assert decision.status == "command"
    assert decision.reason == "retry_followup"


def test_retry_empty_followup_is_marked_terminal():
    gate = WakeWordGate()
    gate.arm("helmet-retry-empty")
    decision = gate.evaluate("helmet-retry-empty", "")
    assert decision.status == "command"
    assert decision.reason == "retry_followup_empty"


def test_new_wake_word_clears_previous_retry_state():
    gate = WakeWordGate()
    gate.arm("helmet-new-session")
    assert gate.evaluate("helmet-new-session", "투투스").status == "armed"
    decision = gate.evaluate("helmet-new-session", "현재 위치 알려줘")
    assert decision.status == "command"
    assert decision.reason == "armed_followup"


def test_control_phrases_bypass_wake_word():
    gate = WakeWordGate()
    assert gate.evaluate("helmet-stop", "그만 말해").command_text == "그만 말해"
    assert gate.evaluate("helmet-call", "전화 끊어줘").command_text == "전화 끊어줘"
