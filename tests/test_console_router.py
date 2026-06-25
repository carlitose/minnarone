"""Test del ConsoleOutputRouter: stampa il messaggio sul canale pubblico."""

import asyncio
import io

from minnarone.console import ConsoleOutputRouter
from minnarone.output import OutputMode, OutputRouter


def test_is_an_output_router():
    assert isinstance(ConsoleOutputRouter(), OutputRouter)


def test_route_public_prints_message():
    buf = io.StringIO()
    router = ConsoleOutputRouter(stream=buf)
    asyncio.run(router.route("ciao a tutti", OutputMode.PUBLIC))
    assert "ciao a tutti" in buf.getvalue()
