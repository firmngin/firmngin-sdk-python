"""Typed payloads matching the Arduino firmnginkit-library JSON surface."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from firmngin.exceptions import PayloadError

JsonObject = dict[str, Any]


def _loads_object(payload: str) -> JsonObject:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PayloadError("payload must be valid JSON") from exc
    if not isinstance(raw, dict):
        raise PayloadError("payload must be a JSON object")
    return raw


def _dumps_object(payload: JsonObject) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True)
class Payment:
    """Payment payload parsed from Arduino keys ``it``, ``pc``, ``oid``, and ``q``."""

    item_title: str = ""
    price: str = ""
    order_id: str = ""
    quantity: int = 1
    is_pending: bool = False
    is_success: bool = False

    @classmethod
    def from_payload(
        cls,
        payload: str,
        *,
        is_pending: bool = False,
        is_success: bool = False,
    ) -> Payment:
        raw = _loads_object(payload)
        quantity = int(raw.get("q", 1))
        return cls(
            item_title=str(raw.get("it", "")),
            price=str(raw.get("pc", "")),
            order_id=str(raw.get("oid", "")),
            quantity=max(quantity, 1),
            is_pending=is_pending,
            is_success=is_success,
        )

    @property
    def is_valid(self) -> bool:
        return bool(self.item_title or self.order_id)

    def to_payload(self) -> str:
        return _dumps_object(
            {
                "it": self.item_title,
                "oid": self.order_id,
                "pc": self.price,
                "q": self.quantity,
            }
        )


@dataclass(frozen=True)
class Verification:
    """Verification payload parsed from Arduino keys ``pi``, ``si``, ``ttl``, ``pn``, ``pr``."""

    pin: str = ""
    session_id: str = ""
    ttl: int = 0
    pin_met: bool = False
    precondition_met: bool = False
    has_result_keys: bool = False

    @classmethod
    def from_payload(cls, payload: str) -> Verification:
        raw = _loads_object(payload)
        return cls(
            pin=str(raw.get("pi", "")),
            session_id=str(raw.get("si", "")),
            ttl=int(raw.get("ttl", 0)),
            pin_met=bool(raw.get("pn", False)),
            precondition_met=bool(raw.get("pr", False)),
            has_result_keys="pn" in raw,
        )

    @property
    def is_valid(self) -> bool:
        return bool(self.pin) or self.has_result_keys

    @property
    def has_pin_number(self) -> bool:
        return bool(self.pin)

    @property
    def has_result(self) -> bool:
        return self.is_valid and not self.pin

    def to_payload(self) -> str:
        return _dumps_object(
            {
                "pi": self.pin,
                "pn": self.pin_met,
                "pr": self.precondition_met,
                "si": self.session_id,
                "ttl": self.ttl,
            }
        )


@dataclass(frozen=True)
class Init:
    """Init payload parsed from Arduino keys ``e``, ``m``, ``oid``, and ``vf``."""

    entities: Any = None
    merchant_status: str = ""
    active_order_id: str = ""
    verification_flag: int = 0
    has_merchant_status: bool = False

    @classmethod
    def from_payload(cls, payload: str) -> Init:
        raw = _loads_object(payload)
        return cls(
            entities=raw.get("e"),
            merchant_status=str(raw.get("m", "")),
            active_order_id=str(raw.get("oid", "")),
            verification_flag=int(raw.get("vf", 0)),
            has_merchant_status="m" in raw,
        )

    @property
    def is_valid(self) -> bool:
        return self.has_merchant_status

    @property
    def is_idle(self) -> bool:
        return self.merchant_status == "idle"

    @property
    def is_pending_payment(self) -> bool:
        return self.merchant_status == "pending_payment"

    @property
    def is_expired_payment(self) -> bool:
        return self.merchant_status == "expired_payment"

    @property
    def is_success_payment(self) -> bool:
        return self.merchant_status == "success_payment"

    @property
    def is_maintenance(self) -> bool:
        return self.merchant_status == "maintenance"

    @property
    def is_on_active_service(self) -> bool:
        return self.merchant_status == "on_active_service"

    @property
    def is_pin_enabled(self) -> bool:
        return self.verification_flag in {1, 3}

    @property
    def is_precondition_enabled(self) -> bool:
        return self.verification_flag in {2, 3}

    @property
    def is_verification_required(self) -> bool:
        return self.verification_flag > 0

    def to_payload(self) -> str:
        return _dumps_object(
            {
                "e": self.entities,
                "m": self.merchant_status,
                "oid": self.active_order_id,
                "vf": self.verification_flag,
            }
        )


@dataclass(frozen=True)
class Usage:
    """Usage payload parsed from Arduino keys ``u``, ``l``, ``r``, ``pct``, ``ra``, ``g``."""

    used: int = 0
    limit: int = 0
    remaining: int = 0
    percentage: int = 0
    reset_at: str = ""
    granularity: str = ""
    near_limit: bool = False
    limit_exceeded: bool = False
    has_metrics: bool = False

    @classmethod
    def from_payload(
        cls,
        payload: str,
        *,
        near_limit: bool = False,
        limit_exceeded: bool = False,
    ) -> Usage:
        raw = _loads_object(payload)
        return cls(
            used=int(raw.get("u", 0)),
            limit=int(raw.get("l", 0)),
            remaining=int(raw.get("r", 0)),
            percentage=int(raw.get("pct", 0)),
            reset_at=str(raw.get("ra", "")),
            granularity=str(raw.get("g", "")),
            near_limit=near_limit,
            limit_exceeded=limit_exceeded,
            has_metrics="u" in raw or "l" in raw,
        )

    @property
    def is_valid(self) -> bool:
        return self.has_metrics


@dataclass(frozen=True)
class DeviceStatus:
    """Device-state payload parsed from Arduino key ``s``."""

    state: str = ""

    @classmethod
    def from_payload(cls, payload: str) -> DeviceStatus:
        raw = _loads_object(payload)
        return cls(state=str(raw.get("s", "")))

    @property
    def is_valid(self) -> bool:
        return bool(self.state)

    @property
    def is_idle(self) -> bool:
        return self.state == "idle"

    @property
    def is_pending_payment(self) -> bool:
        return self.state == "pending_payment"

    @property
    def is_expired_payment(self) -> bool:
        return self.state == "expired_payment"

    @property
    def is_success_payment(self) -> bool:
        return self.state == "success_payment"

    @property
    def is_maintenance(self) -> bool:
        return self.state == "maintenance"

    @property
    def is_on_active_service(self) -> bool:
        return self.state == "on_active_service"

    def to_payload(self) -> str:
        return _dumps_object({"s": self.state})


@dataclass(frozen=True)
class Entity:
    """Simple entity key wrapper.

    Mirrors the Arduino Entity object: it stores only the entity key and lets
    client methods accept an object instead of repeating raw string keys.
    """

    key: str

    def __init__(self, key: str | int) -> None:
        object.__setattr__(self, "key", str(key))
        if not self.key:
            raise ValueError("entity key must be a non-empty string")


@dataclass(frozen=True)
class EntityCommand:
    """Entity command delivered from path segment key plus payload value."""

    key: str
    value: str
    metadata: str = ""

    @classmethod
    def from_key_value(cls, key: str, value: str) -> EntityCommand:
        return cls(key=key, value=value, metadata=value)

    @property
    def is_valid(self) -> bool:
        return bool(self.key)


@dataclass(frozen=True)
class EntityValue:
    """Local entity value helper matching the Arduino convenience object."""

    value: str = ""

    def to_string(self) -> str:
        return self.value

    def to_float(self) -> float:
        try:
            return float(self.value)
        except ValueError:
            return 0.0

    def to_int(self) -> int:
        try:
            return int(float(self.value))
        except ValueError:
            return 0

    def is_on(self) -> bool:
        return self.value in {"1", "true", "on"}


def entity_key(entity: Entity | str | int) -> str:
    """Normalize public entity references into a non-empty key."""
    key = entity.key if isinstance(entity, Entity) else str(entity)
    if not key:
        raise ValueError("entity key must be a non-empty string")
    return key


def entity_value(value: Any, *, decimals: int | None = None) -> str:
    """Serialize an entity value with Arduino-compatible boolean handling."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and decimals is not None:
        precision = min(max(decimals, 0), 6)
        return f"{value:.{precision}f}"
    return str(value)


__all__ = [
    "DeviceStatus",
    "Entity",
    "EntityCommand",
    "EntityValue",
    "Init",
    "JsonObject",
    "Payment",
    "Usage",
    "Verification",
    "entity_key",
    "entity_value",
]
