"""PublicSendPolicy: modulo puro di decisione sull'invio pubblico (slice 02).

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

from .config import TwitchSendConfig, TwitchSendMode
from .twitch_media import normalize_twitch_channel

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

    mode: TwitchSendMode
    promoted: bool
    kill_switch: bool
    consecutive_failures: int
    minute_remaining: int
    hour_remaining: int
    last_decision: SendDecision | None


class PublicSendPolicy:
    """Decisione pura e deterministica sull'invio pubblico in chat Twitch."""

    def __init__(
        self,
        config: TwitchSendConfig,
        *,
        clock: Callable[[], float],
    ) -> None:
        if not isinstance(config, TwitchSendConfig):
            raise TypeError("config deve essere una TwitchSendConfig")
        if not callable(clock):
            raise TypeError("clock deve essere un callable () -> float")
        self._config = config
        self._clock = clock
        # Ogni sessione parte in shadow: `live` in config ARMA la capacità, ma
        # non promuove nulla finché l'operatore non chiama `promote()`.
        self._promoted = False
        self._kill_switch = False
        self._consecutive_failures = 0
        # Timestamp delle decisioni che hanno consumato budget (send + shadow),
        # in ordine crescente. Le finestre si potano ad ogni decisione.
        self._minute_events: deque[float] = deque()
        self._hour_events: deque[float] = deque()
        self._last_decision: SendDecision | None = None

    # -- Decisione ----------------------------------------------------------

    def decide(self, message: str, channel: str) -> SendDecision:
        """Decide se inviare, mettere in shadow o scartare `message` su `channel`.

        Passi (puri, l'unico effetto è aggiornare il budget su send/shadow):

        1. Pota le finestre di budget rispetto all'istante corrente.
        2. Determina l'azione voluta da modo e stato (ignorando il budget).
        3. Le decisioni di `drop` non consumano budget e tornano subito.
        4. `send`/`shadow` consumano budget: se una finestra è esaurita ->
           `drop` col motivo di budget, altrimenti registra il timestamp.
        """
        now = self._clock()
        self._prune(now)

        action, reason = self._intended(channel)

        if action == ACTION_DROP:
            return self._remember(SendDecision(action, reason))

        budget_reason = self._budget_block()
        if budget_reason is not None:
            return self._remember(SendDecision(ACTION_DROP, budget_reason))

        # send e shadow consumano entrambi il budget (fedeltà della prova).
        self._minute_events.append(now)
        self._hour_events.append(now)
        return self._remember(SendDecision(action, reason))

    def _intended(self, channel: str) -> tuple[str, str]:
        """Azione/motivo voluti da modo e stato, prima del vincolo di budget."""
        mode = self._config.mode
        if mode is TwitchSendMode.OFF:
            # In pratica `off` non arriva alla policy (selezione nel router),
            # ma qui deve comunque rispondere in sicurezza.
            return ACTION_DROP, REASON_MODE_OFF
        if mode is TwitchSendMode.SHADOW:
            # In shadow non si controlla l'allow-list: non si invia mai davvero.
            return ACTION_SHADOW, REASON_OK
        # mode is LIVE: shadow finché non promosso, di nuovo shadow se il
        # kill-switch è ingaggiato.
        if self._kill_switch:
            return ACTION_SHADOW, REASON_KILL_SWITCH
        if not self._promoted:
            return ACTION_SHADOW, REASON_NOT_PROMOTED
        # Promosso e senza kill-switch: invio reale, ma allow-list ricontrollata
        # al momento della decisione (difesa in profondità).
        if not self._channel_allowed(channel):
            return ACTION_DROP, REASON_CHANNEL_NOT_ALLOWED
        return ACTION_SEND, REASON_OK

    def _channel_allowed(self, channel: str) -> bool:
        """True se `channel` (normalizzato) è nell'allow-list configurata."""
        try:
            normalized = normalize_twitch_channel(channel)
        except (AttributeError, ValueError):
            # Un canale non normalizzabile non può essere autorizzato.
            return False
        return normalized in self._config.allowed_channels

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
        if self._config.mode is not TwitchSendMode.LIVE:
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
        self._kill_switch = True
        self._promoted = False

    def record_failure(self) -> None:
        """Registra un fallimento d'invio consecutivo; auto-degrada alla soglia.

        Raggiunta `failure_threshold`, ingaggia automaticamente il kill-switch
        (stesso stato di quello manuale). Non disingaggia mai da solo.
        """
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._config.failure_threshold:
            self.engage_kill_switch()

    def record_success(self) -> None:
        """Azzera la serie di fallimenti consecutivi.

        NON disingaggia il kill-switch: solo `promote()` lo fa (auto-degrado
        che non si annulla in silenzio).
        """
        self._consecutive_failures = 0

    # -- Osservabilità ------------------------------------------------------

    def snapshot(self) -> PolicySnapshot:
        """Fotografia read-only dello stato corrente (per TUI/eventi)."""
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
        )
