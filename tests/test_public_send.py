"""Test unitari di PublicSendPolicy (slice 02): decisione pura sull'invio.

Modulo puro e deterministico: nessun `time.time()` interno (clock iniettato),
nessun I/O. La suite copre in modo esaustivo ogni combinazione di
`{mode, promoted, kill-switch, allow-list, budget}` e ogni `reason`.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from threading import Barrier

import pytest

from minnarone.config import TwitchSendConfig, TwitchSendMode
from minnarone.public_send import (
    PolicySnapshot,
    PublicSendPolicy,
    SendDecision,
)


class FakeClock:
    """Clock iniettabile: `now` avanza solo quando lo impostiamo noi."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def _policy(config: TwitchSendConfig, clock: FakeClock | None = None):
    return PublicSendPolicy(config, clock=clock or FakeClock())


# --- Modo OFF --------------------------------------------------------------


def test_mode_off_drops_with_mode_off_reason():
    policy = _policy(TwitchSendConfig(mode=TwitchSendMode.OFF))
    decision = policy.decide("ciao a tutti", "canale")
    assert isinstance(decision, SendDecision)
    assert decision.action == "drop"
    assert decision.reason == "mode_off"


def test_mode_off_never_consumes_budget():
    policy = _policy(TwitchSendConfig(mode=TwitchSendMode.OFF, max_per_minute=1))
    for _ in range(5):
        decision = policy.decide("ciao", "canale")
        assert decision.action == "drop"
        assert decision.reason == "mode_off"


# --- Modo SHADOW -----------------------------------------------------------


def test_mode_shadow_shadows_with_ok_reason():
    policy = _policy(TwitchSendConfig(mode=TwitchSendMode.SHADOW))
    decision = policy.decide("ciao a tutti", "canale")
    assert decision.action == "shadow"
    assert decision.reason == "ok"


def test_mode_shadow_ignores_allow_list():
    # In shadow non si invia mai davvero: l'allow-list non blocca.
    policy = _policy(
        TwitchSendConfig(mode=TwitchSendMode.SHADOW, allowed_channels=("altro",))
    )
    decision = policy.decide("ciao", "canale_non_in_lista")
    assert decision.action == "shadow"
    assert decision.reason == "ok"


def test_mode_shadow_consumes_budget():
    # Anche lo shadow consuma budget (fedeltà della prova): con 1 msg/min il
    # secondo shadow entro la finestra viene scartato per budget.
    policy = _policy(TwitchSendConfig(mode=TwitchSendMode.SHADOW, max_per_minute=1))
    first = policy.decide("primo", "canale")
    second = policy.decide("secondo", "canale")
    assert first.action == "shadow"
    assert second.action == "drop"
    assert second.reason == "budget_minute"


# --- Modo LIVE: promozione e kill-switch -----------------------------------


def _live_config(**kwargs) -> TwitchSendConfig:
    # Budget generoso di default: i test di stato non devono inciampare nel
    # budget (che ha default 1 msg/min). I test di budget lo sovrascrivono.
    kwargs.setdefault("allowed_channels", ("canale",))
    kwargs.setdefault("max_per_minute", 1000)
    kwargs.setdefault("max_per_hour", 1000)
    return TwitchSendConfig(mode=TwitchSendMode.LIVE, **kwargs)


def test_live_starts_not_promoted_shadows():
    # Ogni sessione parte in shadow anche con mode: live.
    policy = _policy(_live_config())
    decision = policy.decide("ciao", "canale")
    assert decision.action == "shadow"
    assert decision.reason == "not_promoted"


def test_live_promoted_allowed_channel_sends():
    policy = _policy(_live_config())
    assert policy.promote() is True
    decision = policy.decide("ciao", "canale")
    assert decision.action == "send"
    assert decision.reason == "ok"


def test_live_promoted_channel_not_allowed_drops():
    policy = _policy(_live_config(allowed_channels=("canale",)))
    policy.promote()
    decision = policy.decide("ciao", "altro_canale")
    assert decision.action == "drop"
    assert decision.reason == "channel_not_allowed"


def test_live_allow_list_normalizes_channel():
    # L'allow-list è confrontata sul canale normalizzato (#Canale -> canale).
    policy = _policy(_live_config(allowed_channels=("canale",)))
    policy.promote()
    decision = policy.decide("ciao", "#Canale")
    assert decision.action == "send"
    assert decision.reason == "ok"


def test_live_kill_switch_reverts_to_shadow():
    policy = _policy(_live_config())
    policy.promote()
    policy.engage_kill_switch()
    decision = policy.decide("ciao", "canale")
    assert decision.action == "shadow"
    assert decision.reason == "kill_switch"


def test_invalid_send_credentials_disarm_live_for_rest_of_session():
    policy = _policy(_live_config())
    assert policy.promote() is True

    policy.disable_live()

    assert policy.decide("ciao", "canale").action == "shadow"
    assert policy.promote() is False


