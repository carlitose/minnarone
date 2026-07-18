"""Read-only disposable runtime doctor for ticket 16."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Any

import yaml


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, relative: str) -> Path:
    root = root.resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"path escapes root: {relative}")
    return target


def _probe_endpoint(base_url: str, endpoint: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url}{endpoint}", timeout=1.0) as response:
            if response.status != 200:
                return False
            if endpoint == "/props":
                payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    return False
                modalities = payload.get("modalities")
                return isinstance(modalities, dict) and modalities.get("vision") is True
            return True
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _dotted(data: dict[str, Any], path: str) -> object:
    value: object = data
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def inspect(
    manifest: dict[str, Any],
    scenario: dict[str, Any],
    root: Path,
    *,
    probe_server: bool = False,
) -> dict[str, Any]:
    profile_name = scenario.get("profile")
    profiles = manifest.get("profiles", {})
    profile = profiles.get(profile_name) if isinstance(profiles, dict) else None
    if not isinstance(profile, dict):
        raise ValueError(f"unknown profile: {profile_name}")
    checks: list[dict[str, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    def skip(name: str, detail: str) -> None:
        checks.append({"name": name, "status": "SKIP", "detail": detail})

    config_relative = scenario.get("config_path")
    if not isinstance(config_relative, str) or not config_relative:
        raise ValueError("scenario.config_path is required")
    config_path = _inside(root, config_relative)
    if config_path.is_file():
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            raise ValueError("config must be a YAML object")
        record("config", True, str(config_path))
    else:
        config = {}
        record("config", False, f"missing {config_path}")

    twitch = config.get("twitch", {}) if isinstance(config, dict) else {}
    send = twitch.get("send", {}) if isinstance(twitch, dict) else {}
    actual_send_mode = send.get("mode") if isinstance(send, dict) else None
    disclosure = config.get("disclosure", {}) if isinstance(config, dict) else {}
    retention = config.get("retention", {}) if isinstance(config, dict) else {}
    speaker = config.get("speaker_embedding", {}) if isinstance(config, dict) else {}

    record("send_mode", actual_send_mode == "shadow", f"actual config mode={actual_send_mode!r}; must be shadow")
    record("shadow_write_token", scenario.get("shadow_requires_send_token") is not True, "shadow must not require send token")
    record("dedicated_bot", scenario.get("account_bot_dedicated") is True, "dedicated bot account required")
    record("broadcaster_consent", isinstance(scenario.get("broadcaster_consent"), bool), "consent decision must be recorded")
    record("disclosure", scenario.get("disclosure_choice") not in (None, "unset"), "operator choice must be explicit")
    record("disclosure_config", isinstance(disclosure, dict) and isinstance(disclosure.get("announce_ai"), bool), "announce_ai must be explicit even though ticket 18 tracks its runtime gap")
    record("retention", scenario.get("retention_ack") is True, "artifact/manual deletion acknowledgement required")
    record("retention_config", isinstance(retention, dict) and "perceptions_days" in retention, "inert field must be visible, not promised as enforced")
    record("python", sys.version_info >= (3, 11), sys.version.split()[0])
    record("uv", shutil.which("uv") is not None, shutil.which("uv") or "missing")

    for field, expected in profile.get("config_expectations", {}).items():
        actual = _dotted(config, field)
        record(f"config:{field}", actual == expected, f"actual={actual!r}, expected={expected!r}")

    min_free_bytes = profile.get("min_free_bytes", 0)
    free_bytes = shutil.disk_usage(root).free
    record("disk", isinstance(min_free_bytes, int) and free_bytes >= min_free_bytes, f"free={free_bytes}, required={min_free_bytes}")

    for tool in profile.get("tools", []):
        record(f"tool:{tool}", shutil.which(tool) is not None, "found on PATH" if shutil.which(tool) else "missing")

    for module in profile.get("modules", []):
        record(f"module:{module}", importlib.util.find_spec(module) is not None, "importable" if importlib.util.find_spec(module) else "missing extra")

    models = manifest.get("models", {})
    for model_name in profile.get("models", []):
        spec = models.get(model_name) if isinstance(models, dict) else None
        if not isinstance(spec, dict):
            record(f"model:{model_name}", False, "missing manifest entry")
            continue
        path = _inside(root, spec["path"])
        if not path.is_file():
            record(f"model:{model_name}", False, f"missing {path}")
            continue
        digest = _sha256(path)
        record(f"sha256:{model_name}", digest == spec["sha256"], digest)
        record(f"revision:{model_name}", isinstance(spec.get("revision"), str) and bool(spec["revision"]), str(spec.get("revision")))
        if "size" in spec:
            record(f"size:{model_name}", path.stat().st_size == spec["size"], str(path.stat().st_size))
        if "dimension" in spec:
            actual_dimension = speaker.get("dimension") if isinstance(speaker, dict) else None
            record(f"dimension:{model_name}", actual_dimension == spec["dimension"], str(actual_dimension))

    endpoints = profile.get("endpoints", [])
    base_url = scenario.get("llamacpp_base_url", "http://127.0.0.1:8080")
    for endpoint in endpoints:
        if probe_server:
            record(f"endpoint:{endpoint}", _probe_endpoint(str(base_url), endpoint), str(base_url))
        else:
            skip(f"endpoint:{endpoint}", "run again with --probe-server after explicit server start")

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {
        "profile": profile_name,
        "status": status,
        "checks": checks,
        "next_commands": [
            f"minnarone {config_relative} --check",
            f"minnarone {config_relative} --tui  # observe bounded shadow; never press p",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--probe-server", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = inspect(
            _read(args.manifest),
            _read(args.scenario),
            args.root,
            probe_server=args.probe_server,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "PASS" else 1
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "ERROR", "detail": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
