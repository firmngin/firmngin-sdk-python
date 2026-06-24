"""Publish entity state updates.

Use this when the device reports its own state to Firmngin.
"""

from __future__ import annotations

import asyncio

from firmngin import ClientConfig, Entity, FirmnginClient, KeysConfig


relay = Entity(1)
temperature = Entity("2")


async def main() -> None:
    config = ClientConfig(keys=KeysConfig.from_file("keys.json"))

    async with FirmnginClient(config) as client:
        await client.connect()

        await client.push_entity(relay, "on")
        await client.push_entity(temperature, 27.5)

        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
