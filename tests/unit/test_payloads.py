"""Unit tests for Arduino-compatible typed payloads."""

from __future__ import annotations

import pytest

from firmngin.exceptions import PayloadError
from firmngin.payloads import (
    DeviceStatus,
    Entity,
    EntityCommand,
    EntityValue,
    Init,
    Payment,
    Verification,
)


def test_payment_parses_arduino_short_keys() -> None:
    payment = Payment.from_payload(
        '{"it":"Coffee","pc":"12000","oid":"ord-1","q":0}',
        is_pending=True,
    )

    assert payment.is_valid
    assert payment.item_title == "Coffee"
    assert payment.price == "12000"
    assert payment.order_id == "ord-1"
    assert payment.quantity == 1
    assert payment.is_pending


def test_verification_parses_pin_payload() -> None:
    verification = Verification.from_payload('{"pi":"1234","si":"ses-1","ttl":60}')

    assert verification.is_valid
    assert verification.has_pin_number
    assert verification.pin == "1234"
    assert verification.session_id == "ses-1"
    assert verification.ttl == 60


def test_verification_parses_result_payload() -> None:
    verification = Verification.from_payload('{"pn":true,"pr":false}')

    assert verification.is_valid
    assert verification.has_result
    assert verification.pin_met
    assert not verification.precondition_met


def test_init_status_helpers_match_arduino() -> None:
    init = Init.from_payload('{"e":{"relay":"on"},"m":"pending_payment","oid":"ord-1","vf":3}')

    assert init.is_valid
    assert init.entities == {"relay": "on"}
    assert init.is_pending_payment
    assert init.is_pin_enabled
    assert init.is_precondition_enabled
    assert init.is_verification_required


def test_device_status_helpers_match_arduino() -> None:
    status = DeviceStatus.from_payload('{"s":"maintenance"}')

    assert status.is_valid
    assert status.is_maintenance
    assert not status.is_idle


def test_entity_command_uses_topic_key_and_payload_value() -> None:
    command = EntityCommand.from_key_value("relay", "on")

    assert command.is_valid
    assert command.key == "relay"
    assert command.value == "on"
    assert command.metadata == "on"


def test_entity_wraps_string_key_like_arduino_entity() -> None:
    entity = Entity("relay")

    assert entity.key == "relay"


def test_entity_wraps_int_key_like_arduino_entity() -> None:
    entity = Entity(1)

    assert entity.key == "1"


def test_entity_rejects_empty_key() -> None:
    with pytest.raises(ValueError, match="entity key"):
        Entity("")


def test_entity_value_helpers_match_arduino() -> None:
    assert EntityValue("on").is_on()
    assert EntityValue("42").to_int() == 42
    assert EntityValue("3.5").to_float() == 3.5


@pytest.mark.parametrize("payload", ["not json", "[]"])
def test_payload_rejects_invalid_json_object(payload: str) -> None:
    with pytest.raises(PayloadError):
        Payment.from_payload(payload)
