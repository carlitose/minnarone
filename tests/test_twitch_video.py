"""Twitch raw video capture behavior."""

import asyncio
import sys
import time
from threading import Event
from types import SimpleNamespace

import pytest

from minnarone.twitch_video import (
    DecodedVideoFrame,
    JpegFrameSplitter,
    PyAvVideoFrameDecoder,
    TwitchPyAvVideoReader,
    TwitchVideoReader,
    validate_video_fps,
)
from minnarone.video import VideoFrame

JPEG_A = b"\xff\xd8frame-a\xff\xd9"
JPEG_B = b"\xff\xd8frame-b\xff\xd9"


class _FakeVideoStream:
    def __init__(self, *, fail_on_close: bool = False) -> None:
        self.closed = False
        self.fail_on_close = fail_on_close

    def close(self) -> None:
        self.closed = True
        if self.fail_on_close:
            raise RuntimeError("close exploded")


class _StreamlinkLikeUnreadableStream:
    def __init__(self) -> None:
        self.closed = False

    def read(self, size=-1):
        return b"video-bytes"

    def readable(self):
        return False

    def close(self) -> None:
        self.closed = True


class _FakeStreamOpener:
    def __init__(self, stream: _FakeVideoStream) -> None:
        self._stream = stream
        self.calls = []

    def open(self, *, channel: str, quality: str):
        self.calls.append({"channel": channel, "quality": quality})
        return self._stream


class _FakeFrameDecoder:
    def __init__(self, frames: list[DecodedVideoFrame]) -> None:
        self._frames = list(frames)
        self.streams = []

    def decode(self, stream):
        self.streams.append(stream)
        yield from self._frames


class _FailingFrameDecoder:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def decode(self, stream):
        yield from ()
        raise self._exc


class _WaitingFrameDecoder:
    def __init__(self) -> None:
        self.started = Event()
        self.stopped = Event()

    def decode(self, stream):
        self.started.set()
        while not stream.closed:
            time.sleep(0.001)
        self.stopped.set()
        yield from ()


class _BlockingFrameDecoder:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def decode(self, stream):
        self.started.set()
        while not self.release.is_set():
            time.sleep(0.001)
        yield from ()


class _ManyFrameDecoder:
    def __init__(self, count: int) -> None:
        self._count = count

    def decode(self, stream):
        for index in range(self._count):
            yield DecodedVideoFrame(pixels=f"frame-{index}", time_seconds=float(index))


def test_jpeg_frame_splitter_extracts_frames_across_chunks():
    splitter = JpegFrameSplitter()

    assert splitter.feed(b"noise" + JPEG_A[:4]) == []
    assert splitter.feed(JPEG_A[4:] + JPEG_B) == [JPEG_A, JPEG_B]


def test_jpeg_frame_splitter_preserves_split_start_marker():
    splitter = JpegFrameSplitter()

    assert splitter.feed(b"noise\xff") == []
    assert splitter.feed(b"\xd8frame-a\xff\xd9") == [JPEG_A]


@pytest.mark.parametrize("fps", [0, -1, float("inf"), 11])
def test_video_fps_rejects_invalid_values(fps):
    with pytest.raises(ValueError, match="video_fps"):
        validate_video_fps(fps)


def test_pyav_video_reader_emits_video_frame_payloads_from_fake_decoder():
    stream = _FakeVideoStream()
    opener = _FakeStreamOpener(stream)
    decoder = _FakeFrameDecoder(
        [
            DecodedVideoFrame(pixels="pixels-a", time_seconds=0.0),
            DecodedVideoFrame(pixels="pixels-b", time_seconds=0.2),
        ]
    )
    timestamps = iter([100.0, 101.0])
    reader = TwitchPyAvVideoReader(
        channel="#Minnarone",
        quality="720p",
        fps=10.0,
        stream_opener=opener,
        frame_decoder=decoder,
        clock=lambda: next(timestamps),
    )

    async def run():
        await reader.start()
        events = [event async for event in reader.events()]
        await reader.stop()
        return events

    events = asyncio.run(run())

    assert opener.calls == [{"channel": "minnarone", "quality": "720p"}]
    assert decoder.streams == [stream]
    assert stream.closed is True
    assert [event.channel for event in events] == ["video", "video"]
    assert [event.payload for event in events] == [
        VideoFrame(pixels="pixels-a", source_label="stream", ts=100.0),
        VideoFrame(pixels="pixels-b", source_label="stream", ts=101.0),
    ]


