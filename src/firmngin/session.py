"""Active session helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from firmngin.payloads import Entity, EntityValue


class ActiveSessionClient(Protocol):
    def entity(self, entity: Entity | str | int) -> EntityValue:
        """Return a locally known entity value."""
        ...

    async def end_session(self) -> bool:
        """Request local active session end."""
        ...


@dataclass(frozen=True)
class ActiveSession:
    """Current active-service session delivered through event callbacks."""

    _client: ActiveSessionClient
    order_id: str
    active: bool
    can_run: bool

    def is_active(self) -> bool:
        return self.active

    def entity(self, entity: Entity | str | int) -> EntityValue:
        return self._client.entity(entity)

    async def end_session(self) -> bool:
        return await self._client.end_session()


__all__ = ["ActiveSession"]
