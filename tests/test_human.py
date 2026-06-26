"""Test unitari di HumanLikeness (slice 08): typing delay, dedup, #end_conv.

Modulo puro e deterministico: nessuno sleep reale, nessuna dipendenza esterna.
"""

from minnarone.human import (
    END_CONV_SENTINEL,
    HumanDecision,
    HumanLikeness,
)

# --- Typing delay ----------------------------------------------------------


def test_typing_delay_grows_with_message_length():
    hl = HumanLikeness(typing_speed=10.0, min_delay=0.0, max_delay=100.0)
    short = hl.process("ciao")
    long = hl.process("ciao " * 20)
    assert not short.drop and not long.drop
    assert long.delay > short.delay


def test_typing_delay_proportional_to_chars():
    hl = HumanLikeness(typing_speed=10.0, min_delay=0.0, max_delay=100.0)
    # 50 caratteri / 10 cps = 5.0s
    msg = "x" * 50
    assert hl.process(msg).delay == 5.0


def test_typing_delay_respects_min_bound():
    hl = HumanLikeness(typing_speed=10.0, min_delay=1.0, max_delay=100.0)
    # "ok" sarebbe 0.2s grezzi, ma il minimo lo alza a 1.0
    assert hl.process("ok").delay == 1.0


def test_typing_delay_respects_max_bound():
    hl = HumanLikeness(typing_speed=10.0, min_delay=0.0, max_delay=3.0)
    assert hl.process("x" * 500).delay == 3.0


def test_process_is_pure_no_state_mutation():
    # Chiamate ripetute con lo stesso input danno lo stesso risultato.
    hl = HumanLikeness()
    a = hl.process("un messaggio qualunque")
    b = hl.process("un messaggio qualunque")
    assert a == b


# --- Dedup -----------------------------------------------------------------


def test_near_duplicate_is_dropped():
    hl = HumanLikeness(dedup_threshold=0.9)
    decision = hl.process(
        "ciao a tutti come va oggi",
        recent_self_messages=["ciao a tutti come va oggi!"],
    )
    assert decision.drop is True


def test_exact_duplicate_ignoring_case_and_space_is_dropped():
    hl = HumanLikeness(dedup_threshold=0.9)
    decision = hl.process(
        "  CIAO   a Tutti  ",
        recent_self_messages=["ciao a tutti"],
    )
    assert decision.drop is True


def test_sufficiently_different_message_is_sent():
    hl = HumanLikeness(dedup_threshold=0.9)
    decision = hl.process(
        "parliamo invece del meteo di domani",
        recent_self_messages=["ciao a tutti come va oggi"],
    )
    assert decision.drop is False
    assert decision.message == "parliamo invece del meteo di domani"


def test_no_recent_messages_never_dedups():
    hl = HumanLikeness()
    assert hl.process("qualcosa", recent_self_messages=[]).drop is False


# --- #end_conv -------------------------------------------------------------


def test_end_conv_sets_flag_and_strips_sentinel():
    hl = HumanLikeness()
    decision = hl.process(f"va bene, ci vediamo {END_CONV_SENTINEL}")
    assert decision.end_conv is True
    assert END_CONV_SENTINEL not in decision.message
    assert decision.message == "va bene, ci vediamo"
    assert decision.drop is False  # c'è ancora testo utile da inviare


def test_end_conv_only_sentinel_drops_message():
    # Se il messaggio è SOLO il sentinella, non esce nessun testo letterale.
    hl = HumanLikeness()
    decision = hl.process(END_CONV_SENTINEL)
    assert decision.end_conv is True
    assert decision.drop is True
    assert decision.message == ""


def test_no_end_conv_flag_when_absent():
    hl = HumanLikeness()
    decision = hl.process("ciao")
    assert decision.end_conv is False


def test_empty_message_is_dropped():
    hl = HumanLikeness()
    decision = hl.process("   ")
    assert decision.drop is True
    assert decision.end_conv is False


def test_decision_type():
    hl = HumanLikeness()
    assert isinstance(hl.process("ciao"), HumanDecision)


def test_end_conv_only_as_delimited_token_not_substring():
    h = HumanLikeness()
    # sentinella dentro una parola: NON è un comando di chiusura
    d = h.process("ok#end_convnow")
    assert d.end_conv is False
    assert d.message == "ok#end_convnow"


def test_end_conv_midmessage_collapses_whitespace():
    h = HumanLikeness()
    d = h.process("ciao #end_conv come stai")
    assert d.end_conv is True
    assert d.message == "ciao come stai"   # niente spazi doppi
    assert d.drop is False


def test_invalid_dedup_threshold_raises():
    import pytest
    with pytest.raises(ValueError):
        HumanLikeness(dedup_threshold=1.5)
    with pytest.raises(ValueError):
        HumanLikeness(dedup_threshold=-0.1)
