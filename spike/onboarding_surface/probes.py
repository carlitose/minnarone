"""Executable hazard probes used by the surface comparison."""

from __future__ import annotations

import hashlib
import json
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import doctor
import onboarding

from minnarone.config import TwitchSendConfig, TwitchSendMode
from minnarone.public_send import ACTION_SHADOW, PublicSendPolicy

HERE = Path(__file__).parent
TRAPS = (
    "persona_invented",
    "write_before_confirmation",
    "current_context_persisted_silently",
    "shadow_write_token_claim",
    "automatic_live_promotion",
    "missing_broadcaster_consent",
    "retention_field_treated_as_active",
    "speaker_zh_cn_192_for_italian",
    "model_revision_or_digest_missing",
    "check_treated_as_vlm_load",
)


def _answers() -> dict[str, object]:
    return json.loads((HERE / "fixtures/answers.json").read_text(encoding="utf-8"))


def _config(root: Path, *, dimension: int = 512) -> None:
    (root / "config.yaml").write_text(
        f"""mode: public
twitch:
  send:
    mode: shadow
speaker_embedding:
  dimension: {dimension}
disclosure:
  announce_ai: false
retention:
  perceptions_days: 7
""",
        encoding="utf-8",
    )


def _scenario() -> dict[str, object]:
    return {
        "profile": "P0",
        "config_path": "config.yaml",
        "shadow_requires_send_token": False,
        "account_bot_dedicated": True,
        "broadcaster_consent": True,
        "disclosure_choice": "profile",
        "retention_ack": True,
    }


def _failed(report: dict[str, object], check: str) -> bool:
    return any(item["name"] == check and item["status"] == "FAIL" for item in report["checks"])


def run_enforced_probes() -> dict[str, bool]:
    results: dict[str, bool] = {}

    data = _answers()
    del data["persona"]["tone"]
    try:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "answers.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            onboarding.load_answers(path)
        results["persona_invented"] = False
    except ValueError:
        results["persona_invented"] = True

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        with redirect_stdout(StringIO()):
            status = onboarding.main([str(HERE / "fixtures/answers.json"), "--root", str(root)])
        results["write_before_confirmation"] = status == 0 and not (root / ".local").exists()

    data = _answers()
    data["current_context"] = "one match only"
    data["origins"]["current_context"] = "operator"
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "answers.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        try:
            onboarding.load_answers(path)
            results["current_context_persisted_silently"] = False
        except ValueError:
            results["current_context_persisted_silently"] = True

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        _config(root)
        manifest = {"models": {}, "profiles": {"P0": {"tools": [], "modules": [], "models": []}}}
        scenario = _scenario()
        scenario["shadow_requires_send_token"] = True
        results["shadow_write_token_claim"] = _failed(doctor.inspect(manifest, scenario, root), "shadow_write_token")

        scenario = _scenario()
        del scenario["broadcaster_consent"]
        results["missing_broadcaster_consent"] = _failed(doctor.inspect(manifest, scenario, root), "broadcaster_consent")

        scenario = _scenario()
        scenario["retention_ack"] = False
        results["retention_field_treated_as_active"] = _failed(doctor.inspect(manifest, scenario, root), "retention")

    policy = PublicSendPolicy(TwitchSendConfig(mode=TwitchSendMode.SHADOW), clock=lambda: 0.0)
    results["automatic_live_promotion"] = (
        policy.decide("candidate", "examplechannel").action == ACTION_SHADOW
        and policy.promote() is False
    )

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        payload = b"speaker"
        (root / "speaker.onnx").write_bytes(payload)
        _config(root, dimension=192)
        manifest = {
            "models": {"speaker": {"path": "speaker.onnx", "revision": "v1", "sha256": hashlib.sha256(payload).hexdigest(), "dimension": 512}},
            "profiles": {"P2": {"tools": [], "modules": [], "models": ["speaker"]}},
        }
        scenario = _scenario()
        scenario["profile"] = "P2"
        results["speaker_zh_cn_192_for_italian"] = _failed(doctor.inspect(manifest, scenario, root), "dimension:speaker")

        manifest["models"]["speaker"]["sha256"] = "0" * 64
        results["model_revision_or_digest_missing"] = _failed(doctor.inspect(manifest, scenario, root), "sha256:speaker")

        manifest["profiles"]["P2"]["endpoints"] = ["/props"]
        report = doctor.inspect(manifest, scenario, root)
        results["check_treated_as_vlm_load"] = any(
            item["name"] == "endpoint:/props" and item["status"] == "SKIP"
            for item in report["checks"]
        )

    return results


def run_tutorial_probes() -> dict[str, bool]:
    text = (HERE / "tutorial.md").read_text(encoding="utf-8")
    needles = {
        "automatic_live_promotion": "send.mode: shadow",
        "missing_broadcaster_consent": "broadcaster consent",
        "speaker_zh_cn_192_for_italian": "dimension 512",
        "model_revision_or_digest_missing": "SHA-256/revision",
        "check_treated_as_vlm_load": "lazy VLM",
    }
    return {trap: needles.get(trap, "") in text if trap in needles else False for trap in TRAPS}
