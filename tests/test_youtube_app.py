"""Production wiring for the YouTube chat-only shadow tracer bullet."""

from __future__ import annotations

import asyncio
import json
import textwrap

import pytest

from minnarone.app import build_agent
from minnarone.cli import main
from minnarone.config import Config, ConfigError
from minnarone.openrouter import HttpResponse
from minnarone.output_sink import MinnaroneOutputStream
from minnarone.youtube_chat import YouTubeApiError, YouTubeLiveChatReader
from minnarone.youtube_shadow import YouTubeShadowOutputRouter


class FakeYouTubeApi:
    def __init__(self) -> None:
        self.video_calls = 0
        self.chat_calls = 0

    async def get_video(self, *, video_id: str, api_key: str):
        del video_id, api_key
        self.video_calls += 1
        if self.video_calls == 1:
            return {
                "items": [
                    {
                        "liveStreamingDetails": {
                            "actualStartTime": "2026-08-03T10:00:00Z",
                            "activeLiveChatId": "synthetic-chat",
                        }
                    }
                ]
            }
        return {
            "items": [
                {
                    "liveStreamingDetails": {
                        "actualStartTime": "2026-08-03T10:00:00Z",
                        "actualEndTime": "2026-08-03T11:00:00Z",
                    }
                }
            ]
        }

    async def list_messages(self, **kwargs):
        del kwargs
        self.chat_calls += 1
        if self.chat_calls > 1:
            raise YouTubeApiError(status=403, reason="liveChatEnded")
        return {
            "nextPageToken": "next",
            "pollingIntervalMillis": 0,
            "items": [
                {
                    "id": "synthetic-message",
                    "snippet": {
                        "type": "textMessageEvent",
                        "publishedAt": "2026-08-03T10:01:00Z",
                        "authorChannelId": "synthetic-author",
                        "textMessageDetails": {"messageText": "minnarone, commenta"},
                    },
                    "authorDetails": {
                        "channelId": "synthetic-author",
                        "displayName": "Synthetic Viewer",
                    },
                }
            ],
        }


def _workspace(tmp_path):
    soul = tmp_path / "soul.md"
    soul.write_text("Sono Minnarone.", encoding="utf-8")
    facts = tmp_path / "facts"
    facts.mkdir()
    (facts / "channel.md").write_text("Canale sintetico.", encoding="utf-8")
    config = tmp_path / "youtube.yaml"
    config.write_text(
        textwrap.dedent(
            f"""
            mode: public
            soul_path: {soul}
            facts_dir: {facts}
            adapter: youtube
            llm_provider: grok
            agent_name: minnarone
            youtube:
              video_id: abcDEF123_-
            disclosure:
              announce_ai: true
            commentator:
              profiles:
                original_chat: {{}}
            """
        ),
        encoding="utf-8",
    )
    return config


def _llm_transport(*, url, headers, body, timeout):
    del url, headers, body, timeout
    payload = {"choices": [{"message": {"content": "RE: chat\nMSG: ciao"}}]}
    return HttpResponse(status=200, body=json.dumps(payload).encode())


def test_build_agent_constructs_read_only_youtube_shadow_without_sender(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    cfg = Config.load(_workspace(tmp_path))
    api = FakeYouTubeApi()

    agent = build_agent(cfg, transport=_llm_transport, youtube_api=api)

    assert isinstance(agent.adapter, YouTubeLiveChatReader)
    assert isinstance(agent.router, YouTubeShadowOutputRouter)
    assert agent.sender is None
    assert agent.token_guard is None
    assert api.video_calls == api.chat_calls == 0


def test_build_agent_fails_closed_when_read_key_is_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    cfg = Config.load(_workspace(tmp_path))

    with pytest.raises(ConfigError, match="YOUTUBE_API_KEY"):
        build_agent(cfg, transport=_llm_transport)


def test_youtube_chat_reaches_existing_perceiver_and_shadow_output(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-llm-key")
    cfg = Config.load(_workspace(tmp_path))
    agent = build_agent(
        cfg,
        transport=_llm_transport,
        youtube_api=FakeYouTubeApi(),
        store_path=tmp_path / "perceptions.jsonl",
    )

    asyncio.run(agent.run())

    assert agent.store.tail(1)[0].text == "minnarone, commenta"
    assert "[SHADOW] ciao" in capsys.readouterr().out
    assert agent.sender is None


def test_youtube_tui_marks_candidate_as_shadow_without_stdout(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-llm-key")
    cfg = Config.load(_workspace(tmp_path))
    agent = build_agent(
        cfg,
        transport=_llm_transport,
        youtube_api=FakeYouTubeApi(),
        store_path=tmp_path / "perceptions.jsonl",
        minnarone_output=MinnaroneOutputStream(),
    )

    asyncio.run(agent.run())

    assert "[SHADOW]" not in capsys.readouterr().out
    panels = {
        panel.title: panel.text
        for panel in agent.observability_snapshot().render_panels()
    }
    assert "[SHADOW] ciao" in panels["MINNARONE"]


def test_cli_check_is_offline_and_does_not_start_youtube_transport(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("YOUTUBE_API_KEY", "synthetic-read-key")
    monkeypatch.setattr(
        "minnarone.youtube_chat.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("--check must stay offline")
        ),
    )

    assert main([str(_workspace(tmp_path)), "--check"]) == 0
    assert "ok: agent" in capsys.readouterr().out
