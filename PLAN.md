# Plan: firmngin-sdk-python — Python port of firmnginkit-library

> **Status:** Draft v1 — awaiting user approval before any code is written.
> **Source of truth:** `/Volumes/Arif_External_Disk/Developments/firmnginkit-library` (Arduino C++ library, v1.0.2).
> **Target repo:** `/Volumes/Arif_External_Disk/Developments/firmngin-sdk/firmngin-sdk-python` (empty, initialized).

---

## 1. Goal

Produce a **production-grade Python SDK** that lets any Python program (gateway, server, Raspberry Pi, CLI tool, integration test) act as a **Firmngin IoT device** on the same protocol surface as the Arduino/ESP32 library.

The SDK must be:

- **Pythonic first** — `async/await`, dataclasses, type hints, context managers.
- **Full feature parity** with the Arduino v1.0.2 library.
- **Async-first** — sync wrapper is a thin adapter for blocking environments (CI scripts, legacy scripts).
- **Hardened** — type-checked (`mypy --strict`), tested (≥90% coverage on core), linted (`ruff`).
- **Distributable** — installable from a Git URL or built wheel via `pip install firmngin`.

---

## 2. Scope

### 2.1 In scope for v1.0.0

| Feature | Arduino (`firmnginkit-library`) | Python (`firmngin-sdk-python`) |
|---|---|---|
| MQTT client over TCP (plain) | PubSubClient | `aiomqtt` |
| MQTT over mTLS (client cert + key) | WiFiClientSecure + BearSSL/mbedtls | `ssl.SSLContext` (built-in) |
| MQTT over TLS with fingerprint pin | BearSSL `setFingerprint` | `ssl.SSLContext` + pinned cert (sha256) |
| E2EE payload encryption | mbedtls AES-GCM 128/256 (ESP32) / ChaChaPoly 256 (ESP8266) | `cryptography` AES-128/256-GCM |
| Persistent offline publish queue | LittleFS circular buffer | File-backed queue — one JSON file per queued publish, atomic temp-write + rename |
| NTP time sync | `configTime()` | `ntplib` (NTP poll on connect) |
| Topic path generation | `getPathXxx()` helpers | internal `_paths.py` module |
| Typed payloads (`Payment`, `Init`, `Verification`, ...) | `firmngin.cpp` classes | `dataclasses` + `from_payload(json)` classmethods |
| Callback registration (state, payment, init, etc.) | `on()` + macros (`ON_PAYMENT`, ...) | `client.on(Event.PAYMENT, cb)` |
| Batch entity update builder | `BatchState` (fluent) | `BatchEntityBuilder` (fluent, async context manager) |
| Location update builder | `LocationUpdate` | `LocationUpdateBuilder` |
| Active session (`begin/endSession`) | `ActiveSession` class | `ActiveSession` context manager |
| Image upload (HTTP multipart) | `uploadImage()` via HTTPClient | `httpx` async multipart |
| Firmware info + `syncFirmwareInfo()` | `setFirmwareInfo()` | `client.set_firmware_info(...)` |
| Debug logging | `_Debug()` macro | `logging` stdlib + structured |
| `setInsecure` flag | boolean | boolean, raises in mTLS mode |
| LWT (Last Will Testament) setup | `setupLWT()` | `_mqtt.will_set(...)` on connect |

### 2.2 Out of scope (deferred)

- **ChaCha20-Poly1305** E2EE — only AES-256-GCM in v1. (ESP8266-only Arduino path; no Python-side need.)
- **Arduino-style global `ON_*` macros** — replaced by decorators (`@on_payment`) registered to a client instance.
- **Vendor-locked PubSubClient re-implementation** — we wrap a maintained MQTT lib.
- **Browser-side crypto / WASM** — server-side Python only.

---

## 3. Architecture

### 3.1 Package layout

