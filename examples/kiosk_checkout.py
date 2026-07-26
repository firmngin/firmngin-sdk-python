"""Kiosk checkout over Device HMAC HTTP + MQTT dispense events.

Requires:
  pip install -e ".[http]"
  keys.json in working directory
  device framework=python, service_type=vending, is_kiosk=true
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import os
from pathlib import Path

from firmngin import (
    AsyncClient,
    ClientConfig,
    Event,
    FirmnginError,
    Init,
    KeysConfig,
    format_error,
)


async def main() -> None:
    config = ClientConfig(keys=KeysConfig.from_file("keys.json"))
    client = AsyncClient(config)

    @client.on(Event.INIT)
    async def on_init(init: Init) -> None:
        print(
            "init",
            {
                "vending": init.is_vending_mode,
                "kiosk": init.is_kiosk,
                "status": init.merchant_status,
            },
        )

    @client.on(Event.DISPENSE)
    async def on_dispense(payload: object) -> None:
        print("dispense", payload)

    listener: asyncio.Task[None] | None = None
    try:
        await client.connect()
        listener = asyncio.create_task(client.run())

        bootstrap = await client.kiosk_bootstrap()
        if bootstrap.readiness_error:
            print(bootstrap.readiness_error)
            print("listening for events; press Ctrl+C to stop")
            await listener
            return
        print(f"kiosk ready: {bootstrap.merchant_name}")

        menu = await client.kiosk_menu()
        active_items = [item for item in menu.items if item.get("is_active")]
        if not active_items:
            print("MENU_EMPTY: no active menu items are available")
            print("listening for events; press Ctrl+C to stop")
            await listener
            return

        print(f"menu: {len(active_items)} active item(s)")
        for item in active_items:
            print(
                f"- {item.get('id')} | {item.get('title')} | "
                f"{bootstrap.currency} {item.get('price')} | {item.get('payment_type')}"
            )

        menu_item_id = os.environ.get("FIRMNGIN_MENU_ITEM_ID", "").strip()
        if not menu_item_id:
            print("listening for events; set FIRMNGIN_MENU_ITEM_ID to create an order")
            await listener
            return
        if not any(str(item.get("id")) == menu_item_id for item in active_items):
            print(f"INVALID_MENU_ITEM_ID: {menu_item_id} is not an active menu item")
            print("listening for events; press Ctrl+C to stop")
            await listener
            return

        order = await client.kiosk_create_order(
            items=[{"menu_item_id": menu_item_id, "quantity": 1}],
        )
        print("order", order.order_id, order.amount, order.qr_reference_id)

        if order.qr:
            out = Path("kiosk_qris.png")
            out.write_bytes(base64.b64decode(order.qr))
            print("wrote", out.resolve())

        for _ in range(30):
            status = await client.kiosk_order_status(order.order_id)
            print("status", status.status, status.payment_status)
            if status.payment_status.lower() in {"paid", "completed", "success"}:
                break
            await asyncio.sleep(2)

        print("listening for events; press Ctrl+C to stop")
        await listener
    finally:
        client.stop()
        if listener is not None and not listener.done():
            listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (FirmnginError, ValueError, OSError, ImportError) as error:
        print(format_error(error))
