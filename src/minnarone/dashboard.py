"""Modello di osservabilità: uno snapshot PURO dello stato del sistema.

La dashboard di osservabilità (slice 10) mostra in tempo reale, in **sola
lettura**, cosa sta facendo l'agente: le percezioni in arrivo, i trigger/eventi
prodotti dal Senser, le finestre di conversazione aperte e i messaggi inviati.

Questo modulo contiene la parte *pura e senza dipendenze* del lavoro:
`DashboardState` e `snapshot()` aggregano le sorgenti già esistenti in dati
semplici (dataclass / liste / stringhe) pronti per essere resi. NON dipende da
`textual`: la vista TUI vive in `dashboard_tui.py` con un import guardato.

Vincolo fondamentale — **strettamente READ-ONLY**: `snapshot()` usa solo gli
accessor di sola lettura delle sorgenti (`store.tail`, `senser.open_windows`,
`senser.recent_triggers`, `reactor.recent_messages`). Non chiama `tick()`, non
fa avanzare cursori, non instrada nulla: produrre uno snapshot non interferisce
con il loop del Reactor né muta lo stato osservato.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .perception import Perception, format_perception_line
from .senser import ConversationWindow, Trigger

# Quante percezioni recenti includere di default nello snapshot.
_DEFAULT_RECENT_PERCEPTIONS = 20

# Quanti trigger e messaggi recenti includere di default.
_DEFAULT_RECENT_TRIGGERS = 20
_DEFAULT_RECENT_MESSAGES = 20


@dataclass(frozen=True, slots=True)
class DashboardState:
    """Vista immutabile e pura dello stato osservabile del sistema.

    Tutti i campi sono dati semplici (copie difensive delle sorgenti), così la
    state è disaccoppiata dagli oggetti vivi: chi la rende non può alterare il
    loop. È volutamente serializzabile e facile da testare offline.

    Attributi:
        perceptions: ultime percezioni viste (ordine cronologico di scrittura).
        triggers: ultimi trigger/eventi emessi dal Senser.
        windows: finestre di conversazione attualmente aperte (interlocutore ->
            finestra).
        messages: ultimi messaggi instradati dall'agente.
    """

    perceptions: list[Perception] = field(default_factory=list)
    triggers: list[Trigger] = field(default_factory=list)
    windows: dict[str, ConversationWindow] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)

    def render_text(self) -> str:
        """Resa testuale dello snapshot, senza alcuna dipendenza da textual.

        È la fonte di verità del *contenuto* da mostrare: la vista Textual la
        riusa nei suoi pannelli, ma il testo è verificabile in modo headless.
        """
        lines: list[str] = []

        lines.append("== Percezioni ==")
        if self.perceptions:
            for p in self.perceptions:
                lines.append(f"[{p.source.value}] {format_perception_line(p)}")
        else:
            lines.append("(nessuna)")

        lines.append("== Trigger/Eventi ==")
        if self.triggers:
            for t in self.triggers:
                who = t.interlocutor if t.interlocutor else "-"
                lines.append(f"{t.kind} <- {who}")
        else:
            lines.append("(nessuno)")

        lines.append("== Finestre aperte ==")
        if self.windows:
            for who in self.windows:
                lines.append(who)
        else:
            lines.append("(nessuna)")

        lines.append("== Messaggi inviati ==")
        if self.messages:
            lines.extend(self.messages)
        else:
            lines.append("(nessuno)")

        return "\n".join(lines)


def snapshot(
    *,
    store=None,
    senser=None,
    reactor=None,
    recent_perceptions: int = _DEFAULT_RECENT_PERCEPTIONS,
    recent_triggers: int = _DEFAULT_RECENT_TRIGGERS,
    recent_messages: int = _DEFAULT_RECENT_MESSAGES,
) -> DashboardState:
    """Aggrega in sola lettura le sorgenti vive in un `DashboardState` puro.

    Ogni sorgente è opzionale: si passano solo quelle disponibili (lo store, il
    Senser, il Reactor). Si usano ESCLUSIVAMENTE accessor di sola lettura, così
    produrre lo snapshot non muta nulla e non interferisce con il loop:

    - `store.tail(n)`            -> percezioni recenti
    - `senser.open_windows()`    -> finestre di conversazione aperte
    - `senser.recent_triggers()` -> trigger/eventi recenti
    - `reactor.recent_messages()`-> messaggi instradati di recente
    """
    perceptions: list[Perception] = []
    if store is not None and recent_perceptions > 0:
        perceptions = list(store.tail(recent_perceptions))

    triggers: list[Trigger] = []
    windows: dict[str, ConversationWindow] = {}
    if senser is not None:
        triggers = list(senser.recent_triggers(recent_triggers))
        # Copia DIFENSIVA: ConversationWindow è mutabile e gli oggetti restituiti
        # da open_windows() sono quelli vivi usati dal Senser per TTL/idle. Lo
        # snapshot è sola-lettura, quindi cloniamo ogni finestra così un consumer
        # non può mutare lo stato di conversazione vivo attraverso lo snapshot.
        windows = {who: replace(win) for who, win in senser.open_windows().items()}

    messages: list[str] = []
    if reactor is not None:
        messages = list(reactor.recent_messages(recent_messages))

    return DashboardState(
        perceptions=perceptions,
        triggers=triggers,
        windows=windows,
        messages=messages,
    )
