"""Synchronous Firmngin device example — relay command + temperature status."""

from __future__ import annotations

from firmngin import Client, ClientConfig, Entity, EntityCommand

relay = Entity(1)
temperature = Entity("temperature")


def main() -> None:
    with Client(ClientConfig.from_file("keys.json")) as client:

        @client.on_entity(relay)
        def handle_relay(command: EntityCommand) -> None:
            print("relay command:", command.value)
        client.set_debug(True)
        client.connect()
        client.push_entity(temperature, 27.5)
        client.run()


if __name__ == "__main__":
    main()
