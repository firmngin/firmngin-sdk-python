"""Basic async Firmngin device example.

This is the intended high-level application shape. Routing, encryption, and
retry handling are managed inside FirmnginClient.
"""

from __future__ import annotations

import asyncio

from firmngin import ClientConfig, Entity, Event, FirmnginClient, Init, KeysConfig, Payment


async def handle_payment(payment: Payment) -> None:
    if payment.is_pending:
        print("waiting for payment:", payment.order_id)
    elif payment.is_success:
        print("paid:", payment.order_id, payment.item_title)


async def handle_init(init: Init) -> None:
    print("merchant status:", init.merchant_status)
    if init.is_pin_enabled:
        print("PIN verification is required")


async def main() -> None:
    config = ClientConfig(keys=KeysConfig.from_file("keys.json"))
    relay = Entity("relay")

    async with FirmnginClient(config) as client:
        client.on(Event.PAYMENT, handle_payment)
        client.on(Event.INIT, handle_init)

        await client.connect()
        await client.request_init()
        await client.push_entity(relay, "on")
        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
