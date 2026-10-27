"""Publish initial entity state, then publish only when a sensor value changes."""

from __future__ import annotations

import asyncio

from firmngin import AsyncClient, ClientConfig, Entity

relay = Entity(1)
temperature = Entity("2")


async def main() -> None:
    config = ClientConfig.from_file("keys.json")

    async with AsyncClient(config) as client:
        last_temperature: float | None = None

        async def publish_temperature(value: float) -> None:
            nonlocal last_temperature
            if value == last_temperature:
                return
            await client.push_entity(temperature, value)
            last_temperature = value

        await client.connect()
        # Send initial state once. The backend keeps the last entity state.
        await client.push_entity(relay, "on")
        await publish_temperature(27.5)
        # Await publish_temperature(new_value) from your sensor's change callback.
        # Do not add periodic state heartbeats: every publish is billable.
        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
