"""Committed YouTube operator surfaces stay sanitized and sender-free."""

from pathlib import Path


def test_youtube_example_is_chat_only_shadow_and_contains_no_secret():
    text = Path("examples/youtube-chat-shadow.example.yaml").read_text()

    assert "adapter: youtube" in text
    assert "video_id: abcDEF123_-" in text
    assert "announce_ai: true" in text
    assert "YOUTUBE_API_KEY=" not in text
    assert "oauth_token" not in text.lower()
    assert "send:" in text
    assert "mode: shadow" in text
    assert "allowed_video_ids: []" in text
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
        "no sender capability",
        "allowed_video_ids",
        "mode_off",
    ):
        assert required in text


def test_youtube_full_shadow_example_reuses_top_level_os_capture_without_sender():
    text = Path("examples/youtube-full-shadow.example.yaml").read_text()

    for required in (
        "adapter: youtube",
        "video_id: abcDEF123_-",
        "os_capture:",
        "audio: true",
        "video: true",
        "monitor: 1",
        "mode: public",
        "announce_ai: true",
    ):
        assert required in text
    for forbidden in ("YOUTUBE_API_KEY=", "oauth", "send:", "streamlink", "yt-dlp"):
        assert forbidden not in text.lower()


def test_youtube_operator_guide_documents_bounded_chrome_os_capture_flow():
    text = Path("docs/youtube-operator.md").read_text()

    for required in (
        "visible Chrome",
        "operator-managed",
        "minnarone-oscapture-smoke",
        "--duration 30",
        "--max-audio-samples 3",
        "--max-video-frames 3",
        "Screen Recording",
        "BlackHole",
        "dedicated monitor",
        "full-monitor",
        "frame neri",
        "silenzio",
        "no LLM",
        "no sender",
        "Ctrl-C",
    ):
        assert required in text


def test_env_template_exposes_only_the_youtube_read_key():
    text = Path(".env.example").read_text()
    youtube_lines = [line for line in text.splitlines() if line.startswith("YOUTUBE_")]

    assert youtube_lines == ["YOUTUBE_API_KEY="]
