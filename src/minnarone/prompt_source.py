"""Prompt-source: caricamento, templating e validazione dei prompt tunabili.

Promosso dallo spike `spike/prompt_externalization/` (ticket 02, 8/8 test verdi)
e portato in produzione dal ticket 03. Gestisce SOLO il testo tunabile dei
prompt; le regole di SICUREZZA (anti-injection, disclosure, fence) restano
cablate in `prompt.py` — un file editabile non deve poter indebolire la
protezione.

Contratto (locked dal ticket 02):

- **Formato**: markdown-only. Un prompt-set = una directory. Un `.md` per prompt
  di prosa; i set "a chiavi" sono un unico `.md` con sezioni `## <chiave>`.
- **Templating**: `{{nome}}` (doppia graffa). Sostituzione sicura: solo i nomi
  in whitelist sono ammessi; il valore iniettato NON viene ri-scansionato
  (niente injection ricorsiva); le graffe singole letterali e i `<...>`
  sopravvivono intatti.
- **Packaging + override**: default impacchettati come package
  (`minnarone.prompts`, letto via `importlib.resources`) + override per-file da
  una directory in config (`prompts_dir`). Precedenza per-file: se il file
  esiste nell'override lo si usa, altrimenti il default impacchettato.
- **Validazione**: fail-fast (mai vuoto silenzioso) su file mancante /
  placeholder mancante o ignoto / token di controllo mancante / sezione chiave
  mancante / contenuto vuoto. Volutamente più stretta di `FileMemory` (che
  degrada con grazia perché la memoria è contesto opzionale): un prompt di
  prosa/regole mancante non deve degradare a vuoto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

# Package che contiene il set di prompt default impacchettati nel wheel.
DEFAULT_PROMPTS_PKG = "minnarone.prompts"


class PromptError(Exception):
    """Errore fatale del prompt-source: il caller deve fallire all'avvio.

    Un persona/regole mancante o malformato NON deve degradare a vuoto
    silenzioso (le regole di sicurezza sono cablate, ma il resto del prompt
    perderebbe di senso). Questo distingue il prompt-source dalla memoria
    (`FileMemory`), che invece degrada con grazia perché è contesto opzionale.
    """


# Un placeholder è ESATTAMENTE `{{ nome }}` (spazi interni opzionali). Le graffe
# singole (`{`, `}`) e i contratti `<...>` non matchano: sopravvivono intatti.
_PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

# Separatore di sezione per i set "a chiavi": una riga che inizia con `## `.
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class PromptSpec:
    """Descrive un file del prompt-set e i suoi vincoli di validazione.

    - `filename`: nome relativo nel set (es. "format.md").
    - `allowed_placeholders`: whitelist dei `{{nome}}` ammessi nel file. Un
      placeholder fuori whitelist è un errore (typo o tentativo di iniettare un
      punto di sostituzione non previsto).
    - `required_placeholders`: devono comparire almeno una volta (canale, ecc.).
    - `required_tokens`: stringhe letterali che DEVONO comparire (token di
      controllo su cui dipende il parser: `#end_conv`, `#nothing`, `RE:`, `MSG:`).
    - `keyed`: se True il file è parsato in sezioni `## <chiave>`.
    - `required_keys`: chiavi che il file a-chiavi DEVE contenere.
    """

    filename: str
    allowed_placeholders: frozenset[str] = frozenset()
    required_placeholders: frozenset[str] = frozenset()
    required_tokens: tuple[str, ...] = ()
    keyed: bool = False
    required_keys: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PromptSetSpec:
    """L'insieme dei file attesi in un prompt-set (il contratto strutturale)."""

    specs: tuple[PromptSpec, ...]

    def by_name(self, filename: str) -> PromptSpec:
        for spec in self.specs:
            if spec.filename == filename:
                return spec
        raise KeyError(filename)


# Mappa codice-lingua → nome. Il valore alimenta la sostituzione di
# `{{language}}`: la fonte è la config (dato fidato), MAI contenuto percepito →
# la sostituzione non è un vettore di injection. Fonte UNICA del mapping (il
# ticket 06 ha rimosso la gemella `prompt._language_name`): `prompt.py` importa
# `language_name` da qui.
_LANGUAGE_NAMES = {
    "it": "italiano",
    "ita": "italiano",
    "italian": "italiano",
    "en": "inglese",
    "eng": "inglese",
    "english": "inglese",
    "es": "spagnolo",
    "spa": "spagnolo",
    "spanish": "spagnolo",
}


def language_name(code: str) -> str:
    return _LANGUAGE_NAMES.get(code.lower(), code)


