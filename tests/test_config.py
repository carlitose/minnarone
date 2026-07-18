"""Test dello schema di configurazione: caricamento valido, errori chiari, punti v2 inerti."""

import textwrap
from pathlib import Path

import pytest

from minnarone.asr import AsrConfig
from minnarone.config import (
    CommentatorConfig,
    CommentatorStyle,
    Config,
    ConfigError,
    MeetingSynthesizerProfileConfig,
    OperatorProfileConfig,
    OriginalChatProfileConfig,
    OsCaptureConfig,
    SuggesterProfileConfig,
    TwitchSendMode,
)
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
    os_capture:
      audio: true
      video: true
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
    os_capture:
      audio: true
      video: true
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


def test_load_resolves_memory_paths_relative_to_config_file(tmp_path):
    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()

    cfg = Config.load(_write(cfg_dir, MINIMAL_YAML))

    assert cfg.soul_path == str(cfg_dir / "soul.md")
    assert cfg.facts_dir == str(cfg_dir / "facts")


def test_prompts_dir_absent_defaults_to_none(tmp_path):
    # Assente in config → None: si usano SOLO i default impacchettati.
    cfg = Config.load(_write(tmp_path, MINIMAL_YAML))
    assert cfg.prompts_dir is None


def test_prompts_dir_parsed_and_resolved_relative_to_config_file(tmp_path):
    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()
    content = MINIMAL_YAML + "prompts_dir: prompts_it\n"

    cfg = Config.load(_write(cfg_dir, content))

    # Risolto rispetto alla dir del file di config, come soul_path/facts_dir.
    assert cfg.prompts_dir == str(cfg_dir / "prompts_it")


def test_prompts_dir_empty_string_is_rejected():
    with pytest.raises(ConfigError, match="prompts_dir"):
        Config(
            OutputMode.PUBLIC,
            "soul.md",
            "facts",
            "none",
            "grok",
            prompts_dir="",
        )


def test_config_positional_constructor_contract_is_preserved():
    # Adapter neutro (né twitch né os_capture) così il contratto posizionale è
    # verificabile senza fornire una sezione sorgente obbligatoria.
    cfg = Config(
        OutputMode.PUBLIC,
        "soul.md",
        "facts",
        "none",
        "grok",
        "custom-name",
        {"thinking": "low"},
    )

    assert cfg.agent_name == "custom-name"
    assert cfg.llm_params == {"thinking": "low"}
    assert cfg.twitch is None
    assert cfg.os_capture is None


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


def test_config_parses_os_capture_section(tmp_path):
    cfg = Config.load(
        _write(
            tmp_path,
            MINIMAL_YAML.replace(
                "os_capture:\n  audio: true\n  video: true\n",
                textwrap.dedent(
                    """
                    os_capture:
                      audio: false
                      video: true
                      audio_chunk_seconds: 2.0
                      video_fps: 3.0
                      monitor: 2
                    """
                ),
            ),
        )
    )
    assert cfg.adapter == "os_capture"
    assert cfg.os_capture is not None
    assert cfg.os_capture.audio is False
    assert cfg.os_capture.video is True
    assert cfg.os_capture.audio_chunk_seconds == 2.0
    assert cfg.os_capture.video_fps == 3.0
    assert cfg.os_capture.monitor == 2


def test_os_capture_adapter_requires_os_capture_section(tmp_path):
    bad = MINIMAL_YAML.replace("os_capture:\n  audio: true\n  video: true\n", "")
    with pytest.raises(ConfigError, match="os_capture"):
        Config.load(_write(tmp_path, bad))


def test_os_capture_section_must_be_a_table(tmp_path):
    bad = MINIMAL_YAML.replace(
        "os_capture:\n  audio: true\n  video: true\n",
        "os_capture: not-a-table\n",
    )
    with pytest.raises(ConfigError, match="tabella"):
        Config.load(_write(tmp_path, bad))


