"""Fake-only contract tests for the YouTube Live chat insert boundary."""

from __future__ import annotations

import asyncio
import json

import pytest

from minnarone.output import OutputMode
from minnarone.public_router import PublicOutputRouter
from minnarone.public_send import PublicSendMode, PublicSendPolicy, PublicTarget
from minnarone.youtube_chat_sender import (
    YOUTUBE_LIVE_CHAT_MESSAGES_INSERT_URL,
    YouTubeChatInsertResponse,
    YouTubeLiveChatSender,
    YouTubeSendError,
)


def _secret(kind: str) -> str:
    return "-".join(("runtime", "only", kind, "value"))


class FakeInsert:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    async def __call__(self, **request):
        self.calls.append(request)
        result = self.responses.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def _sender(fake: FakeInsert) -> YouTubeLiveChatSender:
    return YouTubeLiveChatSender(
        live_chat_id=lambda: "synthetic-live-chat",
        access_token=lambda: _secret("access"),
        insert=fake,
    )


def test_sender_owns_the_exact_insert_request_and_returns_only_message_id():
    fake = FakeInsert(
        [
            YouTubeChatInsertResponse(
                status=200,
                body=json.dumps(
                    {
                        "id": "synthetic-message-id",
                        "snippet": {"displayMessage": "not propagated"},
                    }
                ).encode(),
            )
        ]
    )
    sender = _sender(fake)

    async def run() -> str:
        await sender.start()
        try:
            return await sender.send("ciao live")
        finally:
            await sender.stop()

    assert asyncio.run(run()) == "synthetic-message-id"
    assert len(fake.calls) == 1
    request = fake.calls[0]
    assert request["url"] == YOUTUBE_LIVE_CHAT_MESSAGES_INSERT_URL
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["headers"]["Authorization"] == f"Bearer {_secret('access')}"
    assert json.loads(request["body"]) == {
        "snippet": {
            "liveChatId": "synthetic-live-chat",
            "type": "textMessageEvent",
            "textMessageDetails": {"messageText": "ciao live"},
        }
    }


@pytest.mark.parametrize(
    ("status", "provider_reason", "reason", "disarms_live"),
    [
        (401, "authError", "auth_revoked", True),
        (403, "forbidden", "forbidden", True),
        (403, "liveChatDisabled", "live_chat_disabled", False),
        (403, "liveChatEnded", "live_chat_ended", False),
        (400, "messageTextInvalid", "message_text_invalid", False),
        (404, "liveChatNotFound", "live_chat_not_found", False),
        (403, "rateLimitExceeded", "rate_limited", False),
        (403, "quotaExceeded", "quota_exhausted", False),
        (503, "backendError", "temporary_failure", False),
    ],
)
def test_provider_failures_have_closed_sanitized_reason_codes(
    status, provider_reason, reason, disarms_live
):
    body = json.dumps(
        {
            "error": {
                "message": _secret("provider-payload"),
                "errors": [{"reason": provider_reason}],
            }
        }
    ).encode()
    fake = FakeInsert([YouTubeChatInsertResponse(status=status, body=body)])
    sender = _sender(fake)

    with pytest.raises(YouTubeSendError) as raised:
        asyncio.run(sender.send("candidate"))

    assert raised.value.reason == reason
    assert raised.value.disarms_live is disarms_live
    assert _secret("access") not in str(raised.value)
    assert _secret("provider-payload") not in str(raised.value)
    assert raised.value.__cause__ is None
    assert len(fake.calls) == 1


def test_transport_failure_is_single_attempt_and_has_no_sensitive_exception_chain():
    fake = FakeInsert([OSError(_secret("socket-payload"))])
    sender = _sender(fake)

    with pytest.raises(YouTubeSendError) as raised:
        asyncio.run(sender.send("candidate"))

    assert raised.value.reason == "temporary_failure"
    assert raised.value.__cause__ is None
    assert _secret("socket-payload") not in str(raised.value)
    assert len(fake.calls) == 1


def test_typed_error_rejects_an_untrusted_reason_payload():
    error = YouTubeSendError(_secret("untrusted-reason"))

    assert error.reason == "provider_rejected"
    assert _secret("untrusted-reason") not in str(error)


class _LiveConfig:
    mode = PublicSendMode.LIVE
    allowed_targets = (PublicTarget("youtube", "abcDEF123_-"),)
    max_per_minute = 10
    max_per_hour = 10
    failure_threshold = 3


def test_auth_failure_permanently_disarms_policy_and_records_only_safe_reason(tmp_path):
    from minnarone.run_events import RunEventRecorder

    fake = FakeInsert(
        [
            YouTubeChatInsertResponse(
                status=401,
                body=json.dumps(
                    {"error": {"message": _secret("response"), "errors": []}}
                ).encode(),
            )
        ]
    )
    policy = PublicSendPolicy(_LiveConfig(), clock=lambda: 0.0)
    assert policy.promote() is True
    recorder = RunEventRecorder(tmp_path)
    router = PublicOutputRouter(
        policy=policy,
        target=PublicTarget("youtube", "abcDEF123_-"),
        sender=_sender(fake),
        event_recorder=recorder,
    )

    asyncio.run(router.route("candidate", OutputMode.PUBLIC))

    assert policy.promote() is False
    event_text = recorder.path.read_text(encoding="utf-8")
    assert "auth_revoked" in event_text
    assert "failure_threshold_reached" not in event_text
    assert _secret("access") not in event_text
    assert _secret("response") not in event_text
    assert len(fake.calls) == 1