def test_pyav_decoder_wraps_streamlink_reader_that_reports_unreadable(monkeypatch):
    opened = []

    class FakeFrame:
        time = 12.5

        def to_ndarray(self, *, format):
            assert format == "rgb24"
            return "rgb-pixels"

    class FakeContainer:
        def __init__(self, stream):
            self.stream = stream
            self.closed = False

        def decode(self, *, video):
            assert video == 0
            yield FakeFrame()

        def close(self):
            self.closed = True

    def fake_open(stream):
        assert stream.readable() is True
        assert stream.seekable() is False
        opened.append(stream)
        return FakeContainer(stream)

    monkeypatch.setitem(sys.modules, "av", SimpleNamespace(open=fake_open))
    monkeypatch.setitem(sys.modules, "numpy", SimpleNamespace())
    stream = _StreamlinkLikeUnreadableStream()

    frames = list(PyAvVideoFrameDecoder().decode(stream))

    assert len(opened) == 1
    assert opened[0] is not stream
    assert opened[0].read(1) == b"video-bytes"
    assert frames == [DecodedVideoFrame(pixels="rgb-pixels", time_seconds=12.5)]


def test_pyav_video_reader_does_not_restart_after_fast_decoder_completion():
    stream = _FakeVideoStream()
    opener = _FakeStreamOpener(stream)
    reader = TwitchPyAvVideoReader(
        channel="minnarone",
        stream_opener=opener,
        frame_decoder=_FakeFrameDecoder(
            [DecodedVideoFrame(pixels="fast-frame", time_seconds=0.0)]
        ),
        clock=lambda: 50.0,
    )

    async def run():
        await reader.start()
        for _ in range(100):
            if stream.closed:
                break
            await asyncio.sleep(0.01)
        assert stream.closed is True
        return [event async for event in reader.events()]

    events = asyncio.run(run())

    assert opener.calls == [{"channel": "minnarone", "quality": "best"}]
    assert [event.payload.pixels for event in events] == ["fast-frame"]


def test_pyav_video_reader_samples_by_decoded_frame_time():
    stream = _FakeVideoStream()
    opener = _FakeStreamOpener(stream)
    decoder = _FakeFrameDecoder(
        [
            DecodedVideoFrame(pixels="t0.0", time_seconds=0.0),
            DecodedVideoFrame(pixels="t0.4", time_seconds=0.4),
            DecodedVideoFrame(pixels="t1.0", time_seconds=1.0),
            DecodedVideoFrame(pixels="t1.5", time_seconds=1.5),
            DecodedVideoFrame(pixels="t2.2", time_seconds=2.2),
        ]
    )
    timestamps = iter([10.0, 11.0, 12.0])
    reader = TwitchPyAvVideoReader(
        channel="minnarone",
        fps=1.0,
        stream_opener=opener,
        frame_decoder=decoder,
        clock=lambda: next(timestamps),
    )

    async def run():
        return [event async for event in reader.events()]

    events = asyncio.run(run())

    assert [event.payload.pixels for event in events] == ["t0.0", "t1.0", "t2.2"]
    assert [event.ts for event in events] == [10.0, 11.0, 12.0]


def test_pyav_video_reader_samples_untimestamped_frames_by_wall_clock():
    stream = _FakeVideoStream()
    sample_times = iter([0.0, 0.2, 1.0, 1.1, 2.1])
    timestamps = iter([10.0, 11.0, 12.0])
    reader = TwitchPyAvVideoReader(
        channel="minnarone",
        fps=1.0,
        stream_opener=_FakeStreamOpener(stream),
        frame_decoder=_FakeFrameDecoder(
            [
                DecodedVideoFrame(pixels="f0", time_seconds=None),
                DecodedVideoFrame(pixels="f1", time_seconds=None),
                DecodedVideoFrame(pixels="f2", time_seconds=None),
                DecodedVideoFrame(pixels="f3", time_seconds=None),
                DecodedVideoFrame(pixels="f4", time_seconds=None),
            ]
        ),
        sample_clock=lambda: next(sample_times),
        clock=lambda: next(timestamps),
    )

    async def run():
        return [event async for event in reader.events()]

    events = asyncio.run(run())

    assert [event.payload.pixels for event in events] == ["f0", "f2", "f4"]
    assert [event.ts for event in events] == [10.0, 11.0, 12.0]


