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
from firmngin.payloads import Entity, entity_key

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

    async def upload_image(self, entity: Entity | str | int, image: str | Path) -> str:
        httpx = _require_httpx()
        key = entity_key(entity)
        image_path = Path(image)
        if not image_path.name:
            raise ValueError("image path must point to a file")
        if not image_path.is_file():
            raise FileNotFoundError(str(image_path))

        content_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        data = await asyncio.to_thread(image_path.read_bytes)

        path = "/device-camera/upload"
        timestamp = str(int(time.time()))
        message = f"{self._config.keys.device_id}.{timestamp}.POST.{path}"
        headers = {
            "X-Device-ID": self._config.keys.device_id,
            "X-Device-Timestamp": timestamp,
            "X-Device-Signature": _device_signature(self._config.keys.device_key, message),
        }

        cert: tuple[str, str] | None = None
        if self._config.mtls and self._config.keys.client_cert and self._config.keys.private_key:
            cert_file = self._pem_files.write(self._config.keys.client_cert)
            key_file = self._pem_files.write(self._config.keys.private_key)
            if cert_file is not None and key_file is not None:
                cert = (cert_file, key_file)

        files = {"image": (image_path.name, data, content_type)}
        form = {"entity_key": key}
        url = f"{self._config.api_base_url.rstrip('/')}{path}"

        client = await self._get_client(httpx, cert)
        try:
            response = await client.post(url, headers=headers, data=form, files=files)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            raise ConnectionError("image upload failed") from exc

    async def _get_client(self, httpx: Any, cert: tuple[str, str] | None) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                cert=cert,
                timeout=self._config.connect_timeout_seconds,
                verify=_ssl_context(self._config),
            )
        return self._client


__all__ = ["DeviceHttpClient"]
