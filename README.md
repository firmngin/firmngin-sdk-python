# firmngin

<p align="center">
  <img src="logo.png" alt="Firmngin Logo" width="200"/>
</p>

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Python SDK for building Firmngin device integrations.

This package is intended for gateways, Linux-based devices, Raspberry Pi deployments, integration tests, and server-side tooling that need to interact with Firmngin as devices.

> Status: alpha. The public API may change before v1.0.0.

## Features

- Event-driven device client API.
- TLS, mTLS, and certificate fingerprint validation.
- E2EE enabled by default.
- Typed payload models for payment, init, verification, device status, and entity commands.
- Async-first API with a sync adapter for blocking scripts.
- Entity state publishing, batch updates, location updates, active-session helpers, LWT, reconnect handling, and image upload.

## Installation

From Git:

```bash
pip install git+https://github.com/firmngin/firmngin-sdk-python.git
```

From PyPI after release:

```bash
pip install firmngin
```

## Requirements

- Python 3.9 or newer.
- A platform-issued `keys.json` file for the device.
- Device credentials and TLS material issued by Firmngin.

## Device Keys

Device identity and cryptographic material are loaded from `keys.json`.
Do not commit real device keys. `keys.json` is ignored by git; `keys.json.example` is provided only as a shape reference.

## Quickstart

```python
import asyncio

from firmngin import ClientConfig, Entity, Event, FirmnginClient, Init, KeysConfig, Payment


async def handle_payment(payment: Payment) -> None:
    if payment.is_success:
        print("paid:", payment.order_id)


async def handle_init(init: Init) -> None:
    print("merchant status:", init.merchant_status)


async def main() -> None:
    config = ClientConfig(
        keys=KeysConfig.from_file("keys.json"),
    )
    relay = Entity("1")

    async with FirmnginClient(config) as client:
        client.on(Event.PAYMENT, handle_payment)
        client.on(Event.INIT, handle_init)

        await client.connect()
        await client.request_init()
        await client.push_entity(relay, "on")
        await client.run()


asyncio.run(main())
```

## Runtime Model

Application code should use client methods such as `on(Event.PAYMENT, ...)`,
`push_entity`, and `request_init`.

Supported event groups:

- `Event.PAYMENT`, `Event.PAYMENT_PENDING`, `Event.PAYMENT_SUCCESS`
- `Event.INIT`, `Event.MERCHANT_STATUS`
- `Event.PIN`, `Event.VERIFICATION`
- `Event.DEVICE_STATUS`
- `Event.ENTITY_COMMAND`
- `Event.ACTIVE_SESSION`
- `Event.ERROR`

Entity command handlers can also be registered per entity:

```python
relay = Entity(1)

@client.on_entity(relay)
async def handle_relay(command: EntityCommand) -> None:
    print(command.value)
```

Debug logging can be enabled when diagnosing runtime behavior:

```python
client.set_debug(True)
```

Image upload keeps API paths, signing, and multipart handling inside the SDK:

```python
camera = Entity("camera")
await client.upload_image(camera, "snapshot.jpg")
```

Batch updates use the same `{"k":"...","v":"..."}` wire shape as the device runtime:

```python
batch = client.push_batch_entities()
batch.add(Entity(1), "on")
batch.add(Entity("2"), 27.5)
await batch.send()
```

## Development

Planned release gates:

- `ruff check`
- `ruff format --check`
- `mypy --strict`
- `pytest`
- `pip-audit`
- `bandit`

These commands are documented as release gates; they are not required to import the package.

## License

MIT. See [LICENSE](LICENSE).
