"""Handle active service sessions."""

from __future__ import annotations

import asyncio

from firmngin import ActiveSession, AsyncClient, ClientConfig, Event


async def main() -> None:
    config = ClientConfig.from_file("keys.json")

    async with AsyncClient(config) as client:

        @client.on(Event.ACTIVE_SESSION)
        async def handle_active_session(session: ActiveSession) -> None:
            if session.can_run:
                print("active order:", session.order_id)

        await client.connect()
        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
