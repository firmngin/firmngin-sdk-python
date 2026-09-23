"""Internal HTTP client for Firmngin device APIs."""

from __future__ import annotations

import asyncio
import hmac
import mimetypes
import ssl
import time
from hashlib import sha256
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

from firmngin._pem import TempPemFiles
from firmngin.config import ClientConfig
from firmngin.exceptions import ConnectionError
from firmngin.payloads import (
    Entity,
    KioskBootstrap,
    KioskMenu,
    KioskOrder,
    KioskOrderStatus,
    entity_key,
)

if TYPE_CHECKING:
    import httpx


def _require_httpx() -> Any:
    try:
        import httpx  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError(
            "httpx is required for HTTP features. Install with: pip install firmngin[http]"
        ) from exc
    return httpx


def _device_signature(device_key: str, message: str) -> str:
    return hmac.new(device_key.encode("utf-8"), message.encode("utf-8"), sha256).hexdigest()


def _ssl_context(config: ClientConfig) -> ssl.SSLContext | bool:
    if config.insecure:
        return False
    return ssl.create_default_context(cadata=config.keys.service_ca_cert)


def _http_error_detail(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    status = response.status_code
    try:
        body = response.read()
    except Exception:
        return f"HTTP {status}"
    if not body:
        return f"HTTP {status}"
    text = body.decode("utf-8", errors="replace").strip()
    try:
        payload = __import__("json").loads(body)
    except Exception:
        clean = _strip_html(text)[:200]
        return f"HTTP {status}: {clean}" if clean else f"HTTP {status}"
    if not isinstance(payload, dict):
        return f"HTTP {status}"
    error = payload.get("error")
    message = payload.get("message")
    if error and message:
        return f"{error}: {message}"
    if message:
        return str(message)
    if error:
        return str(error)
    return None


def _strip_html(s: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    import re

    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"&[a-z]+;", lambda m: {"&lt;": "<", "&gt;": ">", "&amp;": "&", "&quot;": '"'}.get(m.group(0), m.group(0)), s)
    return re.sub(r"\s+", " ", s).strip()


class DeviceHttpClient:
    """High-level device HTTP calls; URL and signing details remain internal."""

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._pem_files = TempPemFiles()
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> DeviceHttpClient:
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    def close(self) -> None:
        self._pem_files.cleanup()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._pem_files.cleanup()

    def _signed_headers(self, method: str, path: str) -> dict[str, str]:
        timestamp = str(int(time.time()))
        message = f"{self._config.keys.device_id}.{timestamp}.{method.upper()}.{path}"
        return {
            "X-Device-ID": self._config.keys.device_id,
            "X-Device-Timestamp": timestamp,
            "X-Device-Signature": _device_signature(self._config.keys.device_key, message),
        }

    async def _mtls_cert(self) -> tuple[str, str] | None:
        if self._config.mtls and self._config.keys.client_cert and self._config.keys.private_key:
            cert_file = self._pem_files.write(self._config.keys.client_cert)
            key_file = self._pem_files.write(self._config.keys.private_key)
            if cert_file is not None and key_file is not None:
                return (cert_file, key_file)
        return None

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        httpx = _require_httpx()
        headers = self._signed_headers(method, path)
        url = f"{self._config.api_base_url.rstrip('/')}{path}"
        cert = await self._mtls_cert()
        client = await self._get_client(httpx, cert)
        try:
            response = await client.request(
                method.upper(),
                url,
                headers=headers,
                json=json_body,
            )
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()
        except httpx.HTTPError as exc:
            detail = _http_error_detail(exc)
            suffix = f": {detail}" if detail else ""
            raise ConnectionError(f"device http {method.upper()} {path} failed{suffix}") from exc

    async def upload_image(
        self,
        entity: Entity | str | int,
        image: str | Path | bytes | bytearray | memoryview,
        *,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> str:
        httpx = _require_httpx()
        key = entity_key(entity)

        if isinstance(image, (bytes, bytearray, memoryview)):
            data = bytes(image)
            if not data:
                raise ValueError("image data must not be empty")
            resolved_content_type = content_type or "application/octet-stream"
            image_name = filename or "capture.jpg"
        else:
            image_path = Path(image)
            if not image_path.name:
                raise ValueError("image path must point to a file")
            if not image_path.is_file():
                raise FileNotFoundError(str(image_path))
            data = await asyncio.to_thread(image_path.read_bytes)
            resolved_content_type = (
                content_type
                or mimetypes.guess_type(image_path.name)[0]
                or "application/octet-stream"
            )
            image_name = filename or image_path.name

        path = "/device-camera/upload"
        headers = self._signed_headers("POST", path)
        cert = await self._mtls_cert()

        files = {"image": (image_name, data, resolved_content_type)}
        form = {"entity_key": key}
        url = f"{self._config.api_base_url.rstrip('/')}{path}"

        client = await self._get_client(httpx, cert)
        try:
            response = await client.post(url, headers=headers, data=form, files=files)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            detail = _http_error_detail(exc)
            suffix = f": {detail}" if detail else ""
            raise ConnectionError(f"image upload failed{suffix}") from exc

    async def kiosk_bootstrap(self) -> KioskBootstrap:
        raw = await self._request_json("GET", "/device/kiosk/bootstrap")
        return KioskBootstrap.from_response(raw)

    async def kiosk_menu(self) -> KioskMenu:
        raw = await self._request_json("GET", "/device/kiosk/menu")
        return KioskMenu.from_response(raw)

    async def kiosk_create_order(
        self,
        *,
        items: list[dict[str, Any]],
        customer: dict[str, Any] | None = None,
        client_order_key: str | None = None,
    ) -> KioskOrder:
        body: dict[str, Any] = {"items": items, "payment_method": "qris"}
        if customer is not None:
            body["customer"] = customer
        if client_order_key:
            body["client_order_key"] = client_order_key
        raw = await self._request_json("POST", "/device/kiosk/orders", json_body=body)
        return KioskOrder.from_response(raw)

    async def kiosk_order_status(self, order_id: str) -> KioskOrderStatus:
        oid = str(order_id).strip()
        if not oid:
            raise ValueError("order_id is required")
        raw = await self._request_json("GET", f"/device/kiosk/orders/{oid}")
        return KioskOrderStatus.from_response(raw)

    async def kiosk_cancel_order(self, order_id: str) -> dict[str, Any]:
        oid = str(order_id).strip()
        if not oid:
            raise ValueError("order_id is required")
        raw = await self._request_json("POST", f"/device/kiosk/orders/{oid}/cancel")
        return raw if isinstance(raw, dict) else {}

    async def _get_client(self, httpx: Any, cert: tuple[str, str] | None) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                cert=cert,
                timeout=self._config.connect_timeout_seconds,
                verify=_ssl_context(self._config),
            )
        return self._client


__all__ = ["DeviceHttpClient"]
