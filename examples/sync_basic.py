"""Synchronous-style Firmngin device example."""

from __future__ import annotations

from firmngin import ClientConfig, Entity, Event, KeysConfig, Payment, SyncFirmnginClient


def print_payment(payment: Payment) -> None:
    if payment.is_success:
        print("paid:", payment.order_id)


def main() -> None:
    config = ClientConfig(keys=KeysConfig.from_file("keys.json"))
    relay = Entity("relay")
    client = SyncFirmnginClient(config)

    client.async_client.on(Event.PAYMENT, print_payment)
    client.connect()
    client.push_entity(relay, "off")


if __name__ == "__main__":
    main()
