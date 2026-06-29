import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from minnarone.fakes import FakeLLMProvider
from minnarone.llm import LLMError, LLMProvider
from minnarone.prompt_observation import (
    PROMPT_RECORD_MAX_BYTES,
    PROMPT_TRUNCATION_MARKER,
    ObservedLLMProvider,
    PromptObservation,
    PromptObservationRecorder,
    sanitize_metadata,
)
from minnarone.run_artifacts import create_run_session


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def __call__(self) -> datetime:
        current = self._now
        self._now = self._now + timedelta(milliseconds=25)
        return current


def test_observed_fake_llm_call_records_exact_prompt_and_success_metadata():
    started_at = datetime(2026, 6, 29, 10, 30, tzinfo=UTC)
    recorder = PromptObservationRecorder()
    llm = ObservedLLMProvider(
        FakeLLMProvider(message="ok"),
        recorder=recorder,
        model="fake-model",
        clock=FakeClock(started_at),
    )
    prompt = "## IDENTITA\nSono Minnarone.\n\n## SITUAZIONE\nchat: ciao"

    result = asyncio.run(llm.complete(prompt))

    observation = recorder.latest()
    assert result.message == "ok"
    assert observation is not None
    assert observation.prompt == prompt
    assert observation.model == "fake-model"
    assert observation.status == "success"
    assert observation.started_at == started_at
    assert observation.completed_at == started_at + timedelta(milliseconds=25)
    assert recorder.observations() == [observation]


def test_success_observation_includes_token_cache_and_cost_metadata():
    recorder = PromptObservationRecorder()
    llm = ObservedLLMProvider(
        FakeLLMProvider(
            message="ok",
            model="fake-request-model",
            meta={
                "model": "fake-response-model",
                "prompt_tokens": 100,
                "completion_tokens": 5,
                "total_tokens": 105,
                "cached_tokens": 80,
                "cache_write_tokens": 0,
                "cost": 0.0012,
                "provider": "fake",
            },
        ),
        recorder=recorder,
    )

    asyncio.run(llm.complete("prompt"))

    observation = recorder.latest()
    assert observation is not None
    assert observation.model == "fake-response-model"
    assert observation.token_metadata == {
        "prompt_tokens": 100,
        "completion_tokens": 5,
        "total_tokens": 105,
    }
    assert observation.cache_metadata == {
        "cached_tokens": 80,
        "cache_write_tokens": 0,
    }
    assert observation.cost == 0.0012
    assert observation.response_metadata["provider"] == "fake"


def test_success_observation_uses_total_cost_when_cost_is_none():
    recorder = PromptObservationRecorder()
    llm = ObservedLLMProvider(
        FakeLLMProvider(
            message="ok",
            meta={
                "cost": None,
                "total_cost": 0.12,
            },
        ),
        recorder=recorder,
    )

    asyncio.run(llm.complete("prompt"))

    observation = recorder.latest()
    assert observation is not None
    assert observation.cost == 0.12


class SecretFailingLLM(LLMProvider):
    model = "secret-failing-model"

    async def complete(self, prompt: str):
        del prompt
        raise LLMError(
            "Authorization: Bearer sk-or-error-secret "
            "oauth:badtoken \x00 raw_frame=b'\\x00\\x01\\x02\\x03\\x04\\x05\\x06\\x07'"
        )


def _observation(index: int) -> PromptObservation:
    started = datetime(2026, 6, 29, 10, 30, index, tzinfo=UTC)
    return PromptObservation(
        prompt=f"prompt-{index}",
        model="fake",
        status="success",
        started_at=started,
        completed_at=started + timedelta(milliseconds=1),
    )


def test_observation_redacts_secrets_and_binary_payloads_from_prompt_and_error():
    secret = "sk-or-v1-prompt-secret"
    recorder = PromptObservationRecorder()
    llm = ObservedLLMProvider(SecretFailingLLM(), recorder=recorder)
    prompt = (
        "## IDENTITA\n"
        f"OPENROUTER_API_KEY={secret}\n"
        "Authorization: Bearer twitch-secret-token\n"
        "oauth:chatsecret\n"
        "raw_audio=b'\\x00\\x01\\x02\\x03\\x04\\x05\\x06\\x07\\x08\\x09'\n"
        "normal instruction stays readable\x00\n"
    )

    with pytest.raises(LLMError):
        asyncio.run(llm.complete(prompt))

    observation = recorder.latest()
    assert observation is not None
    assert observation.status == "error"
    combined = f"{observation.prompt}\n{observation.error}"
    assert secret not in combined
    assert "twitch-secret-token" not in combined
    assert "chatsecret" not in combined
    assert "sk-or-error-secret" not in combined
    assert "\x00" not in combined
    assert "\\x01\\x02" not in combined
    assert "[redacted" in combined
    assert "## IDENTITA\n" in observation.prompt
    assert "normal instruction stays readable" in observation.prompt


