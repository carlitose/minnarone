"""Public onboarding and repository-local skill contracts."""

import json
import re
import subprocess
from html import unescape
from pathlib import Path
from urllib.parse import unquote

import yaml

from minnarone.config import Config

ROOT = Path(__file__).resolve().parents[1]
README_PATHS = (ROOT / "README.md", ROOT / "README.it.md")
SKILL_NAMES = (
    "minnarone-prompts",
    "minnarone-twitch-onboarding",
    "minnarone-runtime-doctor",
)
RELEASE_FILES = {
    ".agents/skills/minnarone-runtime-doctor/SKILL.md",
    ".agents/skills/minnarone-runtime-doctor/agents/openai.yaml",
    ".agents/skills/minnarone-twitch-onboarding/SKILL.md",
    ".agents/skills/minnarone-twitch-onboarding/agents/openai.yaml",
    ".claude/skills/minnarone-runtime-doctor",
    ".claude/skills/minnarone-twitch-onboarding",
    ".gitignore",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "README.it.md",
    "README.md",
    "docs/runtime-model-manifest.json",
    "examples/onboarding/facts/channel.md",
    "examples/onboarding/soul.md",
    "examples/onboarding/twitch-chat-shadow.it.yaml",
    "examples/onboarding/twitch-full-shadow.it.yaml",
    "tests/test_public_onboarding_contract.py",
}


def test_readmes_start_with_task_first_quickstarts():
    for path in README_PATHS:
        text = path.read_text(encoding="utf-8")
        quickstart = (
            text.index("## Quickstart")
            if path.name == "README.md"
            else text.index("## Avvio rapido")
        )
        origin = (
            text.index("## Origin")
            if path.name == "README.md"
            else text.index("## Origine")
        )
        assert quickstart < origin


def test_readmes_explain_inputs_and_catalog_every_public_skill():
    for path in README_PATHS:
        text = path.read_text(encoding="utf-8")
        for concept in (
            ("configuration", "soul", "facts", "prompt")
            if path.name == "README.md"
            else ("configurazione", "soul", "facts", "prompt")
        ):
            assert concept in text.lower()
        for name in SKILL_NAMES:
            assert f".agents/skills/{name}/SKILL.md" in text
        for field in (
            ("Trigger", "Actions", "Boundary")
            if path.name == "README.md"
            else ("Trigger", "Azioni", "Confine")
        ):
            assert field in text


def test_readmes_cover_progressive_paths_and_public_safety_contract():
    required = (
        "chat-only shadow",
        "media smoke",
        "full multimodal",
        "attended live",
        "broadcaster consent",
        "dedicated bot account",
        "token validation",
        "disclosure",
        "Chat Bot Badge",
        "Twitch limits",
        "Minnarone budgets",
        "perceptions.jsonl",
        "manual deletion",
        "opt-out",
        "press `p` twice",
        "press `k`",
    )
    italian_required = (
        "shadow solo chat",
        "smoke media",
        "multimodale completo",
        "live presidiato",
        "consenso del broadcaster",
        "account bot dedicato",
        "validazione dei token",
        "disclosure",
        "Chat Bot Badge",
        "limiti Twitch",
        "budget Minnarone",
        "perceptions.jsonl",
        "cancellazione manuale",
        "opt-out",
        "premi `p` due volte",
        "premi `k`",
    )
    for path, phrases in zip(README_PATHS, (required, italian_required), strict=True):
        text = " ".join(path.read_text(encoding="utf-8").split())
        for phrase in phrases:
            assert phrase.lower() in text.lower()


def test_public_onboarding_examples_are_sanitized_shadow_configs():
    paths = (
        ROOT / "examples/onboarding/twitch-chat-shadow.it.yaml",
        ROOT / "examples/onboarding/twitch-full-shadow.it.yaml",
    )
    for path in paths:
        cfg = Config.load(path)
        text = path.read_text(encoding="utf-8")
        assert cfg.twitch is not None
        assert cfg.twitch.channel == "examplechannel"
        assert cfg.twitch.send.mode.value == "shadow"
        assert cfg.commentator.language == "it"
        assert "oauth:" not in text.lower()
        assert "/Users/" not in text
        assert "3dspeaker_speech_campplus_sv_zh-cn" not in text

    full = Config.load(paths[1])
    assert full.speaker_embedding.dimension == 512
    assert full.speaker_clustering.threshold == 0.5
    assert "3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx" in paths[1].read_text(
        encoding="utf-8"
    )


