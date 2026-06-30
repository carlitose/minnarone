"""Test dello schema di configurazione: caricamento valido, errori chiari, punti v2 inerti."""

import textwrap
from pathlib import Path

import pytest

from minnarone.asr import AsrConfig
from minnarone.config import CommentatorConfig, Config, ConfigError
from minnarone.output import OutputMode
from minnarone.speaker import SpeakerClusteringConfig, SpeakerEmbeddingConfig
from minnarone.vad import VadConfig
from minnarone.video import VideoPerceptionConfig
from minnarone.vlm import QwenVlConfig

VALID_YAML = textwrap.dedent(
    """
    mode: public
    soul_path: soul.md
    facts_dir: facts
    adapter: os_capture
    llm_provider: grok
    llm_params:
      thinking: low
    disclosure:
      announce_ai: true
    retention:
      perceptions_days: 7
    """
)

MINIMAL_YAML = textwrap.dedent(
    """
    mode: public
    soul_path: soul.md
    facts_dir: facts
    adapter: os_capture
    llm_provider: grok
    """
)

TWITCH_YAML = textwrap.dedent(
    """
    mode: public
    soul_path: soul.md
    facts_dir: facts
    adapter: twitch
    llm_provider: grok
    twitch:
      channel: "#Minnarone"
      quality: best
      chat: true
      audio: true
      video: true
      audio_chunk_seconds: 1.0
      video_fps: 1.0
    """
)


def _write(tmp_path, content):
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return p


def test_load_valid_config(tmp_path):
    cfg = Config.load(_write(tmp_path, VALID_YAML))
    assert cfg.mode is OutputMode.PUBLIC
    assert cfg.adapter == "os_capture"
    assert cfg.llm_params["thinking"] == "low"


def test_defaults_applied_when_omitted(tmp_path):
    cfg = Config.load(_write(tmp_path, MINIMAL_YAML))
    assert cfg.senser_interval == 0.5
    assert cfg.idle_interval == 150.0
    assert cfg.summarizer_interval == 30.0
    assert cfg.recent_chat_window == 15
    assert cfg.perception_queue_size == 32
    assert cfg.perception_shutdown_timeout == 5.0
    assert cfg.twitch is None


def test_config_positional_constructor_contract_is_preserved():
    cfg = Config(
        OutputMode.PUBLIC,
        "soul.md",
        "facts",
        "os_capture",
        "grok",
        "custom-name",
        {"thinking": "low"},
    )

    assert cfg.agent_name == "custom-name"
    assert cfg.llm_params == {"thinking": "low"}
    assert cfg.twitch is None


def test_twitch_config_parses_and_normalizes_channel(tmp_path):
    cfg = Config.load(_write(tmp_path, TWITCH_YAML))
    assert cfg.adapter == "twitch"
    assert cfg.twitch is not None
    assert cfg.twitch.channel == "minnarone"
    assert cfg.twitch.quality == "best"
    assert cfg.twitch.chat is True
    assert cfg.twitch.audio is True
    assert cfg.twitch.video is True
    assert cfg.twitch.audio_chunk_seconds == 1.0
    assert cfg.twitch.video_fps == 1.0


def test_twitch_adapter_requires_twitch_section(tmp_path):
    bad = MINIMAL_YAML.replace("adapter: os_capture", "adapter: twitch")
    with pytest.raises(ConfigError, match="twitch"):
        Config.load(_write(tmp_path, bad))


