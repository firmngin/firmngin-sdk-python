"""Upload an entity image."""

from __future__ import annotations

import asyncio

from firmngin import ClientConfig, Entity, FirmnginClient, KeysConfig


camera = Entity("camera")


async def main() -> None:
    config = ClientConfig(keys=KeysConfig.from_file("keys.json"))

    async with FirmnginClient(config) as client:
        await client.connect()
        await client.upload_image(camera, "snapshot.jpg")


if __name__ == "__main__":
    asyncio.run(main())