def test_pyav_video_reader_closes_stream_when_decoder_fails():
    stream = _FakeVideoStream()
    reader = TwitchPyAvVideoReader(
        channel="minnarone",
        stream_opener=_FakeStreamOpener(stream),
        frame_decoder=_FailingFrameDecoder(RuntimeError("decode exploded")),
    )

    async def run():
        with pytest.raises(OSError, match="decode exploded"):
            return [event async for event in reader.events()]

    asyncio.run(run())

    assert stream.closed is True


def test_pyav_video_reader_preserves_failure_when_internal_queue_is_full():
    stream = _FakeVideoStream()
    reader = TwitchPyAvVideoReader(
        channel="minnarone",
        stream_opener=_FakeStreamOpener(stream),
        frame_decoder=_FailingFrameDecoder(RuntimeError("decode exploded")),
        event_queue_size=1,
    )

    async def run():
        await reader.start()
        for _ in range(100):
            if stream.closed:
                break
            await asyncio.sleep(0.01)
        with pytest.raises(OSError, match="decode exploded"):
            async for _event in reader.events():
                pass

    asyncio.run(asyncio.wait_for(run(), timeout=1.0))

    assert stream.closed is True


def test_pyav_video_reader_signals_completion_when_stream_close_fails():
    stream = _FakeVideoStream(fail_on_close=True)
    reader = TwitchPyAvVideoReader(
        channel="minnarone",
        stream_opener=_FakeStreamOpener(stream),
        frame_decoder=_FakeFrameDecoder(
            [DecodedVideoFrame(pixels="one", time_seconds=0.0)]
        ),
        clock=lambda: 1.0,
    )

    async def run():
        return [event async for event in reader.events()]

    events = asyncio.run(asyncio.wait_for(run(), timeout=1.0))

    assert stream.closed is True
    assert [event.payload.pixels for event in events] == ["one"]


def test_pyav_video_reader_stop_closes_stream_and_finishes_decode_worker():
    stream = _FakeVideoStream()
    decoder = _WaitingFrameDecoder()
    reader = TwitchPyAvVideoReader(
        channel="minnarone",
        stream_opener=_FakeStreamOpener(stream),
        frame_decoder=decoder,
    )

    async def run():
        await reader.start()
        assert await asyncio.to_thread(decoder.started.wait, 0.5)
        await reader.stop()
        assert await asyncio.to_thread(decoder.stopped.wait, 0.5)

    asyncio.run(run())

    assert stream.closed is True


def test_pyav_video_reader_cooperative_stop_with_tiny_timeout_does_not_deadlock():
    stream = _FakeVideoStream()
    decoder = _WaitingFrameDecoder()
    reader = TwitchPyAvVideoReader(
        channel="minnarone",
        stream_opener=_FakeStreamOpener(stream),
        frame_decoder=decoder,
        cleanup_timeout=0.01,
    )

    async def run():
        await reader.start()
        assert await asyncio.to_thread(decoder.started.wait, 0.5)
        await reader.stop()
        assert await asyncio.to_thread(decoder.stopped.wait, 0.5)

    asyncio.run(asyncio.wait_for(run(), timeout=1.0))

    assert stream.closed is True


def test_pyav_video_reader_stop_with_full_internal_queue_does_not_hang_consumer():
    stream = _FakeVideoStream()
    reader = TwitchPyAvVideoReader(
        channel="minnarone",
        fps=10.0,
        stream_opener=_FakeStreamOpener(stream),
        frame_decoder=_ManyFrameDecoder(20),
        event_queue_size=1,
        clock=lambda: 1.0,
    )

    async def run():
        await reader.start()
        for _ in range(100):
            queue = reader._queue
            if queue is not None and queue.full():
                break
            await asyncio.sleep(0.01)
        await reader.stop()
        return [event async for event in reader.events()]

    events = asyncio.run(asyncio.wait_for(run(), timeout=2.0))

    assert stream.closed is True
    assert len(events) <= 1


