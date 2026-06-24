"""Minimal Flask project using the Firmngin Python SDK."""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading
from pathlib import Path

from flask import Flask, request
from werkzeug.utils import secure_filename

from firmngin import AsyncClient, ClientConfig, Entity, EntityCommand, Event, Payment

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
KEYS_PATH = Path(os.environ.get("FIRMNGIN_KEYS_PATH", BASE_DIR / "keys.json"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

relay = Entity(1)
camera = Entity("camera")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only")
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR

async_client: AsyncClient | None = None
loop: asyncio.AbstractEventLoop | None = None


def create_client() -> AsyncClient:
    config = ClientConfig.from_file(KEYS_PATH)
    device_client = AsyncClient(config)

    @device_client.on(Event.PAYMENT)
    async def handle_payment(payment: Payment) -> None:
        status = "success" if payment.is_success else "pending"
        print(f"payment {status}: order_id={payment.order_id} item={payment.item_title}")

    @device_client.on_entity(relay)
    async def handle_relay(command: EntityCommand) -> None:
        print(f"relay command received: key={command.key} value={command.value}")

    return device_client


async def run_device_client() -> None:
    global async_client

    try:
        async_client = create_client()
        await async_client.connect()
        print("firmngin client connected")
        await async_client.request_init()
        await async_client.run()
    except Exception as exc:
        print(f"firmngin client stopped: {exc}")


def start_device_worker() -> None:
    global loop

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_device_client())


def submit(coro: object) -> object:
    if loop is None or async_client is None:
        raise RuntimeError("Firmngin client is not ready")
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=20)


@app.get("/")
def index() -> tuple[dict[str, str], int]:
    print("health check")
    return {"status": "ok"}, 200


@app.post("/relay")
def update_relay() -> tuple[dict[str, str], int]:
    data = request.get_json(silent=True) or {}
    value = str(data.get("value") or request.form.get("value") or "off")
    if value not in {"on", "off"}:
        return {"error": "value must be on or off"}, 400

    current = async_client
    if current is None:
        return {"error": "Firmngin client is not ready"}, 503

    try:
        submit(current.push_entity(relay, value))
        print(f"relay state sent: {value}")
        return {"status": "sent", "relay": value}, 200
    except Exception as exc:
        print(f"relay publish failed: {exc}")
        return {"error": str(exc)}, 500


@app.post("/image")
def upload_image() -> tuple[dict[str, str], int]:
    uploaded = request.files.get("image")
    if uploaded is None or uploaded.filename == "":
        return {"error": "image file is required"}, 400

    filename = secure_filename(uploaded.filename)
    suffix = Path(filename).suffix or ".jpg"
    current = async_client
    if current is None:
        return {"error": "Firmngin client is not ready"}, 503

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=suffix, dir=app.config["UPLOAD_FOLDER"]
    ) as file:
        uploaded.save(file)
        image_path = Path(file.name)

    try:
        submit(current.upload_image(camera, image_path))
        print(f"image uploaded: {filename}")
        return {"status": "uploaded", "filename": filename}, 200
    except Exception as exc:
        print(f"image upload failed: {exc}")
        return {"error": str(exc)}, 500
    finally:
        image_path.unlink(missing_ok=True)


worker = threading.Thread(target=start_device_worker, daemon=True)
worker.start()


if __name__ == "__main__":
    app.run(debug=False)
