"""Upload an entity image.

Requires: pip install firmngin[http]
"""

from __future__ import annotations

import asyncio

from firmngin import AsyncClient, ClientConfig, Entity

camera = Entity("camera")


async def main() -> None:
    config = ClientConfig.from_file("keys.json")

    async with AsyncClient(config) as client:
        await client.connect()
        await client.upload_image(camera, "snapshot.jpg")


if __name__ == "__main__":
    asyncio.run(main())
