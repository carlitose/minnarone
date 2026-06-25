"""Schema del file di configurazione dell'agente.

Un unico file YAML dichiara come comporre e far girare l'agente. Include i
punti di estensione v2 (`disclosure`, `retention`, `auto_memory`): presenti
nello schema ma INERTI nell'MVP, così non vanno retrofittati in seguito.

La validazione è fatta a mano su dataclasses (errori chiari, indicano il
campo). Il parsing del file usa PyYAML (`yaml.safe_load`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .output import OutputMode


class ConfigError(ValueError):
    """Configurazione mancante o non valida, con messaggio puntuale."""


@dataclass(frozen=True, slots=True)
class DisclosureConfig:
    """Punto v2 (inerte in MVP): se/come l'agente dichiara di essere un'AI."""

    announce_ai: bool = False


@dataclass(frozen=True, slots=True)
class RetentionConfig:
    """Punto v2 (inerte in MVP): per quanto tempo conservare i dati percepiti."""

    perceptions_days: int | None = None


@dataclass(frozen=True, slots=True)
class Config:
    """Configurazione completa dell'agente.

    Campi MVP operativi + punti v2 inerti (`disclosure`, `retention`,
    `auto_memory`).
    """

    mode: OutputMode
    soul_path: str
    facts_dir: str
    adapter: str
    llm_provider: str
    llm_params: dict[str, object] = field(default_factory=dict)
    senser_interval: float = 0.5
    idle_interval: float = 150.0
    recent_chat_window: int = 15
    # --- punti di estensione v2 (presenti ma inerti) ---
    disclosure: DisclosureConfig = field(default_factory=DisclosureConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)
    auto_memory: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.mode, OutputMode):
            raise ConfigError(f"mode non valido: {self.mode!r}")
        for name in ("soul_path", "facts_dir", "adapter", "llm_provider"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ConfigError(f"campo obbligatorio '{name}' mancante o vuoto")
        if self.senser_interval <= 0:
            raise ConfigError("senser_interval deve essere > 0")
        if self.idle_interval <= 0:
            raise ConfigError("idle_interval deve essere > 0")
        if self.recent_chat_window <= 0:
            raise ConfigError("recent_chat_window deve essere > 0")

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "Config":
        """Costruisce e valida una Config da un dizionario (es. TOML parsato)."""
        if "mode" not in data:
            raise ConfigError("campo obbligatorio 'mode' mancante")
        try:
            mode = OutputMode(data["mode"])
        except ValueError as exc:
            raise ConfigError(
                f"mode {data['mode']!r} non valido (ammessi: public, private)"
            ) from exc

        disclosure_raw = data.get("disclosure", {})
        retention_raw = data.get("retention", {})
        if not isinstance(disclosure_raw, dict) or not isinstance(retention_raw, dict):
            raise ConfigError("'disclosure' e 'retention' devono essere tabelle")

        try:
            return cls(
                mode=mode,
                soul_path=data.get("soul_path"),  # type: ignore[arg-type]
                facts_dir=data.get("facts_dir"),  # type: ignore[arg-type]
                adapter=data.get("adapter"),  # type: ignore[arg-type]
                llm_provider=data.get("llm_provider"),  # type: ignore[arg-type]
                llm_params=dict(data.get("llm_params", {})),  # type: ignore[arg-type]
                senser_interval=float(data.get("senser_interval", 0.5)),
                idle_interval=float(data.get("idle_interval", 150.0)),
                recent_chat_window=int(data.get("recent_chat_window", 15)),
                disclosure=DisclosureConfig(
                    announce_ai=bool(disclosure_raw.get("announce_ai", False))
                ),
                retention=RetentionConfig(
                    perceptions_days=retention_raw.get("perceptions_days")
                ),
                auto_memory=bool(data.get("auto_memory", False)),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ConfigError):
                raise
            raise ConfigError(str(exc)) from exc

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        """Carica e valida una Config da un file YAML."""
        p = Path(path)
        if not p.is_file():
            raise ConfigError(f"file di config non trovato: {p}")
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if data is None:
            raise ConfigError(f"file di config vuoto: {p}")
        if not isinstance(data, dict):
            raise ConfigError("la radice del file di config deve essere una mappa")
        return cls.from_dict(data)
