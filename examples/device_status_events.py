"""Handle device status events."""

from __future__ import annotations

import asyncio

from firmngin import AsyncClient, ClientConfig, DeviceStatus, Event


async def main() -> None:
    config = ClientConfig.from_file("keys.json")

    async with AsyncClient(config) as client:

        @client.on(Event.DEVICE_STATUS)
        async def handle_status(status: DeviceStatus) -> None:
            if status.is_maintenance:
                print("device is in maintenance")
            elif status.is_idle:
                print("device is idle")
            else:
                print("device status:", status.state)

        await client.connect()
        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
