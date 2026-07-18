"""Test del Senser arricchito (slice 07): finestre, idle, continuazione.

Tutta la tempistica usa un clock iniettato, così idle e continuazione sono
deterministici e i test non dipendono dal tempo reale.
"""

from minnarone.audio import STREAMER
from minnarone.chat import ChatPerceiver
from minnarone.perception import Perception, Source
from minnarone.senser import Senser
from minnarone.store import PerceptionStore


class FakeClock:
    """Clock iniettabile: parte da `start` e avanza solo via `advance`."""

    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def _setup(tmp_path, clock, *, idle_interval=150.0):
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(
        store, agent_name="Minnarone", clock=clock, idle_interval=idle_interval
    )
    return store, chat, senser


# --- Idle loop -------------------------------------------------------------


def test_idle_emits_proactive_comment_after_interval(tmp_path):
    clock = FakeClock(start=100.0)
    store, chat, senser = _setup(tmp_path, clock, idle_interval=150.0)
    # nessun trigger appena dopo lo start
    assert senser.tick() == []
    clock.advance(149.0)
    assert senser.tick() == []
    clock.advance(2.0)  # ora sono passati 151s senza trigger
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].kind == "idle_comment"


def test_idle_timer_resets_after_any_trigger(tmp_path):
    clock = FakeClock(start=0.0)
    store, chat, senser = _setup(tmp_path, clock, idle_interval=150.0)
    clock.advance(151.0)
    assert len(senser.tick()) == 1  # idle scatta
    # subito dopo, nessun nuovo idle: il timer è ripartito
    assert senser.tick() == []
    clock.advance(100.0)
    assert senser.tick() == []
    clock.advance(51.0)
    assert len(senser.tick()) == 1  # idle di nuovo dopo un altro intervallo


def test_mention_resets_idle_timer(tmp_path):
    clock = FakeClock(start=0.0)
    store, chat, senser = _setup(tmp_path, clock, idle_interval=150.0)
    clock.advance(100.0)
    chat.perceive("ehi minnarone", speaker="enkk", ts=100.0)
    mentions = senser.tick()
    assert len(mentions) == 1
    assert mentions[0].kind == "mention"
    # da qui il timer idle riparte: a +149 niente. Avanziamo poi oltre il ttl
    # della finestra (180s) così la finestra di enkk scade e non sopprime più
    # l'idle: a quel punto l'idle (timer ripartito dalla menzione) scatta.
    clock.advance(149.0)
    assert senser.tick() == []
    clock.advance(200.0)
    assert any(t.kind == "idle_comment" for t in senser.tick())


def test_idle_suppressed_while_window_open(tmp_path):
    # Un idle_comment non deve scattare nel mezzo di uno scambio dal vivo: se
    # c'è una finestra aperta (non scaduta) l'idle è soppresso. Qui idle_interval
    # (10s) < window_ttl (180s), così la finestra resta viva quando l'idle
    # vorrebbe scattare.
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone", clock=clock, idle_interval=10.0)
    chat.perceive("minnarone ciao", speaker="enkk", ts=1.0)
    assert senser.tick()[0].kind == "mention"  # apre la finestra di enkk
    # passa oltre l'idle_interval ma la finestra (ttl 180s) è ancora aperta
    clock.advance(11.0)
    assert all(t.kind != "idle_comment" for t in senser.tick())
    assert "enkk" in senser.open_windows()


def test_idle_fires_once_window_expired(tmp_path):
    # Controprova: quando la finestra scade, l'idle torna a scattare.
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone", clock=clock, idle_interval=10.0)
    chat.perceive("minnarone ciao", speaker="enkk", ts=1.0)
    assert senser.tick()[0].kind == "mention"
    # oltre il ttl della finestra (180s): la finestra è scaduta, idle scatta
    clock.advance(200.0)
    triggers = senser.tick()
    assert any(t.kind == "idle_comment" for t in triggers)
    assert senser.open_windows() == {}


# --- Finestre di conversazione ---------------------------------------------


def test_chat_mention_opens_chat_window(tmp_path):
    clock = FakeClock(start=0.0)
    store, chat, senser = _setup(tmp_path, clock)
    chat.perceive("minnarone ciao", speaker="enkk", ts=1.0)
    triggers = senser.tick()
    assert triggers[0].interlocutor == "enkk"
    assert "enkk" in senser.open_windows()


def test_streamer_speech_mention_opens_streamer_window(tmp_path):
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    store.append(
        Perception(
            ts=1.0,
            source=Source.AUDIO,
            type="speech",
            text="ehi minnarone come va",
            speaker=STREAMER,
        )
    )
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].interlocutor == STREAMER
    assert STREAMER in senser.open_windows()


def test_non_streamer_audio_mention_does_not_open_window(tmp_path):
    # EC02: un'AUDIO percezione con speaker != STREAMER (ospite, audio di un
    # video riprodotto deliberatamente taggato come non-STREAMER) NON apre una
    # finestra e NON è un interlocutore, anche se menziona l'agente.
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    store.append(
        Perception(
            ts=1.0,
            source=Source.AUDIO,
            type="speech",
            text="ehi minnarone come va",
            speaker="ospite",
        )
    )
    triggers = senser.tick()
    assert all(t.kind != "mention" for t in triggers)
    assert senser.open_windows() == {}


