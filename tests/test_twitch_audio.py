"""Twitch raw audio capture behavior."""

import asyncio

import pytest

from minnarone.audio import AudioChunk
from minnarone.twitch_audio import TwitchAudioReader, pcm_chunk_size_bytes


def test_pcm_chunk_size_uses_mono_16khz_signed_16bit_duration():
    assert pcm_chunk_size_bytes(0.25) == 8_000
    assert pcm_chunk_size_bytes(1.0) == 32_000


@pytest.mark.parametrize("duration", [0, -0.1])
def test_pcm_chunk_size_rejects_non_positive_duration(duration):
    with pytest.raises(ValueError, match="audio chunk duration"):
        pcm_chunk_size_bytes(duration)


def test_pcm_chunk_size_rejects_excessive_duration():
    with pytest.raises(ValueError, match="audio chunk duration"):
        pcm_chunk_size_bytes(11.0)


def test_pcm_chunk_size_is_positive_and_sample_aligned():
    assert pcm_chunk_size_bytes(0.0001) == 4
    assert pcm_chunk_size_bytes(1 / 16_000) == 2


class _FakeProcess:
    def __init__(self, stdout_chunks, *, returncode=0):
        self._stdout_chunks = list(stdout_chunks)
        self._returncode = returncode
        self.stdin_writes = []
        self.stdin_closed = False
        self.terminated = False
        self.killed = False
        self.waited = False
        self.wait_calls = 0

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
        self.wait_calls += 1
        self.waited = True
        return self._returncode

    async def terminate(self):
        self.terminated = True

    async def kill(self):
        self.killed = True


class _FakeProcessRunner:
    def __init__(self, processes, *, fail_on_start: int | None = None):
        self._processes = list(processes)
        self._fail_on_start = fail_on_start
        self.commands = []

    async def start(self, argv):
        self.commands.append(argv)
        if self._fail_on_start == len(self.commands):
            raise OSError("process start failed")
        return self._processes.pop(0)


def test_audio_reader_launches_streamlink_and_ffmpeg_and_emits_pcm_chunk():
    streamlink = _FakeProcess([b""])
    pcm = b"a" * 8_000
    ffmpeg = _FakeProcess([pcm, b""])
    runner = _FakeProcessRunner([streamlink, ffmpeg])
    reader = TwitchAudioReader(
        channel="Minnarone",
        quality="audio_only",
        chunk_seconds=0.25,
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

    assert reader.channels() == {"audio"}
    assert runner.commands == [
        [
            "streamlink",
            "--stdout",
            "https://www.twitch.tv/minnarone",
            "audio_only",
        ],
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "s16le",
            "pipe:1",
        ],
    ]
    assert len(events) == 1
    assert events[0].channel == "audio"
    assert events[0].ts == 42.0
    assert events[0].payload == AudioChunk(
        samples=pcm,
        sample_rate=16_000,
        source_label="stream",
        ts=42.0,
    )


def test_audio_reader_reports_non_zero_ffmpeg_exit_status():
    streamlink = _FakeProcess([b""])
    ffmpeg = _FakeProcess([b""], returncode=23)
    reader = TwitchAudioReader(
        channel="minnarone",
        process_runner=_FakeProcessRunner([streamlink, ffmpeg]),
    )

    async def run():
        await reader.start()
        with pytest.raises(OSError, match="ffmpeg exited with status 23"):
            return [event async for event in reader.events()]

    asyncio.run(run())


def test_audio_reader_cleans_streamlink_when_ffmpeg_start_fails():
    streamlink = _FakeProcess([])
    reader = TwitchAudioReader(
        channel="minnarone",
        process_runner=_FakeProcessRunner([streamlink], fail_on_start=2),
        process_stop_timeout=0.01,
    )

    async def run():
        with pytest.raises(OSError, match="process start failed"):
            await reader.start()

    asyncio.run(run())

    assert streamlink.terminated is True
    assert streamlink.waited is True


def test_audio_reader_reports_non_zero_streamlink_exit_status():
    streamlink = _FakeProcess([b""], returncode=44)
    ffmpeg = _FakeProcess([b""])
    reader = TwitchAudioReader(
        channel="minnarone",
        process_runner=_FakeProcessRunner([streamlink, ffmpeg]),
        process_stop_timeout=0.01,
    )

    async def run():
        await reader.start()
        with pytest.raises(OSError, match="streamlink exited with status 44"):
            return [event async for event in reader.events()]

    asyncio.run(run())


def test_audio_reader_stop_cancels_pump_closes_stdin_and_terminates_processes():
    class BlockingStreamlink(_FakeProcess):
        def __init__(self):
            super().__init__([])
            self.read_started = asyncio.Event()

        async def read_stdout(self, size):
            self.read_started.set()
            await asyncio.Event().wait()
            return b""

    streamlink = BlockingStreamlink()
    ffmpeg = _FakeProcess([])
    reader = TwitchAudioReader(
        channel="minnarone",
        process_runner=_FakeProcessRunner([streamlink, ffmpeg]),
    )

    async def run():
        await reader.start()
        await streamlink.read_started.wait()
        await reader.stop()

    asyncio.run(run())

    assert ffmpeg.stdin_closed is True
    assert streamlink.terminated is True
    assert ffmpeg.terminated is True
    assert streamlink.waited is True
    assert ffmpeg.waited is True


def test_audio_reader_stop_kills_process_that_ignores_terminate():
    class StubbornProcess(_FakeProcess):
        async def wait(self):
            self.wait_calls += 1
            if self.killed:
                self.waited = True
                return 0
            await asyncio.Event().wait()
            return 0

    streamlink = _FakeProcess([])
    ffmpeg = StubbornProcess([])
    reader = TwitchAudioReader(
        channel="minnarone",
        process_runner=_FakeProcessRunner([streamlink, ffmpeg]),
        # Questo test verifica il terminate->kill del processo ostinato, non la
        # race sul pump: con un timeout sotto la risoluzione del timer di
        # Windows (~15ms) l'attesa del pump cancellato scade prima che il pump
        # (già cancellato) venga schedulato, falsando lo stop come guasto. La
        # semantica del pump-timeout la copre esplicitamente il test sullo
        # stdin close che si impianta.
        process_stop_timeout=0.1,
    )

    async def run():
        await reader.start()
        await reader.stop()

    asyncio.run(run())

    assert ffmpeg.terminated is True
    assert ffmpeg.killed is True
    assert ffmpeg.waited is True


def test_audio_reader_stop_terminates_processes_when_stdin_close_hangs():
    class HangingCloseProcess(_FakeProcess):
        async def close_stdin(self):
            await asyncio.Event().wait()

    class BlockingStreamlink(_FakeProcess):
        def __init__(self):
            super().__init__([b"data"])
            self.read_started = asyncio.Event()

        async def read_stdout(self, size):
            self.read_started.set()
            await asyncio.Event().wait()
            return b""

    streamlink = BlockingStreamlink()
    ffmpeg = HangingCloseProcess([])
    reader = TwitchAudioReader(
        channel="minnarone",
        process_runner=_FakeProcessRunner([streamlink, ffmpeg]),
        process_stop_timeout=0.01,
    )

    async def run():
        await reader.start()
        await streamlink.read_started.wait()
        with pytest.raises(OSError, match="audio pipeline failed"):
            await reader.stop()

    asyncio.run(run())

    assert ffmpeg.terminated is True
    assert streamlink.terminated is True