```
firmngin-sdk-python/
├── pyproject.toml                  # PEP 621, build + deps + tool config
├── README.md
├── LICENSE                         # MIT (matching Arduino lib)
├── PLAN.md                         # this file
├── CHANGELOG.md
├── src/
│   └── firmngin/
│       ├── __init__.py             # public re-exports
│       ├── client.py               # FirmnginClient (main class, async)
│       ├── client_sync.py          # FirmnginClientSync (sync adapter)
│       ├── config.py               # ClientConfig + KeysConfig (file/env loaded)
│       ├── exceptions.py           # FirmnginError hierarchy
│       ├── paths.py                # topic path builders
│       ├── payloads.py             # dataclasses: Payment, Init, Verification, ...
│       ├── callbacks.py            # CallbackRegistry + decorators
│       ├── mqtt.py                 # MQTT connection, TLS, mTLS, reconnect
│       ├── http.py                 # HTTP client wrapper (httpx) for image upload
│       ├── ntp.py                  # NTP time sync helper
│       ├── crypto.py               # AES-256-GCM E2EE
│       ├── queue.py                # File-backed persistent publish queue
│       ├── builders.py             # BatchEntityBuilder, LocationUpdateBuilder
│       ├── session.py              # ActiveSession context manager
│       ├── logging.py              # structured logger setup
│       └── _version.py             # auto-generated
├── tests/
│   ├── unit/
│   │   ├── test_paths.py
│   │   ├── test_payloads.py
│   │   ├── test_callbacks.py
│   │   ├── test_crypto.py
│   │   ├── test_builders.py
│   │   ├── test_config.py
│   │   ├── test_keys_config.py
│   │   └── test_queue.py
│   ├── integration/
│   │   ├── test_mqtt_connect.py    # needs a broker (testcontainers mosquitto)
│   │   ├── test_round_trip.py
│   │   └── test_image_upload.py
│   ├── conftest.py
│   └── fixtures/
│       └── payloads/               # sample JSON for parser tests
├── examples/
│   ├── async_basic.py
│   ├── sync_basic.py
│   └── async_with_image_upload.py
└── .github/
    └── workflows/
        ├── ci.yml                  # ruff + mypy + pytest
        └── release.yml             # build + publish to PyPI on tag
```

### 3.2 Public API surface (Pythonic)

```python
from firmngin import (
    FirmnginClient,
    FirmnginClientSync,
    ClientConfig, Event,
    Payment, Init, Verifications, DeviceStatus, Entity, EntityCommand, ActiveSession,
)
import asyncio

async def main():
    config = ClientConfig(
        keys=KeysConfig.from_file("keys.json"),      # device_id, device_key, mTLS certs, optional decryptor
    )

    @on_payment
    async def handle_payment(p: Payment):
        if p.is_pending:
            print("waiting for payment:", p.order_id)
        elif p.is_success:
            print("paid!", p.item_title, p.price)

    @on_init
    async def handle_init(i: Init):
        if i.is_pin_enabled:
            await client.request_pin_verification(...)

    async with FirmnginClient(config) as client:
        client.on(Event.PAYMENT, handle_payment)
        client.on(Event.INIT, handle_init)
        # ...
        await client.connect()
        await client.push_entity(Entity("relay"), "on")
        await client.run()                       # blocks until cancelled

asyncio.run(main())
```

### 3.3 Key design decisions

| Decision | Rationale |
|---|---|
| `aiomqtt` (asyncio Paho wrapper) | Most maintained asyncio MQTT lib; built on paho-mqtt 2.x core. |
| File-backed queue for offline publish | Avoids DB dependencies; one queued publish per JSON file with atomic rename keeps the SDK lightweight and durable across restarts. |
| `cryptography` for AES-GCM | Audited (NCC Group, Trail of Bits), FIPS-compatible, used by `httpx` and `paho-mqtt`. |
| `httpx` for HTTP | Async + sync unified API, modern, maintained, HTTP/2-ready. |
| `dataclasses` + `from_payload(json)` classmethod | Idiomatic, immutable by default, JSON serialization trivial. |
| Topic paths in dedicated `paths.py` | Pure functions, 100% unit-testable, easy to evolve. |
| MQTT broker host/port are SDK-managed | Firmngin devices must use the platform broker; users should not configure broker host/port manually. |
| Offline queue path is optional | Queue storage is only needed when offline queueing is enabled; no queue path is required for basic SDK configuration. |
| Single `FirmnginClient` instance per device | Mirrors Arduino `Firmngin` singleton; `FirmnginClientSync` wraps with `asyncio.run`. |
| Callbacks as plain callables (async or sync) | SDK awaits if coroutine, calls directly if not — flexible. |
| Event-driven public API | Mirrors Arduino's `on(...)` model with `client.on(Event.PAYMENT, handler)`; MQTT topics remain internal. |
| `ruff` for lint + format | Replaces black+isort+flake8, faster, single tool. |
| `mypy --strict` | Catches API misuse at type-check time. |

