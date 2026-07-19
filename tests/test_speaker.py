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

    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "altro"
    assert clusterer.assign([0.98, 0.2], duration_seconds=1.0).label == "altro"
    assert clusterer.assign([0.0, 1.0], duration_seconds=1.0).label == "altro"

    stats = clusterer.stats()
    assert stats.total_utterances == 3
    assert stats.clustered_utterances == 3
    assert stats.unknown_utterances == 0
    assert [(c.label, c.updates) for c in stats.clusters] == [
        ("altro", 2),
        ("altro", 1),
    ]
    assert stats.clusters[0].centroid == pytest.approx((0.995, 0.1005), abs=0.001)


def test_distinct_non_streamer_voices_share_altro_label_but_differ_by_cluster_id():
    clusterer = OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=999.0,
            min_update_seconds=0.0,
        )
    )

    first = clusterer.assign([1.0, 0.0], duration_seconds=1.0)
    second = clusterer.assign([0.0, 1.0], duration_seconds=1.0)

    assert first.label == "altro"
    assert second.label == "altro"
    assert first.cluster_id != second.cluster_id

    stats = clusterer.stats()
    assert [c.label for c in stats.clusters] == ["altro", "altro"]
    assert [c.cluster_id for c in stats.clusters] == [
        first.cluster_id,
        second.cluster_id,
    ]


def test_clusterer_freezes_dominant_speaker_after_warmup_without_label_churn():
    clusterer = OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=3.0,
            min_update_seconds=0.0,
        )
    )

    assert clusterer.assign([1.0, 0.0], duration_seconds=2.0).label == "altro"
    assert clusterer.assign([0.0, 1.0], duration_seconds=1.0).label == "altro"
    assert clusterer.stats().streamer_cluster_id == 1

    assert clusterer.assign([0.0, 1.0], duration_seconds=10.0).label == "altro"
    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "streamer"

    stats = clusterer.stats()
    assert stats.streamer_cluster_id == 1
    assert [(c.label, c.talk_time_seconds) for c in stats.clusters] == [
        ("streamer", 3.0),
        ("altro", 11.0),
    ]


def test_short_utterance_emits_unknown_and_does_not_update_centroids():
    clusterer = OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=999.0,
            min_update_seconds=1.0,
        )
    )
    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "altro"
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
    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "altro"

    mismatched = clusterer.assign([1.0, 0.0, 0.0], duration_seconds=1.0)

    assert mismatched.label == "?"
    stats = clusterer.stats()
    assert stats.clustered_utterances == 1
    assert stats.unknown_utterances == 1
    assert len(stats.clusters) == 1


# --- Manual streamer pinning (issue 03) ---------------------------------------


def _pinning_clusterer() -> OnlineSpeakerClusterer:
    # warmup effectively disabled so auto-freeze never fires on its own.
    return OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=999.0,
            min_update_seconds=0.0,
        )
    )


def test_mark_current_speaker_pins_last_cluster_as_streamer():
    clusterer = _pinning_clusterer()
    first = clusterer.assign([1.0, 0.0], duration_seconds=1.0)
    assert first.label == "altro"

    pinned = clusterer.mark_current_speaker_as_streamer()
    assert pinned == first.cluster_id

    again = clusterer.assign([1.0, 0.0], duration_seconds=1.0)
    assert again.label == "streamer"
    assert again.cluster_id == first.cluster_id


def test_mark_current_speaker_rejected_before_any_utterance():
    clusterer = _pinning_clusterer()
    assert clusterer.mark_current_speaker_as_streamer() is None


def test_mark_current_speaker_ignores_short_unknown_utterance():
    # A sub-min-update utterance is `?` (no cluster): the pin targets the last
    # *assigned* cluster, not the unknown one.
    clusterer = OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=999.0,
            min_update_seconds=1.0,
        )
    )
    first = clusterer.assign([1.0, 0.0], duration_seconds=1.0)
    assert first.label == "altro"
    assert clusterer.assign([0.0, 1.0], duration_seconds=0.25).label == "?"

    pinned = clusterer.mark_current_speaker_as_streamer()
    assert pinned == first.cluster_id


