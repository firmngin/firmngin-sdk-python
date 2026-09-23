"""Unit tests for Firmngin device HTTP calls."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from firmngin.config import ClientConfig, KeysConfig
from firmngin.exceptions import ConnectionError
from firmngin.http import DeviceHttpClient

from .test_config import _valid_keys_data


class _Response:
    text = "uploaded"
    content = b"uploaded"

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"data": {"is_kiosk": True, "kiosk_ready": True, "service_type": "vending"}}


class _HttpClient:
    def __init__(self) -> None:
        self.url = ""
        self.method = ""
        self.headers: dict[str, str] = {}
        self.json_body: dict[str, Any] | None = None
        self.files: dict[str, Any] = {}
        self.form: dict[str, Any] = {}

    async def post(self, url: str, **kwargs: Any) -> _Response:
        self.url = url
        self.method = "POST"
        self.headers = kwargs.get("headers") or {}
        self.files = kwargs.get("files") or {}
        self.form = kwargs.get("data") or {}
        return _Response()

    async def request(self, method: str, url: str, **kwargs: Any) -> _Response:
        self.method = method
        self.url = url
        self.headers = kwargs.get("headers") or {}
        self.json_body = kwargs.get("json")
        return _Response()


class _ErrorResponse:
    def json(self) -> dict[str, str]:
        return {
            "error": "KIOSK_NOT_CONFIGURED",
            "message": "Device is not bound to a merchant",
        }


class _HttpStatusError(Exception):
    def __init__(self) -> None:
        super().__init__("404 Not Found")
        self.response = _ErrorResponse()


class _ErrorHttpClient(_HttpClient):
    async def request(self, method: str, url: str, **kwargs: Any) -> _Response:
        await super().request(method, url, **kwargs)
        raise _HttpStatusError


@pytest.mark.asyncio
async def test_upload_image_uses_service_api_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = ClientConfig(keys=KeysConfig.from_dict(_valid_keys_data()))
    device_http = DeviceHttpClient(config)
    http_client = _HttpClient()
    image = tmp_path / "snapshot.jpg"
    image.write_bytes(b"image")

    async def get_client(_httpx: Any, _cert: tuple[str, str] | None) -> _HttpClient:
        return http_client

    monkeypatch.setattr(
        "firmngin.http._require_httpx",
        lambda: SimpleNamespace(HTTPError=Exception),
    )
    monkeypatch.setattr(device_http, "_get_client", get_client)

    result = await device_http.upload_image("camera", image)

    assert result == "uploaded"
    assert http_client.url == "https://ota.firmngin.dev/api/v1/device-camera/upload"
    assert http_client.form == {"entity_key": "camera"}
    assert http_client.files["image"] == ("snapshot.jpg", b"image", "image/jpeg")

    await device_http.aclose()


@pytest.mark.asyncio
async def test_upload_image_accepts_raw_bytes_with_content_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = ClientConfig(keys=KeysConfig.from_dict(_valid_keys_data()))
    device_http = DeviceHttpClient(config)
    http_client = _HttpClient()

    async def get_client(_httpx: Any, _cert: tuple[str, str] | None) -> _HttpClient:
        return http_client

    monkeypatch.setattr(
        "firmngin.http._require_httpx",
        lambda: SimpleNamespace(HTTPError=Exception),
    )
    monkeypatch.setattr(device_http, "_get_client", get_client)

    result = await device_http.upload_image(
        "camera",
        b"\xff\xd8raw-jpeg",
        content_type="image/jpeg",
        filename="frame.jpg",
    )

    assert result == "uploaded"
    assert http_client.form == {"entity_key": "camera"}
    assert http_client.files["image"] == ("frame.jpg", b"\xff\xd8raw-jpeg", "image/jpeg")

    await device_http.aclose()


@pytest.mark.asyncio
async def test_upload_image_raw_bytes_defaults_and_empty_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = ClientConfig(keys=KeysConfig.from_dict(_valid_keys_data()))
    device_http = DeviceHttpClient(config)
    http_client = _HttpClient()

    async def get_client(_httpx: Any, _cert: tuple[str, str] | None) -> _HttpClient:
        return http_client

    monkeypatch.setattr(
        "firmngin.http._require_httpx",
        lambda: SimpleNamespace(HTTPError=Exception),
    )
    monkeypatch.setattr(device_http, "_get_client", get_client)

    await device_http.upload_image("camera", bytearray(b"png-bytes"))

    assert http_client.files["image"] == (
        "capture.jpg",
        b"png-bytes",
        "application/octet-stream",
    )

    with pytest.raises(ValueError, match="image data must not be empty"):
        await device_http.upload_image("camera", b"")

    await device_http.aclose()


@pytest.mark.asyncio
async def test_kiosk_bootstrap_signs_path(monkeypatch: pytest.MonkeyPatch) -> None:
    keys = _valid_keys_data()
    config = ClientConfig(keys=KeysConfig.from_dict(keys))
    device_http = DeviceHttpClient(config)
    http_client = _HttpClient()

    async def get_client(_httpx: Any, _cert: tuple[str, str] | None) -> _HttpClient:
        return http_client

    monkeypatch.setattr(
        "firmngin.http._require_httpx",
        lambda: SimpleNamespace(HTTPError=Exception),
    )
    monkeypatch.setattr(device_http, "_get_client", get_client)

    result = await device_http.kiosk_bootstrap()

    assert result.is_kiosk is True
    assert result.kiosk_ready is True
    assert http_client.method == "GET"
    assert http_client.url == "https://ota.firmngin.dev/api/v1/device/kiosk/bootstrap"
    assert http_client.headers["X-Device-ID"] == keys["device_id"]
    assert "X-Device-Signature" in http_client.headers

    await device_http.aclose()


@pytest.mark.asyncio
async def test_kiosk_bootstrap_preserves_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    config = ClientConfig(keys=KeysConfig.from_dict(_valid_keys_data()))
    device_http = DeviceHttpClient(config)
    http_client = _ErrorHttpClient()

    async def get_client(_httpx: Any, _cert: tuple[str, str] | None) -> _ErrorHttpClient:
        return http_client

    monkeypatch.setattr(
        "firmngin.http._require_httpx",
        lambda: SimpleNamespace(HTTPError=_HttpStatusError),
    )
    monkeypatch.setattr(device_http, "_get_client", get_client)

    with pytest.raises(ConnectionError, match="KIOSK_NOT_CONFIGURED") as exc_info:
        await device_http.kiosk_bootstrap()

    assert "Device is not bound to a merchant" in str(exc_info.value)

    await device_http.aclose()


@pytest.mark.asyncio
async def test_kiosk_create_order_posts_items(monkeypatch: pytest.MonkeyPatch) -> None:
    class _OrderResponse(_Response):
        content = b'{"order_id":"o1","qr":"abc"}'

        def json(self) -> dict[str, Any]:
            return {"order_id": "o1", "qr": "abc", "payment_method": "qris"}

    class _OrderHttpClient(_HttpClient):
        async def request(self, method: str, url: str, **kwargs: Any) -> _OrderResponse:
            await super().request(method, url, **kwargs)
            return _OrderResponse()

    config = ClientConfig(keys=KeysConfig.from_dict(_valid_keys_data()))
    device_http = DeviceHttpClient(config)
    http_client = _OrderHttpClient()

    async def get_client(_httpx: Any, _cert: tuple[str, str] | None) -> _OrderHttpClient:
        return http_client

    monkeypatch.setattr(
        "firmngin.http._require_httpx",
        lambda: SimpleNamespace(HTTPError=Exception),
    )
    monkeypatch.setattr(device_http, "_get_client", get_client)

    order = await device_http.kiosk_create_order(
        items=[{"menu_item_id": "m1", "quantity": 1}],
    )

    assert order.order_id == "o1"
    assert order.qr == "abc"
    assert http_client.method == "POST"
    assert http_client.url == "https://ota.firmngin.dev/api/v1/device/kiosk/orders"
    assert http_client.json_body is not None
    assert http_client.json_body["payment_method"] == "qris"
    assert http_client.json_body["items"][0]["menu_item_id"] == "m1"

    await device_http.aclose()
