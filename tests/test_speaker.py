"""Deterministic speaker embedding and clustering tests."""

from __future__ import annotations

import struct
import sys

import pytest

from minnarone.audio import SpeechSegment
from minnarone.speaker import (
    EmbeddingSpeakerTagger,
    OnlineSpeakerClusterer,
    SherpaOnnxSpeakerEmbeddingBackend,
    SpeakerClusteringConfig,
    SpeakerEmbeddingConfig,
    SpeakerEmbeddingError,
)


def test_clusterer_updates_matching_centroid_and_creates_new_speaker():
    clusterer = OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=999.0,
            min_update_seconds=0.0,
        )
    )

    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "speaker_1"
    assert (
        clusterer.assign([0.98, 0.2], duration_seconds=1.0).label == "speaker_1"
    )
    assert clusterer.assign([0.0, 1.0], duration_seconds=1.0).label == "speaker_2"

    stats = clusterer.stats()
    assert stats.total_utterances == 3
    assert stats.clustered_utterances == 3
    assert stats.unknown_utterances == 0
    assert [(c.label, c.updates) for c in stats.clusters] == [
        ("speaker_1", 2),
        ("speaker_2", 1),
    ]
    assert stats.clusters[0].centroid == pytest.approx((0.995, 0.1005), abs=0.001)


def test_clusterer_freezes_dominant_speaker_after_warmup_without_label_churn():
    clusterer = OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=3.0,
            min_update_seconds=0.0,
        )
    )

    assert clusterer.assign([1.0, 0.0], duration_seconds=2.0).label == "speaker_1"
    assert clusterer.assign([0.0, 1.0], duration_seconds=1.0).label == "speaker_2"
    assert clusterer.stats().streamer_cluster_id == 1

    assert clusterer.assign([0.0, 1.0], duration_seconds=10.0).label == "speaker_2"
    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "streamer"

    stats = clusterer.stats()
    assert stats.streamer_cluster_id == 1
    assert [(c.label, c.talk_time_seconds) for c in stats.clusters] == [
        ("streamer", 3.0),
        ("speaker_2", 11.0),
    ]


def test_short_utterance_emits_unknown_and_does_not_update_centroids():
    clusterer = OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=999.0,
            min_update_seconds=1.0,
        )
    )
    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "speaker_1"
    original_centroid = clusterer.stats().clusters[0].centroid

    short = clusterer.assign([0.0, 1.0], duration_seconds=0.25)

    assert short.label == "?"
    stats = clusterer.stats()
    assert stats.total_utterances == 2
    assert stats.clustered_utterances == 1
    assert stats.unknown_utterances == 1
    assert len(stats.clusters) == 1
    assert stats.clusters[0].centroid == original_centroid


def test_mismatched_embedding_dimension_is_unknown_and_does_not_create_cluster():
    clusterer = OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=999.0,
            min_update_seconds=0.0,
        )
    )
    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "speaker_1"

    mismatched = clusterer.assign([1.0, 0.0, 0.0], duration_seconds=1.0)

    assert mismatched.label == "?"
    stats = clusterer.stats()
    assert stats.clustered_utterances == 1
    assert stats.unknown_utterances == 1
    assert len(stats.clusters) == 1


def test_sherpa_backend_uses_documented_stream_flow_with_fake_extractor(tmp_path):
    sys.modules.pop("sherpa_onnx", None)
    model_path = tmp_path / "campp.onnx"
    model_path.write_bytes(b"fake-model")

    class FakeStream:
        def __init__(self):
            self.waveform = None
            self.sample_rate = None
            self.finished = False

        def accept_waveform(self, *, sample_rate, waveform):
            self.sample_rate = sample_rate
            self.waveform = waveform

        def input_finished(self):
            self.finished = True

    class FakeSherpa:
        created_config = None
        stream = FakeStream()

        class SpeakerEmbeddingExtractorConfig:
            def __init__(self, *, model, num_threads, provider):
                self.model = model
                self.num_threads = num_threads
                self.provider = provider

        class SpeakerEmbeddingExtractor:
            def __init__(self, config):
                FakeSherpa.created_config = config

            def create_stream(self):
                return FakeSherpa.stream

            def is_ready(self, stream):
                return stream.finished

            def compute(self, stream):
                return [3.0, 4.0]

    backend = SherpaOnnxSpeakerEmbeddingBackend(
        SpeakerEmbeddingConfig(
            model_path=model_path,
            provider="cpu",
            num_threads=2,
            dimension=2,
        ),
        sherpa_module=FakeSherpa,
    )

    embedding = backend.embed(
        SpeechSegment(
            samples=struct.pack("<hhh", -32768, 0, 32767),
            sample_rate=16_000,
            ts=1.0,
        )
    )

    assert "sherpa_onnx" not in sys.modules
    assert FakeSherpa.created_config.model == str(model_path)
    assert FakeSherpa.created_config.provider == "cpu"
    assert FakeSherpa.created_config.num_threads == 2
    assert FakeSherpa.stream.sample_rate == 16_000
    assert list(FakeSherpa.stream.waveform) == pytest.approx(
        [-1.0, 0.0, 32767 / 32768]
    )
    assert FakeSherpa.stream.finished is True
    assert embedding == pytest.approx((0.6, 0.8))


def test_sherpa_backend_fails_clearly_when_model_file_is_missing(tmp_path):
    with pytest.raises(SpeakerEmbeddingError, match="model non trovato"):
        SherpaOnnxSpeakerEmbeddingBackend(
            SpeakerEmbeddingConfig(model_path=tmp_path / "missing.onnx"),
            sherpa_module=object(),
        )


def test_embedding_tagger_propagates_backend_failures():
    class FailingBackend:
        def embed(self, segment):
            raise SpeakerEmbeddingError("backend rotto")

    tagger = EmbeddingSpeakerTagger(FailingBackend())

    with pytest.raises(SpeakerEmbeddingError, match="backend rotto"):
        tagger.tag(
            SpeechSegment(
                samples=struct.pack("<h", 0) * 16_000,
                sample_rate=16_000,
            )
        )