def test_full_shadow_example_is_p3_mps_only_and_other_profiles_require_adaptation():
    example = (ROOT / "examples/onboarding/twitch-full-shadow.it.yaml").read_text(
        encoding="utf-8"
    )
    assert "Golden path P3: Apple Silicon" in example
    assert "Golden path P3/P4" not in example

    english = " ".join(README_PATHS[0].read_text(encoding="utf-8").split())
    italian = " ".join(README_PATHS[1].read_text(encoding="utf-8").split())
    assert "P3-only MPS example" in english
    assert "P4 CUDA and P5 llama.cpp" in english
    assert "do not run it unchanged" in english
    assert "esempio MPS solo P3" in italian
    assert "P4 CUDA e P5 llama.cpp" in italian
    assert "non usarlo senza modifiche" in italian


def test_public_skills_have_valid_discovery_metadata_and_relative_claude_links():
    for name in SKILL_NAMES[1:]:
        skill_dir = ROOT / ".agents/skills" / name
        skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        metadata = yaml.safe_load(
            (skill_dir / "agents/openai.yaml").read_text(encoding="utf-8")
        )
        claude_link = ROOT / ".claude/skills" / name

        assert skill_text.startswith(f"---\nname: {name}\n")
        assert f"${name}" in metadata["interface"]["default_prompt"]
        if claude_link.is_symlink():
            assert not claude_link.readlink().is_absolute()
            assert _is_valid_claude_skill_alias(claude_link, skill_dir)
        else:
            assert claude_link.is_file()
            assert not _is_valid_claude_skill_alias(claude_link, skill_dir)


def test_plain_file_symlink_checkout_is_not_a_valid_claude_skill_alias(tmp_path):
    canonical = tmp_path / ".agents/skills/example"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text("canonical", encoding="utf-8")
    alias = tmp_path / ".claude/skills/example"
    alias.parent.mkdir(parents=True)
    alias.write_text("../../.agents/skills/example", encoding="utf-8")

    assert not _is_valid_claude_skill_alias(alias, canonical)


def test_public_skill_carveouts_are_versionable_without_unignoring_local_skills():
    public_files = [f".agents/skills/{name}/SKILL.md" for name in SKILL_NAMES]
    public_results = [
        subprocess.run(
            ["git", "check-ignore", "--quiet", path],
            cwd=ROOT,
            check=False,
        )
        for path in public_files
    ]
    private = subprocess.run(
        ["git", "check-ignore", "--quiet", ".agents/skills/local-only/SKILL.md"],
        cwd=ROOT,
        check=False,
    )
    assert all(result.returncode == 1 for result in public_results)
    assert private.returncode == 0


def test_all_release_files_are_visible_to_git_without_staging():
    visible = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\0")
    assert RELEASE_FILES <= set(visible)


