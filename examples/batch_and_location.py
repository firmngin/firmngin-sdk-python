"""Publish batch entity and location updates."""

from __future__ import annotations

import asyncio

from firmngin import AsyncClient, ClientConfig, Entity

relay = Entity(1)
temperature = Entity("2")


async def main() -> None:
    config = ClientConfig.from_file("keys.json")

    async with AsyncClient(config) as client:
        await client.connect()

        batch = client.push_batch_entities()
        batch.add(relay, "on")
        batch.add(temperature, 27.5)
        await batch.send()

        await client.push_location_values(
            lat=-6.2,
            lon=106.816666,
            accuracy=8.5,
        )

        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
