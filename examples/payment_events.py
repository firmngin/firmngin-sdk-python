"""Handle payment events."""

from __future__ import annotations

import asyncio

from firmngin import AsyncClient, ClientConfig, Event, Payment


async def main() -> None:
    config = ClientConfig.from_file("keys.json")

    async with AsyncClient(config) as client:

        @client.on(Event.PAYMENT_PENDING)
        async def handle_pending(payment: Payment) -> None:
            print("payment pending:", payment.order_id)

        @client.on(Event.PAYMENT_SUCCESS)
        async def handle_success(payment: Payment) -> None:
            print("payment success:", payment.order_id, payment.item_title)

        await client.connect()
        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
