"""Unit tests for internal topic generation matching Arduino library format."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from firmngin._paths import (
    device_id_from_topic,
    get_path_device_status,
    get_path_display_pin,
    get_path_entity_command,
    get_path_init,
    get_path_limit_exceeded,
    get_path_lwt,
    get_path_merchant_status,
    get_path_metadata_on_expired,
    get_path_metadata_on_pending,
    get_path_metadata_on_success,
    get_path_near_limit,
    get_path_ota_trigger,
    get_path_payment,
    get_path_pending_payment,
    get_path_ping,
    get_path_pong,
    get_path_request_init,
    get_path_session_end,
    get_path_update_entities,
    get_path_update_entity,
    get_path_usage_response,
    get_path_verification_result,
    is_inbound_topic,
)

DEV = "dev-1782217379-d5d1680b"


# --------------------------------------------------------------------------------------
# Control-plane topics: Arduino getPathXxx returns /c/<device_id>/<path>
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fn,expected_path",
    [
        (get_path_payment, "pm"),
        (get_path_device_status, "ds"),
        (get_path_pending_payment, "pp"),
        (get_path_metadata_on_pending, "mop"),
        (get_path_metadata_on_expired, "moe"),
        (get_path_metadata_on_success, "mos"),
        (get_path_merchant_status, "mi"),
        (get_path_init, "init"),
        (get_path_display_pin, "dpin"),
        (get_path_verification_result, "vr"),
        (get_path_usage_response, "ur"),
        (get_path_limit_exceeded, "le"),
        (get_path_near_limit, "nl"),
        (get_path_ota_trigger, "ot/trg"),
    ],
)
def test_control_topic_format(fn: Callable[[str], str], expected_path: str) -> None:
    topic = fn(DEV)
    assert topic == f"/c/{DEV}/{expected_path}"
    assert is_inbound_topic(topic)


# --------------------------------------------------------------------------------------
# Device-plane topics: Arduino getPathXxx returns /d/<device_id>/<path>
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fn,expected_path",
    [
        (get_path_update_entity, "ps"),
        (get_path_update_entities, "psb"),
        (get_path_request_init, "a/init"),
        (get_path_session_end, "a/ses-n"),
        (get_path_entity_command, "rs/+"),
        (get_path_pong, "po"),
        (get_path_lwt, "lwt"),
    ],
)
def test_device_topic_format(fn: Callable[[str], str], expected_path: str) -> None:
    topic = fn(DEV)
    assert topic == f"/d/{DEV}/{expected_path}"
    assert not is_inbound_topic(topic)


def test_ping_uses_control_topic() -> None:
    assert get_path_ping(DEV) == f"/c/{DEV}/pi"


# --------------------------------------------------------------------------------------
# Empty / invalid device_id
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fn",
    [
        get_path_payment,
        get_path_init,
        get_path_update_entity,
    ],
)
def test_empty_device_id_raises(fn: Callable[[str], str]) -> None:
    with pytest.raises(ValueError, match="device_id"):
        fn("")


# --------------------------------------------------------------------------------------
# Topic classification
# --------------------------------------------------------------------------------------
def test_is_inbound_topic_true() -> None:
    assert is_inbound_topic("/c/dev-abc/pm")


def test_is_inbound_topic_false() -> None:
    assert not is_inbound_topic("/d/dev-abc/ps")


# --------------------------------------------------------------------------------------
# Round-trip: device_id_from_topic
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fn",
    [
        get_path_payment,
        get_path_init,
        get_path_update_entity,
        get_path_session_end,
        get_path_ping,
    ],
)
def test_device_id_round_trip(fn: Callable[[str], str]) -> None:
    topic = fn(DEV)
    assert device_id_from_topic(topic) == DEV


def test_device_id_from_malformed_topic_returns_none() -> None:
    assert device_id_from_topic("garbage") is None
    assert device_id_from_topic("") is None
