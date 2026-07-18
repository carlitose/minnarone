"""Test del modulo `prompt_source`: loader reale promosso dallo spike (ticket 03).

Copre il contratto deciso nel ticket 02: formato markdown-only, templating
`{{nome}}` sicuro, packaging via `importlib.resources` + override per-file da
`prompts_dir`, validazione fail-fast (mai vuoto silenzioso).
"""

from pathlib import Path

import pytest

from minnarone.prompt_source import (
    DEFAULT_PROMPTS_PKG,
    ORIGINAL_CHAT_SET,
    KeySpec,
    PromptError,
    PromptSet,
    PromptSetSpec,
    PromptSpec,
    find_placeholders,
    language_name,
    load_prompt_set,
    load_summarizer_prompt_set,
    render,
)

# --- default impacchettato (importlib.resources) ---


def test_default_set_loads_packaged_format() -> None:
    ps = load_prompt_set()
    text = ps.text("format.md")
    assert "RE:" in text
    assert "MSG:" in text
    assert "#end_conv" in text


def test_default_set_has_no_override() -> None:
    # Senza prompts_dir → solo default impacchettati (fresh install).
    ps = PromptSet(ORIGINAL_CHAT_SET, default_pkg=DEFAULT_PROMPTS_PKG)
    assert "ESATTAMENTE due righe" in ps.text("format.md")


# --- override per-file (precedenza) ---


def test_override_file_wins_over_default(tmp_path: Path) -> None:
    (tmp_path / "format.md").write_text(
        "RE: x\nMSG: y oppure #end_conv\nOVERRIDE\n", encoding="utf-8"
    )
    ps = PromptSet(
        ORIGINAL_CHAT_SET, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path
    )
    assert "OVERRIDE" in ps.text("format.md")


def test_missing_override_file_falls_back_to_default(tmp_path: Path) -> None:
    # override_dir esiste ma è vuoto → format.md cade sul default impacchettato.
    ps = PromptSet(
        ORIGINAL_CHAT_SET, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path
    )
    assert "ESATTAMENTE due righe" in ps.text("format.md")


# --- templating sicuro ---


def test_render_substitutes_double_brace() -> None:
    assert render("ciao {{nome}}", {"nome": "mondo"}) == "ciao mondo"


def test_render_single_braces_and_angles_survive() -> None:
    assert render("codice { non toccato } e <x> e {{y}}", {"y": "OK"}) == (
        "codice { non toccato } e <x> e OK"
    )


def test_render_injected_value_is_not_rescanned() -> None:
    # Un valore che contiene {{z}} NON viene ri-espanso: niente injection.
    assert render("{{x}}", {"x": "{{z}} letterale"}) == "{{z}} letterale"


def test_render_missing_placeholder_fails_fast() -> None:
    with pytest.raises(PromptError):
        render("ciao {{ignoto}}", {})


def test_find_placeholders() -> None:
    assert find_placeholders("{{a}} e {{ b }} e { c }") == {"a", "b"}


def test_language_name_maps_known_codes() -> None:
    assert language_name("it") == "italiano"
    assert language_name("en") == "inglese"
    assert language_name("xx") == "xx"


# --- validazione fail-fast ---


def test_missing_required_file_fails_fast() -> None:
    spec = PromptSetSpec(specs=(PromptSpec(filename="inesistente.md"),))
    with pytest.raises(PromptError, match="obbligatorio mancante"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG)