---

## 4. Dependencies

### Runtime
- `aiomqtt >= 2.0` (wraps paho-mqtt 2.x)
- `httpx >= 0.27`
- `cryptography >= 42.0`
- `ntplib >= 0.4`
- `pydantic >= 2.6` (config validation, env loading)
- `typing-extensions >= 4.10` (backport for 3.9)

### Dev / CI
- `pytest >= 8.0`
- `pytest-asyncio >= 0.23`
- `pytest-cov >= 5.0`
- `respx >= 0.21` (HTTP mocking)
- `mypy >= 1.10`
- `ruff >= 0.5`
- `testcontainers[mqtt,postgres] >= 4.7` (integration tests)
- `build >= 1.2`
- `twine >= 5.0`

All deps pinned to `>=` floors with upper bound only on Python compat metadata.

---

## 5. Implementation phases (incremental)

Each phase ends with **green tests + mypy clean + ruff clean**. Commits per phase, single PR per phase unless phased work spans >400 lines.

### Phase 0 — Project skeleton (1 commit)
- `pyproject.toml`, `README.md`, `LICENSE`, `.gitignore`, `src/firmngin/__init__.py` stub, `tests/` empty, `examples/` empty.
- CI workflow: install, ruff, mypy, pytest.
- Result: `pip install -e .` works, `import firmngin` works.

### Phase 1 — Config + paths + payloads (no I/O)
- `config.py`: `KeysConfig` (loaded from `keys.json` or env) + `ClientConfig` pydantic model with validators. `KeysConfig` validates PEM cert blocks parse correctly, key bytes are exactly 32 bytes after base64 decode.
- `paths.py`: pure functions, full coverage against a fixtures table.
- `payloads.py`: dataclasses with `from_payload(json: str) -> Self` and `to_payload() -> str`.
- `exceptions.py`: hierarchy (`FirmnginError`, `ConnectionError`, `AuthError`, `PayloadError`).
- Unit tests for all three modules. **No MQTT, no HTTP, no I/O.**
- Exit: `mypy --strict` clean, coverage ≥95% on these modules.

### Phase 2 — Crypto + E2EE
- Internal `crypto.py`: AES-GCM encrypt/decrypt helpers hidden behind `FirmnginClient` publish/dispatch paths. Packet format remains `nonce[12] || ciphertext || tag[16]`; callers do not use these helpers directly.
- Round-trip tests with NIST AES-128-GCM and AES-256-GCM test vectors.
- Tamper-detection test (flip a bit → decrypt raises `CryptoError`).
- `KeysConfig` validator: hex `decryptor` decodes to 16 or 32 bytes, otherwise `ValueError` with field name.
- Exit: 100% coverage on `crypto.py`.

### Phase 3 — Persistent queue (file-backed)
- Internal `queue.py`: `OfflineQueue` async class used by `FirmnginClient` when offline queueing is enabled.
  - Storage: one JSON file per queued publish (`id`, `topic`, base64 `payload`, `retained`, `created_at`, `attempts`).
  - `enqueue(topic, payload, retained)`, `peek()`, `drop()`, `drain(publish_fn)`.
  - Atomic write via temp file + `os.replace`; oldest-first by timestamped message id.
- Unit tests with temp queue directory.
- Crash-recovery test: kill mid-drain → restart → no loss, no duplicates.
- Exit: 100% coverage on `queue.py`.

### Phase 4 — MQTT client + connect/reconnect + paths
- `mqtt.py`: `MQTTConnection` async wrapper around `aiomqtt`.
  - TLS / mTLS setup via `ssl.SSLContext`.
  - Fingerprint pinning (verify cert sha256 against pinned value).
  - Exponential backoff reconnect.
  - LWT setup on connect.
- Path-based subscribe (uses `paths.py`).
- Integration test: testcontainers `eclipse-mosquitto` → connect, publish, receive.
- Exit: integration test passes against real broker.

