"""Basic async Firmngin device example."""

from __future__ import annotations

import asyncio

from firmngin import AsyncClient, ClientConfig, Entity, Event, Init, EntityCommand

relay = Entity(1)
temperature = Entity("temperature")


async def main() -> None:
    config = ClientConfig.from_file("keys.json")

    async with AsyncClient(config) as client:
        @client.on_entity(relay)
        def handle_relay(command: EntityCommand) -> None:
            print("relay command:", command.value)

        client.set_debug(True)
        await client.connect()
        await client.request_init()
        await client.push_entity(temperature, 27.5)
        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
