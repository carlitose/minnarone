"""HumanLikeness: filtro finale prima dell'output (slice 08).

È l'ultimo stadio della catena del Reactor, fra il risultato dell'LLM e
l'`OutputRouter`. È un modulo PURO e deterministico: data una bozza di
messaggio e gli ultimi messaggi *propri* dell'agente, decide

- quanto **ritardare** l'invio per simulare un tempo di battitura plausibile
  (le risposte istantanee sono innaturali). Il ritardo è proporzionale alla
  lunghezza del messaggio, con limiti min/max. Calcola SOLO il numero di
  secondi: NON dorme. È il Reactor che applica l'attesa (via uno sleep
  asincrono iniettato) così il loop non si blocca.
- se **scartare** il messaggio perché quasi-identico a uno recente (dedup), per
  evitare che l'agente ripeta sé stesso. La similarità riusa lo stesso pattern
  `difflib.SequenceMatcher` già impiegato dal Senser per le menzioni storpiate.
- se il messaggio contiene il sentinella **`#end_conv`**: in tal caso il testo
  ripulito dal sentinella NON va inviato come messaggio letterale; la decisione
  segnala `end_conv=True` così il Reactor può chiudere la finestra di
  conversazione corrispondente (coordinandosi col Senser dello slice 07).

L'anti-ripetizione vera e propria (mostrare all'LLM i suoi ultimi messaggi)
vive nel prompt; qui c'è SOLO il cancello di dedup, non si duplica quello stato.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

# Sentinella emessa dall'LLM per chiudere la conversazione (FR25, UC09).
END_CONV_SENTINEL = "#end_conv"

# Velocità di battitura simulata (caratteri al secondo). ~17 cps ≈ una persona
# che digita svelta ma non istantanea: 50 caratteri -> ~3s.
_DEFAULT_TYPING_SPEED = 17.0

# Limiti del ritardo (secondi): mai sotto il minimo (anche un "ok" non è
# istantaneo) né oltre il massimo (non si fa attendere all'infinito).
_DEFAULT_MIN_DELAY = 0.8
_DEFAULT_MAX_DELAY = 8.0

# Soglia di similarità oltre la quale un messaggio è "quasi-duplicato" di uno
# recente e va scartato. 0.9 tollera differenze minime (punteggiatura, una
# parola) ma scarta i ricalchi sostanziali.
_DEFAULT_DEDUP_THRESHOLD = 0.9


@dataclass(frozen=True, slots=True)
class HumanDecision:
    """Esito del filtro human-likeness su una bozza di messaggio.

    Attributi:
        message: il testo (eventualmente ripulito dal sentinella) da inviare.
            Significativo solo se `drop` è False.
        delay: secondi da attendere PRIMA di inviare (il Reactor li applica via
            sleep asincrono iniettato). Solo un calcolo: qui non si dorme mai.
        drop: True se il messaggio NON va inviato (quasi-duplicato, oppure il
            testo residuo dopo lo strip del sentinella è vuoto).
        end_conv: True se la bozza conteneva `#end_conv`: il Reactor deve
            chiudere la finestra dell'interlocutore corrente.
    """

    message: str
    delay: float
    drop: bool
    end_conv: bool


class HumanLikeness:
    """Filtro puro: stima il typing delay, fa dedup e interpreta `#end_conv`."""

    def __init__(
        self,
        *,
        typing_speed: float = _DEFAULT_TYPING_SPEED,
        min_delay: float = _DEFAULT_MIN_DELAY,
        max_delay: float = _DEFAULT_MAX_DELAY,
        dedup_threshold: float = _DEFAULT_DEDUP_THRESHOLD,
    ) -> None:
        if typing_speed <= 0:
            raise ValueError("typing_speed must be > 0")
        if min_delay > max_delay:
            raise ValueError("min_delay cannot exceed max_delay")
        if not 0.0 <= dedup_threshold <= 1.0:
            raise ValueError("dedup_threshold must be in [0.0, 1.0]")
        self._typing_speed = typing_speed
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._dedup_threshold = dedup_threshold

    def process(
        self, message: str, recent_self_messages: Sequence[str] = ()
    ) -> HumanDecision:
        """Decide come/se inviare `message` viste le ultime risposte dell'agente.

        Passi (puri, nessun side-effect):

        1. Rileva ed estrae il sentinella `#end_conv` (ovunque nel testo), che
           segnala la volontà di chiudere. Il testo ripulito è ciò che, semmai,
           verrà inviato; il sentinella stesso non esce MAI come chat letterale.
        2. Se dopo lo strip non resta testo significativo -> `drop=True` (si
           chiude soltanto, senza messaggio).
        3. Dedup: se il testo è quasi-identico a un messaggio recente
           dell'agente -> `drop=True`.
        4. Altrimenti calcola il typing delay ∝ lunghezza, entro [min, max].
        """
        end_conv, cleaned = self._extract_end_conv(message)

        if not cleaned:
            # Niente da dire: o era solo il sentinella, o il messaggio era vuoto.
            return HumanDecision(message="", delay=0.0, drop=True, end_conv=end_conv)

        if self._is_near_duplicate(cleaned, recent_self_messages):
            return HumanDecision(
                message=cleaned, delay=0.0, drop=True, end_conv=end_conv
            )

        return HumanDecision(
            message=cleaned,
            delay=self._typing_delay(cleaned),
            drop=False,
            end_conv=end_conv,
        )

    # -- Logica interna -----------------------------------------------------

    @staticmethod
    def _extract_end_conv(message: str) -> tuple[bool, str]:
        """Ritorna (era_presente, testo_ripulito) per il sentinella `#end_conv`.

        Il sentinella è riconosciuto solo come TOKEN delimitato (confini di
        parola), non come sottostringa dentro una parola: `ok#end_convnow` non
        è un comando di chiusura. Il testo ripulito ha gli spazi interni
        normalizzati, così la rimozione del sentinella non lascia spazi doppi.
        """
        pattern = rf"(?<!\S){re.escape(END_CONV_SENTINEL)}(?!\S)"
        if not re.search(pattern, message):
            return False, " ".join(message.split())
        cleaned = re.sub(pattern, " ", message)
        return True, " ".join(cleaned.split())

    def _typing_delay(self, message: str) -> float:
        """Secondi di attesa ∝ lunghezza, limitati a [min_delay, max_delay]."""
        raw = len(message) / self._typing_speed
        return max(self._min_delay, min(self._max_delay, raw))

    def _is_near_duplicate(
        self, message: str, recent_self_messages: Sequence[str]
    ) -> bool:
        """True se `message` è quasi-identico a uno dei messaggi recenti propri."""
        norm = self._normalize(message)
        if not norm:
            return False
        for prev in recent_self_messages:
            prev_norm = self._normalize(prev)
            if not prev_norm:
                continue
            if SequenceMatcher(None, norm, prev_norm).ratio() >= (
                self._dedup_threshold
            ):
                return True
        return False

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalizza per il confronto: minuscole, spazi collassati."""
        return " ".join(text.lower().split())
