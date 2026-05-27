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


# -- Pointer wire-format tests ----------------------------------------------
#
# These pin the v0.3.3 wire-format fixes. Pre-v0.3.3, our pointer methods
# emitted `x:N\ny:N` instead of `dx:N\ndy:N` and `drag:True` instead of
# `down:1`, so every move()/scroll() sent was silently dropped by webOS.
# The tests below assert the exact string sent on `_pointer_websocket.send`,
# matching the canonical wire format used by pywebostv upstream and lgtv2.


def _input_control_with_mocked_pointer(mock_client):
    """Construct an InputControl with a pre-connected mock pointer socket,
    bypassing connect_input() so wire-format tests can run synchronously."""
    inputs = InputControl(mock_client)
    inputs._pointer_websocket = AsyncMock()
    inputs._is_connected = True
    return inputs


def _last_sent(inputs):
    """Return the raw string passed to the last _pointer_websocket.send()."""
    inputs._pointer_websocket.send.assert_called()
    args, _kwargs = inputs._pointer_websocket.send.call_args
    return args[0]


@pytest.mark.asyncio
async def test_move_emits_dx_dy_down_in_wire_format(mock_client):
    """webOS pointer move protocol uses `dx`/`dy` (deltas) and `down` (drag
    flag). Pre-v0.3.3 emitted x/y/drag which the TV silently ignored."""
    inputs = _input_control_with_mocked_pointer(mock_client)
    await inputs.move(10, -5)
    assert _last_sent(inputs) == "type:move\ndx:10\ndy:-5\ndown:0\n\n"


@pytest.mark.asyncio
async def test_move_with_drag_emits_down_1(mock_client):
    inputs = _input_control_with_mocked_pointer(mock_client)
    await inputs.move(3, 7, drag=True)
    assert _last_sent(inputs) == "type:move\ndx:3\ndy:7\ndown:1\n\n"


@pytest.mark.asyncio
async def test_click_emits_bare_type_click(mock_client):
    """webOS pointer click protocol takes no fields beyond `type:click`."""
    inputs = _input_control_with_mocked_pointer(mock_client)
    await inputs.click()
    assert _last_sent(inputs) == "type:click\n\n"


@pytest.mark.asyncio
async def test_click_ignores_deprecated_args_on_wire(mock_client):
    """The pre-v0.3.3 click(x, y, drag) signature is preserved for back-compat
    but the deprecated args MUST NOT appear on the wire — webOS ignores them
    and `type:click\\n\\n` is the only valid payload."""
    inputs = _input_control_with_mocked_pointer(mock_client)
    await inputs.click(100, 200, drag=True)
    assert _last_sent(inputs) == "type:click\n\n"


@pytest.mark.asyncio
async def test_scroll_emits_dx_dy(mock_client):
    """webOS pointer scroll protocol uses `dx`/`dy` deltas. Pre-v0.3.3
    also sent an unrecognised `wheelDirection` field; the v0.3.3 signature
    drops it entirely (sign of dy encodes direction)."""
    inputs = _input_control_with_mocked_pointer(mock_client)
    await inputs.scroll(0, 5)
    assert _last_sent(inputs) == "type:scroll\ndx:0\ndy:5\n\n"


@pytest.mark.asyncio
async def test_scroll_negative_dy_for_scroll_up(mock_client):
    """Confirms direction encoding: dy<0 means scroll up."""
    inputs = _input_control_with_mocked_pointer(mock_client)
    await inputs.scroll(0, -3)
    assert _last_sent(inputs) == "type:scroll\ndx:0\ndy:-3\n\n"


@pytest.mark.asyncio
async def test_button_press_emits_type_button_name(mock_client):
    """Buttons go through _send_pointer_command first; wire format is
    `type:button\\nname:<NAME>\\n\\n`. Confirmed against the webOS forum
    quote for `type:button\\nname:INFO\\n\\n`."""
    inputs = _input_control_with_mocked_pointer(mock_client)
    await inputs.home()
    assert _last_sent(inputs) == "type:button\nname:HOME\n\n"


@pytest.mark.asyncio
async def test_pointer_send_omits_register_preamble(mock_client):
    """The register\\n\\n preamble was a non-canonical addition to the
    async port (pre-v0.3.3) — neither pywebostv nor lgtv2 sends it. The
    v0.3.3 connect_input() must NOT send it."""
    inputs = _input_control_with_mocked_pointer(mock_client)
    # No connect_input() call happened (we mocked the socket directly), so
    # the only way a `register\n\n` would show up is if _send_pointer_command
    # itself emitted one. Call a few commands and verify the wire is clean.
    await inputs.click()
    await inputs.move(1, 1)
    sent_payloads = [
        call.args[0]
        for call in inputs._pointer_websocket.send.call_args_list
    ]
    assert "register\n\n" not in sent_payloads
