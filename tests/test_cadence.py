"""Test al boundary di `CadenceLoop`: la meccanica del loop async fermabile.

Verifica direttamente le proprietà che prima erano provate solo indirettamente
via Reactor/Summarizer: esegue N step poi `stop()`; `stop()` termina il loop;
lo `sleep` iniettato rende tutto deterministico; lo `swallow` salta il ciclo e
chiama `on_skip` senza rompere il loop; un'eccezione non in `swallow` propaga;
`CancelledError` non viene mai assorbito.
"""

import asyncio

import pytest

from minnarone.cadence import CadenceLoop


def test_runs_steps_then_stops_on_request():
    # step si ferma da solo dopo N giri chiamando stop(): contiamo gli step.
    calls = 0

    async def fake_sleep(_seconds: float) -> None:
        return None

    async def step() -> None:
        nonlocal calls
        calls += 1
        if calls >= 3:
            loop.stop()

    loop = CadenceLoop(step, interval=0.001, sleep=fake_sleep)
    asyncio.run(loop.run())

    assert calls == 3


def test_stop_ends_the_loop():
    # Avvia il loop come task, poi stop() lo fa terminare (run() ritorna).
    async def step() -> None:
        return None

    async def fake_sleep(_seconds: float) -> None:
        # Cede al loop di eventi così il drive() concorrente può girare e
        # chiamare stop() senza che il while affami lo scheduler.
        await asyncio.sleep(0)

    loop = CadenceLoop(step, interval=0.001, sleep=fake_sleep)

    async def drive():
        task = asyncio.create_task(loop.run())
        await asyncio.sleep(0.01)
        loop.stop()
        await asyncio.wait_for(task, timeout=1.0)

    asyncio.run(drive())  # non deve sollevare/appendere


def test_injected_sleep_is_called_with_interval_deterministically():
    # Lo sleep iniettato riceve sempre l'intervallo configurato, una volta per giro.
    slept: list[float] = []
    calls = 0

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    async def step() -> None:
        nonlocal calls
        calls += 1
        if calls >= 2:
            loop.stop()

    loop = CadenceLoop(step, interval=0.25, sleep=fake_sleep)
    asyncio.run(loop.run())

    # uno sleep per giro (step eseguito poi sleep), sempre con l'intervallo.
    assert slept == [0.25, 0.25]


def test_swallowed_exception_calls_on_skip_and_loop_continues():
    skipped: list[BaseException] = []
    calls = 0

    class Boom(Exception):
        pass

    async def fake_sleep(_seconds: float) -> None:
        return None

    async def step() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise Boom("salta questo giro")
        loop.stop()

    loop = CadenceLoop(
        step,
        interval=0.001,
        sleep=fake_sleep,
        swallow=(Boom,),
        on_skip=skipped.append,
    )
    asyncio.run(loop.run())

    # il primo giro è stato saltato (on_skip chiamato), il loop è proseguito.
    assert calls == 2
    assert len(skipped) == 1 and isinstance(skipped[0], Boom)


def test_swallowed_exception_without_on_skip_is_silent():
    # Senza on_skip lo skip resta silenzioso (nessun crash, nessun hook).
    calls = 0

    class Boom(Exception):
        pass

    async def fake_sleep(_seconds: float) -> None:
        return None

    async def step() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise Boom()
        loop.stop()

    loop = CadenceLoop(step, interval=0.001, sleep=fake_sleep, swallow=(Boom,))
    asyncio.run(loop.run())

    assert calls == 2


def test_non_swallowed_exception_propagates():
    class Boom(Exception):
        pass

    async def fake_sleep(_seconds: float) -> None:
        return None

    async def step() -> None:
        raise Boom("non assorbito")

    # swallow vuoto: l'eccezione deve propagare fuori da run().
    loop = CadenceLoop(step, interval=0.001, sleep=fake_sleep)

    with pytest.raises(Boom):
        asyncio.run(loop.run())


def test_cancelled_error_is_never_swallowed():
    # Anche se per assurdo si mettesse CancelledError in swallow, qui verifichiamo
    # che con swallow tipico (un'eccezione applicativa) la CancelledError propaga.
    class Boom(Exception):
        pass

    async def step() -> None:
        raise asyncio.CancelledError()

    loop = CadenceLoop(step, interval=0.001, swallow=(Boom,))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(loop.run())