def test_pyav_video_reader_cleanup_timeout_uses_daemon_decode_thread():
    stream = _FakeVideoStream()
    decoder = _BlockingFrameDecoder()
    reader = TwitchPyAvVideoReader(
        channel="minnarone",
        stream_opener=_FakeStreamOpener(stream),
        frame_decoder=decoder,
        cleanup_timeout=0.01,
    )

    async def run():
        await reader.start()
        assert await asyncio.to_thread(decoder.started.wait, 0.5)
        thread = reader._decode_thread
        assert thread is not None
        assert thread.daemon is True
        with pytest.raises(TimeoutError, match="cleanup timed out"):
            await reader.stop()
        decoder.release.set()
        await asyncio.to_thread(thread.join, 1.0)
        assert not thread.is_alive()

    asyncio.run(run())

    assert stream.closed is True


class _FakeProcess:
    def __init__(self, stdout_chunks, *, returncode=0):
        self._stdout_chunks = list(stdout_chunks)
        self._returncode = returncode
        self.stdin_writes = []
        self.stdin_closed = False
        self.terminated = False
        self.killed = False
        self.waited = False

    async def read_stdout(self, size):
        if not self._stdout_chunks:
            return b""
        chunk = self._stdout_chunks.pop(0)
        if len(chunk) <= size:
            return chunk
        self._stdout_chunks.insert(0, chunk[size:])
        return chunk[:size]

    async def write_stdin(self, data):
        self.stdin_writes.append(data)

    async def close_stdin(self):
        self.stdin_closed = True

    async def wait(self):
        self.waited = True
        return self._returncode

    async def terminate(self):
        self.terminated = True

    async def kill(self):
        self.killed = True


class _FakeProcessRunner:
    def __init__(self, processes):
        self._processes = list(processes)
        self.commands = []

    async def start(self, argv):
        self.commands.append(argv)
        return self._processes.pop(0)


def test_video_reader_launches_streamlink_and_ffmpeg_and_emits_jpeg_frames():
    streamlink = _FakeProcess([b""])
    ffmpeg = _FakeProcess([JPEG_A + JPEG_B, b""])
    runner = _FakeProcessRunner([streamlink, ffmpeg])
    reader = TwitchVideoReader(
        channel="Minnarone",
        quality="best",
        fps=0.5,
        process_runner=runner,
        clock=lambda: 42.0,
    )

    async def run():
        await reader.start()
        events = []
        async for event in reader.events():
            events.append(event)
        await reader.stop()
        return events

    events = asyncio.run(run())

    assert reader.channels() == {"video"}
    assert runner.commands == [
        [
            "streamlink",
            "--stdout",
            "https://www.twitch.tv/minnarone",
            "best",
        ],
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-an",
            "-vf",
            "fps=0.5",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        ],
    ]
    assert [event.channel for event in events] == ["video", "video"]
    assert [event.payload for event in events] == [
        VideoFrame(pixels=JPEG_A, source_label="stream", ts=42.0),
        VideoFrame(pixels=JPEG_B, source_label="stream", ts=42.0),
    ]


def test_video_reader_reports_non_zero_ffmpeg_exit_status():
    streamlink = _FakeProcess([b""])
    ffmpeg = _FakeProcess([b""], returncode=23)
    reader = TwitchVideoReader(
        channel="minnarone",
        process_runner=_FakeProcessRunner([streamlink, ffmpeg]),
    )

    async def run():
        await reader.start()
        with pytest.raises(OSError, match="ffmpeg exited with status 23"):
            return [event async for event in reader.events()]

    asyncio.run(run())


def test_video_reader_reports_non_zero_streamlink_exit_status():
    streamlink = _FakeProcess([b""], returncode=44)
    ffmpeg = _FakeProcess([b""])
    reader = TwitchVideoReader(
        channel="minnarone",
        process_runner=_FakeProcessRunner([streamlink, ffmpeg]),
        process_stop_timeout=0.01,
    )

    async def run():
        await reader.start()
        with pytest.raises(OSError, match="streamlink exited with status 44"):
            return [event async for event in reader.events()]

    asyncio.run(run())