def test_os_capture_adapter_rejects_wrong_os_capture_object_type():
    with pytest.raises(ConfigError, match="OsCaptureConfig"):
        Config(
            mode=OutputMode.PUBLIC,
            soul_path="soul.md",
            facts_dir="facts",
            adapter="os_capture",
            llm_provider="grok",
            os_capture="not-a-config",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "line, replacement, message",
    [
        ('channel: "#Minnarone"', "channel: '#'", "channel Twitch"),
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


def test_os_capture_config_defaults_applied():
    cfg = OsCaptureConfig.from_dict({})
    assert cfg.audio is True
    assert cfg.video is True
    assert cfg.audio_chunk_seconds == 1.0
    assert cfg.video_fps == 1.0
    assert cfg.monitor == 1


def test_os_capture_config_parses_overrides():
    cfg = OsCaptureConfig.from_dict(
        {
            "audio": False,
            "video": True,
            "audio_chunk_seconds": 2.0,
            "video_fps": 3.0,
            "monitor": 2,
        }
    )
    assert cfg.audio is False
    assert cfg.video is True
    assert cfg.audio_chunk_seconds == 2.0
    assert cfg.video_fps == 3.0
    assert cfg.monitor == 2


def test_os_capture_config_rejects_unknown_field():
    with pytest.raises(ConfigError, match="os_capture non riconosciuti"):
        OsCaptureConfig.from_dict({"moitor": 1})


def test_os_capture_config_requires_at_least_one_channel():
    with pytest.raises(ConfigError, match="almeno audio o video"):
        OsCaptureConfig.from_dict({"audio": False, "video": False})


@pytest.mark.parametrize(
    "data, message",
    [
        ({"audio": "yes"}, "os_capture.audio"),
        ({"video": 1}, "os_capture.video"),
        ({"audio_chunk_seconds": 0}, "os_capture.audio_chunk_seconds"),
        ({"audio_chunk_seconds": True}, "os_capture.audio_chunk_seconds"),
        ({"video_fps": 0}, "os_capture.video_fps"),
        ({"video_fps": True}, "os_capture.video_fps"),
        ({"monitor": 0}, "os_capture.monitor"),
        ({"monitor": True}, "os_capture.monitor"),
        ({"monitor": 1.5}, "os_capture.monitor"),
        ({"monitor": "1"}, "os_capture.monitor"),
    ],
)
def test_os_capture_config_validation_rules(data, message):
    with pytest.raises(ConfigError, match=message):
        OsCaptureConfig.from_dict(data)


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
    assert cfg.speaker_clustering == SpeakerClusteringConfig(threshold=0.45)

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
                  language: it
                  profiles:
                    operator:
                      idle_interval: 12.5
                """
            ),
        )
    )

    assert configured.commentator.language == "it"
    assert CommentatorStyle.OPERATOR in configured.commentator.profiles
    assert configured.commentator.profiles[CommentatorStyle.OPERATOR] == (
        OperatorProfileConfig(idle_interval=12.5)
    )

    with pytest.raises(ConfigError, match="commentator.language"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "commentator:\n  language: ''\n"))
    with pytest.raises(ConfigError, match="commentator non riconosciuti"):
        Config.load(_write(tmp_path, MINIMAL_YAML + "commentator:\n  unexpected: 1\n"))


def test_commentator_empty_profiles_means_disabled():
    cfg = CommentatorConfig()
    assert cfg.profiles == {}
    assert cfg.active_styles() == []
    assert cfg.uses_local_output(OutputMode.PRIVATE) is False


def test_commentator_single_profile_active():
    cfg = CommentatorConfig(
        profiles={CommentatorStyle.OPERATOR: OperatorProfileConfig(idle_interval=30.0)}
    )
    assert cfg.active_styles() == [CommentatorStyle.OPERATOR]
    assert cfg.uses_local_output(OutputMode.PRIVATE) is True
    assert cfg.uses_local_output(OutputMode.PUBLIC) is False


def test_public_twitch_rejects_non_original_chat_profile(tmp_path):
    # Su Twitch in public la persona È l'original_chat: un profilo operator
    # (telecronista) parlerebbe all'operatore invece di scrivere in chat.
    bad = TWITCH_YAML + textwrap.dedent(
        """
        commentator:
          language: it
          profiles:
            operator:
              idle_interval: 30.0
        """
    )
    with pytest.raises(ConfigError, match="original_chat"):
        Config.load(_write(tmp_path, bad))


def test_public_twitch_allows_original_chat_profile(tmp_path):
    good = TWITCH_YAML + textwrap.dedent(
        """
        commentator:
          language: it
          profiles:
            original_chat:
              idle_interval: 30.0
        """
    )
    cfg = Config.load(_write(tmp_path, good))
    assert cfg.commentator.active_styles() == [CommentatorStyle.ORIGINAL_CHAT]


def test_public_twitch_without_profile_allowed(tmp_path):
    # Nessun profilo è ammesso: il default per twitch+public è original_chat.
    cfg = Config.load(_write(tmp_path, TWITCH_YAML))
    assert cfg.commentator.active_styles() == []


def test_commentator_multiple_profiles_active():
    cfg = CommentatorConfig(
        profiles={
            CommentatorStyle.OPERATOR: OperatorProfileConfig(),
            CommentatorStyle.MEETING_SYNTHESIZER: MeetingSynthesizerProfileConfig(),
            CommentatorStyle.SUGGESTER: SuggesterProfileConfig(),
        }
    )
    styles = cfg.active_styles()
    assert CommentatorStyle.OPERATOR in styles
    assert CommentatorStyle.MEETING_SYNTHESIZER in styles
    assert CommentatorStyle.SUGGESTER in styles
    assert len(styles) == 3


def test_commentator_unknown_profile_key_raises(tmp_path):
    with pytest.raises(ConfigError, match="commentator.profiles.*glitch"):
        Config.load(
            _write(
                tmp_path,
                MINIMAL_YAML.replace("mode: public", "mode: private")
                + textwrap.dedent(
                    """
                    commentator:
                      profiles:
                        glitch: {}
                    """,
                ),
            )
        )


def test_commentator_unknown_field_within_profile_raises(tmp_path):
    with pytest.raises(
        ConfigError, match="commentator.profiles.operator non riconosciuti"
    ):
        Config.load(
            _write(
                tmp_path,
                MINIMAL_YAML.replace("mode: public", "mode: private")
                + textwrap.dedent(
                    """
                    commentator:
                      profiles:
                        operator:
                          bogus_field: 42
                    """,
                ),
            )
        )


def test_commentator_profile_validation_negative_interval_raises(tmp_path):
    with pytest.raises(ConfigError, match="MeetingSynthesizerProfileConfig.interval_s"):
        Config.load(
            _write(
                tmp_path,
                MINIMAL_YAML.replace("mode: public", "mode: private")
                + textwrap.dedent(
                    """
                    commentator:
                      profiles:
                        meeting_synthesizer:
                          interval_s: -1
                    """,
                ),
            )
        )


def test_commentator_private_only_profiles_require_private_mode(tmp_path):
    with pytest.raises(ConfigError, match="mode: private"):
        Config.load(
            _write(
                tmp_path,
                MINIMAL_YAML
                + textwrap.dedent(
                    """
                    commentator:
                      profiles:
                        meeting_synthesizer:
                          interval_s: 180
                    """
                ),
            )
        )


def test_commentator_operator_profile_allowed_in_public_mode(tmp_path):
    cfg = Config.load(
        _write(
            tmp_path,
            MINIMAL_YAML
            + textwrap.dedent(
                """
                commentator:
                  profiles:
                    operator: {}
                """
            ),
        )
    )
    assert len(cfg.commentator.active_styles()) == 1


def test_commentator_original_chat_profile_loads_in_private_mode(tmp_path):
    cfg = Config.load(
        _write(
            tmp_path,
            MINIMAL_YAML.replace("mode: public", "mode: private")
            + textwrap.dedent(
                """
                commentator:
                  profiles:
                    original_chat: {}
                """
            ),
        )
    )
    assert CommentatorStyle.ORIGINAL_CHAT in cfg.commentator.profiles
    assert isinstance(
        cfg.commentator.profiles[CommentatorStyle.ORIGINAL_CHAT],
        OriginalChatProfileConfig,
    )


def test_commentator_empty_dict_profile_produces_valid_config(tmp_path):
    cfg = Config.load(
        _write(
            tmp_path,
            MINIMAL_YAML.replace("mode: public", "mode: private")
            + textwrap.dedent(
                """
                commentator:
                  profiles:
                    suggester: {}
                """
            ),
        )
    )
    assert isinstance(
        cfg.commentator.profiles[CommentatorStyle.SUGGESTER],
        SuggesterProfileConfig,
    )


def test_commentator_null_profile_value_produces_valid_config(tmp_path):
    """YAML `suggester:` without a value parses as None; must produce valid config."""
    cfg = Config.load(
        _write(
            tmp_path,
            MINIMAL_YAML.replace("mode: public", "mode: private")
            + textwrap.dedent(
                """
                commentator:
                  profiles:
                    suggester:
                """
            ),
        )
    )
    assert isinstance(
        cfg.commentator.profiles[CommentatorStyle.SUGGESTER],
        SuggesterProfileConfig,
    )


def test_commentator_round_trip_from_dict():
    """Construct from dict and verify all fields survive the round-trip."""
    from minnarone.config import _commentator_config_from_dict

    data = {
        "language": "en",
        "profiles": {
            "operator": {"idle_interval": 30.0},
            "meeting_synthesizer": {"interval_s": 60},
            "suggester": {},
        },
    }
    cfg = _commentator_config_from_dict(data)
    assert cfg.language == "en"
    assert len(cfg.profiles) == 3
    assert cfg.profiles[CommentatorStyle.OPERATOR] == OperatorProfileConfig(
        idle_interval=30.0,
    )
    assert cfg.profiles[CommentatorStyle.MEETING_SYNTHESIZER] == (
        MeetingSynthesizerProfileConfig(interval_s=60.0)
    )
    assert cfg.profiles[CommentatorStyle.SUGGESTER] == SuggesterProfileConfig()


def test_commentator_unknown_top_level_key_raises():
    from minnarone.config import _commentator_config_from_dict

    with pytest.raises(ConfigError, match="commentator non riconosciuti.*enabled"):
        _commentator_config_from_dict({"enabled": True})


def test_commentator_validate_for_mode_public_with_private_only_profile_raises():
    cfg = CommentatorConfig(
        profiles={
            CommentatorStyle.MEETING_SYNTHESIZER: MeetingSynthesizerProfileConfig()
        },
    )
    with pytest.raises(ConfigError, match="mode: private"):
        cfg.validate_for_mode(OutputMode.PUBLIC)


def test_commentator_validate_for_mode_public_with_operator_ok():
    cfg = CommentatorConfig(
        profiles={CommentatorStyle.OPERATOR: OperatorProfileConfig()},
    )
    cfg.validate_for_mode(OutputMode.PUBLIC)


def test_commentator_validate_for_mode_private_with_profiles_ok():
    cfg = CommentatorConfig(
        profiles={CommentatorStyle.OPERATOR: OperatorProfileConfig()},
    )
    cfg.validate_for_mode(OutputMode.PRIVATE)  # no exception


def test_commentator_validate_for_mode_public_without_profiles_ok():
    cfg = CommentatorConfig()
    cfg.validate_for_mode(OutputMode.PUBLIC)  # no exception


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


# ---------------------------------------------------------------------------
# twitch.send: configurazione dell'invio pubblico (shadow-first)
# ---------------------------------------------------------------------------


def test_twitch_send_defaults_when_absent(tmp_path):
    cfg = Config.load(_write(tmp_path, TWITCH_YAML))

    assert cfg.twitch is not None
    assert cfg.twitch.send.mode is TwitchSendMode.OFF
    assert cfg.twitch.send.allowed_channels == ()
    assert cfg.twitch.send.max_per_minute == 1
    assert cfg.twitch.send.max_per_hour == 20
    assert cfg.twitch.send.failure_threshold == 3


def _twitch_yaml_with_send(send_block: str) -> str:
    return TWITCH_YAML + textwrap.indent(textwrap.dedent(send_block), "  ")


def test_twitch_send_parses_full_block_and_normalizes_channels(tmp_path):
    yaml_text = _twitch_yaml_with_send(
        """
        send:
          mode: shadow
          allowed_channels: ["#Minnarone", "AltroCanale"]
          max_per_minute: 2
          max_per_hour: 10
          failure_threshold: 5
        """
    )

    cfg = Config.load(_write(tmp_path, yaml_text))

    send = cfg.twitch.send
    assert send.mode is TwitchSendMode.SHADOW
    assert send.allowed_channels == ("minnarone", "altrocanale")
    assert send.max_per_minute == 2
    assert send.max_per_hour == 10
    assert send.failure_threshold == 5


@pytest.mark.parametrize(
    "send_block, message",
    [
        ("\nsend:\n  mode: loud\n", "twitch.send.mode"),
        ("\nsend:\n  max_per_minute: 0\n", "twitch.send.max_per_minute"),
        ("\nsend:\n  max_per_minute: true\n", "twitch.send.max_per_minute"),
        ("\nsend:\n  max_per_hour: -5\n", "twitch.send.max_per_hour"),
        ("\nsend:\n  failure_threshold: 0\n", "twitch.send.failure_threshold"),
        ("\nsend:\n  allowed_channels: ['']\n", "twitch.send.allowed_channels"),
        ("\nsend:\n  allowed_channels: canale\n", "twitch.send.allowed_channels"),
        ("\nsend:\n  budget: 3\n", "twitch.send non riconosciuti"),
        ("\nsend: not-a-table\n", "tabella"),
    ],
)
def test_invalid_twitch_send_config_fails_clearly(tmp_path, send_block, message):
    bad = _twitch_yaml_with_send(send_block)
    with pytest.raises(ConfigError, match=message):
        Config.load(_write(tmp_path, bad))


def test_twitch_send_mode_unquoted_truthy_boolean_suggests_quoting(tmp_path):
    # YAML 1.1 parsa `on`/`yes`/`true` non quotati come booleano True: il
    # messaggio deve spiegare l'ambiguità e suggerire di quotare il valore.
    bad = _twitch_yaml_with_send("\nsend:\n  mode: on\n")
    with pytest.raises(ConfigError) as excinfo:
        Config.load(_write(tmp_path, bad))
    message = str(excinfo.value)
    assert "twitch.send.mode: usa 'off', 'shadow' o 'live'" in message
    assert "quota il valore: YAML interpreta on/yes/true come booleano" in message


def test_twitch_send_shadow_requires_public_mode(tmp_path):
    bad = _twitch_yaml_with_send("\nsend:\n  mode: shadow\n").replace(
        "mode: public", "mode: private"
    )
    with pytest.raises(ConfigError, match="'shadow' richiede mode: public"):
        Config.load(_write(tmp_path, bad))


def test_twitch_send_shadow_allowed_in_public_mode(tmp_path):
    yaml_text = _twitch_yaml_with_send("\nsend:\n  mode: shadow\n")

    cfg = Config.load(_write(tmp_path, yaml_text))

    assert cfg.mode is OutputMode.PUBLIC
    assert cfg.twitch.send.mode is TwitchSendMode.SHADOW


def test_twitch_send_off_allowed_in_private_mode(tmp_path):
    yaml_text = _twitch_yaml_with_send("\nsend:\n  mode: 'off'\n").replace(
        "mode: public", "mode: private"
    )

    cfg = Config.load(_write(tmp_path, yaml_text))

    assert cfg.mode is OutputMode.PRIVATE
    assert cfg.twitch.send.mode is TwitchSendMode.OFF


def test_twitch_send_live_requires_channel_in_allowed_channels(tmp_path, monkeypatch):
    monkeypatch.setenv("TWITCH_SEND_OAUTH_TOKEN", "oauth:finto-token-di-test")
    bad = _twitch_yaml_with_send(
        """
        send:
          mode: live
          allowed_channels: ["altrocanale"]
        """
    )
    with pytest.raises(ConfigError, match="allowed_channels"):
        Config.load(_write(tmp_path, bad))


def test_twitch_send_live_config_loads_without_write_token(tmp_path, monkeypatch):
    """Lo schema è puro rispetto all'ambiente: la PRESENZA del token di
    scrittura è verificata al build dell'agente (vedi test_app/test_cli),
    non a `Config.load`."""
    monkeypatch.delenv("TWITCH_SEND_OAUTH_TOKEN", raising=False)
    yaml_text = _twitch_yaml_with_send(
        """
        send:
          mode: live
          allowed_channels: ["minnarone"]
        """
    )

    cfg = Config.load(_write(tmp_path, yaml_text))

    assert cfg.twitch.send.mode is TwitchSendMode.LIVE


def test_twitch_send_live_error_never_contains_token_value(tmp_path, monkeypatch):
    secret = "oauth:segretissimo-non-deve-apparire"
    monkeypatch.setenv("TWITCH_SEND_OAUTH_TOKEN", secret)
    bad = _twitch_yaml_with_send(
        """
        send:
          mode: live
          allowed_channels: ["altrocanale"]
        """
    )
    with pytest.raises(ConfigError) as excinfo:
        Config.load(_write(tmp_path, bad))
    assert secret not in str(excinfo.value)


@pytest.mark.parametrize("mode", ["off", "shadow"])
def test_twitch_send_off_and_shadow_never_require_write_token(
    tmp_path, monkeypatch, mode
):
    monkeypatch.delenv("TWITCH_SEND_OAUTH_TOKEN", raising=False)
    yaml_text = _twitch_yaml_with_send(
        f"""
        send:
          mode: {mode}
        """
    )

    cfg = Config.load(_write(tmp_path, yaml_text))

    assert cfg.twitch.send.mode is TwitchSendMode(mode)


def test_twitch_send_live_valid_when_armed_and_token_present(tmp_path, monkeypatch):
    monkeypatch.setenv("TWITCH_SEND_OAUTH_TOKEN", "oauth:finto-token-di-test")
    yaml_text = _twitch_yaml_with_send(
        """
        send:
          mode: live
          allowed_channels: ["#Minnarone"]
        """
    )

    cfg = Config.load(_write(tmp_path, yaml_text))

    assert cfg.twitch.send.mode is TwitchSendMode.LIVE
    assert cfg.twitch.channel in cfg.twitch.send.allowed_channels


# ---------------------------------------------------------------------------
# Issue 01: new CommentatorStyle enum values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("meeting_synthesizer", CommentatorStyle.MEETING_SYNTHESIZER),
        ("suggester", CommentatorStyle.SUGGESTER),
    ],
)
def test_new_commentator_style_enum_values_coerce_from_string(raw, expected):
    assert CommentatorStyle(raw) is expected


# ---------------------------------------------------------------------------
# Issue 01: ProfileConfig dataclasses — defaults
# ---------------------------------------------------------------------------


def test_operator_profile_config_defaults():
    cfg = OperatorProfileConfig()
    assert cfg.idle_interval is None


def test_original_chat_profile_config_defaults():
    cfg = OriginalChatProfileConfig()
    assert cfg.idle_interval is None


def test_meeting_synthesizer_profile_config_defaults():
    cfg = MeetingSynthesizerProfileConfig()
    assert cfg.interval_s == 180.0


def test_suggester_profile_config_instantiates():
    cfg = SuggesterProfileConfig()
    assert isinstance(cfg, SuggesterProfileConfig)


# ---------------------------------------------------------------------------
# Issue 01: ProfileConfig dataclasses — validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [0, -1, -0.5])
def test_operator_profile_config_rejects_non_positive_idle_interval(bad_value):
    with pytest.raises(ConfigError, match="OperatorProfileConfig.idle_interval"):
        OperatorProfileConfig(idle_interval=bad_value)


def test_operator_profile_config_rejects_boolean_idle_interval():
    with pytest.raises(ConfigError, match="OperatorProfileConfig.idle_interval"):
        OperatorProfileConfig(idle_interval=True)  # type: ignore[arg-type]


def test_operator_profile_config_accepts_valid_idle_interval():
    cfg = OperatorProfileConfig(idle_interval=10.0)
    assert cfg.idle_interval == 10.0


@pytest.mark.parametrize("bad_value", [0, -1, -0.5])
def test_original_chat_profile_config_rejects_non_positive_idle_interval(bad_value):
    with pytest.raises(ConfigError, match="OriginalChatProfileConfig.idle_interval"):
        OriginalChatProfileConfig(idle_interval=bad_value)


def test_original_chat_profile_config_rejects_boolean_idle_interval():
    with pytest.raises(ConfigError, match="OriginalChatProfileConfig.idle_interval"):
        OriginalChatProfileConfig(idle_interval=True)  # type: ignore[arg-type]


def test_original_chat_profile_config_accepts_valid_idle_interval():
    cfg = OriginalChatProfileConfig(idle_interval=5.5)
    assert cfg.idle_interval == 5.5


@pytest.mark.parametrize("bad_value", [0, -1, -180.0])
def test_meeting_synthesizer_profile_config_rejects_non_positive_interval_s(bad_value):
    with pytest.raises(ConfigError, match="MeetingSynthesizerProfileConfig.interval_s"):
        MeetingSynthesizerProfileConfig(interval_s=bad_value)


def test_meeting_synthesizer_profile_config_rejects_boolean_interval_s():
    with pytest.raises(ConfigError, match="MeetingSynthesizerProfileConfig.interval_s"):
        MeetingSynthesizerProfileConfig(interval_s=True)  # type: ignore[arg-type]


def test_meeting_synthesizer_profile_config_accepts_valid_interval_s():
    cfg = MeetingSynthesizerProfileConfig(interval_s=60.0)
    assert cfg.interval_s == 60.0


# ---------------------------------------------------------------------------
# Issue 01: ProfileConfig dataclasses — frozen
# ---------------------------------------------------------------------------


def test_profile_configs_are_frozen():
    with pytest.raises(AttributeError):
        OperatorProfileConfig().__setattr__("idle_interval", 1.0)
    with pytest.raises(AttributeError):
        OriginalChatProfileConfig().__setattr__("idle_interval", 1.0)
    with pytest.raises(AttributeError):
        MeetingSynthesizerProfileConfig().__setattr__("interval_s", 1.0)
    # SuggesterProfileConfig has no fields; empty frozen slotted dataclasses
    # raise TypeError on __setattr__ in CPython 3.12 — both error types confirm
    # immutability.
    with pytest.raises((AttributeError, TypeError)):
        SuggesterProfileConfig().__setattr__("x", 1)
