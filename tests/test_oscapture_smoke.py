"""Comportamento del runner di smoke capture-only per la cattura del SO.

Testa `run_oscapture_smoke` con sorgenti fake in-memory (liste di `AudioChunk` /
`VideoFrame`): artifact scritti sotto una tmp dir, conteggi eventi corretti,
failure segnalata su zero eventi per un canale abilitato, e capture-only
(nessun ASR/VLM invocato).
"""

import asyncio
import json

import pytest

from minnarone.audio import AudioChunk, SpeechSegment
from minnarone.oscapture_smoke import main, run_oscapture_smoke
from minnarone.twitch_smoke_artifacts import SmokeStats
from minnarone.video import VideoFrame


class _ExplodingSource:
    """Sorgente device che fallisce all'apertura (prima iterazione)."""

    def __init__(self, message: str) -> None:
        self._message = message

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError(self._message)


class _TrackingSource:
    """Sorgente che registra se è stata iterata (per il contratto lazy)."""

    def __init__(self) -> None:
        self.iterated = False

    def __aiter__(self):
        self.iterated = True
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class _OneSegmentVad:
    """VAD diagnostico deterministico: un segmento per chunk."""

    def __init__(self) -> None:
        self.calls = 0

    def segments(self, chunk: AudioChunk):
        self.calls += 1
        return [
            SpeechSegment(
                samples=chunk.samples,
                sample_rate=chunk.sample_rate,
                source_label=chunk.source_label,
                ts=chunk.ts,
            )
        ]


def _audio_chunk(samples: bytes, *, ts: float) -> AudioChunk:
    return AudioChunk(samples=samples, sample_rate=16_000, source_label="system", ts=ts)


def _video_frame(pixels: bytes, *, ts: float) -> VideoFrame:
    return VideoFrame(pixels=pixels, source_label="screen", ts=ts)


def test_run_oscapture_smoke_writes_audio_and_video_artifacts(tmp_path):
    output = tmp_path / "smoke"
    audio_source = [
        _audio_chunk(b"\x01\x02", ts=1.0),
        _audio_chunk(b"\x03\x04", ts=2.0),
    ]
    video_source = [
        _video_frame(b"jpeg-a", ts=1.0),
        _video_frame(b"jpeg-b", ts=2.0),
    ]

    stats = asyncio.run(
        run_oscapture_smoke(
            output_dir=output,
            duration=1.0,
            enable_audio=True,
            enable_video=True,
            audio_source=audio_source,
            video_source=video_source,
        )
    )

    assert stats.audio_events == 2
    assert stats.video_events == 2
    assert stats.audio_samples_saved == 2
    assert stats.video_frames_saved == 2
    assert stats.failures == []

    audio_samples = sorted((output / "raw" / "audio").glob("*.pcm"))
    video_frames = sorted((output / "raw" / "video").glob("*.jpg"))
    assert len(audio_samples) == 2
    assert len(video_frames) == 2

    stats_json = json.loads((output / "stats.json").read_text(encoding="utf-8"))
    assert stats_json["audio_events"] == 2
    assert stats_json["video_events"] == 2


def test_run_oscapture_smoke_audio_only_skips_video(tmp_path):
    output = tmp_path / "smoke"
    audio_source = [_audio_chunk(b"\x01\x02", ts=1.0)]

    stats = asyncio.run(
        run_oscapture_smoke(
            output_dir=output,
            duration=1.0,
            enable_audio=True,
            enable_video=False,
            audio_source=audio_source,
        )
    )

    assert stats.audio_events == 1
    assert stats.video_events == 0
    assert stats.failures == []
    assert sorted((output / "raw" / "video").glob("*.jpg")) == []


def test_run_oscapture_smoke_respects_sample_and_frame_caps(tmp_path):
    output = tmp_path / "smoke"
    audio_source = [_audio_chunk(b"\x01\x02", ts=float(i)) for i in range(5)]
    video_source = [_video_frame(b"jpeg", ts=float(i)) for i in range(5)]

    stats = asyncio.run(
        run_oscapture_smoke(
            output_dir=output,
            duration=1.0,
            enable_audio=True,
            enable_video=True,
            max_audio_samples=2,
            max_video_frames=1,
            audio_source=audio_source,
            video_source=video_source,
        )
    )

    assert stats.audio_events == 5
    assert stats.video_events == 5
    assert stats.audio_samples_saved == 2
    assert stats.video_frames_saved == 1
    assert len(sorted((output / "raw" / "audio").glob("*.pcm"))) == 2
    assert len(sorted((output / "raw" / "video").glob("*.jpg"))) == 1