def test_prompt_debug_record_is_saved_inside_current_run_debug_dir(tmp_path):
    session = create_run_session(root=tmp_path / "runs")
    recorder = PromptObservationRecorder(debug_dir=session.debug_dir)
    llm = ObservedLLMProvider(
        FakeLLMProvider(
            message="ok",
            meta={"prompt_tokens": 3, "cached_tokens": 1, "cost": 0.0001},
        ),
        recorder=recorder,
    )

    asyncio.run(llm.complete("## SITUAZIONE\nciao"))

    prompt_dir = session.debug_dir / "prompts"
    files = sorted(prompt_dir.glob("prompt-*.json"))
    assert len(files) == 1
    assert session.run_dir in files[0].parents
    assert files[0].parent == prompt_dir
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["prompt"] == "## SITUAZIONE\nciao"
    assert data["status"] == "success"
    assert data["token_metadata"] == {"prompt_tokens": 3}
    assert data["cache_metadata"] == {"cached_tokens": 1}
    assert data["cost"] == 0.0001


def test_prompt_capture_retains_only_latest_fifty_in_memory_and_on_disk(tmp_path):
    session = create_run_session(root=tmp_path / "runs")
    recorder = PromptObservationRecorder(debug_dir=session.debug_dir)

    for index in range(55):
        recorder.record(_observation(index))

    assert [obs.prompt for obs in recorder.observations()] == [
        f"prompt-{index}" for index in range(5, 55)
    ]
    files = sorted((session.debug_dir / "prompts").glob("prompt-*.json"))
    assert len(files) == 50
    assert json.loads(files[0].read_text(encoding="utf-8"))["prompt"] == "prompt-5"
    assert json.loads(files[-1].read_text(encoding="utf-8"))["prompt"] == "prompt-54"


def test_saved_prompt_record_is_capped_at_200kb_with_truncation_marker(tmp_path):
    session = create_run_session(root=tmp_path / "runs")
    recorder = PromptObservationRecorder(debug_dir=session.debug_dir)
    oversized = "A" * (PROMPT_RECORD_MAX_BYTES + 50_000)
    recorder.record(
        PromptObservation(
            prompt=oversized,
            model="fake",
            status="success",
            started_at=datetime(2026, 6, 29, 10, 30, tzinfo=UTC),
            completed_at=datetime(2026, 6, 29, 10, 30, 1, tzinfo=UTC),
        )
    )

    [path] = list((session.debug_dir / "prompts").glob("prompt-*.json"))
    content = path.read_bytes()
    data = json.loads(content.decode("utf-8"))

    assert len(content) <= PROMPT_RECORD_MAX_BYTES
    assert data["truncated"] is True
    assert PROMPT_TRUNCATION_MARKER in data["prompt"]


def test_recorder_redacts_manual_observations_before_retention_and_persistence(
    tmp_path,
):
    session = create_run_session(root=tmp_path / "runs")
    recorder = PromptObservationRecorder(debug_dir=session.debug_dir)
    recorder.record(
        PromptObservation(
            prompt="token=manual-secret\nraw_frame=b'\\x00\\x01\\x02\\x03\\x04\\x05'",
            model="fake",
            status="error",
            started_at=datetime(2026, 6, 29, 10, 30, tzinfo=UTC),
            completed_at=datetime(2026, 6, 29, 10, 30, 1, tzinfo=UTC),
            error="Bearer manual-error-secret",
        )
    )

    latest = recorder.latest()
    [path] = list((session.debug_dir / "prompts").glob("prompt-*.json"))
    saved = path.read_text(encoding="utf-8")
    combined = f"{latest.prompt}\n{latest.error}\n{saved}"

    assert "manual-secret" not in combined
    assert "manual-error-secret" not in combined
    assert "\\x01\\x02" not in combined
    assert "[redacted" in combined