def find_placeholders(text: str) -> set[str]:
    """Nomi di tutti i `{{...}}` presenti nel testo."""
    return {m.group(1) for m in _PLACEHOLDER_RE.finditer(text)}


def render(text: str, values: dict[str, str]) -> str:
    """Sostituisce i `{{nome}}` con i valori dati, in modo SICURO.

    - Solo i pattern `{{nome}}` sono toccati: le graffe singole e i `<...>`
      restano letterali.
    - Il valore iniettato è inserito così com'è, senza ri-scansione: se un
      valore contenesse a sua volta `{{x}}` NON verrebbe ri-espanso (niente
      injection ricorsiva via template).
    - Un placeholder senza valore è un errore (fail-fast), non una stringa vuota.
    """

    def _repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise PromptError(f"placeholder non risolto: {{{{{name}}}}}")
        # re.sub con funzione: il ritorno è usato LETTERALMENTE (nessun
        # processing di backreference, nessuna ri-scansione).
        return values[name]

    return _PLACEHOLDER_RE.sub(_repl, text)


def _split_sections(text: str) -> dict[str, str]:
    """Parsa un file a-chiavi in `{chiave: corpo}` dalle intestazioni `## <chiave>`."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text))
    for i, match in enumerate(matches):
        key = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[key] = text[start:end].strip()
    return sections


@dataclass(frozen=True)
class LoadedPrompt:
    """Un file di prompt caricato e validato (template ancora da renderizzare)."""

    filename: str
    text: str
    sections: dict[str, str] = field(default_factory=dict)


class PromptSet:
    """Carica e valida un prompt-set: default impacchettato + override per-file.

    `default_pkg` è il package Python che contiene il set default (letto via
    `importlib.resources`). `override_dir` è una directory su disco (dalla config
    `prompts_dir`): se un file esiste lì ha la precedenza sul default.
    """

    def __init__(
        self,
        set_spec: PromptSetSpec,
        *,
        default_pkg: str,
        override_dir: str | Path | None = None,
    ) -> None:
        self._set_spec = set_spec
        self._default_root: Traversable = files(default_pkg)
        self._override_dir = Path(override_dir) if override_dir else None
        self._loaded: dict[str, LoadedPrompt] = {}
        self._load_all()

    # --- caricamento + validazione (all'avvio: fail-fast) ---

    def _read_source(self, filename: str) -> tuple[str, str]:
        """Legge il testo di un file, con precedenza override → default.

        Ritorna (testo, origine) dove origine ∈ {"override", "default"}.
        Fail-fast se assente in ENTRAMBI.
        """
        if self._override_dir is not None:
            candidate = self._override_dir / filename
            if candidate.is_file():
                try:
                    return candidate.read_text(encoding="utf-8"), "override"
                except (OSError, UnicodeDecodeError) as exc:
                    raise PromptError(
                        f"override illeggibile: {candidate}: {exc}"
                    ) from exc

        resource = self._default_root / filename
        if not resource.is_file():
            raise PromptError(
                f"file di prompt obbligatorio mancante: '{filename}' "
                f"(né in override {self._override_dir} né nel set default)"
            )
        try:
            return resource.read_text(encoding="utf-8"), "default"
        except (OSError, UnicodeDecodeError) as exc:
            raise PromptError(f"default illeggibile: {filename}: {exc}") from exc

    def _load_all(self) -> None:
        for spec in self._set_spec.specs:
            text, _origin = self._read_source(spec.filename)
            self._loaded[spec.filename] = self._validate(spec, text)

    @staticmethod
    def _validate(spec: PromptSpec, text: str) -> LoadedPrompt:
        if not text.strip():
            raise PromptError(
                f"contenuto obbligatorio vuoto: '{spec.filename}' "
                "(mai vuoto silenzioso per un prompt richiesto)"
            )

        found = find_placeholders(text)
        # I placeholder obbligatori sono implicitamente ammessi: evita di doverli
        # dichiarare due volte (footgun per chi aggiunge prompt in 04-06).
        allowed = spec.allowed_placeholders | spec.required_placeholders
        unknown = found - allowed
        if unknown:
            raise PromptError(
                f"placeholder ignoti in '{spec.filename}': "
                f"{sorted(unknown)} (ammessi: {sorted(allowed)})"
            )
        missing_ph = spec.required_placeholders - found
        if missing_ph:
            raise PromptError(
                f"placeholder obbligatori mancanti in '{spec.filename}': "
                f"{sorted(missing_ph)}"
            )

        for token in spec.required_tokens:
            if token not in text:
                raise PromptError(
                    f"token di controllo mancante in '{spec.filename}': "
                    f"{token!r} (il parser dell'output ne dipende)"
                )

        sections: dict[str, str] = {}
        if spec.keyed:
            sections = _split_sections(text)
            missing_keys = spec.required_keys - sections.keys()
            if missing_keys:
                raise PromptError(
                    f"sezioni chiave mancanti in '{spec.filename}': "
                    f"{sorted(missing_keys)}"
                )
            for key, body in sections.items():
                if not body.strip():
                    raise PromptError(
                        f"sezione '## {key}' vuota in '{spec.filename}'"
                    )

        return LoadedPrompt(spec.filename, text, sections)

    # --- accesso (a runtime: rendering) ---

    def _get(self, filename: str) -> LoadedPrompt:
        """Recupera un prompt caricato, fail-fast su filename non registrato.

        Contratto uniforme: un typo di filename in 04-06 solleva `PromptError`,
        non un `KeyError` nudo che i chiamanti non intercettano.
        """
        try:
            return self._loaded[filename]
        except KeyError:
            raise PromptError(f"prompt non registrato: {filename!r}") from None

    def text(self, filename: str, **values: str) -> str:
        """Testo di un prompt di prosa, con i `{{...}}` sostituiti.

        Il testo è restituito così com'è stato caricato (incluso il newline
        finale del file): questo preserva la byte-invarianza quando il chiamante
        compone il prefisso stabile.
        """
        return render(self._get(filename).text, values)

    def section(self, filename: str, key: str, **values: str) -> str:
        """Corpo di una sezione `## <key>` di un file a-chiavi, sostituito."""
        loaded = self._get(filename)
        if key not in loaded.sections:
            raise PromptError(f"chiave sconosciuta '{key}' in '{filename}'")
        return render(loaded.sections[key], values)

    def keys(self, filename: str) -> frozenset[str]:
        return frozenset(self._get(filename).sections)


# --- contratto concreto del prompt-set "original-chat" ---
#
# Cresce man mano che i prompt migrano: il ticket 03 ha impacchettato `format.md`
# (il tracer, accoppiato al parser RE/MSG → token obbligatori). Il ticket 04
# aggiunge il testo tunabile della modalità original-chat: `rules.md` (prosa
# persona/regole, con `{{channel}}`, servita byte-preserving nel prefisso
# stabile), `intro.md` (banner + riga canale, dinamico) e `situations.md` (le 6
# situazioni a chiavi, con il token di controllo `#end_conv`). I ticket 05-06
# aggiungeranno il summarizer e i template di stile (`{{language}}`).

FORMAT_SPEC = PromptSpec(
    filename="format.md",
    required_tokens=("RE:", "MSG:", "#end_conv"),
)

# Regole persona/stile original-chat: prosa servita con `.text()` (byte-preserving)
# nel prefisso stabile. `{{channel}}` è l'unico punto di sostituzione: la fonte è
# la config/codice (dato fidato), mai contenuto percepito → non è un vettore di
# injection. Obbligatorio così un override non può "perdere" il canale.
RULES_SPEC = PromptSpec(
    filename="rules.md",
    allowed_placeholders=frozenset({"channel"}),
    required_placeholders=frozenset({"channel"}),
)

# Apertura dinamica (banner + canale). Stesso `{{channel}}` delle regole: canale
# unificato, reso da una sola fonte a runtime.
INTRO_SPEC = PromptSpec(
    filename="intro.md",
    allowed_placeholders=frozenset({"channel"}),
    required_placeholders=frozenset({"channel"}),
)

# Le 6 varianti di SITUAZIONE, a chiavi. `#end_conv` è un token di controllo del
# parser dell'output: deve sopravvivere in almeno una variante (fail-fast se un
# override lo elimina). `{{user}}`/`{{mention}}` (chat) e `{{reason}}` (fallback)
# sono i soli punti di sostituzione; i valori vengono neutralizzati a monte
# (`_sanitize_display_token`) prima di essere iniettati.
SITUATIONS_SPEC = PromptSpec(
    filename="situations.md",
    allowed_placeholders=frozenset({"user", "mention", "reason"}),
    required_tokens=("#end_conv",),
    keyed=True,
    required_keys=frozenset(
        {
            "idle",
            "chat-mention",
            "chat-continuation",
            "streamer-mention",
            "streamer-continuation",
            "generic",
        }
    ),
)

# Regole per-stile delle modalità non-original-chat (ticket 06). Prosa servita
# con `.text()` (byte-preserving) nel prefisso stabile del rispettivo stile.
# `{{language}}` è l'unico punto di sostituzione: la fonte è la config/codice
# (dato fidato, reso da `language_name`), mai contenuto percepito → non è un
# vettore di injection. È OBBLIGATORIO così un override non può "perdere" la
# lingua. Il file del suggester DEVE contenere il token di controllo `#nothing`
# (la sentinella "niente da suggerire"): fail-fast se un override lo elimina.
OPERATOR_RULES_SPEC = PromptSpec(
    filename="operator.md",
    allowed_placeholders=frozenset({"language"}),
    required_placeholders=frozenset({"language"}),
)

MEETING_SYNTHESIZER_RULES_SPEC = PromptSpec(
    filename="meeting_synthesizer.md",
    allowed_placeholders=frozenset({"language"}),
    required_placeholders=frozenset({"language"}),
)

SUGGESTER_RULES_SPEC = PromptSpec(
    filename="suggester.md",
    allowed_placeholders=frozenset({"language"}),
    required_placeholders=frozenset({"language"}),
    required_tokens=("#nothing",),
)

# Set condiviso del prompt di reazione: oltre ai file original-chat include le
# regole per-stile (ticket 06), così il PromptSet unico iniettato nel
# `PromptBuilder` serve TUTTI gli stili senza doverne portare un secondo.
ORIGINAL_CHAT_SET = PromptSetSpec(
    specs=(
        FORMAT_SPEC,
        RULES_SPEC,
        INTRO_SPEC,
        SITUATIONS_SPEC,
        OPERATOR_RULES_SPEC,
        MEETING_SYNTHESIZER_RULES_SPEC,
        SUGGESTER_RULES_SPEC,
    )
)


def load_prompt_set(prompts_dir: str | Path | None = None) -> PromptSet:
    """Costruisce il prompt-set original-chat: default impacchettati + override.

    `prompts_dir` è la directory di override (da `Config.prompts_dir`): se un
    file c'è lì vince sull'impacchettato, altrimenti si usa il default nel wheel.
    Assente → SOLO i default impacchettati (fresh install funziona).
    """
    return PromptSet(
        ORIGINAL_CHAT_SET,
        default_pkg=DEFAULT_PROMPTS_PKG,
        override_dir=prompts_dir,
    )


# --- contratto concreto del prompt-set "summarizer" (ticket 05) ---
#
# Testo tunabile della memoria a breve termine, esternalizzato dal `summarizer.py`
# hard-coded. Set a-chiavi in UN solo file (`summarizer.md`): l'istruzione rolling,
# il placeholder del primo giro, le tre etichette di gruppo per fonte
# (STREAMER/SCHERMO/CHAT) e le intestazioni di scaffolding del prompt. NON ha
# placeholder `{{...}}` né token di controllo del parser (il summarizer non passa
# per il contratto RE/MSG dell'output). La mappa fonte→etichetta resta in codice
# (`summarizer._SOURCE_LABEL_KEYS`); qui si esternalizza solo il TESTO.
#
# Set SEPARATO da `ORIGINAL_CHAT_SET` di proposito: il prompt del summarizer è una
# preoccupazione distinta (NON fa parte del prefisso stabile in cache) e mantiene
# il `Summarizer` disaccoppiato dal contratto original-chat — gli serve solo
# `summarizer.md`. Stessa meccanica del factory `load_prompt_set`: default
# impacchettati + override per-file da `prompts_dir`.
SUMMARIZER_SPEC = PromptSpec(
    filename="summarizer.md",
    keyed=True,
    required_keys=frozenset(
        {
            "instruction",
            "empty_placeholder",
            "label_streamer",
            "label_schermo",
            "label_chat",
            "current_summary_header",
            "recent_events_header",
            "update_instruction",
        }
    ),
)

SUMMARIZER_SET = PromptSetSpec(specs=(SUMMARIZER_SPEC,))


def load_summarizer_prompt_set(prompts_dir: str | Path | None = None) -> PromptSet:
    """Costruisce il prompt-set del summarizer: default impacchettati + override.

    Gemello di `load_prompt_set`, ma per il set `SUMMARIZER_SET`. `prompts_dir`
    è la directory di override (da `Config.prompts_dir`): un `summarizer.md` lì
    vince sull'impacchettato. Assente → SOLO il default nel wheel.
    """
    return PromptSet(
        SUMMARIZER_SET,
        default_pkg=DEFAULT_PROMPTS_PKG,
        override_dir=prompts_dir,
    )
