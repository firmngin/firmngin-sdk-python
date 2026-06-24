"""Blocking wrapper around the async Firmngin client."""

from __future__ import annotations

import asyncio
from typing import Any

from firmngin.client import FirmnginClient
from firmngin.config import ClientConfig
from firmngin.payloads import Entity


class SyncFirmnginClient:
    """Small sync adapter for scripts that cannot manage an event loop."""

    def __init__(self, config: ClientConfig) -> None:
        self._client = FirmnginClient(config)

    @property
    def async_client(self) -> FirmnginClient:
        return self._client

    def connect(self) -> None:
        asyncio.run(self._client.connect())

    def disconnect(self) -> None:
        asyncio.run(self._client.disconnect())

    def push_entity(self, entity: Entity | str | int, value: Any) -> None:
        asyncio.run(self._client.push_entity(entity, value))

    def update_entities(self, entities: dict[str, Any]) -> None:
        asyncio.run(self._client.update_entities(entities))

    def request_init(self) -> None:
        asyncio.run(self._client.request_init())

    def upload_image(self, entity: Entity | str | int, image: str) -> str:
        return asyncio.run(self._client.upload_image(entity, image))


__all__ = ["SyncFirmnginClient"]
