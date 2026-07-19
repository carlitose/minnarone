"""Speaker embedding, online clustering, and audio speaker labels."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from .asr import AsrInputError, pcm_s16le_to_float32
from .audio import OTHER, STREAMER, UNKNOWN_SPEAKER, SpeechSegment


class SpeakerConfigError(ValueError):
    """Invalid speaker tagging configuration."""


class SpeakerEmbeddingError(RuntimeError):
    """Speaker embedding extraction failed."""


@runtime_checkable
class SpeakerEmbeddingBackend(Protocol):
    """Extract one normalized speaker embedding from one VAD utterance."""

    def embed(self, segment: SpeechSegment) -> tuple[float, ...]:
        """Return a normalized speaker embedding for `segment`."""
        ...


@dataclass(frozen=True, slots=True)
class SpeakerEmbeddingConfig:
    """Configuration for sherpa-onnx speaker embedding extraction."""

    model_path: str | Path | None = None
    provider: str = "cpu"
    num_threads: int = 1
    dimension: int = 192

    def __post_init__(self) -> None:
        model_path = self.model_path
        if model_path is not None:
            if isinstance(model_path, Path):
                model_path = model_path.expanduser()
            elif isinstance(model_path, str):
                if not model_path.strip():
                    raise SpeakerConfigError("model_path must be a non-empty path")
                model_path = Path(model_path).expanduser()
            else:
                raise SpeakerConfigError("model_path must be a non-empty path")
        provider = _non_empty_string(self.provider, "provider")
        num_threads = _positive_int(self.num_threads, "num_threads")
        dimension = _positive_int(self.dimension, "dimension")
        object.__setattr__(self, "model_path", model_path)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "num_threads", num_threads)
        object.__setattr__(self, "dimension", dimension)


@dataclass(frozen=True, slots=True)
class SpeakerClusteringConfig:
    """Tuning knobs for online speaker clustering."""

    # Join floor di similarità coseno: più alto = più splitting. 0.45 è un
    # punto di partenza ragionevole per CAM++ su parlato non-mandarino con
    # segmenti brevi (0.6 sovra-segmentava); tarare per modello/lingua (vedi docs).
    threshold: float = 0.45
    warmup_seconds: float = 60.0
    min_update_seconds: float = 1.0

    def __post_init__(self) -> None:
        threshold = _finite_float(self.threshold, "threshold")
        warmup_seconds = _finite_float(self.warmup_seconds, "warmup_seconds")
        min_update_seconds = _finite_float(
            self.min_update_seconds, "min_update_seconds"
        )
        if not 0.0 <= threshold <= 1.0:
            raise SpeakerConfigError("threshold must be between 0 and 1")
        if warmup_seconds < 0:
            raise SpeakerConfigError("warmup_seconds must be >= 0")
        if min_update_seconds < 0:
            raise SpeakerConfigError("min_update_seconds must be >= 0")
        object.__setattr__(self, "threshold", threshold)
        object.__setattr__(self, "warmup_seconds", warmup_seconds)
        object.__setattr__(self, "min_update_seconds", min_update_seconds)


@dataclass(frozen=True, slots=True)
class SpeakerAssignment:
    """Observable result for one utterance speaker assignment."""

    label: str
    cluster_id: int | None
    similarity: float | None


@dataclass(frozen=True, slots=True)
class SpeakerClusterStats:
    """Diagnostic state for one online speaker cluster."""

    cluster_id: int
    label: str
    talk_time_seconds: float
    updates: int
    centroid: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class SpeakerTaggingStats:
    """Snapshot of speaker clustering diagnostics."""

    total_utterances: int
    clustered_utterances: int
    unknown_utterances: int
    streamer_cluster_id: int | None
    clusters: tuple[SpeakerClusterStats, ...]


@dataclass(slots=True)
class _Cluster:
    cluster_id: int
    centroid: tuple[float, ...]
    talk_time_seconds: float
    updates: int


class OnlineSpeakerClusterer:
    """Assign normalized speaker embeddings to stable online speaker labels."""

    def __init__(self, config: SpeakerClusteringConfig | None = None) -> None:
        self._config = config or SpeakerClusteringConfig()
        self._clusters: list[_Cluster] = []
        self._next_cluster_id = 1
        self._total_utterances = 0
        self._clustered_utterances = 0
        self._unknown_utterances = 0
        self._total_clustered_seconds = 0.0
        self._streamer_cluster_id: int | None = None
        # Clusters pinned as streamer by the operator (issue 03). Multiple pins
        # are allowed (multi-streamer). Once non-empty, the auto-dominant freeze
        # is disabled so it can never steal a manually marked cluster.
        self._manual_streamer_ids: set[int] = set()
        # cluster_id of the most-recent *assigned* (clustered) utterance; the
        # anchor for "mark current speaker". None until the first assignment.
        self._last_cluster_id: int | None = None

    def assign(
        self, embedding: Sequence[float], *, duration_seconds: float
    ) -> SpeakerAssignment:
        """Assign one utterance embedding to a speaker label."""
        self._total_utterances += 1
        duration = _finite_float(duration_seconds, "duration_seconds")
        if duration < self._config.min_update_seconds:
            return self._unknown()

        vector = _normalize(embedding)
        if vector is None:
            return self._unknown()
        if self._clusters and len(vector) != len(self._clusters[0].centroid):
            return self._unknown()

        cluster, similarity = self._best_cluster(vector)
        if cluster is None or similarity < self._config.threshold:
            cluster = self._new_cluster(vector, duration)
            similarity = None
        else:
            self._update_cluster(cluster, vector, duration)

        self._clustered_utterances += 1
        self._total_clustered_seconds += duration
        self._last_cluster_id = cluster.cluster_id
        self._freeze_streamer_if_ready()
        return SpeakerAssignment(
            label=self._label_for(cluster),
            cluster_id=cluster.cluster_id,
            similarity=similarity,
        )

    def mark_current_speaker_as_streamer(self) -> int | None:
        """Pin the most-recent assigned utterance's cluster as a manual streamer.

        "Current speaker" is the cluster of the last *assigned* utterance, not an
        audio snapshot: short ``?`` utterances (no cluster) never update it. From
        here on ``_label_for`` returns ``STREAMER`` for the pinned cluster, and
        the auto-dominant freeze is disabled so it cannot steal the manual pin.
        Multiple pins accumulate (multi-streamer). Returns the pinned cluster id,
        or ``None`` when no utterance has been assigned yet.

        Recording a pin also revokes any stale auto-dominant pick: if the freeze
        already crowned a *different* cluster before the operator marked one, that
        cluster must no longer label ``STREAMER`` (manual takes precedence).
        """
        if self._last_cluster_id is None:
            return None
        self._manual_streamer_ids.add(self._last_cluster_id)
        # Manual marking supersedes the auto-dominant pick: revoke it so only
        # manual pins can label STREAMER from now on (issue 03).
        self._streamer_cluster_id = None
        return self._last_cluster_id

    def stats(self) -> SpeakerTaggingStats:
        """Return a deterministic diagnostics snapshot."""
        return SpeakerTaggingStats(
            total_utterances=self._total_utterances,
            clustered_utterances=self._clustered_utterances,
            unknown_utterances=self._unknown_utterances,
            streamer_cluster_id=self._streamer_cluster_id,
            clusters=tuple(
                SpeakerClusterStats(
                    cluster_id=cluster.cluster_id,
                    label=self._label_for(cluster),
                    talk_time_seconds=cluster.talk_time_seconds,
                    updates=cluster.updates,
                    centroid=cluster.centroid,
                )
                for cluster in self._clusters
            ),
        )

    def _best_cluster(self, vector: tuple[float, ...]) -> tuple[_Cluster | None, float]:
        best_cluster: _Cluster | None = None
        best_similarity = -1.0
        for cluster in self._clusters:
            similarity = _dot(cluster.centroid, vector)
            if similarity > best_similarity:
                best_similarity = similarity
                best_cluster = cluster
        return best_cluster, best_similarity

    def _new_cluster(self, vector: tuple[float, ...], duration: float) -> _Cluster:
        cluster = _Cluster(
            cluster_id=self._next_cluster_id,
            centroid=vector,
            talk_time_seconds=duration,
            updates=1,
        )
        self._next_cluster_id += 1
        self._clusters.append(cluster)
        return cluster

    def _update_cluster(
        self, cluster: _Cluster, vector: tuple[float, ...], duration: float
    ) -> None:
        weight = cluster.updates
        averaged = tuple(
            ((value * weight) + incoming) / (weight + 1)
            for value, incoming in zip(cluster.centroid, vector, strict=True)
        )
        normalized = _normalize(averaged)
        if normalized is not None:
            cluster.centroid = normalized
        cluster.talk_time_seconds += duration
        cluster.updates += 1

    def _freeze_streamer_if_ready(self) -> None:
        # A manual pin disables the auto-dominant fallback entirely so the freeze
        # can never steal an operator-marked cluster (issue 03).
        if self._manual_streamer_ids:
            return
        if self._streamer_cluster_id is not None:
            return
        if self._total_clustered_seconds < self._config.warmup_seconds:
            return
        if not self._clusters:
            return
        dominant = max(self._clusters, key=lambda cluster: cluster.talk_time_seconds)
        self._streamer_cluster_id = dominant.cluster_id

    def _label_for(self, cluster: _Cluster) -> str:
        if cluster.cluster_id in self._manual_streamer_ids:
            return STREAMER
        if cluster.cluster_id == self._streamer_cluster_id:
            return STREAMER
        return OTHER

    def _unknown(self) -> SpeakerAssignment:
        self._unknown_utterances += 1
        return SpeakerAssignment(
            label=UNKNOWN_SPEAKER,
            cluster_id=None,
            similarity=None,
        )


class SherpaOnnxSpeakerEmbeddingBackend:
    """`SpeakerEmbeddingBackend` implementation backed by `sherpa_onnx`."""

    def __init__(
        self,
        config: SpeakerEmbeddingConfig,
        *,
        sherpa_module: object | None = None,
    ) -> None:
        self._config = config
        if config.model_path is None:
            raise SpeakerEmbeddingError(
                "speaker embedding model_path is missing: configure an ONNX file"
            )
        if not config.model_path.is_file():
            raise SpeakerEmbeddingError(
                f"speaker embedding model not found: {config.model_path}"
            )
        module = sherpa_module or _import_sherpa_onnx()
        try:
            extractor_config = module.SpeakerEmbeddingExtractorConfig(
                model=str(config.model_path),
                num_threads=config.num_threads,
                provider=config.provider,
            )
            self._extractor = module.SpeakerEmbeddingExtractor(extractor_config)
        except Exception as exc:  # noqa: BLE001 - wrap backend-specific failures.
            raise SpeakerEmbeddingError(
                "sherpa-onnx speaker embedding setup failed "
                f"(model={str(config.model_path)!r}, "
                f"provider={config.provider!r}, "
                f"num_threads={config.num_threads!r}): {exc}"
            ) from exc

    @property
    def config(self) -> SpeakerEmbeddingConfig:
        """Effective backend configuration."""
        return self._config

    def embed(self, segment: SpeechSegment) -> tuple[float, ...]:
        """Extract and normalize one speaker embedding from a VAD utterance."""
        if segment.sample_rate != 16_000:
            raise SpeakerEmbeddingError("SpeechSegment.sample_rate must be 16000 Hz")
        try:
            waveform = pcm_s16le_to_float32(segment.samples)
        except AsrInputError as exc:
            raise SpeakerEmbeddingError(str(exc)) from exc

        try:
            stream = self._extractor.create_stream()
            stream.accept_waveform(sample_rate=segment.sample_rate, waveform=waveform)
            stream.input_finished()
            if not self._extractor.is_ready(stream):
                raise SpeakerEmbeddingError("sherpa-onnx stream is not ready")
            embedding = self._extractor.compute(stream)
        except SpeakerEmbeddingError:
            raise
        except Exception as exc:  # noqa: BLE001 - wrap backend-specific failures.
            raise SpeakerEmbeddingError(
                f"sherpa-onnx speaker embedding failed: {exc}"
            ) from exc

        normalized = _normalize(embedding)
        if normalized is None:
            raise SpeakerEmbeddingError("sherpa-onnx produced an empty embedding")
        if len(normalized) != self._config.dimension:
            raise SpeakerEmbeddingError(
                "unexpected speaker embedding dimension: "
                f"{len(normalized)} != {self._config.dimension}"
            )
        return normalized


class EmbeddingSpeakerTagger:
    """`SpeakerTagger` implementation backed by embeddings and online clustering."""

    def __init__(
        self,
        embedding_backend: SpeakerEmbeddingBackend,
        clusterer: OnlineSpeakerClusterer | None = None,
    ) -> None:
        self._embedding_backend = embedding_backend
        self._clusterer = clusterer or OnlineSpeakerClusterer()

    def tag(self, segment: SpeechSegment) -> str:
        """Return `streamer`, `altro`, or `?` for one VAD utterance."""
        embedding = self._embedding_backend.embed(segment)
        duration = speech_segment_duration_seconds(segment)
        return self._clusterer.assign(
            embedding,
            duration_seconds=duration,
        ).label

    def mark_current_speaker_as_streamer(self) -> int | None:
        """Pin the current speaker's cluster as a manual streamer (issue 03)."""
        return self._clusterer.mark_current_speaker_as_streamer()

    def stats(self) -> SpeakerTaggingStats:
        """Expose clustering diagnostics for operators and tests."""
        return self._clusterer.stats()