def test_live_disabled_is_an_independent_fail_closed_decision_gate():
    policy = _policy(_live_config())
    assert policy.promote() is True

    # Simula uno snapshot concorrente nel punto tra il disarmo permanente e
    # l'ingaggio del kill-switch: live_disabled deve bastare da solo.
    policy._live_disabled = True
    policy._kill_switch = False

    decision = policy.decide("ciao", "canale")

    assert decision.action == "shadow"
    assert decision.reason == "kill_switch"


def test_concurrent_promote_and_disable_always_finish_fail_closed():
    policy = _policy(_live_config())
    start = Barrier(3)

    def promote():
        start.wait()
        return policy.promote()

    def disable():
        start.wait()
        policy.disable_live()

    with ThreadPoolExecutor(max_workers=2) as executor:
        promote_result = executor.submit(promote)
        disable_result = executor.submit(disable)
        start.wait()
        promote_result.result(timeout=1.0)
        disable_result.result(timeout=1.0)

    assert policy.promote() is False
    assert policy.decide("ciao", "canale").action == "shadow"
    assert policy.snapshot().kill_switch is True


def test_kill_switch_reason_distinct_from_not_promoted():
    policy = _policy(_live_config())
    assert policy.decide("a", "canale").reason == "not_promoted"
    policy.promote()
    policy.engage_kill_switch()
    assert policy.decide("a", "canale").reason == "kill_switch"


def test_promote_reenables_after_kill_switch():
    policy = _policy(_live_config())
    policy.promote()
    policy.engage_kill_switch()
    assert policy.promote() is True
    decision = policy.decide("ciao", "canale")
    assert decision.action == "send"
    assert decision.reason == "ok"


# --- Promozione rifiutata se il config non arma live -----------------------


def test_promote_rejected_when_mode_off():
    policy = _policy(TwitchSendConfig(mode=TwitchSendMode.OFF))
    assert policy.promote() is False
    # Nessun cambio di stato: continua a droppare per mode_off.
    assert policy.decide("ciao", "canale").reason == "mode_off"


def test_promote_rejected_when_mode_shadow():
    policy = _policy(TwitchSendConfig(mode=TwitchSendMode.SHADOW))
    assert policy.promote() is False
    # Resta in shadow, non passa a send.
    decision = policy.decide("ciao", "canale")
    assert decision.action == "shadow"
    assert decision.reason == "ok"


# --- Budget: finestre scorrevoli, send e shadow consumano ------------------


def test_live_send_consumes_budget_and_second_drops():
    clock = FakeClock()
    policy = _policy(_live_config(max_per_minute=1), clock)
    policy.promote()
    first = policy.decide("primo", "canale")
    second = policy.decide("secondo", "canale")
    assert first.action == "send"
    assert second.action == "drop"
    assert second.reason == "budget_minute"


def test_drop_does_not_consume_budget():
    # Un drop (canale non permesso) non intacca il budget: appena si autorizza
    # il canale, l'invio è ancora possibile.
    policy = _policy(_live_config(allowed_channels=("canale",), max_per_minute=1))
    policy.promote()
    assert policy.decide("x", "vietato").action == "drop"
    assert policy.decide("x", "vietato").action == "drop"
    # Il budget è intatto: il primo invio sul canale valido passa.
    assert policy.decide("ok", "canale").action == "send"


def test_budget_minute_window_frees_exactly_at_boundary():
    clock = FakeClock(start=0.0)
    policy = _policy(_live_config(max_per_minute=1, max_per_hour=1000), clock)
    policy.promote()
    assert policy.decide("t0", "canale").action == "send"  # ts=0
    clock.now = 59.0
    assert policy.decide("t59", "canale").reason == "budget_minute"
    clock.now = 60.0  # confine: l'evento a t=0 esce dalla finestra
    assert policy.decide("t60", "canale").action == "send"


def test_budget_hour_window_frees_exactly_at_boundary():
    clock = FakeClock(start=0.0)
    policy = _policy(_live_config(max_per_minute=1000, max_per_hour=1), clock)
    policy.promote()
    assert policy.decide("t0", "canale").action == "send"  # ts=0
    clock.now = 3599.0
    assert policy.decide("mid", "canale").reason == "budget_hour"
    clock.now = 3600.0  # confine orario
    assert policy.decide("t3600", "canale").action == "send"


def test_budget_hour_reason_when_minute_ok():
    clock = FakeClock()
    policy = _policy(_live_config(max_per_minute=1000, max_per_hour=2), clock)
    policy.promote()
    clock.now = 0.0
    policy.decide("a", "canale")
    clock.now = 1.0
    policy.decide("b", "canale")
    clock.now = 2.0
    decision = policy.decide("c", "canale")
    assert decision.action == "drop"
    assert decision.reason == "budget_hour"