def test_onboarding_skill_uses_the_validate_prompts_subcommand_contract():
    text = (ROOT / ".agents/skills/minnarone-twitch-onboarding/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "uv run python -m minnarone validate-prompts --config <config-path>" in text
    assert "uv run python -m minnarone <config-path> validate-prompts" not in text


def test_runtime_manifest_covers_every_profile_and_public_speaker_contract():
    manifest = json.loads(
        (ROOT / "docs/runtime-model-manifest.json").read_text(encoding="utf-8")
    )
    assert set(manifest["profiles"]) == {f"P{i}" for i in range(6)}
    speaker = manifest["artifacts"]["speaker-voxceleb-campp-512"]
    assert speaker["embedding_dimension"] == 512
    assert len(speaker["sha256"]) == 64
    for artifact in manifest["artifacts"].values():
        assert len(artifact["sha256"]) == 64
    runtime = manifest["runtimes"]["llama-cpp-b10016"]
    assert runtime["revision"].startswith("b10016")
    assert len(runtime["verified_asset"]["sha256"]) == 64


def test_runtime_manifest_requires_complete_loadable_bundles_not_weight_hashes():
    manifest = json.loads(
        (ROOT / "docs/runtime-model-manifest.json").read_text(encoding="utf-8")
    )
    assert set(manifest["policy"]["model_readiness_pass_requires"]) == {
        "all_required_bundle_files_present",
        "all_required_bundle_files_authenticated_at_pinned_source",
        "all_published_digests_match",
        "profile_specific_local_loader_smoke_passed",
    }

    bundles = manifest["bundles"]
    artifacts = manifest["artifacts"]
    referenced_artifacts: set[str] = set()
    for bundle in bundles.values():
        assert bundle["source"]["owner"]
        assert bundle["source"]["revision"]
        artifact_refs = set(bundle["artifacts"])
        assert artifact_refs <= artifacts.keys()
        referenced_artifacts.update(artifact_refs)
        required_files = bundle["required_files"]
        assert required_files
        resolved_refs: set[str] = set()
        for filename, integrity in required_files.items():
            assert set(integrity) in ({"artifact"}, {"bytes", "sha256"})
            if "artifact" in integrity:
                ref = integrity["artifact"]
                assert ref in artifacts
                assert artifacts[ref]["filename"] == filename
                assert artifacts[ref]["owner"] == bundle["source"]["owner"]
                assert artifacts[ref]["revision"] == bundle["source"]["revision"]
                assert artifacts[ref]["bytes"] > 0
                assert re.fullmatch(r"[0-9a-f]{64}", artifacts[ref]["sha256"])
                resolved_refs.add(ref)
            else:
                assert integrity["bytes"] > 0
                assert re.fullmatch(r"[0-9a-f]{64}", integrity["sha256"])
        assert resolved_refs == artifact_refs
        assert bundle["loader_smoke"]["probe"]
        assert bundle["loader_smoke"]["pass_condition"]
    assert referenced_artifacts == artifacts.keys()

    for profile in manifest["profiles"].values():
        assert set(profile["bundles"]) <= bundles.keys()
        runtime_ref = profile.get("runtime")
        assert runtime_ref is None or runtime_ref in manifest["runtimes"]

    assert (
        "authenticated at its bundle source owner and revision"
        in manifest["policy"]["required_file_provenance"]
    )

    doctor = " ".join(
        (ROOT / ".agents/skills/minnarone-runtime-doctor/SKILL.md")
        .read_text(encoding="utf-8")
        .split()
    )
    for phrase in (
        "weights alone",
        "all required bundle files",
        "pinned source owner and revision",
        "authenticated integrity entry",
        "artifact reference",
        "local loader smoke",
        "must be `FAIL`",
    ):
        assert phrase in doctor


def test_manifest_records_supplied_snapshot_file_integrity_exactly():
    manifest = json.loads(
        (ROOT / "docs/runtime-model-manifest.json").read_text(encoding="utf-8")
    )
    expected = {
        ("asr-large-v3-turbo", "config.json"): (
            2263,
            "b0253ea6c0d3bea6b1e19e91a02acfd3b53f4467362efcb5a3e6b16c9b3a9b7e",
        ),
        ("asr-large-v3-turbo", "preprocessor_config.json"): (
            340,
            "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711",
        ),
        ("asr-large-v3-turbo", "tokenizer.json"): (
            2710337,
            "297b13372ac43916285644fb9687add3cc62ee2a1adb60da3dc25cc94c1871fd",
        ),
        ("asr-large-v3-turbo", "vocabulary.json"): (
            1068114,
            "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1",
        ),
        ("qwen2-vl-2b-torch", "config.json"): (
            1196,
            "422adefa19e62dd175961cec85bc0400344fe5bf9b22bd1182e05aaae78556e0",
        ),
        ("qwen2-vl-2b-torch", "generation_config.json"): (
            272,
            "d2864bf1edea5863d331edfff48106b586a366f5a2c41aa77731fadc53aa25d2",
        ),
        ("qwen2-vl-2b-torch", "merges.txt"): (
            1671839,
            "599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3",
        ),
        ("qwen2-vl-2b-torch", "model.safetensors.index.json"): (
            56411,
            "260ab9fa1418d6d6ab79daa1d9da2c47264f3b72edb4630fc799077ac67d27c6",
        ),
        ("qwen2-vl-2b-torch", "preprocessor_config.json"): (
            347,
            "b5eaad0c2815f07631535dcc58f3c462b0d73693638ad21d19f3c50820eae1cc",
        ),
        ("qwen2-vl-2b-torch", "tokenizer.json"): (
            7029741,
            "cb63a0a23eef3d5b01063a9880a1925a65aaf4d1591d519910ee3527852950a0",
        ),
        ("qwen2-vl-2b-torch", "tokenizer_config.json"): (
            4190,
            "ff5c4fd898fe8c39591eb70e5d39d2782802d4204d6ae9ba1223252f354842a0",
        ),
        ("qwen2-vl-2b-torch", "vocab.json"): (
            2776833,
            "ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910",
        ),
    }
    for (bundle, filename), (size, digest) in expected.items():
        integrity = manifest["bundles"][bundle]["required_files"][filename]
        assert integrity == {"bytes": size, "sha256": digest}


def test_contributor_entrypoints_route_architecture_quality_safety_and_skills():
    combined = "\n".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in ("AGENTS.md", "CONTRIBUTING.md")
    ).lower()
    for phrase in (
        "architecture",
        "quality",
        "prompt safety",
        "dirty worktree",
        "skill routing",
        ".agents/skills/minnarone-prompts/skill.md",
        ".agents/skills/minnarone-twitch-onboarding/skill.md",
        ".agents/skills/minnarone-runtime-doctor/skill.md",
    ):
        assert phrase in combined