def test_empty_required_content_not_silent(tmp_path: Path) -> None:
    (tmp_path / "format.md").write_text("   \n", encoding="utf-8")
    spec = PromptSetSpec(specs=(PromptSpec(filename="format.md"),))
    with pytest.raises(PromptError, match="vuoto"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


def test_unknown_placeholder_fails_fast(tmp_path: Path) -> None:
    (tmp_path / "format.md").write_text(
        "RE: MSG: #end_conv {{boom}}\n", encoding="utf-8"
    )
    spec = PromptSetSpec(
        specs=(PromptSpec(filename="format.md", allowed_placeholders=frozenset()),)
    )
    with pytest.raises(PromptError, match="ignoti"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


def test_missing_required_placeholder_fails_fast(tmp_path: Path) -> None:
    (tmp_path / "format.md").write_text("RE: MSG: #end_conv\n", encoding="utf-8")
    spec = PromptSetSpec(
        specs=(
            PromptSpec(
                filename="format.md",
                allowed_placeholders=frozenset({"channel"}),
                required_placeholders=frozenset({"channel"}),
            ),
        )
    )
    with pytest.raises(PromptError, match="channel"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


def test_missing_control_token_fails_fast(tmp_path: Path) -> None:
    (tmp_path / "format.md").write_text("nessun token qui\n", encoding="utf-8")
    spec = PromptSetSpec(
        specs=(PromptSpec(filename="format.md", required_tokens=("#end_conv",)),)
    )
    with pytest.raises(PromptError, match="#end_conv"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


def test_missing_required_key_fails_fast(tmp_path: Path) -> None:
    (tmp_path / "keyed.md").write_text("## a\ncorpo a\n", encoding="utf-8")
    spec = PromptSetSpec(
        specs=(
            PromptSpec(
                filename="keyed.md",
                keyed=True,
                required_keys=frozenset({"a", "b"}),
            ),
        )
    )
    with pytest.raises(PromptError, match="chiave"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


# --- accesso a sezioni a-chiavi ---


def test_keyed_sections_parsed_and_rendered(tmp_path: Path) -> None:
    (tmp_path / "keyed.md").write_text(
        "## a\nciao {{nome}}\n\n## b\naltro corpo\n", encoding="utf-8"
    )
    spec = PromptSetSpec(
        specs=(
            PromptSpec(
                filename="keyed.md",
                allowed_placeholders=frozenset({"nome"}),
                keyed=True,
                required_keys=frozenset({"a", "b"}),
            ),
        )
    )
    ps = PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)
    assert ps.keys("keyed.md") == frozenset({"a", "b"})
    assert ps.section("keyed.md", "a", nome="mondo") == "ciao mondo"


# --- validazione per-sezione (ticket FU-02): meccanismo `key_specs` ---


def _keyed_spec(**key_specs: KeySpec) -> PromptSetSpec:
    """Spec sintetica di un file a-chiavi con vincoli per-sezione."""
    return PromptSetSpec(
        specs=(
            PromptSpec(
                filename="keyed.md",
                keyed=True,
                required_keys=frozenset(key_specs),
                key_specs=key_specs,
            ),
        )
    )


def test_key_spec_missing_token_names_file_and_section(tmp_path: Path) -> None:
    # Il token manca SOLO nella sezione 'b': l'errore nomina file E sezione.
    (tmp_path / "keyed.md").write_text(
        "## a\ncorpo con #tok\n\n## b\ncorpo senza token\n", encoding="utf-8"
    )
    spec = _keyed_spec(
        a=KeySpec(required_tokens=("#tok",)),
        b=KeySpec(required_tokens=("#tok",)),
    )
    with pytest.raises(PromptError, match=r"'keyed\.md' sezione 'b'.*#tok"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


def test_key_spec_foreign_placeholder_names_file_and_section(tmp_path: Path) -> None:
    # `{{user}}` in una sezione che non lo ammette: errore con file e sezione
    # (a livello di file intero sarebbe passato, perché ammesso in 'a').
    (tmp_path / "keyed.md").write_text(
        "## a\nciao {{user}}\n\n## b\nanche qui {{user}}\n", encoding="utf-8"
    )
    spec = _keyed_spec(
        a=KeySpec(allowed_placeholders=frozenset({"user"})),
        b=KeySpec(),
    )
    with pytest.raises(PromptError, match=r"'keyed\.md' sezione 'b'.*user"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


def test_key_spec_missing_required_placeholder_names_section(tmp_path: Path) -> None:
    (tmp_path / "keyed.md").write_text("## a\nsenza placeholder\n", encoding="utf-8")
    spec = _keyed_spec(a=KeySpec(required_placeholders=frozenset({"user"})))
    with pytest.raises(PromptError, match=r"'keyed\.md' sezione 'a'.*user"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


def test_key_spec_key_is_implicitly_required(tmp_path: Path) -> None:
    # Una chiave con KeySpec ma assente dal file è un errore anche se non è
    # elencata in `required_keys` (il vincolo per-sezione la rende obbligatoria).
    (tmp_path / "keyed.md").write_text("## a\ncorpo\n", encoding="utf-8")
    spec = PromptSetSpec(
        specs=(
            PromptSpec(
                filename="keyed.md",
                keyed=True,
                key_specs={"b": KeySpec(required_tokens=("#tok",))},
            ),
        )
    )
    with pytest.raises(PromptError, match="chiave"):
        PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)


def test_key_spec_valid_file_passes(tmp_path: Path) -> None:
    (tmp_path / "keyed.md").write_text(
        "## a\nciao {{user}} #tok\n\n## b\nsolo testo\n", encoding="utf-8"
    )
    spec = _keyed_spec(
        a=KeySpec(
            allowed_placeholders=frozenset({"user"}),
            required_tokens=("#tok",),
        ),
        b=KeySpec(),
    )
    ps = PromptSet(spec, default_pkg=DEFAULT_PROMPTS_PKG, override_dir=tmp_path)
    assert ps.section("keyed.md", "a", user="mondo") == "ciao mondo #tok"


# --- set original-chat completo (ticket 04): rules/intro/situations ---


def test_original_chat_set_serves_rules_intro_situations() -> None:
    ps = load_prompt_set()
    assert "Sei Minnarone" in ps.text("rules.md", channel="enkk")
    assert "SITUAZIONE ATTUALE" in ps.text("intro.md", channel="enkk")
    assert ps.keys("situations.md") == frozenset(
        {
            "idle",
            "chat-mention",
            "chat-continuation",
            "streamer-mention",
            "streamer-continuation",
            "generic",
        }
    )


def test_original_chat_rules_missing_channel_placeholder_fails_fast(
    tmp_path: Path,
) -> None:
    # Un override di rules.md senza `{{channel}}` è fail-fast: il canale
    # obbligatorio non deve poter sparire.
    (tmp_path / "rules.md").write_text("- Nessun canale qui.\n", encoding="utf-8")
    with pytest.raises(PromptError, match="channel"):
        load_prompt_set(tmp_path)


def test_original_chat_situations_missing_key_fails_fast(tmp_path: Path) -> None:
    (tmp_path / "situations.md").write_text(
        "## idle\nsolo idle MSG: #end_conv\n", encoding="utf-8"
    )
    with pytest.raises(PromptError, match="chiave"):
        load_prompt_set(tmp_path)


def test_original_chat_situations_missing_end_conv_fails_fast(
    tmp_path: Path,
) -> None:
    # Tutte le chiavi presenti ma nessun `#end_conv`: fail-fast sul token.
    (tmp_path / "situations.md").write_text(
        "## idle\nidle\n\n## chat-mention\n{{user}} {{mention}}\n\n"
        "## chat-continuation\n{{user}} {{mention}}\n\n"
        "## streamer-mention\ns\n\n## streamer-continuation\ns\n\n"
        "## generic\n{{reason}}\n",
        encoding="utf-8",
    )
    with pytest.raises(PromptError, match="#end_conv"):
        load_prompt_set(tmp_path)


# --- vincoli per-sezione dei set reali (situations.md / summarizer.md) ---

# Override di `situations.md` conforme ai percorsi di render reali: `#end_conv`
# dove il default lo ha (idle, chat-*, streamer-continuation), placeholder solo
# dove il render li fornisce. Base dei test che rompono UNA sezione alla volta.
_VALID_SITUATIONS = {
    "idle": "idle, se nulla MSG: #end_conv",
    "chat-mention": "{{user}} scrive ({{mention}}); se nulla MSG: #end_conv",
    "chat-continuation": "{{user}} continua ({{mention}}); se no MSG: #end_conv",
    "streamer-mention": "lo streamer ti parla, rispondi",
    "streamer-continuation": "forse continua; se no MSG: #end_conv",
    "generic": "reagisci a {{reason}}:",
}


def _write_situations(tmp_path: Path, overrides: dict[str, str]) -> None:
    sections = {**_VALID_SITUATIONS, **overrides}
    text = "\n\n".join(f"## {key}\n{body}" for key, body in sections.items())
    (tmp_path / "situations.md").write_text(text + "\n", encoding="utf-8")


def test_situations_valid_per_key_override_passes(tmp_path: Path) -> None:
    # Il layout conforme (senza #end_conv in streamer-mention/generic, come il
    # default impacchettato) DEVE passare: quelle sezioni non lo richiedono.
    _write_situations(tmp_path, {})
    ps = load_prompt_set(tmp_path)
    assert "rispondi" in ps.section("situations.md", "streamer-mention")


def test_situations_end_conv_missing_in_one_section_names_it(
    tmp_path: Path,
) -> None:
    # `#end_conv` sparisce SOLO da chat-mention: a livello di file intero
    # passerebbe (c'è altrove); il vincolo per-sezione nomina file e sezione.
    _write_situations(tmp_path, {"chat-mention": "{{user}} scrive, rispondi"})
    with pytest.raises(
        PromptError,
        match=r"'situations\.md' sezione 'chat-mention'.*#end_conv",
    ):
        load_prompt_set(tmp_path)


def test_situations_placeholder_in_wrong_section_names_it(tmp_path: Path) -> None:
    # `{{user}}` in streamer-mention: il render di quella sezione non fornisce
    # valori → oggi esploderebbe a runtime. Deve fallire al load, con sezione.
    _write_situations(tmp_path, {"streamer-mention": "lo streamer parla a {{user}}"})
    with pytest.raises(
        PromptError,
        match=r"'situations\.md' sezione 'streamer-mention'.*user",
    ):
        load_prompt_set(tmp_path)


def test_situations_reason_only_allowed_in_generic(tmp_path: Path) -> None:
    # `{{reason}}` è fornito solo dal render di `generic`: altrove è un errore.
    _write_situations(tmp_path, {"idle": "idle {{reason}} MSG: #end_conv"})
    with pytest.raises(PromptError, match=r"'situations\.md' sezione 'idle'.*reason"):
        load_prompt_set(tmp_path)


def test_summarizer_placeholder_in_section_names_it(tmp_path: Path) -> None:
    # Il summarizer non fornisce MAI valori: un `{{user}}` in una sezione deve
    # fallire al load nominando file e sezione (non a runtime al primo giro).
    (tmp_path / "summarizer.md").write_text(
        "## instruction\nsintetizza\n\n## empty_placeholder\n(niente)\n\n"
        "## label_streamer\nSTREAMER:\n\n## label_schermo\nSCHERMO:\n\n"
        "## label_chat\nCHAT di {{user}}:\n\n"
        "## current_summary_header\nRiassunto:\n\n"
        "## recent_events_header\nEventi:\n\n"
        "## update_instruction\nAggiorna.\n",
        encoding="utf-8",
    )
    with pytest.raises(
        PromptError, match=r"'summarizer\.md' sezione 'label_chat'.*user"
    ):
        load_summarizer_prompt_set(tmp_path)


def test_default_sets_pass_per_key_validation() -> None:
    # I default impacchettati passano invariati con i vincoli per-sezione.
    load_prompt_set()
    load_summarizer_prompt_set()


# --- headers.md (FU-03): header di sezione esternalizzati -------------------

# Le chiavi del contratto `headers.md`: ogni header/framing tunabile del prompt
# di reazione. `cosa_sai` e' l'unica con `{{channel}}`; le `_std` sono le
# etichette degli stili non-original-chat (il prefisso `## ` resta strutturale,
# composto in codice).
_HEADER_KEYS = frozenset(
    {
        "regole",
        "memoria_permanente",
        "memoria_permanente_uso",
        "chi_sei",
        "cosa_sai",
        "formato_risposta",
        "memoria",
        "memoria_suffix",
        "tuoi_ultimi_messaggi",
        "conversazione_recente",
        "situazione",
        "chat_recente",
        "parlato_recente",
        "schermo_recente",
        "riassunto_std",
        "conversazione_recente_std",
        "situazione_std",
    }
)

# Base per gli override nei test: un headers.md inglese completo e conforme.
_VALID_HEADERS_EN = {
    "regole": "[RULES]",
    "memoria_permanente": "[PERMANENT MEMORY] (context about you and the streamer)",
    "memoria_permanente_uso": "Use it ONLY when it makes sense.",
    "chi_sei": "WHO YOU ARE:",
    "cosa_sai": "WHAT YOU KNOW ABOUT @{{channel}} (the streamer):",
    "formato_risposta": "[RESPONSE FORMAT]",
    "memoria": "[MEMORY]",
    "memoria_suffix": "(how the stream has been going)",
    "tuoi_ultimi_messaggi": "[YOUR LAST MESSAGES]",
    "conversazione_recente": "[RECENT CONVERSATION]",
    "situazione": "[SITUATION]",
    "chat_recente": "[RECENT CHAT]",
    "parlato_recente": "[RECENT SPEECH]",
    "schermo_recente": "[RECENT SCREEN]",
    "riassunto_std": "SUMMARY",
    "conversazione_recente_std": "RECENT CONVERSATION",
    "situazione_std": "SITUATION",
}


def _write_headers(tmp_path: Path, overrides: dict[str, str]) -> None:
    sections = {**_VALID_HEADERS_EN, **overrides}
    text = "\n\n".join(f"## {key}\n{body}" for key, body in sections.items())
    (tmp_path / "headers.md").write_text(text + "\n", encoding="utf-8")


def test_headers_default_set_serves_all_keys() -> None:
    ps = load_prompt_set()
    assert ps.keys("headers.md") == _HEADER_KEYS
    # I default sono byte-identici agli header storici cablati.
    assert ps.section("headers.md", "regole") == "[REGOLE]"
    assert ps.section("headers.md", "memoria") == "[MEMORIA]"
    assert ps.section("headers.md", "memoria_suffix") == (
        "(com'e' andata la live e le conversazioni recenti)"
    )
    assert ps.section("headers.md", "tuoi_ultimi_messaggi") == (
        "[I TUOI ULTIMI MESSAGGI]"
    )
    assert ps.section("headers.md", "cosa_sai", channel="enkk") == (
        "COSA SAI SU @enkk (lo streamer):"
    )
    assert ps.section("headers.md", "riassunto_std") == "RIASSUNTO"


def test_headers_valid_full_override_passes(tmp_path: Path) -> None:
    _write_headers(tmp_path, {})
    ps = load_prompt_set(tmp_path)
    assert ps.section("headers.md", "regole") == "[RULES]"
    assert ps.section("headers.md", "cosa_sai", channel="pepper") == (
        "WHAT YOU KNOW ABOUT @pepper (the streamer):"
    )


def test_headers_missing_key_fails_fast(tmp_path: Path) -> None:
    # Un headers.md senza una chiave obbligatoria fallisce all'avvio nominando
    # il file (mai un header vuoto silenzioso a runtime).
    (tmp_path / "headers.md").write_text("## regole\n[RULES]\n", encoding="utf-8")
    with pytest.raises(PromptError, match=r"headers\.md"):
        load_prompt_set(tmp_path)


def test_headers_channel_only_allowed_in_cosa_sai(tmp_path: Path) -> None:
    # `{{channel}}` fuori da `cosa_sai` e' un errore per-sezione: il render
    # degli altri header non fornisce valori.
    _write_headers(tmp_path, {"situazione": "[SITUATION of {{channel}}]"})
    with pytest.raises(
        PromptError, match=r"'headers\.md' sezione 'situazione'.*channel"
    ):
        load_prompt_set(tmp_path)


def test_headers_cosa_sai_requires_channel(tmp_path: Path) -> None:
    # Un override non puo' "perdere" il canale (stessa regola di rules/intro).
    _write_headers(tmp_path, {"cosa_sai": "WHAT YOU KNOW (the streamer):"})
    with pytest.raises(PromptError, match=r"'headers\.md' sezione 'cosa_sai'.*channel"):
        load_prompt_set(tmp_path)


def test_headers_reject_header_ref_placeholders_no_recursion(
    tmp_path: Path,
) -> None:
    # I placeholder `{{header_*}}` sono per i CORPI (situations.md), non per
    # headers.md stesso: niente ricorsione header->header.
    _write_headers(tmp_path, {"memoria": "{{header_situazione}}"})
    with pytest.raises(PromptError, match=r"'headers\.md' sezione 'memoria'"):
        load_prompt_set(tmp_path)


def test_situations_bodies_may_cite_headers_via_placeholder(
    tmp_path: Path,
) -> None:
    # I riferimenti incrociati nei corpi usano `{{header_*}}`: ammessi in ogni
    # sezione di situations.md (il render li fornisce sempre).
    _write_situations(
        tmp_path,
        {
            "idle": "guarda {{header_memoria}}; se nulla MSG: #end_conv",
            "streamer-mention": (
                "rispondi tenendo il filo ({{header_tuoi_ultimi_messaggi}} "
                "e {{header_memoria}})"
            ),
            "chat-continuation": (
                "{{user}} continua ({{mention}}): guarda "
                "{{header_conversazione_recente}}; se no MSG: #end_conv"
            ),
        },
    )
    ps = load_prompt_set(tmp_path)
    rendered = ps.section(
        "situations.md",
        "streamer-mention",
        header_memoria="[MEMORIA]",
        header_tuoi_ultimi_messaggi="[I TUOI ULTIMI MESSAGGI]",
        header_conversazione_recente="[CONVERSAZIONE RECENTE]",
    )
    assert "[I TUOI ULTIMI MESSAGGI] e [MEMORIA]" in rendered


def test_default_situations_reference_headers_not_literals() -> None:
    # Nei default i corpi NON cablano piu' i nomi degli header: li citano via
    # placeholder, risolti dagli stessi valori di headers.md (coerenza per
    # costruzione).
    from importlib.resources import files

    raw = (files(DEFAULT_PROMPTS_PKG) / "situations.md").read_text(encoding="utf-8")
    assert "{{header_tuoi_ultimi_messaggi}}" in raw
    assert "{{header_memoria}}" in raw
    assert "{{header_conversazione_recente}}" in raw
    assert "[I TUOI ULTIMI MESSAGGI]" not in raw
    assert "[CONVERSAZIONE RECENTE]" not in raw
    assert "[MEMORIA]" not in raw