### Phase 5 — Callbacks + builders + `FirmnginClient` orchestration
- `callbacks.py`: `CallbackRegistry` with priority + multiple-handler support.
- `builders.py`: `BatchEntityBuilder` + `LocationUpdateBuilder` (fluent, async).
- `session.py`: `ActiveSession` async context manager.
- `client.py`: `FirmnginClient` orchestrator.
  - `connect()`, `run()`, `disconnect()`, `push_entity(...)`, `update_entities(json)`, `request_init()`, `end_session()`, `set_firmware_info(...)`, `sync_firmware_info()`.
  - Hooks callback registry to MQTT message dispatch.
  - Hooks offline queue: publish → if fail → enqueue → drain on reconnect.
- `client_sync.py`: thin sync wrapper.
- Unit tests with mocked MQTT + offline queue.
- Integration test: end-to-end connect → receive init → push entity → receive payment → callback fires.

### Phase 6 — Image upload
- HTTP multipart upload via `httpx.AsyncClient`.
- `client.upload_image(entity, image_path)`; API path, auth headers, multipart details, and content-type detection remain internal.
- Integration test: mock HTTP server, verify multipart body, verify success/error callbacks.

### Phase 7 — NTP sync + time helpers
- `ntp.py`: `sync_time(server, timeout)` via `ntplib`.
- Auto-call on first connect.
- Integration test: mock NTP server response, verify epoch skew.

### Phase 8 — Documentation + examples
- `README.md`: install, quickstart, mTLS setup, E2EE setup, image upload.
- 4 `examples/*.py` (already enumerated above) — each must run end-to-end on a dev broker.
- `CHANGELOG.md` 0.1.0 entry.
- `docs/` (optional MkDocs site).

### Phase 9 — Hardening + release prep
- `mypy --strict` clean across entire codebase.
- `ruff` clean.
- Coverage gate ≥90% (core ≥95%).
- Security audit: `pip-audit`, `bandit`.
- `pyproject.toml` metadata complete (classifiers, URLs, keywords matching Arduino).
- Tag `v1.0.0`, build, publish to PyPI.
- Release notes cross-link to Arduino v1.0.2.

---

## 6. Testing strategy

- **Unit**: pure functions, mocked I/O. Fast (<1s total). Run on every commit.
- **Integration**: real broker via testcontainers, real temporary queue directory. Run on CI nightly + pre-release.
- **Coverage gates**: core (`client.py`, `mqtt.py`, `queue.py`, `crypto.py`, `paths.py`, `payloads.py`) ≥95%, overall ≥90%.
- **Type safety**: `mypy --strict` on `src/firmngin/`.
- **Contract tests**: payload JSON must round-trip against fixtures derived from Arduino library's expected wire format (cross-check topic paths byte-for-byte against `keywords.txt` + `library.json`).

---

## 7. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Arduino wire protocol differs from docs (undocumented fields) | Med | High | Cross-validate every payload type against Arduino `.cpp` JSON parsing logic before finalizing dataclasses. |
| `aiomqtt` upstream churn | Low | Med | Pin version, vendor fork fallback plan. |
| File queue can duplicate a publish if the process crashes after broker publish but before local file delete | Med | Med | Document at-least-once semantics; server/device handlers must remain idempotent by message content. |
| `mypy --strict` friction with `paho-mqtt` types | Med | Low | Type stubs (`types-aio-paho-mqtt`) or thin local protocols. |
| Python 3.9 minimum vs `cryptography` latest needing 3.10+ | Med | Med | Pin `cryptography >= 42, < 44` (last 3.9-compatible line is 43.x). Document upper pin. |
| E2EE required breaks Arduino users without `decryptor` | High | High | Loud `ValueError` at config load with field name and reason; README migration guide shows how to generate 16-byte hex key and update `keys.json`. `keys.json.example` always includes `decryptor` placeholder. |
| Reviewer burnout from too-large diff | Med | Med | Phase-by-phase PRs, ≤400 lines each. |

---

## 8. Non-goals (explicit)

- We do **not** re-implement `PubSubClient`. We depend on a maintained lib.
- We do **not** ship a CLI tool — pure library only. (CLI can be a future sibling repo.)
- We do **not** support Python ≤ 3.8. Final: 3.9 minimum.
- We do **not** ship ChaCha20-Poly1305 in v1. AES-256-GCM only.
- We do **not** claim "drop-in replacement" for Arduino code. We are a **Python-native equivalent**; migration requires code rewrite.

---

## 9. Resolved decisions

