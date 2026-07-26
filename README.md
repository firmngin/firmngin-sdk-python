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

## Client vs AsyncClient

There are two client classes: `Client` (sync, blocking) and `AsyncClient` (async, non-blocking). Both support the same events and payloads. Use `AsyncClient` in an async context with `await client.connect()` and `await client.run()`. Use `Client` in a sync context with `client.connect()` and `client.run()`.

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
| `Event.POSTPAID_READY`   | `Payment`       | Postpaid order ready   |
| `Event.INIT`             | `Init`          | Device init payload    |
| `Event.DISPENSE`         | `Dispense`      | Vending SKU list to dispense |
| `Event.MERCHANT_STATUS`  | `str`           | Merchant status string |
| `Event.VERIFICATION`     | `Verification`  | Verification result    |
| `Event.PIN`              | `Verification`  | PIN display            |
| `Event.DEVICE_STATUS`    | `DeviceStatus`  | Device lifecycle       |
| `Event.ENTITY_COMMAND`   | `EntityCommand` | Any entity command     |
| `Event.ACTIVE_SESSION`   | `ActiveSession` | Active paid session    |
| `Event.METADATA_PENDING` | `str`           | Pending-payment metadata JSON |
| `Event.METADATA_ACTIVE_SERVICE` | `str`    | Active-service metadata JSON |
| `Event.METADATA_EXPIRED` | `str`           | Expired-payment metadata JSON |
| `Event.METADATA_SUCCESS` | `str`           | Successful-payment metadata JSON |
| `Event.METADATA_POSTPAID_READY` | `str`     | Postpaid-ready metadata JSON |
| `Event.ERROR`            | `Exception`     | Runtime error          |

Metadata events pass the decrypted payload as a **JSON string** — parse it in your handler.

`Event.POSTPAID_READY` uses the same `Payment` fields as pending and successful
payments: item title, price, order ID, and quantity (always `1` for postpaid).
When the catalog item has postpaid-ready metadata, it is delivered separately
through `Event.METADATA_POSTPAID_READY`.

Every `Payment` also exposes mutually exclusive payment-type booleans:
`is_post_paid` / `is_pre_paid`. These flags are separate from
`is_pending` and `is_success`.

### Init business mode

Use `is_service_mode` / `is_vending_mode` to detect business mode:

```python
@client.on(Event.INIT)
def on_init(init: Init) -> None:
    if init.is_vending_mode:
        print("vending mode")
```

### Vending dispense

When business mode is vending, a paid order delivers catalog SKUs to dispense.
Handle with `Event.DISPENSE` / `Dispense`:

```python
from firmngin import Dispense, Event

@client.on(Event.DISPENSE)
def on_dispense(dispense: Dispense) -> None:
    if not dispense.is_valid:
        return
    for sku in dispense.skus:
        print("dispense:", sku)
```

When the service enters `on_active_service`, optional catalog metadata is
delivered separately through `Event.METADATA_ACTIVE_SERVICE`. Like the other
metadata events, the payload remains a decrypted raw JSON string.

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
| `Entity`, `Payment`, `Init`, `Dispense`, … | Typed payloads            |

## Device keys

Download `keys.json` from the Firmngin dashboard. The SDK accepts dashboard fields including `server_fingerprint_bytes` (20-byte Arduino-style fingerprint) and picks the right TLS validation mode automatically.

The generated `service_ca_cert` is the trust anchor for HTTPS device services at
`ota.firmngin.dev`, including image upload. MQTT continues to use `ca_cert`
independently.

Never commit real keys. See `keys.json.example`.

For a local development broker, add these fields to `keys.json`:

```json
{
  "firmngin_broker_addr": "192.168.100.31",
  "firmngin_broker_port": 1883,
  "firmngin_no_tls": true,
  "firmngin_api_base_url": "http://192.168.100.31:8080/api/v1",
  "firmngin_ota_base_url": "http://192.168.100.31:8080/api/v1/ota"
}
```

The broker fields only change the MQTT connection. `firmngin_no_tls` sends MQTT
traffic without TLS and must only be used in a trusted development network.
`firmngin_api_base_url` configures HTTP device-service requests. The OTA URL is
reserved for OTA support and is not consumed by an OTA executor yet.

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
