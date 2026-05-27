"""Tests for InputControl.get_input() and the app_id_to_input_id helper.

v0.3.2 redesigned the "current input" path after HW evidence and LG's own
developer statement that webOS provides no documented endpoint for querying
the currently active external input. The library now derives `inputId` from
the foreground app id (`com.webos.app.hdmi<N>` -> `HDMI_<N>`) and omits it
for any non-HDMI foreground.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from asyncwebostv.controls import InputControl, app_id_to_input_id


# -- Helper unit tests ------------------------------------------------------


def test_app_id_to_input_id_parses_hdmi_app_ids():
    assert app_id_to_input_id("com.webos.app.hdmi1") == "HDMI_1"
    assert app_id_to_input_id("com.webos.app.hdmi2") == "HDMI_2"
    assert app_id_to_input_id("com.webos.app.hdmi3") == "HDMI_3"
    assert app_id_to_input_id("com.webos.app.hdmi4") == "HDMI_4"


def test_app_id_to_input_id_returns_none_for_internal_apps():
    """The launcher, Live TV, installed apps must NOT map to any inputId —
    no external input is active in those states."""
    assert app_id_to_input_id("com.webos.app.home") is None
    assert app_id_to_input_id("com.webos.app.livetv") is None
    assert app_id_to_input_id("youtube.leanback.v4") is None
    assert app_id_to_input_id("ivi") is None


def test_app_id_to_input_id_returns_none_for_falsy_input():
    assert app_id_to_input_id(None) is None
    assert app_id_to_input_id("") is None


def test_app_id_to_input_id_rejects_partial_matches():
    """Defensive: the regex must anchor on both ends to avoid false positives."""
    assert app_id_to_input_id("com.webos.app.hdmi") is None  # no digits
    assert app_id_to_input_id("prefix.com.webos.app.hdmi1") is None
    assert app_id_to_input_id("com.webos.app.hdmi1.suffix") is None


# -- InputControl.get_input integration tests -------------------------------


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.send_message = AsyncMock()
    return client


def _payload_queue(payload):
    queue = AsyncMock()
    queue.get = AsyncMock(return_value={"payload": payload})
    return queue


@pytest.mark.asyncio
async def test_get_input_returns_inputId_when_foreground_is_hdmi(mock_client):
    """HW context for handoff #2 had the TV foregrounded on
    com.webos.app.hdmi2 (the Emotiva XMC). get_input() must synthesise
    inputId='HDMI_2' from that appId."""
    mock_client.send_message.return_value = _payload_queue({
        "appId": "com.webos.app.hdmi2",
        "windowId": "",
        "processId": "1234",
        "returnValue": True,
    })
    inputs = InputControl(mock_client)
    result = await inputs.get_input()
    assert result["inputId"] == "HDMI_2"
    # Original webOS fields must be preserved.
    assert result["appId"] == "com.webos.app.hdmi2"
    assert result["returnValue"] is True


@pytest.mark.asyncio
async def test_get_input_omits_inputId_when_foreground_is_launcher(mock_client):
    """When foreground is the launcher (no external input active),
    inputId must be absent — matches webOS's own model and the v0.3.2 spec."""
    mock_client.send_message.return_value = _payload_queue({
        "appId": "com.webos.app.home",
        "windowId": "",
        "processId": "5678",
        "returnValue": True,
    })
    inputs = InputControl(mock_client)
    result = await inputs.get_input()
    assert "inputId" not in result
    assert result["appId"] == "com.webos.app.home"


@pytest.mark.asyncio
async def test_get_input_omits_inputId_for_installed_apps(mock_client):
    """Same contract for arbitrary installed apps (YouTube, IVI, etc.)."""
    mock_client.send_message.return_value = _payload_queue({
        "appId": "youtube.leanback.v4",
        "returnValue": True,
    })
    inputs = InputControl(mock_client)
    result = await inputs.get_input()
    assert "inputId" not in result
    assert result["appId"] == "youtube.leanback.v4"


@pytest.mark.asyncio
async def test_get_input_calls_getForegroundAppInfo_not_external_input(mock_client):
    """The library MUST call getForegroundAppInfo (the working endpoint),
    not the unofficial getCurrentExternalInput (silent on current
    firmware)."""
    mock_client.send_message.return_value = _payload_queue({
        "appId": "com.webos.app.hdmi1",
        "returnValue": True,
    })
    inputs = InputControl(mock_client)
    await inputs.get_input()
    args, _kwargs = mock_client.send_message.call_args
    assert args[0] == 'request'
    assert args[1] == 'ssap://com.webos.applicationManager/getForegroundAppInfo'


@pytest.mark.asyncio
async def test_get_input_returns_empty_dict_when_no_payload(mock_client):
    """If the response has no payload, return {} — nothing to synthesise."""
    queue = AsyncMock()
    queue.get = AsyncMock(return_value={})
    mock_client.send_message.return_value = queue

    inputs = InputControl(mock_client)
    result = await inputs.get_input()
    assert result == {}