def test_streamer_audio_mention_does_open_window(tmp_path):
    # Controprova: lo stesso testo ma con speaker == STREAMER apre la finestra.
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    store.append(
        Perception(
            ts=1.0,
            source=Source.AUDIO,
            type="speech",
            text="ehi minnarone come va",
            speaker=STREAMER,
        )
    )
    triggers = senser.tick()
    assert any(t.kind == "mention" and t.interlocutor == STREAMER for t in triggers)
    assert STREAMER in senser.open_windows()


def test_streamer_and_chat_windows_coexist(tmp_path):
    clock = FakeClock(start=0.0)
    store = PerceptionStore(tmp_path / "perceptions.jsonl")
    chat = ChatPerceiver(store)
    senser = Senser(store, agent_name="Minnarone", clock=clock)
    store.append(
        Perception(
            ts=1.0,
            source=Source.AUDIO,
            type="speech",
            text="minnarone guarda qua",
            speaker=STREAMER,
        )
    )
    chat.perceive("minnarone rispondi a me", speaker="ada", ts=2.0)
    triggers = senser.tick()
    interlocutors = {t.interlocutor for t in triggers}
    assert interlocutors == {STREAMER, "ada"}
    # entrambe le finestre aperte, nessuna clobbera l'altra
    assert STREAMER in senser.open_windows()
    assert "ada" in senser.open_windows()


# --- Continuazione ---------------------------------------------------------


def test_continuation_when_interlocutor_speaks_after_agent_message(tmp_path):
    clock = FakeClock(start=0.0)
    store, chat, senser = _setup(tmp_path, clock)
    # apri una finestra con enkk via menzione
    chat.perceive("minnarone ciao", speaker="enkk", ts=1.0)
    assert senser.tick()[0].kind == "mention"
    # l'agente risponde
    clock.advance(2.0)
    senser.note_agent_message(clock())
    # enkk risponde subito dopo, SENZA rinominare l'agente
    clock.advance(3.0)
    chat.perceive("ah davvero?", speaker="enkk", ts=clock())
    triggers = senser.tick()
    assert len(triggers) == 1
    assert triggers[0].kind == "continuation"
    assert triggers[0].interlocutor == "enkk"


def test_no_continuation_without_open_window(tmp_path):
    clock = FakeClock(start=0.0)
    store, chat, senser = _setup(tmp_path, clock)
    # nessuna finestra aperta; l'agente parla, poi uno sconosciuto scrive
    senser.note_agent_message(clock())
    clock.advance(2.0)
    chat.perceive("bla bla", speaker="pippo", ts=clock())
    assert senser.tick() == []


def test_no_continuation_if_interlocutor_silent_too_long(tmp_path):
    clock = FakeClock(start=0.0)
    store, chat, senser = _setup(tmp_path, clock)
    chat.perceive("minnarone ciao", speaker="enkk", ts=1.0)
    senser.tick()
    senser.note_agent_message(clock())
    # passa MOLTO tempo prima che enkk parli: non è una continuazione "subito dopo"
    clock.advance(120.0)
    chat.perceive("ci sei ancora?", speaker="enkk", ts=clock())
    triggers = senser.tick()
    assert all(t.kind != "continuation" for t in triggers)


# --- Idempotenza e word-boundary preservate --------------------------------


def test_idempotent_does_not_refire_seen_perceptions(tmp_path):
    clock = FakeClock(start=0.0)
    store, chat, senser = _setup(tmp_path, clock)
    chat.perceive("minnarone!", speaker="enkk", ts=1.0)
    assert len(senser.tick()) == 1
    assert senser.tick() == []


def test_word_boundary_no_false_trigger_on_substring(tmp_path):
    clock = FakeClock(start=0.0)
    store, chat, senser = _setup(tmp_path, clock)
    chat.perceive("seguite minnaroneitalia", speaker="enkk", ts=1.0)
    assert all(t.kind == "idle_comment" for t in senser.tick())  # solo idle al limite


def test_storpiato_name_still_opens_window(tmp_path):
    clock = FakeClock(start=0.0)
    store, chat, senser = _setup(tmp_path, clock)
    # nome storpiato/fonetico: deve comunque aprire la finestra (EC09)
    chat.perceive("ehi minarone come stai", speaker="enkk", ts=1.0)
    triggers = senser.tick()
    assert any(t.kind == "mention" for t in triggers)
    assert "enkk" in senser.open_windows()


# --- Hook bandwagon (no-op v2) ----------------------------------------------


def test_bandwagon_hook_is_noop(tmp_path):
    clock = FakeClock(start=0.0)
    store, chat, senser = _setup(tmp_path, clock)
    # esiste ed è un no-op: non solleva e non produce trigger
    assert senser.consider_bandwagon() is None
    assert senser.tick() == []
