from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import compare
import doctor
import onboarding

from minnarone.config import TwitchSendConfig, TwitchSendMode
from minnarone.public_send import ACTION_SHADOW, PublicSendPolicy

HERE = Path(__file__).parent


class OnboardingPrototypeTest(unittest.TestCase):
    def test_preview_is_no_write(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            output = StringIO()
            with redirect_stdout(output):
                status = onboarding.main([str(HERE / "fixtures/answers.json"), "--root", str(root)])
            self.assertEqual(status, 0)
            self.assertIn("NO_WRITE", output.getvalue())
            self.assertFalse((root / ".local").exists())

    def test_exact_digest_applies_confirmed_markdown(self) -> None:
        data = onboarding.load_answers(HERE / "fixtures/answers.json")
        files = onboarding.render_files(data)
        digest = onboarding.preview_digest(data, files)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            status = onboarding.main([
                str(HERE / "fixtures/answers.json"),
                "--root", str(root),
                "--confirm-digest", digest,
            ])
            self.assertEqual(status, 0)
            self.assertEqual(
                (root / ".local/examplechannel/soul.md").read_text(encoding="utf-8"),
                files[".local/examplechannel/soul.md"],
            )

    def test_missing_required_question_fails_before_write(self) -> None:
        data = json.loads((HERE / "fixtures/answers.json").read_text(encoding="utf-8"))
        del data["persona"]["tone"]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            answers = root / "answers.json"
            answers.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(onboarding.main([str(answers), "--root", str(root)]), 2)
            self.assertFalse((root / ".local").exists())

    def test_confirmation_digest_binds_origin_labels(self) -> None:
        data = onboarding.load_answers(HERE / "fixtures/answers.json")
        files = onboarding.render_files(data)
        original = onboarding.preview_digest(data, files)
        data["origins"]["persona.name"] = "confirmed_inference"
        self.assertNotEqual(onboarding.preview_digest(data, files), original)

    def test_channel_path_traversal_is_rejected_before_write(self) -> None:
        data = json.loads((HERE / "fixtures/answers.json").read_text(encoding="utf-8"))
        data["channel"] = "../../escaped"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            answers = root / "answers.json"
            answers.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(onboarding.main([str(answers), "--root", str(root)]), 2)
            self.assertFalse((root.parent / "escaped").exists())

    def test_existing_file_requires_update_flag(self) -> None:
        data = onboarding.load_answers(HERE / "fixtures/answers.json")
        files = onboarding.render_files(data)
        digest = onboarding.preview_digest(data, files)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            soul = root / ".local/examplechannel/soul.md"
            soul.parent.mkdir(parents=True)
            soul.write_text("user-owned\n", encoding="utf-8")
            status = onboarding.main([
                str(HERE / "fixtures/answers.json"), "--root", str(root),
                "--confirm-digest", digest,
            ])
            self.assertEqual(status, 2)
            self.assertEqual(soul.read_text(encoding="utf-8"), "user-owned\n")

    def test_confirmed_fixture_passes_real_cli_check(self) -> None:
        data = onboarding.load_answers(HERE / "fixtures/answers.json")
        files = onboarding.render_files(data)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            onboarding.apply_files(root, files, allow_update=False)
            config_dir = root / ".local/examplechannel"
            shutil.copy(HERE / "fixtures/shadow.yaml", config_dir / "config.yaml")
            result = subprocess.run(
                ["uv", "run", "minnarone", str(config_dir / "config.yaml"), "--check"],
                cwd=HERE.parents[1],
                env={
                    **os.environ,
                    "OPENROUTER_API_KEY": "dry_run",
                    "TWITCH_BOT_USERNAME": "dry_run",
                    "TWITCH_OAUTH_TOKEN": "oauth:dry_run",
                },
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class DoctorPrototypeTest(unittest.TestCase):
    @staticmethod
    def _scenario(profile: str) -> dict[str, object]:
        return {
            "profile": profile,
            "config_path": "config.yaml",
            "shadow_requires_send_token": False,
            "account_bot_dedicated": True,
            "broadcaster_consent": True,
            "disclosure_choice": "profile",
            "retention_ack": True,
        }

    @staticmethod
    def _write_config(
        root: Path,
        *,
        profile: str = "P0",
        mode: str = "shadow",
        dimension: int = 512,
    ) -> None:
        audio = profile in {"P2", "P5"}
        video = profile == "P5"
        provider = "llamacpp" if profile == "P5" else "grok"
        vlm = "\nvlm:\n  backend: llamacpp\n" if profile == "P5" else ""
        (root / "config.yaml").write_text(
            f"""mode: public
llm_provider: {provider}
twitch:
  chat: true
  audio: {str(audio).lower()}
  video: {str(video).lower()}
  send:
    mode: {mode}
speaker_embedding:
  dimension: {dimension}
disclosure:
  announce_ai: false
retention:
  perceptions_days: 7
{vlm}
""",
            encoding="utf-8",
        )

    def test_p0_passes_safety_checks_without_models(self) -> None:
        manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
        scenario = json.loads((HERE / "fixtures/scenario-p0.json").read_text(encoding="utf-8"))
        report = doctor.inspect(manifest, scenario, HERE.parents[1])
        self.assertEqual(report["status"], "PASS")

    def test_missing_config_never_passes(self) -> None:
        manifest = {"models": {}, "profiles": {"P0": {"tools": [], "models": []}}}
        with tempfile.TemporaryDirectory() as raw:
            report = doctor.inspect(manifest, self._scenario("P0"), Path(raw))
        self.assertEqual(report["status"], "FAIL")

    def test_p2_rejects_speaker_192_dimension(self) -> None:
        payload = b"speaker"
        digest = hashlib.sha256(payload).hexdigest()
        manifest = {
            "models": {"speaker": {"path": "speaker.onnx", "revision": "v1", "sha256": digest, "dimension": 512}},
            "profiles": {"P2": {"tools": [], "modules": [], "models": ["speaker"], "min_free_bytes": 0}},
        }
        scenario = self._scenario("P2")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "speaker.onnx").write_bytes(payload)
            self._write_config(root, profile="P2", dimension=192)
            report = doctor.inspect(manifest, scenario, root)
        self.assertEqual(report["status"], "FAIL")
        self.assertIn("dimension:speaker", {item["name"] for item in report["checks"] if item["status"] == "FAIL"})

    def test_p2_accepts_pinned_512_model_and_required_tool(self) -> None:
        payload = b"speaker"
        manifest = {
            "models": {"speaker": {"path": "speaker.onnx", "revision": "v1", "sha256": hashlib.sha256(payload).hexdigest(), "dimension": 512}},
            "profiles": {"P2": {"tools": ["streamlink"], "modules": [], "models": ["speaker"], "min_free_bytes": 0}},
        }
        scenario = self._scenario("P2")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "speaker.onnx").write_bytes(payload)
            self._write_config(root, profile="P2")
            tool = root / "streamlink"
            tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            tool.chmod(0o755)
            with patch.dict(os.environ, {"PATH": f"{root}{os.pathsep}{os.environ['PATH']}"}):
                report = doctor.inspect(manifest, scenario, root)
        self.assertEqual(report["status"], "PASS")

    def test_p5_accepts_pinned_gguf_and_mmproj(self) -> None:
        files = {"model.gguf": b"gguf", "mmproj.gguf": b"vision"}
        manifest = {
            "models": {
                name: {"path": name, "revision": "pinned", "sha256": hashlib.sha256(payload).hexdigest()}
                for name, payload in files.items()
            },
            "profiles": {"P5": {"tools": ["llama-server"], "modules": [], "models": list(files), "min_free_bytes": 0, "endpoints": ["/health", "/props"], "config_expectations": {"llm_provider": "llamacpp", "twitch.audio": True, "twitch.video": True, "vlm.backend": "llamacpp"}}},
        }
        scenario = self._scenario("P5")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name, payload in files.items():
                (root / name).write_bytes(payload)
            self._write_config(root, profile="P5")
            tool = root / "llama-server"
            tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            tool.chmod(0o755)
            with patch.dict(os.environ, {"PATH": f"{root}{os.pathsep}{os.environ['PATH']}"}), patch.object(doctor, "_probe_endpoint", return_value=True):
                report = doctor.inspect(manifest, scenario, root, probe_server=True)
        self.assertEqual(report["status"], "PASS")

    def test_p5_rejects_non_llamacpp_config(self) -> None:
        manifest = {
            "models": {},
            "profiles": {"P5": {
                "tools": [], "modules": [], "models": [],
                "config_expectations": {
                    "llm_provider": "llamacpp",
                    "twitch.audio": True,
                    "twitch.video": True,
                    "vlm.backend": "llamacpp",
                },
            }},
        }
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._write_config(root, profile="P0")
            report = doctor.inspect(manifest, self._scenario("P5"), root)
        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(item["name"] == "config:vlm.backend" for item in report["checks"]))

    def test_props_requires_vision_modality(self) -> None:
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            @staticmethod
            def read() -> bytes:
                return b'{"modalities":{"vision":false}}'

        with patch.object(doctor.urllib.request, "urlopen", return_value=Response()):
            self.assertFalse(doctor._probe_endpoint("http://127.0.0.1:8080", "/props"))

    def test_props_rejects_valid_json_with_wrong_shape(self) -> None:
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            @staticmethod
            def read() -> bytes:
                return b"[]"

        with patch.object(doctor.urllib.request, "urlopen", return_value=Response()):
            self.assertFalse(doctor._probe_endpoint("http://127.0.0.1:8080", "/props"))

    def test_live_mode_is_never_accepted(self) -> None:
        manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
        scenario = self._scenario("P0")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._write_config(root, mode="live")
            report = doctor.inspect(manifest, scenario, root)
        self.assertEqual(report["status"], "FAIL")

    def test_offline_shadow_gate_never_sends(self) -> None:
        policy = PublicSendPolicy(
            TwitchSendConfig(mode=TwitchSendMode.SHADOW),
            clock=lambda: 0.0,
        )
        decision = policy.decide("prototype message", "examplechannel")
        self.assertEqual(decision.action, ACTION_SHADOW)
        self.assertFalse(policy.promote())


class SurfaceComparisonTest(unittest.TestCase):
    def test_selected_surface_catches_all_seeded_errors_with_low_duplication(self) -> None:
        result = compare.summarize(HERE / "comparison.json")
        selected = result["surfaces"][result["choice"]]
        self.assertEqual(selected["errors_avoided"], 10)
        self.assertEqual(selected["errors_missed"], [])
        self.assertLess(selected["estimated_duplicated_rules"], 2)

    def test_skill_names_and_prompt_boundary_match_catalog(self) -> None:
        onboarding_skill = (HERE / "skills/minnarone-twitch-onboarding/SKILL.md").read_text(encoding="utf-8")
        doctor_skill = (HERE / "skills/minnarone-runtime-doctor/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("name: minnarone-twitch-onboarding", onboarding_skill)
        self.assertIn("name: minnarone-runtime-doctor", doctor_skill)
        self.assertIn("minnarone-prompts", onboarding_skill)


if __name__ == "__main__":
    unittest.main()