def test_docs_define_portable_canonical_skills_and_optional_symlink_aliases():
    combined = " ".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in ("README.md", "README.it.md", "CONTRIBUTING.md")
    )
    for phrase in (
        ".agents/skills/",
        "portable canonical",
        "core.symlinks=false",
        "plain file",
        "optional",
    ):
        assert phrase in combined


def test_added_onboarding_markdown_links_resolve_from_a_clean_checkout():
    paths = (*README_PATHS, ROOT / "AGENTS.md", ROOT / "CONTRIBUTING.md")
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for raw_target in re.findall(r"\[[^]]+]\(([^)]+)\)", text):
            if "://" in raw_target or raw_target.startswith("mailto:"):
                continue
            target, separator, fragment = raw_target.partition("#")
            target_path = path if not target else path.parent / unquote(target)
            assert target_path.exists(), f"broken link in {path}: {raw_target}"
            if separator and fragment and target_path.is_file():
                anchors = _markdown_heading_anchors(
                    target_path.read_text(encoding="utf-8")
                )
                assert unquote(fragment) in anchors, (
                    f"broken fragment in {path}: {raw_target}; "
                    f"known anchors include {sorted(anchors)[:10]}"
                )


def _markdown_heading_anchors(text: str) -> set[str]:
    """Return GitHub-style anchors for ATX headings, including duplicates."""
    anchors: set[str] = set()
    occurrences: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(r"^ {0,3}#{1,6}\s+(.+?)(?:\s+#+\s*)?$", line)
        if match is None:
            continue
        heading = unescape(match.group(1))
        heading = re.sub(r"!\[([^]]*)]\([^)]+\)", r"\1", heading)
        heading = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", heading)
        heading = re.sub(r"<[^>]*>", "", heading)
        heading = heading.replace("`", "").replace("*", "").replace("_", "")
        base = re.sub(r"[^\w\s-]", "", heading.lower(), flags=re.UNICODE)
        base = re.sub(r"\s+", "-", base.strip())
        duplicate = occurrences.get(base, 0)
        occurrences[base] = duplicate + 1
        anchors.add(base if duplicate == 0 else f"{base}-{duplicate}")
    return anchors


def _is_valid_claude_skill_alias(alias: Path, canonical: Path) -> bool:
    return (
        alias.is_symlink()
        and not alias.readlink().is_absolute()
        and alias.resolve() == canonical.resolve()
    )
