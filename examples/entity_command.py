"""Handle entity commands from Firmngin.

Use this when the server/platform sends an instruction to one entity.
"""

from __future__ import annotations

import asyncio

from firmngin import ClientConfig, Entity, EntityCommand, FirmnginClient, KeysConfig


relay = Entity(1)
temperature = Entity("2")


async def main() -> None:
    config = ClientConfig(keys=KeysConfig.from_file("keys.json"))

    async with FirmnginClient(config) as client:
        @client.on_entity(relay)
        async def handle_relay(command: EntityCommand) -> None:
            print("relay command:", command.value)

        @client.on_entity(temperature)
        async def handle_temperature(command: EntityCommand) -> None:
            print("temperature command:", command.value)

        await client.connect()
        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
