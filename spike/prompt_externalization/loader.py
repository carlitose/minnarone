"""Loader spike: contratto di prompt-source (formato + templating + validazione).

SPIKE THROWAWAY (ticket 02). Prova le decisioni di design senza toccare la
produzione. Le regole di sicurezza (anti-injection, disclosure, fence) NON
sono qui: restano cablate in `prompt.py`. Questo loader gestisce SOLO il testo
tunabile.

Contratto provato qui:

- **Formato**: markdown-only. Un prompt-set = una directory. Un `.md` per prompt
  di prosa; i set "a chiavi" sono un unico `.md` con sezioni `## <chiave>`.
- **Templating**: `{{nome}}` (doppia graffa). Sostituzione sicura: solo i nomi
  in whitelist sono ammessi; il valore iniettato NON viene ri-scansionato
  (niente injection ricorsiva); le graffe singole letterali sopravvivono.
- **Packaging + override**: default via `importlib.resources` su un package;
  override per-file da una directory (config `prompts_dir`). Precedenza: se il
  file esiste nell'override lo si usa, altrimenti il default impacchettato.
- **Validazione**: fail-fast (mai vuoto silenzioso) su file mancante /
  placeholder mancante o ignoto / token di controllo mancante / sezione chiave
  mancante / contenuto vuoto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path


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

    - `filename`: nome relativo nel set (es. "rules.md").
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


# Mappa codice-lingua → nome (portata dallo spike da prompt._language_name).
# Il valore alimenta la sostituzione di `{{language}}`: la fonte è la config
# (dato fidato), MAI contenuto percepito → la sostituzione non è un vettore di
# injection.
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
        unknown = found - spec.allowed_placeholders
        if unknown:
            raise PromptError(
                f"placeholder ignoti in '{spec.filename}': "
                f"{sorted(unknown)} (ammessi: {sorted(spec.allowed_placeholders)})"
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

    def text(self, filename: str, **values: str) -> str:
        """Testo di un prompt di prosa, con i `{{...}}` sostituiti."""
        return render(self._loaded[filename].text, values)

    def section(self, filename: str, key: str, **values: str) -> str:
        """Corpo di una sezione `## <key>` di un file a-chiavi, sostituito."""
        loaded = self._loaded[filename]
        if key not in loaded.sections:
            raise PromptError(f"chiave sconosciuta '{key}' in '{filename}'")
        return render(loaded.sections[key], values)

    def keys(self, filename: str) -> frozenset[str]:
        return frozenset(self._loaded[filename].sections)
