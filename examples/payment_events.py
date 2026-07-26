"""Handle payment events."""

from __future__ import annotations

import asyncio
import json

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

        @client.on(Event.POSTPAID_READY)
        async def handle_postpaid_ready(payment: Payment) -> None:
            print("postpaid ready:", payment.order_id, payment.item_title, payment.price, payment.is_post_paid)

        @client.on(Event.METADATA_ACTIVE_SERVICE)
        async def handle_active_service_metadata(raw_json: str) -> None:
            print("active service metadata:", json.loads(raw_json))

        await client.connect()
        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
