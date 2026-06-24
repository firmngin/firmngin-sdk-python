# Firmngin Python SDK

<p align="center">
  <img src="https://raw.githubusercontent.com/firmngin/firmngin-sdk-python/main/logo.png" alt="Firmngin Logo" width="96"/>
</p>

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Python SDK for [Firmngin](https://firmngin.dev) device clients, Raspberry Pi. Supports async and sync styles with mTLS, E2EE, entity state, payments, and optional image upload.

**Docs:** [Introduction](https://firmngin.dev/docs/libraries/raspi) — Python SDK menu on [firmngin.dev/docs](https://firmngin.dev/docs)

## Install

```bash
pip install firmngin
```

Image upload (optional):

```bash
pip install firmngin[http]
```

From Git:

```bash
pip install git+https://github.com/firmngin/firmngin-sdk-python.git
```

## Dependencies

Core install uses `aiomqtt` (MQTT) and `cryptography` (TLS + AES-GCM E2EE) only.

## Client vs AsyncClient

|            | `AsyncClient`                   | `Client`                  |
| ---------- | ------------------------------- | ------------------------- | --- |
| Style      | `async` / `await`               | Blocking calls            |     |
| Push state | `await client.push_entity(...)` | `client.push_entity(...)` |
| Event loop | `await client.run()`            | `client.run()`            |

Both use `ClientConfig.from_file("keys.json")` and support the same events.

## Quickstart

```python
from firmngin import Client, ClientConfig, Entity, EntityCommand

relay = Entity("relay")
temperature = Entity("temperature")

with Client(ClientConfig.from_file("keys.json")) as client:

    @client.on_entity(relay)
    def handle_relay(command: EntityCommand) -> None:
        print("relay:", command.value)

    client.connect()
    client.push_entity(temperature, 27.5)
    client.run()
```

## Debug mode

Debug is **off** by default — no banner or console output.

```python
client.set_debug(True)
client.connect()
```

With debug enabled, `connect()` prints the Firmngin banner, connection details, and connect/disconnect messages.

## Events

Register handlers with `client.on(Event.X, handler)`:

| Event                    | Payload         | Description            |
| ------------------------ | --------------- | ---------------------- |
| `Event.PAYMENT`          | `Payment`       | Payment updates        |
| `Event.PAYMENT_PENDING`  | `Payment`       | Payment pending        |
| `Event.PAYMENT_SUCCESS`  | `Payment`       | Payment succeeded      |
| `Event.INIT`             | `Init`          | Device init payload    |
| `Event.MERCHANT_STATUS`  | `str`           | Merchant status string |
| `Event.VERIFICATION`     | `Verification`  | Verification result    |
| `Event.PIN`              | `Verification`  | PIN display            |
| `Event.DEVICE_STATUS`    | `DeviceStatus`  | Device lifecycle       |
| `Event.ENTITY_COMMAND`   | `EntityCommand` | Any entity command     |
| `Event.ACTIVE_SESSION`   | `ActiveSession` | Active paid session    |
| `Event.METADATA_PENDING` | `str`           | Raw JSON from `mop`    |
| `Event.METADATA_EXPIRED` | `str`           | Raw JSON from `moe`    |
| `Event.METADATA_SUCCESS` | `str`           | Raw JSON from `mos`    |
| `Event.ERROR`            | `Exception`     | Runtime error          |

Metadata events pass the decrypted payload as a **JSON string** — parse it in your handler.

```python
import json

@client.on(Event.METADATA_PENDING)
def on_metadata(raw_json: str) -> None:
    data = json.loads(raw_json)
```

Per-entity commands:

```python
@client.on_entity(Entity("relay"))
def on_relay(command: EntityCommand) -> None:
    print(command.value)
```

## API overview

| Import                         | Role                             |
| ------------------------------ | -------------------------------- |
| `AsyncClient`                  | Async device client              |
| `Client`                       | Sync blocking client             |
| `ClientConfig`                 | Runtime settings                 |
| `KeysConfig`                   | `keys.json` loader               |
| `Event`                        | Event names for `client.on(...)` |
| `Entity`, `Payment`, `Init`, … | Typed payloads                   |

## Device keys

Download `keys.json` from the Firmngin dashboard. The SDK accepts dashboard fields including `server_fingerprint_bytes` (20-byte Arduino-style fingerprint) and picks the right TLS validation mode automatically.

Never commit real keys. See `keys.json.example`.

## Image upload

```bash
pip install firmngin[http]
```

```python
await client.upload_image(Entity("camera"), "snapshot.jpg")
```

## Examples

See [`examples/`](examples/).

## License

MIT — see [LICENSE](LICENSE).
