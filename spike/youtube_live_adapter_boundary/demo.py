"""One-command deterministic demonstration of both prototype branches."""

from __future__ import annotations

import asyncio
import json

from .prototype import (
    YouTubeVideoId,
    build_specific_branch,
    build_typed_media_branch,
)


async def _observe(builder):
    target = YouTubeVideoId("abcDEF123_-")
    branch = builder(target)
    await branch.adapter.start()
    events = [event async for event in branch.adapter.events()]
    stats = branch.adapter.stats()
    return {
        "branch": branch.name,
        "channels": sorted(event.channel for event in events),
        "payload_types": {
            event.channel: type(event.payload).__name__ for event in events
        },
        "starts": {
            channel: reader.starts for channel, reader in branch.readers.items()
        },
        "stops": {channel: reader.stops for channel, reader in branch.readers.items()},
        "failures": stats.failures,
        "all_fake_streams_closed": all(stream.closed for stream in branch.opener.opened)
        if branch.opener is not None
        else True,
    }


async def _priority(builder):
    target = YouTubeVideoId("abcDEF123_-")
    branch = builder(target, queue_size=1)
    await branch.adapter.start()
    await asyncio.sleep(0)
    await branch.adapter.stop()
    stats = branch.adapter.stats()
    return {"branch": branch.name, "produced": stats.produced, "dropped": stats.dropped}


async def _main() -> None:
    builders = (build_specific_branch, build_typed_media_branch)
    result = {
        "offline": True,
        "branches": [await _observe(builder) for builder in builders],
        "queue_priority": [await _priority(builder) for builder in builders],
        "decision": "typed media source boundary, only after the media policy gate",
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(_main())