def test_budget_exhaustion_and_recovery():
    clock = FakeClock()
    policy = _policy(_live_config(max_per_minute=2, max_per_hour=1000), clock)
    policy.promote()
    assert policy.decide("1", "canale").action == "send"
    assert policy.decide("2", "canale").action == "send"
    assert policy.decide("3", "canale").action == "drop"  # esaurito
    clock.now = 61.0  # entrambi gli eventi (t=0) fuori finestra
    assert policy.decide("4", "canale").action == "send"


def test_shadow_budget_drop_reason_is_budget_minute():
    policy = _policy(TwitchSendConfig(mode=TwitchSendMode.SHADOW, max_per_minute=2))
    assert policy.decide("1", "canale").action == "shadow"
    assert policy.decide("2", "canale").action == "shadow"
    third = policy.decide("3", "canale")
    assert third.action == "drop"
    assert third.reason == "budget_minute"


# --- Fallimenti consecutivi e auto-degrado ---------------------------------


def test_failure_threshold_auto_engages_kill_switch():
    policy = _policy(_live_config(failure_threshold=3))
    policy.promote()
    policy.record_failure()
    policy.record_failure()
    # Sotto soglia: ancora live.
    assert policy.decide("x", "canale").action == "send"
    policy.record_failure()  # terza: auto-degrado
    decision = policy.decide("x", "canale")
    assert decision.action == "shadow"
    assert decision.reason == "kill_switch"


def test_record_success_resets_failure_streak():
    policy = _policy(_live_config(failure_threshold=3))
    policy.promote()
    policy.record_failure()
    policy.record_failure()
    policy.record_success()  # azzera la serie
    policy.record_failure()
    policy.record_failure()
    # Solo 2 fallimenti consecutivi dopo il reset: niente auto-degrado.
    assert policy.decide("x", "canale").action == "send"


def test_record_success_does_not_disengage_kill_switch():
    policy = _policy(_live_config(failure_threshold=2))
    policy.promote()
    policy.record_failure()
    policy.record_failure()  # auto-degrado
    policy.record_success()  # NON deve riabilitare live
    decision = policy.decide("x", "canale")
    assert decision.action == "shadow"
    assert decision.reason == "kill_switch"


def test_promote_after_auto_degrade_restores_live():
    policy = _policy(_live_config(failure_threshold=2))
    policy.promote()
    policy.record_failure()
    policy.record_failure()  # kill-switch automatico
    assert policy.promote() is True
    assert policy.decide("x", "canale").action == "send"


def test_promote_resets_failure_counter():
    policy = _policy(_live_config(failure_threshold=2))
    policy.promote()
    policy.record_failure()
    policy.record_failure()  # auto-degrade at threshold
    assert policy.promote() is True
    policy.record_failure()  # single failure after re-promotion must NOT re-degrade
    assert policy.decide("x", "canale").action == "send"


# --- Osservabilità: snapshot -----------------------------------------------


def test_snapshot_reports_initial_state():
    policy = _policy(
        _live_config(max_per_minute=2, max_per_hour=20, failure_threshold=3)
    )
    snap = policy.snapshot()
    assert isinstance(snap, PolicySnapshot)
    assert snap.mode is TwitchSendMode.LIVE
    assert snap.promoted is False
    assert snap.kill_switch is False
    assert snap.consecutive_failures == 0
    assert snap.minute_remaining == 2
    assert snap.hour_remaining == 20
    assert snap.last_decision is None


def test_snapshot_tracks_budget_and_last_decision():
    policy = _policy(_live_config(max_per_minute=2, max_per_hour=20))
    policy.promote()
    decision = policy.decide("ciao", "canale")
    snap = policy.snapshot()
    assert snap.promoted is True
    assert snap.minute_remaining == 1
    assert snap.hour_remaining == 19
    assert snap.last_decision == decision


def test_snapshot_reports_kill_switch_and_failures():
    policy = _policy(_live_config(failure_threshold=5))
    policy.promote()
    policy.record_failure()
    policy.engage_kill_switch()
    snap = policy.snapshot()
    assert snap.kill_switch is True
    assert snap.promoted is False
    assert snap.consecutive_failures == 1


# --- Purezza e validazione degli input -------------------------------------


def test_decide_is_deterministic_for_fixed_clock():
    clock = FakeClock()
    a = _policy(_live_config(), clock)
    b = _policy(_live_config(), clock)
    assert a.decide("stesso", "canale") == b.decide("stesso", "canale")


def test_send_decision_is_frozen():
    decision = SendDecision("send", "ok")
    with pytest.raises(FrozenInstanceError):
        decision.action = "drop"  # type: ignore[misc]


def test_constructor_rejects_non_config():
    with pytest.raises(TypeError):
        PublicSendPolicy("non-una-config", clock=lambda: 0.0)  # type: ignore[arg-type]


def test_constructor_rejects_non_callable_clock():
    with pytest.raises(TypeError):
        PublicSendPolicy(TwitchSendConfig(), clock=123)  # type: ignore[arg-type]