def test_twitch_adapter_rejects_wrong_twitch_object_type():
    with pytest.raises(ConfigError, match="TwitchConfig"):
        Config(
            mode=OutputMode.PUBLIC,
            soul_path="soul.md",
            facts_dir="facts",
            adapter="twitch",
            llm_provider="grok",
            twitch="not-a-config",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "line, replacement, message",
    [
        ("channel: \"#Minnarone\"", "channel: '#'", "channel Twitch"),
        ("quality: best", "quality: ''", "quality"),
        ("audio_chunk_seconds: 1.0", "audio_chunk_seconds: 0", "audio_chunk_seconds"),
        (
            "audio_chunk_seconds: 1.0",
            "audio_chunk_seconds: true",
            "audio_chunk_seconds",
        ),
        ("video_fps: 1.0", "video_fps: 0", "video_fps"),
        ("video_fps: 1.0", "video_fps: true", "video_fps"),
        ("chat: true", "chat: 'yes'", "chat"),
        ("video_fps: 1.0", "vide_fps: 1.0", "vide_fps"),
    ],
)
def test_invalid_twitch_config_fails_clearly(tmp_path, line, replacement, message):
    bad = TWITCH_YAML.replace(line, replacement)
    with pytest.raises(ConfigError, match=message):
        Config.load(_write(tmp_path, bad))


def test_summarizer_interval_parsed_and_validated(tmp_path):
    cfg = Config.load(_write(tmp_path, MINIMAL_YAML + "summarizer_interval: 5\n"))
    assert cfg.summarizer_interval == 5.0
    with pytest.raises(ConfigError, match="summarizer_interval"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "summarizer_interval: 0\n"))


def test_perception_queue_config_is_parsed_and_validated(tmp_path):
    cfg = Config.load(
        _write(
            tmp_path,
            MINIMAL_YAML
            + "perception_queue_size: 3\n"
            + "perception_shutdown_timeout: 0.25\n",
        )
    )
    assert cfg.perception_queue_size == 3
    assert cfg.perception_shutdown_timeout == 0.25

    with pytest.raises(ConfigError, match="perception_queue_size"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "perception_queue_size: 0\n"))
    with pytest.raises(ConfigError, match="perception_queue_size"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "perception_queue_size: 1.5\n"))
    with pytest.raises(ConfigError, match="perception_shutdown_timeout"):
        Config.load(
            _write(tmp_path, MINIMAL_YAML + "perception_shutdown_timeout: true\n")
        )
    with pytest.raises(ConfigError, match="perception_shutdown_timeout"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "perception_shutdown_timeout: 0\n"))


def test_vad_config_defaults_overrides_and_validation(tmp_path):
    cfg = Config.load(_write(tmp_path, MINIMAL_YAML))
    assert cfg.vad == VadConfig()

    configured = Config.load(
        _write(
            tmp_path,
            MINIMAL_YAML
            + textwrap.dedent(
                """
                vad:
                  mode: 3
                  frame_ms: 20
                  padding_ms: 200
                  max_utterance_seconds: 12.5
                """
            ),
        )
    )
    assert configured.vad == VadConfig(
        mode=3,
        frame_ms=20,
        padding_ms=200,
        max_utterance_seconds=12.5,
    )

    with pytest.raises(ConfigError, match="vad.frame_ms"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "vad:\n  frame_ms: 25\n"))


def test_asr_config_defaults_overrides_and_validation(tmp_path):
    cfg = Config.load(_write(tmp_path, MINIMAL_YAML))
    assert cfg.asr == AsrConfig()

    configured = Config.load(
        _write(
            tmp_path,
            MINIMAL_YAML
            + textwrap.dedent(
                """
                asr:
                  model: turbo
                  device: cpu
                  compute_type: int8
                  language: it
                  beam_size: 3
                  condition_on_previous_text: true
                """
            ),
        )
    )
    assert configured.asr == AsrConfig(
        model="turbo",
        device="cpu",
        compute_type="int8",
        language="it",
        beam_size=3,
        condition_on_previous_text=True,
    )

    with pytest.raises(ConfigError, match="asr.beam_size"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "asr:\n  beam_size: 0\n"))
    with pytest.raises(ConfigError, match="asr.model"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "asr:\n  model: ''\n"))
    with pytest.raises(ConfigError, match="asr.unexpected"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "asr:\n  unexpected: true\n"))


