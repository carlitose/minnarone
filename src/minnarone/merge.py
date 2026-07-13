"""Motore neutro di merge/backpressure per `SourceAdapter` per-canale.

`MergingSourceAdapter` compone una `Mapping[str, SourceAdapter]` (un reader per
canale) in un unico stream `RawEvent` bounded. Sotto pressione preferisce
mantenere gli eventi dei canali prioritari droppando quelli non prioritari;
espone conteggi diagnostici (`produced`/`dropped`/`failures`) e isola i guasti
per-canale.

Il modulo resta NEUTRO: non conosce alcuna piattaforma né il SO. La priorità di
drop è parametrica (`priority_channels`), così ogni composizione sceglie quali
canali proteggere.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field

from .source import RawEvent, SourceAdapter


@dataclass(frozen=True, slots=True)
class MergeStats:
    """Snapshot dei contatori diagnostici del merge.

    I dict esposti sono copie indipendenti dello stato interno: mutarli non
    intacca l'adapter, ma restano dict mutabili (non sono viste immutabili).
    """

    running: bool
    produced: dict[str, int] = field(default_factory=dict)
    dropped: dict[str, int] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)


class MergeRuntimeError(RuntimeError):
    """Errore runtime del merge quando tutti i reader falliscono senza output."""


class MergingSourceAdapter(SourceAdapter):
    """Compone reader per-canale in un unico stream bounded di `RawEvent`."""

    def __init__(
        self,
        *,
        readers: Mapping[str, SourceAdapter],
        priority_channels: Iterable[str] = ("chat",),
        queue_size: int = 100,
        cleanup_timeout: float = 5.0,
    ) -> None:
        if not readers:
            raise ValueError("serve almeno un reader")
        if queue_size <= 0:
            raise ValueError("queue_size deve essere > 0")
        if cleanup_timeout <= 0:
            raise ValueError("cleanup_timeout deve essere > 0")
        self._readers = dict(readers)
        self._validate_reader_channels()
        self._priority = frozenset(priority_channels)
        self._queue_size = queue_size
        self._cleanup_timeout = cleanup_timeout
        self._buffer: deque[RawEvent] = deque()
        self._not_empty = asyncio.Condition()
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._pending: set[str] = set()
        self._running = False
        self._ever_started = False
        self._produced = self._zeroed()
        self._dropped = self._zeroed()
        self._failures: dict[str, str] = {}
        # Messaggi già registrati per canale, per deduplicare per uguaglianza
        # esatta (non per contenimento) evitando di scartare guasti distinti.
        self._failure_messages: dict[str, list[str]] = {}
        # Canali il cui reader ha sollevato durante start()/events() PRIMA di
        # produrre eventi: sono guasti di produzione veri, distinti dai guasti
        # di cleanup (stop() lento/errato) che restano benigni per un canale
        # semplicemente silenzioso.
        self._production_failed: set[str] = set()

    def channels(self) -> set[str]:
        return set(self._readers)

    def ordered_channels(self) -> list[str]:
        """Canali in ordine deterministico (l'ordine di iniezione della mappa)."""
        return list(self._readers)

    async def start(self) -> None:
        # Idempotente per una sessione attiva-o-appena-drenata: finché ci sono
        # worker (in corso o esauriti dopo un drain naturale) NON rimappiamo
        # `self._workers`, così non si orfanano task né si condivide
        # buffer/pending/contatori tra due run. Solo con nessuna sessione viva
        # (`_workers` vuoto) si (re)inizializza.
        if self._running or self._workers:
            return
        self._buffer.clear()
        self._failures.clear()
        self._failure_messages.clear()
        self._production_failed.clear()
        self._produced = self._zeroed()
        self._dropped = self._zeroed()
        self._pending = set(self._readers)
        self._running = True
        self._ever_started = True
        self._workers = {
            channel: asyncio.create_task(self._drain_reader(channel, reader))
            for channel, reader in self._readers.items()
        }

    async def stop(self) -> None:
        self._running = False
        workers = dict(self._workers)
        for worker in workers.values():
            if not worker.done():
                worker.cancel()
        if workers:
            # Bound esterno sull'attesa dell'insieme dei worker. Ogni worker ha
            # già un bound interno `cleanup_timeout` sul solo `reader.stop()`
            # (in `_drain_reader`); qui raddoppiamo per lasciare margine alla
            # cancellazione del worker e al ritorno dal suo finally oltre a quel
            # bound interno, senza però attendere all'infinito.
            done, still_running = await asyncio.wait(
                workers.values(),
                timeout=self._cleanup_timeout * 2,
            )
            self._collect_worker_outcomes(workers, done, still_running)
        self._workers = {}
        self._pending.clear()
        await self._wake_consumers()

    async def events(self) -> AsyncIterator[RawEvent]:
        if not self._running and not self._ever_started:
            await self.start()
        while True:
            async with self._not_empty:
                await self._not_empty.wait_for(self._has_output_or_finished)
                if self._buffer:
                    item = self._buffer.popleft()
                    self._not_empty.notify_all()
                else:
                    self._raise_if_all_failed_silently()
                    return
            yield item

    def stats(self) -> MergeStats:
        return MergeStats(
            running=self._running,
            produced=dict(self._produced),
            dropped=dict(self._dropped),
            failures=dict(self._failures),
        )

    # --- helpers interni -------------------------------------------------

    def _has_output_or_finished(self) -> bool:
        return bool(self._buffer) or not self._running or not self._pending

    def _zeroed(self) -> dict[str, int]:
        return dict.fromkeys(self._readers, 0)

    def _validate_reader_channels(self) -> None:
        for channel, reader in self._readers.items():
            exposed = reader.channels()
            if exposed != {channel}:
                raise ValueError(
                    f"il reader del canale {channel!r} espone {exposed!r}, "
                    f"deve esporre solo {{{channel!r}}}"
                )

    async def _drain_reader(self, channel: str, reader: SourceAdapter) -> None:
        try:
            await reader.start()
            async for event in reader.events():
                await self._enqueue(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - isolamento per-canale.
            # Guasto di PRODUZIONE: il reader ha sollevato prima/durante la
            # produzione. Solo questi contano per il guard "tutti falliti".
            self._production_failed.add(channel)
            self._note_failure(channel, str(exc))
        finally:
            await self._close_reader(channel, reader)
            self._pending.discard(channel)
            if not self._pending:
                self._running = False
            await self._wake_consumers()

    async def _close_reader(self, channel: str, reader: SourceAdapter) -> None:
        # `reader.stop()` è un punto di sospensione: se il worker è in fase di
        # cancellazione, una seconda CancelledError potrebbe abortire il
        # rilascio della risorsa (device/socket) prima ancora di eseguirlo. Lo
        # schermiamo con `asyncio.shield` per garantire che stop() parta e possa
        # rilasciare, restando comunque bounded da `cleanup_timeout` (no hang).
        # Se arriva la cancellazione, la ri-solleviamo dopo aver dato a stop()
        # la sua chance: la semantica CancelledError del task è preservata.
        stop_task = asyncio.ensure_future(reader.stop())
        try:
            await asyncio.wait_for(asyncio.shield(stop_task), timeout=self._cleanup_timeout)
        except TimeoutError:
            self._note_failure(channel, "cleanup timed out")
        except asyncio.CancelledError:
            # Diamo a stop() la possibilità di completare (bounded) prima di
            # propagare la cancellazione, così il rilascio risorse non viene
            # saltato.
            with suppress(TimeoutError, asyncio.CancelledError, Exception):
                await asyncio.wait_for(
                    asyncio.shield(stop_task), timeout=self._cleanup_timeout
                )
            raise
        except Exception as exc:  # noqa: BLE001 - riportato nelle stats.
            self._note_failure(channel, str(exc))

    async def _enqueue(self, event: RawEvent) -> None:
        async with self._not_empty:
            has_room = len(self._buffer) < self._queue_size
            if not has_room and self._is_priority(event) and self._evict_one_low():
                has_room = True
            if has_room:
                self._buffer.append(event)
                self._bump(self._produced, event.channel)
            else:
                self._bump(self._dropped, event.channel)
            self._not_empty.notify_all()

    def _is_priority(self, event: RawEvent) -> bool:
        return event.channel in self._priority

    def _evict_one_low(self) -> bool:
        for index, queued in enumerate(self._buffer):
            if queued.channel not in self._priority:
                del self._buffer[index]
                self._bump(self._dropped, queued.channel)
                return True
        return False

    def _collect_worker_outcomes(
        self,
        workers: Mapping[str, asyncio.Task[None]],
        done: set[asyncio.Task[None]],
        still_running: set[asyncio.Task[None]],
    ) -> None:
        for channel, worker in workers.items():
            if worker in still_running:
                self._note_failure(channel, "cleanup timed out")
                worker.cancel()
            elif worker in done:
                with suppress(asyncio.CancelledError):
                    error = worker.exception()
                    if error is not None:
                        self._note_failure(channel, str(error))

    async def _wake_consumers(self) -> None:
        async with self._not_empty:
            self._not_empty.notify_all()

    def _raise_if_all_failed_silently(self) -> None:
        # Fatale solo se il guasto è di PRODUZIONE: un reader ha sollevato prima
        # di produrre. Un canale semplicemente silenzioso (zero eventi) il cui
        # unico "guasto" è di cleanup (stop() lento/errato) è normale per la
        # cattura OS e NON deve far crashare la sessione.
        if not self._production_failed or any(self._produced.values()):
            return
        summary = "; ".join(
            f"{channel}: {message}"
            for channel, message in sorted(self._failures.items())
            if channel in self._production_failed
        )
        raise MergeRuntimeError(f"merge failed before producing events: {summary}")

    def _note_failure(self, channel: str, message: str) -> None:
        # Dedup per UGUAGLIANZA ESATTA contro i messaggi già registrati: un
        # nuovo guasto distinto va sempre accodato, anche se è sottostringa di
        # uno accumulato (il contenimento scartava erroneamente guasti nuovi).
        seen = self._failure_messages.setdefault(channel, [])
        if message in seen:
            return
        seen.append(message)
        previous = self._failures.get(channel)
        self._failures[channel] = message if previous is None else f"{previous}; {message}"

    @staticmethod
    def _bump(counter: dict[str, int], channel: str) -> None:
        counter[channel] = counter.get(channel, 0) + 1
