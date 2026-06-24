"""Internal HTTP client for Firmngin device APIs."""

from __future__ import annotations

import asyncio
import hmac
import mimetypes
import ssl
import tempfile
import time
from hashlib import sha256
from pathlib import Path
from types import TracebackType

import httpx

from firmngin.config import ClientConfig
from firmngin.exceptions import ConnectionError
from firmngin.payloads import Entity, entity_key


class _TempPemFiles:
    """Keep PEM strings available as files for clients that require file paths."""

    def __init__(self) -> None:
        self._files: list[Path] = []

    def write(self, content: str | None) -> str | None:
        if content is None:
            return None
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as file:
            file.write(content)
            file.flush()
            path = Path(file.name)
        self._files.append(path)
        return str(path)

    def cleanup(self) -> None:
        for path in self._files:
            path.unlink(missing_ok=True)
        self._files.clear()


def _device_signature(device_key: str, message: str) -> str:
    return hmac.new(device_key.encode("utf-8"), message.encode("utf-8"), sha256).hexdigest()


def _ssl_context(config: ClientConfig) -> ssl.SSLContext | bool:
    if config.insecure:
        return False
    context = ssl.create_default_context(cadata=config.keys.service_ca_cert)
    return context


class DeviceHttpClient:
    """High-level device HTTP calls; URL and signing details remain internal."""

    def __init__(self, config: ClientConfig) -> None:
        self._config = config
        self._pem_files = _TempPemFiles()

    async def __aenter__(self) -> DeviceHttpClient:
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._pem_files.cleanup()

    async def upload_image(self, entity: Entity | str | int, image: str | Path) -> str:
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

        try:
            async with httpx.AsyncClient(
                cert=cert,
                timeout=self._config.connect_timeout_seconds,
                verify=_ssl_context(self._config),
            ) as client:
                response = await client.post(url, headers=headers, data=form, files=files)
                response.raise_for_status()
                return response.text
        except httpx.HTTPError as exc:
            raise ConnectionError("image upload failed") from exc


__all__ = ["DeviceHttpClient"]
