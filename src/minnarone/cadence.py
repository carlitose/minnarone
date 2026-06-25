"""Runner di cadenza condiviso: la meccanica del loop async fermabile.

`Reactor` e `Summarizer` avevano lo stesso loop a cadenza
(`_running = True; while _running: <step>; await sleep(interval)`) più lo
`stop()` che abbassa il flag. `CadenceLoop` possiede quella meccanica una volta
sola; i due moduli la COMPONGONO e restano proxy sottili sulle proprie firme
pubbliche `run()/stop()`.

Modulo profondo: l'interfaccia è minima (`run`/`stop` + i parametri di
costruzione), mentre flag `_running`, `while`, `sleep` e l'eventuale
`try/except` per saltare il ciclo restano nascosti.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

# Lo sleep è iniettabile: in produzione `asyncio.sleep`, nei test un fake
# deterministico (lo stesso pattern già usato altrove nel repo).
SleepFn = Callable[[float], Awaitable[None]]


class CadenceLoop:
    """Esegue `step` a cadenza finché non viene fermato.

    Ordine di un giro: prima `await step()`, poi `await sleep(interval)`. Lo
    `stop()` abbassa il flag ma non interrompe il giro in corso: il loop esce al
    controllo successivo (latenza fino a un intervallo — comportamento
    invariato rispetto ai loop originali di Reactor/Summarizer).

    Se `swallow` è non vuoto, un'eccezione di quei tipi sollevata da `step`
    viene assorbita (si salta il ciclo, il loop prosegue) e `on_skip` — se
    fornito — viene invocato con l'eccezione. `on_skip` è l'unico hook di
    osservabilità per lo skip silenzioso: di default è None, quindi lo skip
    resta silenzioso (nessun log) come prima. `CancelledError` NON va mai messo
    in `swallow`: deve propagare per cancellare il task.
    """

    def __init__(
        self,
        # Il valore restituito da `step` è ignorato (un giro è un effetto, non un
        # risultato): `Awaitable[object]` accetta sia coroutine `-> None` (es.
        # `Reactor.run_once`) sia con valore (es. `Summarizer.summarize -> str`).
        step: Callable[[], Awaitable[object]],
        interval: float,
        *,
        sleep: SleepFn = asyncio.sleep,
        swallow: tuple[type[BaseException], ...] = (),
        on_skip: Callable[[BaseException], None] | None = None,
    ) -> None:
        self._step = step
        self._interval = interval
        self._sleep = sleep
        self._swallow = swallow
        self._on_skip = on_skip
        self._running = False

    async def run(self) -> None:
        """Esegue `step` a cadenza finché `stop()` non viene chiamato."""
        self._running = True
        while self._running:
            try:
                await self._step()
            except self._swallow as exc:
                # Salta il ciclo senza rompere il loop. `on_skip` è il punto
                # unico di osservabilità (es. un log opzionale): off di default.
                if self._on_skip is not None:
                    self._on_skip(exc)
            await self._sleep(self._interval)

    def stop(self) -> None:
        """Richiede l'arresto del loop al prossimo controllo del flag."""
        self._running = False