def test_run_oscapture_smoke_zero_events_records_no_failure_but_empty_counts(tmp_path):
    # Il runner scrive gli artifact; la segnalazione di zero-eventi come failure
    # avviene a livello CLI (slice 10). Qui verifichiamo che uno stream vuoto
    # produca semplicemente conteggi a zero senza crash.
    output = tmp_path / "smoke"

    stats = asyncio.run(
        run_oscapture_smoke(
            output_dir=output,
            duration=1.0,
            enable_audio=True,
            enable_video=False,
            audio_source=[],
        )
    )

    assert stats.audio_events == 0
    assert stats.audio_samples_saved == 0
    assert (output / "stats.json").exists()


def test_run_oscapture_smoke_surfaces_channel_failure(tmp_path):
    output = tmp_path / "smoke"

    stats = asyncio.run(
        run_oscapture_smoke(
            output_dir=output,
            duration=1.0,
            enable_audio=True,
            enable_video=False,
            audio_source=_ExplodingSource("device di loopback non disponibile"),
        )
    )

    assert stats.audio_events == 0
    assert any("device di loopback non disponibile" in f for f in stats.failures)


def test_run_oscapture_smoke_requires_at_least_one_channel(tmp_path):
    with pytest.raises(ValueError):
        asyncio.run(
            run_oscapture_smoke(
                output_dir=tmp_path / "smoke",
                duration=1.0,
                enable_audio=False,
                enable_video=False,
            )
        )


def test_run_oscapture_smoke_vad_diagnostic_reports_utterances(tmp_path):
    output = tmp_path / "smoke"
    audio_source = [
        _audio_chunk(b"\x01\x02\x03\x04", ts=1.0),
        _audio_chunk(b"\x05\x06\x07\x08", ts=2.0),
    ]
    vad = _OneSegmentVad()

    stats = asyncio.run(
        run_oscapture_smoke(
            output_dir=output,
            duration=1.0,
            enable_audio=True,
            enable_video=False,
            enable_vad_diagnostic=True,
            audio_source=audio_source,
            vad=vad,
        )
    )

    assert stats.audio_events == 2
    assert stats.vad_utterances == 2
    assert len(stats.vad_utterance_durations_ms) == 2
    assert vad.calls == 2


def test_run_oscapture_smoke_vad_diagnostic_requires_audio(tmp_path):
    with pytest.raises(ValueError):
        asyncio.run(
            run_oscapture_smoke(
                output_dir=tmp_path / "smoke",
                duration=1.0,
                enable_audio=False,
                enable_video=True,
                enable_vad_diagnostic=True,
                video_source=[_video_frame(b"jpeg", ts=1.0)],
            )
        )


def test_run_oscapture_smoke_is_capture_only_no_asr_or_vlm(tmp_path):
    # Capture-only: nessun ASR/VLM viene costruito o invocato. Verifichiamo che i
    # payload catturati siano scritti come raw (pcm/jpg) senza alcuna
    # trascrizione o caption negli artifact.
    output = tmp_path / "smoke"
    audio_source = [_audio_chunk(b"\x01\x02", ts=1.0)]
    video_source = [_video_frame(b"jpeg", ts=1.0)]

    stats = asyncio.run(
        run_oscapture_smoke(
            output_dir=output,
            duration=1.0,
            enable_audio=True,
            enable_video=True,
            audio_source=audio_source,
            video_source=video_source,
        )
    )

    stats_json = json.loads((output / "stats.json").read_text(encoding="utf-8"))
    # Nessun campo di trascrizione/caption: lo stats contiene solo conteggi di
    # cattura e (eventuale) diagnostica VAD.
    assert "transcript" not in stats_json
    assert "caption" not in stats_json
    assert stats.audio_samples_saved == 1
    assert stats.video_frames_saved == 1


def test_run_oscapture_smoke_disabling_audio_does_not_iterate_audio_source(tmp_path):
    output = tmp_path / "smoke"
    audio_source = _TrackingSource()

    stats = asyncio.run(
        run_oscapture_smoke(
            output_dir=output,
            duration=1.0,
            enable_audio=False,
            enable_video=True,
            audio_source=audio_source,
            video_source=[_video_frame(b"jpeg", ts=1.0)],
        )
    )

    assert audio_source.iterated is False
    assert stats.video_events == 1


# --- CLI (main) ---------------------------------------------------------------
#
# I test della CLI pilotano `main(argv)` monkeypatchando `run_oscapture_smoke`
# con un fake: nessun hardware viene aperto. Verificano parsing, validazione e
# mapping degli exit code (0 successo / 1 failure di cattura / 2 input invalido).