def test_redaction_handles_quoted_and_non_bearer_secrets(tmp_path):
    session = create_run_session(root=tmp_path / "runs")
    recorder = PromptObservationRecorder(debug_dir=session.debug_dir)

    recorder.record(
        PromptObservation(
            prompt=(
                'password="correct horse battery staple"\n'
                "Authorization: Basic abc_def_123\n"
                "safe text"
            ),
            model="fake",
            status="success",
            started_at=datetime(2026, 6, 29, 10, 30, tzinfo=UTC),
            completed_at=datetime(2026, 6, 29, 10, 30, 1, tzinfo=UTC),
        )
    )

    latest = recorder.latest()
    [path] = list((session.debug_dir / "prompts").glob("prompt-*.json"))
    combined = f"{latest.prompt}\n{path.read_text(encoding='utf-8')}"

    assert "correct horse battery staple" not in combined
    assert "abc_def_123" not in combined
    assert "safe text" in combined


def test_metadata_keys_are_redacted_before_display_and_persistence(tmp_path):
    session = create_run_session(root=tmp_path / "runs")
    recorder = PromptObservationRecorder(debug_dir=session.debug_dir)

    recorder.record(
        PromptObservation(
            prompt="prompt",
            model="fake",
            status="success",
            started_at=datetime(2026, 6, 29, 10, 30, tzinfo=UTC),
            completed_at=datetime(2026, 6, 29, 10, 30, 1, tzinfo=UTC),
            response_metadata={"sk-or-key-in-key-name": "value"},
        )
    )

    latest = recorder.latest()
    [path] = list((session.debug_dir / "prompts").glob("prompt-*.json"))
    combined = f"{latest.response_metadata}\n{path.read_text(encoding='utf-8')}"

    assert "sk-or-key-in-key-name" not in combined
    assert "[redacted-openrouter-key]" in combined


@pytest.mark.parametrize(
    "key",
    [
        "access_token",
        "ACCESS-TOKEN",
        "refreshToken",
        "api_key",
        "x-api-key",
        "openrouter_api_key",
        "authorization",
        "Authorization",
        "password",
        "user-password",
        "secret",
        "secretToken",
        "apiSecret",
        "client_secret",
        "private_key",
        "cookie",
        "set-cookie",
        "csrf_token",
        "anthropic_token",
        "provider_token",
        "credential",
        "credentials",
        "request_header",
        "response_headers",
        "authorizationHeader",
        "signature",
        "x-signature",
    ],
)
def test_sanitize_metadata_redacts_secret_key_variants(key):
    sanitized = sanitize_metadata({key: "raw-secret-value"})

    assert list(sanitized.values()) == ["[redacted]"]


def test_sanitize_metadata_does_not_redact_usage_token_counters():
    sanitized = sanitize_metadata(
        {
            "prompt_tokens": 3,
            "completion_tokens": 4,
            "total_tokens": 7,
            "cached_tokens": 2,
            "cache_write_tokens": 1,
            "cache_read_tokens": 5,
        }
    )

    assert sanitized == {
        "prompt_tokens": 3,
        "completion_tokens": 4,
        "total_tokens": 7,
        "cached_tokens": 2,
        "cache_write_tokens": 1,
        "cache_read_tokens": 5,
    }


def test_sanitize_metadata_redacts_secret_keys_recursively():
    sanitized = sanitize_metadata(
        {
            "safe": {
                "access_token": "nested-secret",
                "secretToken": "nested-secret-token",
            },
            "headers": {
                "authorization": "nested-header-secret",
            },
            "items": [
                {"openrouter_api_key": "list-secret"},
                {"cookie": "list-cookie-secret"},
                {"safe": "visible"},
            ],
        }
    )

    assert sanitized == {
        "safe": {
            "access_token": "[redacted]",
            "secretToken": "[redacted]",
        },
        "headers": "[redacted]",
        "items": [
            {"openrouter_api_key": "[redacted]"},
            {"cookie": "[redacted]"},
            {"safe": "visible"},
        ],
    }


def test_oversized_non_prompt_fields_are_capped_without_raising(tmp_path):
    session = create_run_session(root=tmp_path / "runs")
    recorder = PromptObservationRecorder(debug_dir=session.debug_dir)
    huge = "E" * (PROMPT_RECORD_MAX_BYTES + 10_000)

    recorder.record(
        PromptObservation(
            prompt="short prompt",
            model=huge,
            status="error",
            started_at=datetime(2026, 6, 29, 10, 30, tzinfo=UTC),
            completed_at=datetime(2026, 6, 29, 10, 30, 1, tzinfo=UTC),
            context=huge,
            error=huge,
            response_metadata={"huge": huge},
        )
    )

    [path] = list((session.debug_dir / "prompts").glob("prompt-*.json"))
    data = json.loads(path.read_text(encoding="utf-8"))

    assert path.stat().st_size <= PROMPT_RECORD_MAX_BYTES
    assert data["truncated"] is True