def test_mark_current_speaker_supports_multiple_streamers():
    clusterer = _pinning_clusterer()
    a = clusterer.assign([1.0, 0.0], duration_seconds=1.0)
    assert clusterer.mark_current_speaker_as_streamer() == a.cluster_id
    b = clusterer.assign([0.0, 1.0], duration_seconds=1.0)
    assert clusterer.mark_current_speaker_as_streamer() == b.cluster_id

    assert a.cluster_id != b.cluster_id
    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "streamer"
    assert clusterer.assign([0.0, 1.0], duration_seconds=1.0).label == "streamer"
    assert {c.label for c in clusterer.stats().clusters} == {"streamer"}


def test_manual_pin_takes_precedence_and_is_not_stolen_by_auto_freeze():
    clusterer = OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=3.0,
            min_update_seconds=0.0,
        )
    )
    first = clusterer.assign([1.0, 0.0], duration_seconds=1.0)
    assert first.cluster_id == 1
    assert clusterer.mark_current_speaker_as_streamer() == 1

    # Cluster 2 dominates by talk time and crosses warmup; without a manual pin
    # the auto-freeze would crown cluster 2. The manual pin must win.
    clusterer.assign([0.0, 1.0], duration_seconds=10.0)

    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "streamer"
    assert clusterer.assign([0.0, 1.0], duration_seconds=1.0).label == "altro"
    # Auto-freeze never fired: it is disabled once a manual pin exists.
    assert clusterer.stats().streamer_cluster_id is None


def test_manual_pin_supersedes_a_stale_auto_pick_on_a_different_cluster():
    # Auto-freeze crowns cluster 1 FIRST; the operator then marks a DIFFERENT
    # cluster (cluster 2). The stale auto pick must be revoked so only the
    # manually pinned cluster labels STREAMER (issue 03 acceptance criteria).
    clusterer = OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=1.0,
            min_update_seconds=0.0,
        )
    )
    first = clusterer.assign([1.0, 0.0], duration_seconds=2.0)
    assert first.cluster_id == 1
    # Warmup crossed on cluster 1 -> auto-dominant freeze crowned cluster 1.
    assert clusterer.stats().streamer_cluster_id == 1

    second = clusterer.assign([0.0, 1.0], duration_seconds=1.0)
    assert second.cluster_id == 2
    assert clusterer.mark_current_speaker_as_streamer() == 2

    labels = {c.cluster_id: c.label for c in clusterer.stats().clusters}
    assert labels[1] == "altro"
    assert labels[2] == "streamer"
    # Manual pin active -> the stale auto pick is revoked.
    assert clusterer.stats().streamer_cluster_id is None


def test_auto_freeze_remains_fallback_until_first_manual_pin():
    clusterer = OnlineSpeakerClusterer(
        SpeakerClusteringConfig(
            threshold=0.8,
            warmup_seconds=3.0,
            min_update_seconds=0.0,
        )
    )
    # No manual pin -> auto-dominant freeze still works (existing behavior).
    clusterer.assign([1.0, 0.0], duration_seconds=2.0)
    clusterer.assign([0.0, 1.0], duration_seconds=1.0)
    assert clusterer.stats().streamer_cluster_id == 1
    assert clusterer.assign([1.0, 0.0], duration_seconds=1.0).label == "streamer"


def test_embedding_tagger_delegates_marking_to_clusterer():
    class ConstantBackend:
        def embed(self, segment):
            return (1.0, 0.0)

    clusterer = _pinning_clusterer()
    tagger = EmbeddingSpeakerTagger(ConstantBackend(), clusterer)

    segment = SpeechSegment(
        samples=struct.pack("<h", 1000) * 16_000,
        sample_rate=16_000,
    )
    assert tagger.tag(segment) == "altro"
    assert tagger.mark_current_speaker_as_streamer() == 1
    assert tagger.tag(segment) == "streamer"


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
    assert list(FakeSherpa.stream.waveform) == pytest.approx([-1.0, 0.0, 32767 / 32768])
    assert FakeSherpa.stream.finished is True
    assert embedding == pytest.approx((0.6, 0.8))


def test_sherpa_backend_fails_clearly_when_model_file_is_missing(tmp_path):
    with pytest.raises(SpeakerEmbeddingError, match="model not found"):
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
