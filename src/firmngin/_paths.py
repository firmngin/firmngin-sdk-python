"""Topic path generation for the Firmngin MQTT protocol.

Every MQTT topic the SDK publishes to or subscribes from is a function of the
``device_id``. Topic strings follow the Firmngin v1.0.2 wire format — the same
format the Arduino ``firmnginkit-library`` emits. Functions here are pure and
side-effect-free; they take a ``device_id`` and return a string.

Examples
--------
>>> get_path_payment("dev-abc")
'/c/dev-abc/pm'
>>> get_path_init("dev-abc")
'/c/dev-abc/init'
>>> get_path_update_entity("dev-abc")
'/d/dev-abc/ps'
"""

from __future__ import annotations

# Topic short-codes matching Arduino library constants
PAYMENT = "pm"
DEVICE_STATUS = "ds"
PENDING_PAYMENT = "pp"
METADATA_ON_PENDING = "mop"
METADATA_ON_EXPIRED = "moe"
METADATA_ON_SUCCESS = "mos"
MERCHANT_STATUS = "mi"
INIT = "init"
DISPLAY_PIN = "dpin"
VERIFICATION_RESULT = "vr"
UPDATE_ENTITY = "update_entity"
UPDATE_ENTITIES = "update_entities"
REQUEST_INIT = "request_init"
ENTITY_COMMAND = "entity_command"
SESSION_END = "session_end"
PING = "pi"
PONG = "po"
LWT = "lwt"

_CONTROL_PREFIX = "/c"
_DEVICE_PREFIX = "/d"


def _device_topic(prefix: str, device_id: str, path: str) -> str:
    """Build a per-device topic from the Arduino v1.0.2 wire format."""
    if not device_id:
        raise ValueError("device_id must be a non-empty string")
    return f"{prefix}/{device_id}/{path}"


# --------------------------------------------------------------------------------------
# Inbound topics (server -> device)
# --------------------------------------------------------------------------------------
def get_path_payment(device_id: str) -> str:
    """Inbound payment result topic."""
    return _device_topic(_CONTROL_PREFIX, device_id, PAYMENT)


def get_path_device_status(device_id: str) -> str:
    return _device_topic(_CONTROL_PREFIX, device_id, DEVICE_STATUS)


def get_path_pending_payment(device_id: str) -> str:
    return _device_topic(_CONTROL_PREFIX, device_id, PENDING_PAYMENT)


def get_path_metadata_on_pending(device_id: str) -> str:
    return _device_topic(_CONTROL_PREFIX, device_id, METADATA_ON_PENDING)


def get_path_metadata_on_expired(device_id: str) -> str:
    return _device_topic(_CONTROL_PREFIX, device_id, METADATA_ON_EXPIRED)


def get_path_metadata_on_success(device_id: str) -> str:
    return _device_topic(_CONTROL_PREFIX, device_id, METADATA_ON_SUCCESS)


def get_path_merchant_status(device_id: str) -> str:
    return _device_topic(_CONTROL_PREFIX, device_id, MERCHANT_STATUS)


def get_path_init(device_id: str) -> str:
    return _device_topic(_CONTROL_PREFIX, device_id, INIT)


def get_path_display_pin(device_id: str) -> str:
    return _device_topic(_CONTROL_PREFIX, device_id, DISPLAY_PIN)


def get_path_verification_result(device_id: str) -> str:
    return _device_topic(_CONTROL_PREFIX, device_id, VERIFICATION_RESULT)


def get_path_entity_command(device_id: str) -> str:
    """Inbound entity command topic — broker pushes an entity key/value pair."""
    return _device_topic(_DEVICE_PREFIX, device_id, "rs/+")


# --------------------------------------------------------------------------------------
# Outbound topics (device -> server)
# --------------------------------------------------------------------------------------
def get_path_update_entity(device_id: str) -> str:
    """Outbound single-entity update topic."""
    return _device_topic(_DEVICE_PREFIX, device_id, "ps")


def get_path_update_entities(device_id: str) -> str:
    """Outbound batch-entities update topic."""
    return _device_topic(_DEVICE_PREFIX, device_id, "psb")


def get_path_request_init(device_id: str) -> str:
    """Outbound init request topic."""
    return _device_topic(_DEVICE_PREFIX, device_id, "a/init")


def get_path_session_end(device_id: str) -> str:
    """Outbound active-session end topic."""
    return _device_topic(_DEVICE_PREFIX, device_id, "a/ses-n")


def get_path_ping(device_id: str) -> str:
    return _device_topic(_CONTROL_PREFIX, device_id, PING)


def get_path_pong(device_id: str) -> str:
    return _device_topic(_DEVICE_PREFIX, device_id, PONG)


def get_path_lwt(device_id: str) -> str:
    return _device_topic(_DEVICE_PREFIX, device_id, LWT)


# --------------------------------------------------------------------------------------
# Topic classification
# --------------------------------------------------------------------------------------
def is_inbound_topic(topic: str) -> bool:
    """Return True if the topic is a control-plane topic."""
    return topic.startswith(f"{_CONTROL_PREFIX}/")


def device_id_from_topic(topic: str) -> str | None:
    """Extract device_id from a topic. Returns None if the topic doesn't match the format.

    Works for both control-plane (``/c/device_id/path``) and device-plane
    (``/d/device_id/path``) topics.
    """
    parts = topic.split("/")
    if len(parts) < 4 or parts[0] != "" or parts[1] not in {"c", "d"} or not parts[2]:
        return None
    return parts[2]


__all__ = [
    "DEVICE_STATUS",
    "DISPLAY_PIN",
    "ENTITY_COMMAND",
    "INIT",
    "LWT",
    "MERCHANT_STATUS",
    "METADATA_ON_EXPIRED",
    "METADATA_ON_PENDING",
    "METADATA_ON_SUCCESS",
    "PAYMENT",
    "PENDING_PAYMENT",
    "PING",
    "PONG",
    "REQUEST_INIT",
    "SESSION_END",
    "UPDATE_ENTITIES",
    "UPDATE_ENTITY",
    "VERIFICATION_RESULT",
    "device_id_from_topic",
    "get_path_device_status",
    "get_path_display_pin",
    "get_path_entity_command",
    "get_path_init",
    "get_path_lwt",
    "get_path_merchant_status",
    "get_path_metadata_on_expired",
    "get_path_metadata_on_pending",
    "get_path_metadata_on_success",
    "get_path_payment",
    "get_path_pending_payment",
    "get_path_ping",
    "get_path_pong",
    "get_path_request_init",
    "get_path_session_end",
    "get_path_update_entities",
    "get_path_update_entity",
    "get_path_verification_result",
    "is_inbound_topic",
]
