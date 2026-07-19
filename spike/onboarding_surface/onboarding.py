"""Disposable onboarding state machine for ticket 16.

The prototype writes only after the operator confirms the digest of the exact
Markdown preview. It is intentionally not a production CLI.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
from pathlib import Path
from typing import Any

REQUIRED_PERSONA = (
    "name",
    "role",
    "tone",
    "traits_opinions",
    "behavioral_limits",
    "typical_message_length",
)
REQUIRED_CHANNEL = ("name", "content", "relationship")
ALLOWED_ORIGINS = {"operator", "verified_metadata", "confirmed_inference"}
TWITCH_CHANNEL_RE = re.compile(r"[a-z0-9_]{1,25}")


def _require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing answer: {label}")
    return value.strip()


def load_answers(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("answers must be a JSON object")
    channel = _require_text(data.get("channel"), "channel")
    if TWITCH_CHANNEL_RE.fullmatch(channel) is None:
        raise ValueError("channel must be a lowercase Twitch login (letters, digits, underscore)")
    _require_text(data.get("language"), "language")
    persona = data.get("persona")
    channel_facts = data.get("channel_facts")
    if not isinstance(persona, dict) or not isinstance(channel_facts, dict):
        raise ValueError("persona and channel_facts must be objects")
    for field in REQUIRED_PERSONA:
        if field == "traits_opinions":
            traits = persona.get(field)
            if not isinstance(traits, list) or not 2 <= len(traits) <= 5:
                raise ValueError("persona.traits_opinions must contain 2-5 items")
            for index, item in enumerate(traits):
                _require_text(item, f"persona.traits_opinions[{index}]")
        else:
            _require_text(persona.get(field), f"persona.{field}")
    for field in REQUIRED_CHANNEL:
        _require_text(channel_facts.get(field), f"channel_facts.{field}")
    origins = data.get("origins")
    if not isinstance(origins, dict):
        raise ValueError("origins must label each confirmed field")
    required_origins = [
        *(f"persona.{field}" for field in REQUIRED_PERSONA),
        *(f"channel_facts.{field}" for field in REQUIRED_CHANNEL),
    ]
    required_origins.extend(
        f"persona.{field}"
        for field in ("age", "bio", "team", "interests")
        if persona.get(field)
    )
    if channel_facts.get("details"):
        required_origins.append("channel_facts.details")
    if data.get("current_context"):
        required_origins.append("current_context")
    for field in required_origins:
        if origins.get(field) not in ALLOWED_ORIGINS:
            raise ValueError(f"missing or invalid origin: {field}")
    if data.get("current_context") and not data.get("persist_current_context"):
        raise ValueError("current_context requires explicit persist_current_context")
    return data


def _optional_line(label: str, value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return f"- {label}: {value.strip()}"
    return None


def render_files(data: dict[str, Any]) -> dict[str, str]:
    channel = _require_text(data["channel"], "channel")
    persona = data["persona"]
    facts = data["channel_facts"]
    soul_lines = [
        "# Persona",
        "",
        f"- Nome: {persona['name']}",
        f"- Ruolo: {persona['role']}",
        f"- Tono: {persona['tone']}",
        f"- Lunghezza tipica: {persona['typical_message_length']}",
        f"- Limiti comportamentali: {persona['behavioral_limits']}",
    ]
    for label, field in (
        ("Età", "age"),
        ("Bio", "bio"),
        ("Squadra", "team"),
        ("Interessi", "interests"),
    ):
        line = _optional_line(label, persona.get(field))
        if line:
            soul_lines.append(line)
    soul_lines.extend(("", "## Tratti e opinioni", ""))
    soul_lines.extend(f"- {item.strip()}" for item in persona["traits_opinions"])

    fact_lines = [
        f"# Canale {facts['name']}",
        "",
        f"- Contenuto: {facts['content']}",
        f"- Relazione con la persona: {facts['relationship']}",
    ]
    details = facts.get("details")
    if isinstance(details, list) and details:
        fact_lines.extend(("", "## Dettagli confermati", ""))
        fact_lines.extend(f"- {_require_text(item, 'channel_facts.details')}" for item in details)
    context = data.get("current_context")
    if context:
        fact_lines.extend(("", "## Contesto corrente", "", _require_text(context, "current_context")))

    return {
        f".local/{channel}/soul.md": "\n".join(soul_lines).rstrip() + "\n",
        f".local/{channel}/facts/channel.md": "\n".join(fact_lines).rstrip() + "\n",
    }


def preview_digest(data: dict[str, Any], files: dict[str, str]) -> str:
    payload = json.dumps(
        {"files": files, "origins": data["origins"]},
        ensure_ascii=False,
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def preview(data: dict[str, Any], files: dict[str, str]) -> str:
    lines = ["# Origini confermate", ""]
    for field, origin in sorted(data["origins"].items()):
        lines.append(f"- `{field}`: `{origin}`")
    lines.extend(("", "# Markdown esatto", ""))
    for path, content in files.items():
        lines.extend((f"## `{path}`", "", "```markdown", content.rstrip(), "```", ""))
    lines.append(f"CONFIRM_DIGEST={preview_digest(data, files)}")
    return "\n".join(lines)


def apply_files(root: Path, files: dict[str, str], *, allow_update: bool) -> None:
    root = root.resolve()
    conflicts: list[str] = []
    for relative, content in files.items():
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"target escapes root: {relative}")
        if target.exists() and target.read_text(encoding="utf-8") != content:
            old = target.read_text(encoding="utf-8").splitlines(keepends=True)
            new = content.splitlines(keepends=True)
            print("".join(difflib.unified_diff(old, new, fromfile=str(target), tofile=relative)))
            conflicts.append(relative)
    if conflicts and not allow_update:
        joined = ", ".join(conflicts)
        raise ValueError(f"existing files differ; explicit --allow-update required: {joined}")
    for relative, content in files.items():
        target = (root / relative).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("answers", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--confirm-digest")
    parser.add_argument("--allow-update", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = load_answers(args.answers)
        files = render_files(data)
        rendered = preview(data, files)
        print(rendered)
        digest = preview_digest(data, files)
        if args.confirm_digest is None:
            print("NO_WRITE: confirm the exact preview digest to apply")
            return 0
        if args.confirm_digest != digest:
            raise ValueError("confirmation digest does not match exact preview")
        apply_files(args.root, files, allow_update=args.allow_update)
        channel = data["channel"]
        print(f"NEXT: minnarone validate-prompts --config .local/{channel}/config.yaml")
        print(f"NEXT: minnarone .local/{channel}/config.yaml --check")
        print("STOP: do not start or promote the runtime")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
