# Examples

Runnable samples for the Firmngin Python SDK. Each script expects `keys.json` in the working directory.

| File | What it shows |
|------|----------------|
| `async_basic.py` | `AsyncClient` — connect, handlers, publish |
| `sync_basic.py` | `Client` — blocking sync wrapper |
| `payment_events.py` | Payment pending/success |
| `entity_publish.py` | Push entity state |
| `entity_command.py` | Per-entity command handlers |
| `batch_and_location.py` | Batch updates + GPS |
| `async_with_image_upload.py` | Image upload (`firmngin[http]`) |
| `merchant_status_events.py` | Merchant lifecycle |
| `device_status_events.py` | Device status |
| `pin_verification_events.py` | PIN / verification |
| `active_session_events.py` | Active paid sessions |
| `flask_device_dashboard/` | Flask + background `AsyncClient` |

## Run

```bash
pip install -e ".[http]"
cp keys.json.example keys.json
python examples/async_basic.py
```

Docs: [firmngin.dev — Raspberry Pi SDK](https://firmngin.dev/docs/libraries/raspi)
