"""Normalizer for original-chat reaction LLM output."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .human import END_CONV_SENTINEL

_LABEL_RE = re.compile(
    r"^\s*(re|msg)\b(?:\s*:\s*|\s*-\s+|\s+)(.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class OriginalChatResponse:
    """Canonical local representation of one original-chat LLM response."""

    reason: str
    message: str
    end_conversation: bool
    raw_text: str
    display_text: str


def normalize_original_chat_response(raw_text: str) -> OriginalChatResponse:
    """Parse original-chat `RE`/`MSG` output into canonical display text."""
    reason = ""
    message = ""
    seen_label = False
    raw_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    unlabeled_after_label: list[str] = []
    for line in raw_text.splitlines():
        match = _LABEL_RE.match(line)
        if match is None:
            if seen_label and line.strip():
                unlabeled_after_label.append(line.strip())
            continue
        seen_label = True
        label = match.group(1).lower()
        value = match.group(2).strip()
        if label == "re":
            reason = value
        elif label == "msg":
            message = value
    if not message:
        message = "\n".join(unlabeled_after_label)
    if not message and not seen_label:
        message = "\n".join(raw_lines)

    return OriginalChatResponse(
        reason=reason,
        message=message,
        end_conversation=message == END_CONV_SENTINEL,
        raw_text=raw_text,
        display_text=f"RE: {reason}\nMSG: {message}",
    )