def speech_segment_duration_seconds(segment: SpeechSegment) -> float:
    """Infer utterance duration from mono signed 16-bit PCM bytes."""
    if segment.sample_rate <= 0:
        return 0.0
    samples = segment.samples
    if isinstance(samples, (bytes, bytearray, memoryview)):
        return len(samples) / (segment.sample_rate * 2)
    return 0.0


def _normalize(values: Sequence[float]) -> tuple[float, ...] | None:
    try:
        vector = tuple(float(value) for value in values)
    except (TypeError, ValueError):
        return None
    if not vector:
        return None
    if any(not math.isfinite(value) for value in vector):
        return None
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0.0:
        return None
    return tuple(value / norm for value in vector)


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        return -1.0
    return sum(a * b for a, b in zip(left, right, strict=True))


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise SpeakerConfigError(f"{field_name} must be numeric")
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise SpeakerConfigError(f"{field_name} must be numeric") from exc
    if not math.isfinite(parsed):
        raise SpeakerConfigError(f"{field_name} must be finite")
    return parsed


def _positive_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise SpeakerConfigError(f"{field_name} must be an integer >= 1")
    if isinstance(value, float) and not value.is_integer():
        raise SpeakerConfigError(f"{field_name} must be an integer >= 1")
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise SpeakerConfigError(f"{field_name} must be an integer >= 1") from exc
    if parsed < 1:
        raise SpeakerConfigError(f"{field_name} must be an integer >= 1")
    return parsed


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpeakerConfigError(f"{field_name} must be a non-empty string")
    return value.strip()


def _import_sherpa_onnx() -> object:
    try:
        return __import__("sherpa_onnx")
    except ImportError as exc:
        raise SpeakerEmbeddingError(
            "sherpa-onnx is not installed: install the 'sherpa-onnx' package "
            "before enabling local speaker embedding"
        ) from exc