def test_speaker_configs_defaults_overrides_and_validation(tmp_path):
    cfg = Config.load(_write(tmp_path, MINIMAL_YAML))
    assert cfg.speaker_embedding == SpeakerEmbeddingConfig()
    assert cfg.speaker_clustering == SpeakerClusteringConfig()

    configured = Config.load(
        _write(
            tmp_path,
            MINIMAL_YAML
            + textwrap.dedent(
                """
                speaker_embedding:
                  model_path: /models/campp.onnx
                  provider: coreml
                  num_threads: 2
                  dimension: 256
                speaker_clustering:
                  threshold: 0.72
                  warmup_seconds: 5.0
                  min_update_seconds: 0.4
                """
            ),
        )
    )
    assert configured.speaker_embedding == SpeakerEmbeddingConfig(
        model_path=Path("/models/campp.onnx"),
        provider="coreml",
        num_threads=2,
        dimension=256,
    )
    assert configured.speaker_clustering == SpeakerClusteringConfig(
        threshold=0.72,
        warmup_seconds=5.0,
        min_update_seconds=0.4,
    )

    with pytest.raises(ConfigError, match="speaker_embedding.num_threads"):
        Config.load(
            _write(tmp_path, MINIMAL_YAML + "speaker_embedding:\n  num_threads: 0\n")
        )
    with pytest.raises(ConfigError, match="speaker_embedding.model_path"):
        Config.load(
            _write(tmp_path, MINIMAL_YAML + "speaker_embedding:\n  model_path: 123\n")
        )
    with pytest.raises(ConfigError, match="speaker_clustering.threshold"):
        Config.load(
            _write(tmp_path, MINIMAL_YAML + "speaker_clustering:\n  threshold: 1.5\n")
        )
    with pytest.raises(ConfigError, match="speaker_clustering.unexpected"):
        Config.load(
            _write(
                tmp_path,
                MINIMAL_YAML + "speaker_clustering:\n  unexpected: true\n",
            )
        )


def test_video_config_defaults_overrides_and_validation(tmp_path):
    cfg = Config.load(_write(tmp_path, MINIMAL_YAML))
    assert cfg.video == VideoPerceptionConfig()

    configured = Config.load(
        _write(
            tmp_path,
            MINIMAL_YAML
            + textwrap.dedent(
                """
                video:
                  sample_every: 3
                  dedup_change_threshold: 0.25
                """
            ),
        )
    )
    assert configured.video == VideoPerceptionConfig(
        sample_every=3,
        dedup_change_threshold=0.25,
    )

    with pytest.raises(ConfigError, match="video.sample_every"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "video:\n  sample_every: 0\n"))
    with pytest.raises(ConfigError, match="video.dedup_change_threshold"):
        Config.load(
            _write(tmp_path, MINIMAL_YAML + "video:\n  dedup_change_threshold: 1.5\n")
        )
    with pytest.raises(ConfigError, match="video.dedup_change_threshold"):
        Config.load(
            _write(tmp_path, MINIMAL_YAML + "video:\n  dedup_change_threshold: 1.0\n")
        )
    with pytest.raises(ConfigError, match="video.unexpected"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "video:\n  unexpected: true\n"))


