# Examples

Runnable samples for the Firmngin Python SDK. Each script expects `keys.json` in the working directory.

| File | What it shows |
|------|----------------|
| `async_basic.py` | `AsyncClient` — connect, handlers, publish |
| `sync_basic.py` | `Client` — blocking sync wrapper |
| `payment_events.py` | Payment pending/success |
| `entity_publish.py` | Publish initial state and skip unchanged sensor values |
| `entity_command.py` | Per-entity command handlers |
| `batch_and_location.py` | Batch updates + GPS |
| `async_with_image_upload.py` | Image upload (`firmngin[http]`) |
| `kiosk_checkout.py` | Vending kiosk HTTP checkout + QR image (`firmngin[http]`) |
| `merchant_status_events.py` | Merchant lifecycle |
| `device_status_events.py` | Device status |
| `pin_verification_events.py` | PIN / verification |
| `active_session_events.py` | Active paid sessions |
| `flask_device_dashboard/` | Flask + background `AsyncClient` |

## Entity state publishing

Publish the device's current entity state once after init/connect. After that,
publish only when the value changes, from a sensor or hardware change callback.
`entity_publish.py` shows a callback helper that skips unchanged readings.
For batches, include only changed entities after the initial state publish.

The backend keeps the last entity state, so periodic entity-state heartbeats are
unnecessary. Every publish is billable; do not put `push_entity()` or batch state
publishes on a fixed short timer. An unchanged sensor reading needs no publish.
This is separate from the SDK's MQTT keepalive and ping/pong handling.

## Run

```bash
pip install -e ".[http]"
cp keys.json.example keys.json
python examples/async_basic.py
```

Docs: [Introduction — Python SDK](https://firmngin.dev/docs/libraries/raspi)
