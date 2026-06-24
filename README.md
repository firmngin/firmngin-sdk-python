# Firmngin Python SDK

<p align="center">
  <img src="logo.png" alt="Firmngin Logo" width="96"/>
</p>

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Python SDK for [Firmngin](https://firmngin.dev) as a device client. It supports both synchronous and asynchronous programming styles, with a focus on IoT devices and event-driven architectures.
secure communication (mTLS), OTA firmware updates, image upload, GPS location, and payment/verification flows for the Firmngin platform.

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

This SDK needs a few extra packages `aiomqtt` and `cryptography` for Messages transport and TLS/AES-GCM end-to-end encryption.

## Client vs AsyncClient

The SDK offers two entry points — pick the one that fits your code:

|            | `AsyncClient`                   | `Client`                  |
| ---------- | ------------------------------- | ------------------------- |
| Style      | `async` / `await`               | Regular blocking calls    |
| Push state | `await client.push_entity(...)` | `client.push_entity(...)` |
| Event loop | `await client.run()`            | `client.run()`            |

Both use the same `ClientConfig` and support the same events.

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

## API overview

| Import                         | Role                                                     |
| ------------------------------ | -------------------------------------------------------- |
| `AsyncClient`                  | Async device client                                      |
| `Client`                       | Synchronous blocking client                              |
| `ClientConfig`                 | Runtime settings — `ClientConfig.from_file("keys.json")` |
| `KeysConfig`                   | Low-level keys loader                                    |
| `Event`                        | Event names for `client.on(...)`                         |
| `Entity`, `Payment`, `Init`, … | Typed event payloads                                     |

Legacy aliases: `FirmnginClient` (= `AsyncClient`), `SyncClient` (= `Client`).

### Events

```python
client.on(Event.PAYMENT, handler)
client.on(Event.INIT, handler)
client.on(Event.ERROR, handler)
```

### Per-entity commands

```python
from firmngin import Entity, EntityCommand

@client.on_entity(Entity("relay"))
async def on_relay(command: EntityCommand) -> None:
    print(command.value)
```

### Image upload

```bash
pip install firmngin[http]
```

```python
await client.upload_image(Entity("camera"), "snapshot.jpg")
```

## Device keys

Download `keys.json` from the Firmngin dashboard. See `keys.json.example`. Never commit real keys.

## Examples

See [`examples/`](examples/).

## License

MIT — see [LICENSE](LICENSE).
