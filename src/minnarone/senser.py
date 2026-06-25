"""Il Senser: trasforma percezioni in `Trigger` che fanno reagire l'agente.

Partendo dalla menzione base dello slice 01, questo modulo arricchisce la
logica conversazionale (slice 07):

- **Finestre di conversazione** per interlocutore (lo STREAMER e i singoli
  utenti di chat). Una finestra si apre/aggiorna quando viene rilevata
  un'interazione e si chiude da sola dopo un periodo di inattività. Streamer e
  chat possono avere finestre aperte CONTEMPORANEAMENTE senza interferire: lo
  stato è un piccolo dizionario `interlocutore -> ConversationWindow`, non un
  insieme di flag sparsi.
- **Idle loop**: se nessun trigger scatta per ~`idle_interval` secondi, il
  Senser emette un trigger proattivo `idle_comment` sul contesto corrente. Il
  timer riparte dopo *qualsiasi* trigger.
- **Continuazione**: se un interlocutore con finestra aperta parla poco dopo un
  messaggio dell'agente (entro `continuation_window` secondi da
  `note_agent_message`), si emette un trigger `continuation` anche senza una
  nuova menzione esplicita.

Il tempo è iniettato via un `clock` (default `time.time`) così idle e
continuazione sono testabili in modo deterministico, senza dipendere dal tempo
reale (stesso spirito della cadenza di Reactor/Summarizer, ma qui il *contenuto*
del tick dipende dal tempo, quindi il clock entra nella logica pura).

L'idempotenza si appoggia a un *cursore di posizione* dello store (offset in
byte), non al `ts`: così due percezioni con lo stesso `ts` vengono entrambe
viste. La menzione è riconosciuta con un match per-parola (confine di parola)
che tollera nomi storpiati/fonetici (EC09) senza scattare dentro token più
grandi (es. "minnaroneitalia", URL, hashtag).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher

from .audio import STREAMER
from .perception import Perception, Source
from .store import PerceptionStore

# Quanto può discostarsi una parola dal nome dell'agente per contare come
# menzione storpiata (EC09). 0.85 accetta "minarone"/"minnarne" (~0.94) ma
# rifiuta "minnaroneitalia" (~0.75), che resta una NON-menzione.
_MENTION_SIMILARITY = 0.85

# Default dell'intervallo idle (secondi): in assenza di trigger, dopo questo
# tempo l'agente commenta spontaneamente (PRD ~150s).
_DEFAULT_IDLE_INTERVAL = 150.0

# Quanto a lungo una finestra di conversazione resta "aperta" senza nuova
# interazione prima di considerarsi chiusa.
_DEFAULT_WINDOW_TTL = 180.0

# Entro quanti secondi da un messaggio dell'agente la risposta di un
# interlocutore con finestra aperta conta come *continuazione* (UC03).
_DEFAULT_CONTINUATION_WINDOW = 30.0

_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class Trigger:
    """Motivo per cui l'agente dovrebbe reagire ora.

    Attributi:
        reason: etichetta legacy del tipo di trigger; rispecchia `kind` ed è
            mantenuta per compatibilità (il PromptBuilder la usa nella sezione
            SITUAZIONE).
        perception: la percezione che ha originato il trigger. È `None` per i
            trigger proattivi `idle_comment`, che non nascono da una percezione.
        kind: tipo strutturato del trigger: "mention", "continuation" o
            "idle_comment".
        interlocutor: a chi è rivolta la reazione (lo speaker della chat, lo
            STREAMER, o `None` per un commento idle non indirizzato).
    """

    reason: str
    perception: Perception | None
    kind: str = "mention"
    interlocutor: str | None = None


@dataclass(slots=True)
class ConversationWindow:
    """Stato di una finestra di conversazione aperta con un interlocutore.

    `opened_at` è quando la finestra si è aperta; `last_seen` quando vi è stata
    l'ultima interazione (menzione o continuazione). Una finestra è scaduta se
    `now - last_seen > ttl`.
    """

    interlocutor: str
    opened_at: float
    last_seen: float

    def refresh(self, now: float) -> None:
        self.last_seen = now


class Senser:
    """Rileva menzioni, gestisce finestre e idle, ed emette `Trigger`."""

    def __init__(
        self,
        store: PerceptionStore,
        *,
        agent_name: str,
        clock=time.time,
        idle_interval: float = _DEFAULT_IDLE_INTERVAL,
        window_ttl: float = _DEFAULT_WINDOW_TTL,
        continuation_window: float = _DEFAULT_CONTINUATION_WINDOW,
    ) -> None:
        self._store = store
        self._agent_name = agent_name.lower()
        # Match esatto a confine di parola (veloce); il fuzzy interviene solo se
        # questo fallisce, per tollerare i nomi storpiati senza falsi positivi.
        self._mention = re.compile(rf"\b{re.escape(agent_name)}\b", re.IGNORECASE)
        self._clock = clock
        self._idle_interval = idle_interval
        self._window_ttl = window_ttl
        self._continuation_window = continuation_window
        self._position = 0
        # Stato esplicito delle finestre: interlocutore -> finestra aperta.
        self._windows: dict[str, ConversationWindow] = {}
        # Quando è scattato l'ultimo trigger (per il timer idle). Inizializzato
        # al clock corrente così l'idle parte da "adesso", non dall'epoca 0.
        self._last_trigger_at = self._clock()
        # Quando l'agente ha inviato il suo ultimo messaggio (per la
        # continuazione). `None` finché il Reactor non lo comunica.
        self._last_agent_message_at: float | None = None

    # -- API pubblica per il Reactor ----------------------------------------

    def now(self) -> float:
        """Lettura del clock iniettato.

        Esposta così il Reactor può marcare `note_agent_message` con LO STESSO
        orologio del Senser: la tempistica della continuazione resta
        deterministica anche nel sistema assemblato.
        """
        return self._clock()

    def note_agent_message(self, ts: float) -> None:
        """Informa il Senser che l'agente ha appena inviato un messaggio.

        Serve a riconoscere la *continuazione*: se un interlocutore con finestra
        aperta parla entro `continuation_window` secondi da questo istante, il
        suo messaggio innesca un trigger di continuazione anche senza menzione.

        Nota (UC04, multi-party): `_last_agent_message_at` NON viene azzerato
        dopo una continuazione. È intenzionale: con più interlocutori a finestra
        aperta, ognuno può continuare entro la finestra dopo lo stesso messaggio
        dell'agente, senza che la continuazione del primo "consumi" il segnale
        per gli altri.
        """
        self._last_agent_message_at = ts

    def open_windows(self) -> dict[str, ConversationWindow]:
        """Snapshot delle finestre attualmente aperte (interlocutore -> finestra)."""
        self._expire_windows(self._clock())
        return dict(self._windows)

    def consider_bandwagon(self) -> None:
        """Hook *bandwagon* (FR24, v2): per ora un NO-OP documentato.

        In v2 qui andrà la logica per cui l'agente si accoda a un'ondata di
        messaggi simili in chat (effetto "bandwagon"). Nell'MVP non fa nulla e
        non emette trigger: è solo il punto di innesto previsto.
        """
        return None

    # -- Loop principale ----------------------------------------------------

    def tick(self) -> list[Trigger]:
        """Esamina le nuove percezioni + il tempo e restituisce i trigger."""
        now = self._clock()
        self._expire_windows(now)
        new, self._position = self._store.read_from(self._position)

        triggers: list[Trigger] = []
        for p in new:
            trigger = self._classify(p, now)
            if trigger is not None:
                triggers.append(trigger)

        # Hook v2 (no-op): valutazione bandwagon. Tenuto qui così lo slot esiste
        # nel flusso del tick senza alterarne il comportamento.
        self.consider_bandwagon()

        # Idle: solo se nessun trigger è scattato in questo tick, abbastanza
        # tempo è passato dall'ultimo trigger, e NON c'è uno scambio dal vivo in
        # corso. Una finestra ancora aperta (non scaduta) significa che siamo nel
        # mezzo di una conversazione: l'idle proattivo verrebbe fuori luogo.
        if (
            not triggers
            and (now - self._last_trigger_at) >= self._idle_interval
            and not self._windows
        ):
            triggers.append(
                Trigger(
                    reason="idle_comment",
                    perception=None,
                    kind="idle_comment",
                    interlocutor=None,
                )
            )

        if triggers:
            # Qualsiasi trigger (menzione, continuazione, idle) resetta il timer.
            self._last_trigger_at = now
        return triggers

    # -- Logica interna -----------------------------------------------------

    def _classify(self, p: Perception, now: float) -> Trigger | None:
        """Classifica una percezione in un eventuale trigger e aggiorna lo stato."""
        # Consideriamo solo le percezioni con un interlocutore identificabile.
        # Per la CHAT l'interlocutore è lo speaker. Per l'AUDIO è interlocutore
        # SOLO lo STREAMER (EC02): un ospite o l'audio di un video riprodotto —
        # che il modulo audio tagga deliberatamente come non-STREAMER — non apre
        # finestre e non emette trigger come interlocutore.
        if p.source == Source.CHAT:
            interlocutor = p.speaker
        elif p.source == Source.AUDIO:
            interlocutor = STREAMER if p.speaker == STREAMER else None
        else:
            return None
        if not interlocutor:
            return None

        if self._is_mention(p.text):
            self._touch_window(interlocutor, now)
            return Trigger(
                reason="mention",
                perception=p,
                kind="mention",
                interlocutor=interlocutor,
            )

        # Continuazione: finestra aperta + l'agente ha parlato di recente +
        # questo interlocutore risponde entro la finestra di continuazione.
        if self._is_continuation(interlocutor, now):
            self._touch_window(interlocutor, now)
            return Trigger(
                reason="continuation",
                perception=p,
                kind="continuation",
                interlocutor=interlocutor,
            )
        return None

    def _is_mention(self, text: str) -> bool:
        """Menzione del nome: match esatto a confine di parola o fuzzy (EC09)."""
        if self._mention.search(text):
            return True
        for token in _WORD_RE.findall(text.lower()):
            if SequenceMatcher(None, self._agent_name, token).ratio() >= (
                _MENTION_SIMILARITY
            ):
                return True
        return False

    def _is_continuation(self, interlocutor: str, now: float) -> bool:
        if interlocutor not in self._windows:
            return False
        if self._last_agent_message_at is None:
            return False
        return (now - self._last_agent_message_at) <= self._continuation_window

    def _touch_window(self, interlocutor: str, now: float) -> None:
        """Apre o aggiorna la finestra dell'interlocutore."""
        window = self._windows.get(interlocutor)
        if window is None:
            self._windows[interlocutor] = ConversationWindow(
                interlocutor=interlocutor, opened_at=now, last_seen=now
            )
        else:
            window.refresh(now)

    def _expire_windows(self, now: float) -> None:
        """Chiude le finestre inattive da più di `window_ttl`."""
        expired = [
            who
            for who, w in self._windows.items()
            if (now - w.last_seen) > self._window_ttl
        ]
        for who in expired:
            del self._windows[who]
