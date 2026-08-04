"""Platform-neutral public output safety policy.

È il cuore della sicurezza dell'output pubblico. Dato un messaggio candidato,
il canale bersaglio e l'istante corrente (clock INIETTATO), decide se il
messaggio viene davvero inviato (`send`), solo registrato come "sarebbe stato
inviato" (`shadow`) o scartato (`drop`), in base al proprio stato interno:
modo configurato, promozione/kill-switch, allow-list, budget a finestra
scorrevole e conteggio dei fallimenti consecutivi.

Come `HumanLikeness`, è PURO e deterministico: nessun I/O, niente
`time.time()` interno (il clock è iniettato, come lo sleep del Reactor),
nessuna attesa. Tutte le transizioni di stato sono esplicite
(`promote`, `engage_kill_switch`, `record_failure`, `record_success`).
Decisioni, budget e transizioni sono serializzati da un lock reentrante: la
revoca permanente vince anche se arriva insieme a una promozione operatore.

Vocabolario chiuso delle decisioni (contratto per router, eventi e TUI dei
prossimi slice):

- azioni: ``send``, ``shadow``, ``drop``
- motivi: ``ok``, ``mode_off``, ``not_promoted``, ``kill_switch``,
  ``channel_not_allowed``, ``budget_minute``, ``budget_hour``
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from threading import RLock

# --- Vocabolario chiuso delle azioni e dei motivi --------------------------

ACTION_SEND = "send"
ACTION_SHADOW = "shadow"
ACTION_DROP = "drop"

REASON_OK = "ok"
REASON_MODE_OFF = "mode_off"
REASON_NOT_PROMOTED = "not_promoted"
REASON_KILL_SWITCH = "kill_switch"
REASON_CHANNEL_NOT_ALLOWED = "channel_not_allowed"
REASON_BUDGET_MINUTE = "budget_minute"
REASON_BUDGET_HOUR = "budget_hour"

# Ampiezza delle finestre di budget (secondi). Scorrevoli: un timestamp `ts`
# occupa la finestra finché `now - ts < ampiezza` (confine esatto: alla soglia
# lo slot si libera).
_MINUTE_WINDOW = 60.0
_HOUR_WINDOW = 3600.0


class PublicSendMode(Enum):
    """Configured public-output posture for one platform target."""

    OFF = "off"
    SHADOW = "shadow"
    LIVE = "live"


@dataclass(frozen=True, slots=True)
class PublicTarget:
    """Stable, namespaced identifier authorized for public output."""

    platform: str
    identifier: str

    def __post_init__(self) -> None:
        if not isinstance(self.platform, str) or not self.platform.strip():
            raise ValueError("public target platform must be a non-empty string")
        if not isinstance(self.identifier, str) or not self.identifier.strip():
            raise ValueError("public target identifier must be a non-empty string")
        object.__setattr__(self, "platform", self.platform.strip().lower())
        object.__setattr__(self, "identifier", self.identifier.strip())


@dataclass(frozen=True, slots=True)
class PublicSendConfig:
    """Neutral inputs consumed by :class:`PublicSendPolicy`."""

    mode: PublicSendMode = PublicSendMode.OFF
    allowed_targets: tuple[PublicTarget, ...] = ()
    max_per_minute: int = 1
    max_per_hour: int = 20
    failure_threshold: int = 3

    def __post_init__(self) -> None:
        mode = self.mode
        if isinstance(mode, str):
            try:
                mode = PublicSendMode(mode)
            except ValueError as exc:
                raise ValueError(
                    "public send mode must be off, shadow, or live"
                ) from exc
        if not isinstance(mode, PublicSendMode):
            raise TypeError("public send mode must be a PublicSendMode")
        object.__setattr__(self, "mode", mode)

        targets = self.allowed_targets
        if not isinstance(targets, (list, tuple)):
            raise TypeError("allowed_targets must be a list of PublicTarget values")
        if not all(isinstance(target, PublicTarget) for target in targets):
            raise TypeError("allowed_targets must contain only PublicTarget values")
        object.__setattr__(self, "allowed_targets", tuple(targets))

        for name in ("max_per_minute", "max_per_hour", "failure_threshold"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be an integer >= 1")


@dataclass(frozen=True, slots=True)
class SendDecision:
    """Esito immutabile della decisione su un messaggio pubblico.

    Attributi:
        action: ``send`` | ``shadow`` | ``drop``.
        reason: motivo dal vocabolario chiuso (vedi costanti ``REASON_*``).
    """

    action: str
    reason: str


@dataclass(frozen=True, slots=True)
class PolicySnapshot:
    """Fotografia read-only dello stato della policy (osservabilità slice 04).

    Solo dati semplici: nessun riferimento allo stato mutabile interno.
    """

    mode: PublicSendMode
    promoted: bool
    kill_switch: bool
    consecutive_failures: int
    minute_remaining: int
    hour_remaining: int
    last_decision: SendDecision | None
    live_capability: bool = True


class PublicSendPolicy:
    """Pure public-output decision state shared by platform adapters."""

    def __init__(
        self,
        config: object,
        *,
        clock: Callable[[], float],
        live_capability: bool = True,
    ) -> None:
        required = (
            "mode",
            "allowed_targets",
            "max_per_minute",
            "max_per_hour",
            "failure_threshold",
        )
        if not isinstance(config, PublicSendConfig) and not all(
            hasattr(config, name) for name in required
        ):
            raise TypeError("config must implement the public send settings contract")
        if not callable(clock):
            raise TypeError("clock must be a callable () -> float")
        if not isinstance(live_capability, bool):
            raise TypeError("live_capability must be boolean")
        self._config = config
        self._clock = clock
        self._live_capability = live_capability
        self._lock = RLock()
        # Ogni sessione parte in shadow: `live` in config ARMA la capacità, ma
        # non promuove nulla finché l'operatore non chiama `promote()`.
        self._promoted = False
        self._kill_switch = False
        self._live_disabled = False
        self._consecutive_failures = 0
        # Timestamp delle decisioni che hanno consumato budget (send + shadow),
        # in ordine crescente. Le finestre si potano ad ogni decisione.
        self._minute_events: deque[float] = deque()
        self._hour_events: deque[float] = deque()
        self._last_decision: SendDecision | None = None

    # -- Decisione ----------------------------------------------------------

    def decide(self, message: str, target: PublicTarget | str) -> SendDecision:
        """Decide whether to send, shadow, or drop for ``target``.

        Passi (puri, l'unico effetto è aggiornare il budget su send/shadow):

        1. Pota le finestre di budget rispetto all'istante corrente.
        2. Determina l'azione voluta da modo e stato (ignorando il budget).
        3. Le decisioni di `drop` non consumano budget e tornano subito.
        4. `send`/`shadow` consumano budget: se una finestra è esaurita ->
           `drop` col motivo di budget, altrimenti registra il timestamp.
        """
        with self._lock:
            now = self._clock()
            self._prune(now)

            action, reason = self._intended(self._coerce_target(target))

            if action == ACTION_DROP:
                return self._remember(SendDecision(action, reason))

            budget_reason = self._budget_block()
            if budget_reason is not None:
                return self._remember(SendDecision(ACTION_DROP, budget_reason))

            # send e shadow consumano entrambi il budget (fedeltà della prova).
            self._minute_events.append(now)
            self._hour_events.append(now)
            return self._remember(SendDecision(action, reason))

    def _intended(self, target: PublicTarget | None) -> tuple[str, str]:
        """Azione/motivo voluti da modo e stato, prima del vincolo di budget."""
        mode = self._config.mode
        if mode is PublicSendMode.OFF:
            # In pratica `off` non arriva alla policy (selezione nel router),
            # ma qui deve comunque rispondere in sicurezza.
            return ACTION_DROP, REASON_MODE_OFF
        if mode is PublicSendMode.SHADOW:
            # In shadow non si controlla l'allow-list: non si invia mai davvero.
            return ACTION_SHADOW, REASON_OK
        # mode is LIVE: shadow finché non promosso, di nuovo shadow se il
        # kill-switch è ingaggiato.
        if self._live_disabled or self._kill_switch:
            return ACTION_SHADOW, REASON_KILL_SWITCH
        if not self._promoted:
            return ACTION_SHADOW, REASON_NOT_PROMOTED
        # Promosso e senza kill-switch: invio reale, ma allow-list ricontrollata
        # al momento della decisione (difesa in profondità).
        if not self._target_allowed(target):
            return ACTION_DROP, REASON_CHANNEL_NOT_ALLOWED
        return ACTION_SEND, REASON_OK

    def _coerce_target(self, target: PublicTarget | str) -> PublicTarget | None:
        if isinstance(target, PublicTarget):
            return target
        # Explicit compatibility boundary for existing Twitch string callers.
        # The platform config owns normalization; the neutral policy imports no
        # platform parser.
        coerce = getattr(self._config, "coerce_target", None)
        if not callable(coerce):
            return None
        try:
            result = coerce(target)
        except (AttributeError, TypeError, ValueError):
            return None
        return result if isinstance(result, PublicTarget) else None

    def _target_allowed(self, target: PublicTarget | None) -> bool:
        """True only for a typed target in the configured allow-list."""
        return target is not None and target in self._config.allowed_targets

    def _budget_block(self) -> str | None:
        """Motivo di budget se una finestra è esaurita, altrimenti None."""
        if len(self._minute_events) >= self._config.max_per_minute:
            return REASON_BUDGET_MINUTE
        if len(self._hour_events) >= self._config.max_per_hour:
            return REASON_BUDGET_HOUR
        return None

    def _prune(self, now: float) -> None:
        """Rimuove i timestamp usciti dalle finestre (memoria limitata)."""
        minute_floor = now - _MINUTE_WINDOW
        while self._minute_events and self._minute_events[0] <= minute_floor:
            self._minute_events.popleft()
        hour_floor = now - _HOUR_WINDOW
        while self._hour_events and self._hour_events[0] <= hour_floor:
            self._hour_events.popleft()

    def _remember(self, decision: SendDecision) -> SendDecision:
        self._last_decision = decision
        return decision

    # -- Transizioni di stato ----------------------------------------------

    def promote(self) -> bool:
        """Promuove a invio reale; consentito solo se il config arma `live`.

        Ritorna True se la promozione è avvenuta, False se rifiutata (nessun
        cambio di stato). La promozione è l'UNICA azione che disingaggia il
        kill-switch (nessun re-enable silenzioso).
        """
        with self._lock:
            if (
                self._config.mode is not PublicSendMode.LIVE
                or self._live_disabled
                or not self._live_capability
            ):
                return False
            self._promoted = True
            self._kill_switch = False
            self._consecutive_failures = 0
            return True

    def engage_kill_switch(self) -> None:
        """Degrada l'invio a shadow immediatamente (operatore o auto-degrado).

        Idempotente. Revoca la promozione: tornare live richiede un `promote()`
        esplicito.
        """
        with self._lock:
            self._kill_switch = True
            self._promoted = False

    def disable_live(self) -> None:
        """Permanently disarm live sending for this session after auth failure."""
        with self._lock:
            self._live_disabled = True
            self._live_capability = False
            self.engage_kill_switch()

    def enable_live_capability(self) -> bool:
        """Mark a startup capability validated without promoting public send.

        A permanently disabled session cannot be re-enabled. The operator must
        still invoke ``promote()`` after this transition.
        """
        with self._lock:
            if self._live_disabled or self._config.mode is not PublicSendMode.LIVE:
                return False
            self._live_capability = True
            return True

    def record_failure(self) -> None:
        """Registra un fallimento d'invio consecutivo; auto-degrada alla soglia.

        Raggiunta `failure_threshold`, ingaggia automaticamente il kill-switch
        (stesso stato di quello manuale). Non disingaggia mai da solo.
        """
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._config.failure_threshold:
                self.engage_kill_switch()

    def record_success(self) -> None:
        """Azzera la serie di fallimenti consecutivi.

        NON disingaggia il kill-switch: solo `promote()` lo fa (auto-degrado
        che non si annulla in silenzio).
        """
        with self._lock:
            self._consecutive_failures = 0

    # -- Osservabilità ------------------------------------------------------

    def snapshot(self) -> PolicySnapshot:
        """Fotografia read-only dello stato corrente (per TUI/eventi)."""
        with self._lock:
            now = self._clock()
            self._prune(now)
            return PolicySnapshot(
                mode=self._config.mode,
                promoted=self._promoted,
                kill_switch=self._kill_switch,
                consecutive_failures=self._consecutive_failures,
                minute_remaining=self._config.max_per_minute - len(self._minute_events),
                hour_remaining=self._config.max_per_hour - len(self._hour_events),
                last_decision=self._last_decision,
                live_capability=self._live_capability,
            )
