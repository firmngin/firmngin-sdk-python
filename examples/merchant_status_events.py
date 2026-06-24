"""Handle merchant status changes."""

from __future__ import annotations

import asyncio

from firmngin import AsyncClient, ClientConfig, Event


async def main() -> None:
    config = ClientConfig.from_file("keys.json")

    async with AsyncClient(config) as client:

        @client.on(Event.MERCHANT_STATUS)
        async def handle_merchant_status(status: str) -> None:
            if status == "idle":
                print("merchant is idle")
            elif status == "pending_payment":
                print("merchant has pending payment")
            elif status == "on_active_service":
                print("merchant is on active service")
            else:
                print("merchant status:", status)

        await client.connect()
        await client.request_init()
        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
