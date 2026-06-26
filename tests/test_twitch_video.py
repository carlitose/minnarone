"""Twitch raw video capture behavior."""

import asyncio

import pytest

from minnarone.twitch_video import (
    JpegFrameSplitter,
    TwitchVideoReader,
    validate_video_fps,
)
from minnarone.video import VideoFrame

JPEG_A = b"\xff\xd8frame-a\xff\xd9"
JPEG_B = b"\xff\xd8frame-b\xff\xd9"


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
