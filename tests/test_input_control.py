"""Tests for InputControl.

Currently focused on the v0.3.1 get_input() payload normalisation: the
method must guarantee an `inputId` key in the returned dict whether the
underlying webOS firmware uses `inputId`, `id`, or `input_id` as the key
name. HW capture wasn't available at fix-time (the consumer's poll
silently returned when `inputId` was missing), so the normalisation is
defensive across several plausible key names.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from asyncwebostv.controls import InputControl


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.send_message = AsyncMock()
    return client


def _payload_queue(payload):
    """Return a mock queue whose first .get() yields the given payload
    wrapped in the standard webOS response envelope."""
    queue = AsyncMock()
    queue.get = AsyncMock(return_value={"payload": payload})
    return queue


@pytest.mark.asyncio
async def test_get_input_preserves_existing_inputId(mock_client):
    """If the firmware already returns an `inputId` field, get_input must
    leave it untouched."""
    mock_client.send_message.return_value = _payload_queue(
        {"inputId": "HDMI_2", "returnValue": True}
    )
    inputs = InputControl(mock_client)
    result = await inputs.get_input()
    assert result["inputId"] == "HDMI_2"


@pytest.mark.asyncio
async def test_get_input_synthesises_inputId_from_id(mock_client):
    """The HW-captured list_inputs payload uses `id` (not `inputId`) for
    each device. The single-input getCurrentExternalInput response is
    expected to follow the same convention; get_input must synthesise an
    `inputId` field from `id` so consumers don't have to know which key
    the firmware happened to use."""
    mock_client.send_message.return_value = _payload_queue(
        {"id": "HDMI_2", "label": "Emotiva XMC", "returnValue": True}
    )
    inputs = InputControl(mock_client)
    result = await inputs.get_input()
    assert result["inputId"] == "HDMI_2"
    # Original keys must still be present.
    assert result["id"] == "HDMI_2"
    assert result["label"] == "Emotiva XMC"


@pytest.mark.asyncio
async def test_get_input_synthesises_inputId_from_input_id(mock_client):
    """Defensive fallback for the `input_id` casing."""
    mock_client.send_message.return_value = _payload_queue(
        {"input_id": "HDMI_1", "returnValue": True}
    )
    inputs = InputControl(mock_client)
    result = await inputs.get_input()
    assert result["inputId"] == "HDMI_1"


@pytest.mark.asyncio
async def test_get_input_returns_empty_dict_when_no_payload(mock_client):
    """If the response has no payload, return {} — no inputId synthesised
    (no source to synthesise from)."""
    queue = AsyncMock()
    queue.get = AsyncMock(return_value={})
    mock_client.send_message.return_value = queue

    inputs = InputControl(mock_client)
    result = await inputs.get_input()
    assert result == {}