def _base_args(tmp_path):
    return ["--duration", "1", "--output", str(tmp_path / "smoke")]


def test_cli_help_opens(capsys):
    # argparse solleva SystemExit(0) su --help; main lo intercetta e ritorna 0.
    code = main(["--help"])
    assert code == 0
    assert "minnarone-oscapture-smoke" in capsys.readouterr().out


def test_cli_audio_and_video_success(tmp_path, monkeypatch):
    calls = []

    async def fake_smoke(**kwargs):
        calls.append(kwargs)
        return SmokeStats(
            audio_events=1,
            audio_samples_saved=1,
            video_events=1,
            video_frames_saved=1,
        )

    monkeypatch.setattr("minnarone.oscapture_smoke.run_oscapture_smoke", fake_smoke)

    code = main(
        _base_args(tmp_path)
        + ["--audio", "--video", "--monitor", "2", "--sample-rate", "8000"]
    )

    assert code == 0
    assert calls[0]["enable_audio"] is True
    assert calls[0]["enable_video"] is True
    assert calls[0]["monitor"] == 2
    assert calls[0]["sample_rate"] == 8000


def test_cli_requires_at_least_one_channel(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "minnarone.oscapture_smoke.run_oscapture_smoke",
        _fail_if_called,
    )

    code = main(_base_args(tmp_path))

    assert code == 2
    assert "almeno" in capsys.readouterr().err


def test_cli_rejects_non_positive_duration(tmp_path, capsys):
    code = main(["--duration", "0", "--output", str(tmp_path / "smoke"), "--audio"])
    assert code == 2
    assert "--duration" in capsys.readouterr().err


def test_cli_rejects_nonfinite_video_fps(tmp_path, capsys):
    code = main(_base_args(tmp_path) + ["--video", "--video-fps", "nan"])
    assert code == 2
    assert "--video-fps" in capsys.readouterr().err


def test_cli_rejects_invalid_monitor(tmp_path, capsys):
    code = main(_base_args(tmp_path) + ["--video", "--monitor", "0"])
    assert code == 2
    assert "--monitor" in capsys.readouterr().err


def test_cli_rejects_invalid_vad_mode(tmp_path, capsys):
    code = main(_base_args(tmp_path) + ["--audio", "--vad-diagnostic", "--vad-mode", "5"])
    assert code == 2
    assert "--vad-mode" in capsys.readouterr().err


def test_cli_rejects_invalid_vad_frame_ms(tmp_path, capsys):
    code = main(
        _base_args(tmp_path) + ["--audio", "--vad-diagnostic", "--vad-frame-ms", "15"]
    )
    assert code == 2
    assert "--vad-frame-ms" in capsys.readouterr().err


def test_cli_rejects_negative_caps(tmp_path, capsys):
    code = main(_base_args(tmp_path) + ["--audio", "--max-audio-samples", "-1"])
    assert code == 2
    assert "--max-audio-samples" in capsys.readouterr().err


def test_cli_capture_failure_maps_to_exit_1(tmp_path, monkeypatch, capsys):
    async def fake_smoke(**_kwargs):
        raise OSError("device di loopback non disponibile")

    monkeypatch.setattr("minnarone.oscapture_smoke.run_oscapture_smoke", fake_smoke)

    code = main(_base_args(tmp_path) + ["--audio"])

    assert code == 1
    assert "fallito" in capsys.readouterr().err


def test_cli_zero_events_maps_to_exit_1(tmp_path, monkeypatch, capsys):
    async def fake_smoke(**_kwargs):
        return SmokeStats(audio_events=0)

    monkeypatch.setattr("minnarone.oscapture_smoke.run_oscapture_smoke", fake_smoke)

    code = main(_base_args(tmp_path) + ["--audio"])

    assert code == 1
    assert "fallito" in capsys.readouterr().err


def test_cli_vad_diagnostic_reports_utterances(tmp_path, monkeypatch, capsys):
    async def fake_smoke(**_kwargs):
        return SmokeStats(
            audio_events=1,
            vad_utterances=2,
            vad_utterance_durations_ms=[300.0, 450.0],
        )

    monkeypatch.setattr("minnarone.oscapture_smoke.run_oscapture_smoke", fake_smoke)

    code = main(_base_args(tmp_path) + ["--audio", "--vad-diagnostic"])

    assert code == 0
    assert "vad_utterances=2" in capsys.readouterr().out


async def _fail_if_called(**_kwargs):
    raise AssertionError("run_oscapture_smoke non deve essere invocato")
