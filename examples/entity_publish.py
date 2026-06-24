"""Publish entity state updates."""

from __future__ import annotations

import asyncio

from firmngin import AsyncClient, ClientConfig, Entity

relay = Entity(1)
temperature = Entity("2")


async def main() -> None:
    config = ClientConfig.from_file("keys.json")

    async with AsyncClient(config) as client:
        await client.connect()
        await client.push_entity(relay, "on")
        await client.push_entity(temperature, 27.5)
        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