1. **Python minimum**: **3.9** ✅
2. **Distribution name on PyPI**: **`firmngin`** ✅
3. **Repository URL**: **`github.com/firmngin/firmngin-sdk-python`** ✅
4. **Default E2EE + material config**: **E2EE REQUIRED**. All cryptographic material and device identity are loaded from a **single `keys.json` file** managed by the platform. Contents (matches production schema):
   - `device_id` (str) — **REQUIRED**. MQTT client username / device identifier (e.g. `dev-1782217379-d5d1680b`)
   - `device_key` (str) — **REQUIRED**. MQTT client password / device secret (e.g. `key-kdxQXIXNmteivUYzzoNBT`)
   - `decryptor` (str, hex) — **REQUIRED**. E2EE key (32 hex chars = 16 bytes AES-128-GCM, or 64 hex chars = 32 bytes AES-256-GCM). Mirrors Arduino `crypto.cpp` key-length handling. SDK raises `ValueError` at config load if missing or invalid length.
   - `validation_mode` (str) — **REQUIRED**. `"ca"` | `"pin"` | `"both"`. Default `"both"` if unspecified. Controls broker cert verification strategy.
   - `ca_cert` (str, PEM) — **REQUIRED for `ca` and `both` modes**. CA cert for **MQTT broker** TLS verification.
   - `service_ca_cert` (str, PEM) — **REQUIRED**. CA cert for **REST API** image upload TLS verification.
   - `client_cert` (str, PEM) — **REQUIRED for mTLS**. Device client certificate for mTLS.
   - `private_key` (str, PEM) — **REQUIRED for mTLS**. Device client private key for mTLS (note: field is `private_key`, not `client_key`).
   - `fingerprint_sha256` (str, optional, hex colon-separated) — **REQUIRED for `pin` and `both` modes**. Broker cert pin.
   
   Loaded via `KeysConfig.from_file(path)` or `KeysConfig.from_env(prefix="FIRMNGIN_")`. Every required field raises a specific `ValueError` with field name and reason at load time — the SDK refuses to instantiate `ClientConfig` with a partial `KeysConfig`. A `keys.json.example` template ships with the SDK (real `keys.json` is gitignored).
   
   **Implication for Arduino migration**: Python SDK is stricter than Arduino — a device that works on Arduino without `keys.h` will fail to instantiate on Python until `decryptor` is added. Documented in README migration guide.
5. **PyPI publishing**: **deferred** to end-of-project after user review. Release workflow will be **draft-only**: tag triggers build + TestPyPI upload + manual `twine upload` command documented in release notes. No auto-publish to production PyPI.

---

## 10. Acceptance criteria (v1.0.0)

- [ ] All 10 phases complete with green tests.
- [ ] `mypy --strict` clean.
- [ ] `ruff check` + `ruff format --check` clean.
- [ ] Coverage: core ≥95%, overall ≥90%.
- [ ] `keys.json.example` template included in repo; loading `KeysConfig.from_file("keys.json.example")` succeeds and validates all field shapes.
- [ ] E2EE round-trip: 16-byte and 32-byte keys both encrypt/decrypt successfully with Arduino packet format (nonce[12] || ct || tag[16]).
- [ ] `validation_mode="both"` enforces both CA verification AND fingerprint pin; mismatched CA raises TLS error; mismatched fingerprint raises TLS error.
- [ ] `KeysConfig.from_file()` raises `ValueError` with field name if `decryptor` is missing or wrong length; same for missing `device_id`, `device_key`, `ca_cert`, `service_ca_cert`, `client_cert`, `private_key` as applicable per `validation_mode`.
- [ ] README migration guide explains how an existing Arduino user generates a 16-byte hex `decryptor` and updates `keys.json` to migrate to Python SDK.
- [ ] `examples/async_basic.py` connects to `asia-jkt1.firmngin.dev:58884` with mTLS and exchanges init → push_entity → receives payment.
- [ ] Offline queue: kill connection mid-publish, reconnect, queued messages drain in order without loss/duplication.
- [ ] Image upload: 1MB JPEG, mock server receives multipart body with correct content-type.
- [ ] `pip-audit` clean (no known vulns in deps).
- [ ] README quickstart works on a fresh Python 3.9 venv in <5 minutes.

---

## 11. Out of plan (track for future)

- TypeScript / Node.js SDK (sibling repo)
- Go SDK (sibling repo)
- Integration test harness against staging Firmngin backend (requires backend cooperation)
- CLI tool wrapping the SDK