def test_vlm_config_defaults_overrides_and_validation(tmp_path):
    cfg = Config.load(_write(tmp_path, MINIMAL_YAML))
    assert cfg.vlm == QwenVlConfig()

    configured = Config.load(
        _write(
            tmp_path,
            MINIMAL_YAML
            + textwrap.dedent(
                """
                vlm:
                  model: /models/qwen2-vl
                  device: cpu
                  device_map: null
                  torch_dtype: float16
                  attn_implementation: sdpa
                  max_new_tokens: 32
                  timeout_seconds: 12.5
                  language: en
                  prompt: Describe the frame briefly in concise English.
                  max_caption_chars: 120
                  max_image_edge: 448
                  max_image_pixels: 200000
                """
            ),
        )
    )
    assert configured.vlm == QwenVlConfig(
        model=Path("/models/qwen2-vl"),
        device="cpu",
        device_map=None,
        torch_dtype="float16",
        attn_implementation="sdpa",
        max_new_tokens=32,
        timeout_seconds=12.5,
        language="en",
        prompt="Describe the frame briefly in concise English.",
        max_caption_chars=120,
        max_image_edge=448,
        max_image_pixels=200000,
    )

    with pytest.raises(ConfigError, match="vlm.max_new_tokens"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "vlm:\n  max_new_tokens: 0\n"))
    with pytest.raises(ConfigError, match="vlm.timeout_seconds"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "vlm:\n  timeout_seconds: 0\n"))
    with pytest.raises(ConfigError, match="vlm.model"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "vlm:\n  model: ''\n"))
    with pytest.raises(ConfigError, match="vlm.max_image_edge"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "vlm:\n  max_image_edge: 0\n"))
    with pytest.raises(ConfigError, match="vlm.max_image_pixels"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "vlm:\n  max_image_pixels: 0\n"))
    with pytest.raises(ConfigError, match="vlm.unexpected"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "vlm:\n  unexpected: true\n"))


def test_v2_points_present_and_inert_by_default(tmp_path):
    cfg = Config.load(_write(tmp_path, MINIMAL_YAML))
    assert cfg.disclosure.announce_ai is False
    assert cfg.retention.perceptions_days is None
    assert cfg.auto_memory is False
    assert cfg.commentator == CommentatorConfig()


def test_v2_points_parsed_when_present(tmp_path):
    cfg = Config.load(_write(tmp_path, VALID_YAML))
    assert cfg.disclosure.announce_ai is True
    assert cfg.retention.perceptions_days == 7


def test_commentator_config_defaults_overrides_and_validation(tmp_path):
    configured = Config.load(
        _write(
            tmp_path,
            MINIMAL_YAML.replace("mode: public", "mode: private")
            + textwrap.dedent(
                """
                commentator:
                  enabled: true
                  language: it
                  idle_interval: 12.5
                """
            ),
        )
    )

    assert configured.commentator == CommentatorConfig(
        enabled=True,
        language="it",
        idle_interval=12.5,
    )

    with pytest.raises(ConfigError, match="commentator.enabled"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "commentator:\n  enabled: 1\n"))
    with pytest.raises(ConfigError, match="commentator.language"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "commentator:\n  language: ''\n"))
    with pytest.raises(ConfigError, match="commentator.idle_interval"):
        Config.load(
            _write(tmp_path, MINIMAL_YAML + "commentator:\n  idle_interval: 0\n")
        )
    with pytest.raises(ConfigError, match="commentator.unexpected"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "commentator:\n  unexpected: 1\n"))


def test_commentator_requires_private_mode(tmp_path):
    with pytest.raises(ConfigError, match="mode: private"):
        Config.load(
            _write(
                tmp_path,
                MINIMAL_YAML
                + textwrap.dedent(
                    """
                    commentator:
                      enabled: true
                    """
                ),
            )
        )


def test_invalid_mode_raises_clear_error(tmp_path):
    bad = VALID_YAML.replace("mode: public", "mode: telepathic")
    with pytest.raises(ConfigError, match="mode"):
        Config.load(_write(tmp_path, bad))


def test_missing_required_field_raises(tmp_path):
    bad = textwrap.dedent(
        """
        mode: public
        facts_dir: facts
        adapter: os_capture
        llm_provider: grok
        """
    )
    with pytest.raises(ConfigError, match="soul_path"):
        Config.load(_write(tmp_path, bad))


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="non trovato"):
        Config.load(tmp_path / "nope.yaml")


def test_empty_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="vuoto"):
        Config.load(_write(tmp_path, ""))


def test_non_positive_interval_raises(tmp_path):
    bad = MINIMAL_YAML + "senser_interval: 0\n"
    with pytest.raises(ConfigError, match="senser_interval"):
        Config.load(_write(tmp_path, bad))
