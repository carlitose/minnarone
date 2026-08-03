"""Committed YouTube operator surfaces stay sanitized and shadow-only."""

from pathlib import Path


def test_youtube_example_is_chat_only_shadow_and_contains_no_secret():
    text = Path("examples/youtube-chat-shadow.example.yaml").read_text()

    assert "adapter: youtube" in text
    assert "video_id: abcDEF123_-" in text
    assert "announce_ai: true" in text
    assert "YOUTUBE_API_KEY=" not in text
    assert "oauth" not in text.lower()
    assert "send:" not in text
    assert "audio:" not in text
    assert "video:" not in text


def test_youtube_operator_guide_documents_read_only_and_artifact_boundaries():
    text = Path("docs/youtube-operator.md").read_text()

    for required in (
        "YOUTUBE_API_KEY",
        "activeLiveChatId",
        "pollingIntervalMillis",
        "[SHADOW]",
        "--check",
        "retention.perceptions_days",
        "manual deletion",
        "does not authorize public send",
        "no OAuth",
        "no audio or video",
    ):
        assert required in text


def test_env_template_exposes_only_the_youtube_read_key():
    text = Path(".env.example").read_text()
    youtube_lines = [line for line in text.splitlines() if line.startswith("YOUTUBE_")]

    assert youtube_lines == ["YOUTUBE_API_KEY="]
