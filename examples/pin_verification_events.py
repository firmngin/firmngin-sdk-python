"""Handle PIN and verification events."""

from __future__ import annotations

import asyncio

from firmngin import ClientConfig, Event, FirmnginClient, KeysConfig, Verification


async def main() -> None:
    config = ClientConfig(keys=KeysConfig.from_file("keys.json"))

    async with FirmnginClient(config) as client:
        @client.on(Event.PIN)
        async def handle_pin(verification: Verification) -> None:
            print("PIN:", verification.pin)
            print("session:", verification.session_id)

        @client.on(Event.VERIFICATION)
        async def handle_verification(verification: Verification) -> None:
            print("PIN met:", verification.pin_met)
            print("precondition met:", verification.precondition_met)

        await client.connect()
        await client.run()


if __name__ == "__main__":
    asyncio.run(main())
