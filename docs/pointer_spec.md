# Pointer / Magic-Remote API Specification

This document covers the non-subscription `InputControl` surface that
emulates LG's Magic Remote pointer: `move()`, `click()`, `scroll()`, and
the named-button methods (`home()`, `back()`, `volumeup()`, …). It also
covers the `connect_input()` lifecycle.

The IME / text-entry methods (`type()`, `delete()`, `enter()`) on
`InputControl` go through the **main** SSAP socket via cmd_info entries
and follow normal request/response semantics — they're not pointer
commands and aren't covered here.

---

## 1. Dual-socket architecture

`InputControl` is the only control class that holds **two** WebSocket
connections to the TV:

| Socket | Purpose | API |
|---|---|---|
| Main SSAP socket | Goes through `self.client`. Used for IME (`type`, `delete`, `enter`) and as a *fallback* path for button presses (`ssap://com.webos.service.networkinput/sendInputButton`). | JSON over the standard webOS SSAP frame. |
| Pointer socket | A dedicated WebSocket held in `self._pointer_websocket`. Used for `move()` / `click()` / `scroll()` and as the *primary* path for button presses. | **Plain-text** wire format (see §3). |

The pointer socket URI is obtained at connect time by issuing
`ssap://com.webos.service.networkinput/getPointerInputSocket` on the
main socket — webOS replies with a one-shot URL (e.g.
`wss://192.168.1.10:3001/resources/.../netinput.pointer.sock/`) that
the library then connects to as a plain WebSocket.

**Consumers must call pointer methods through the library**, not by
sending JSON to fake SSAP URIs on the main socket. webOS has no SSAP
endpoint that accepts `{"type": "move", "x": …, "y": …}` — such messages
are silently dropped.

---

## 2. Connection lifecycle

### Lazy connect

`InputControl` does **not** open the pointer socket eagerly. The first
`move()` / `click()` / `scroll()` / button call triggers
`connect_input()` automatically (because `_send_pointer_command` checks
`_is_connected` and calls `connect_input()` if False).

Consumers may also call `await input_control.connect_input()`
explicitly at startup to fail fast if the TV doesn't have a pointer
socket available.

### Retry policy

`connect_input()` makes up to **3** WebSocket-connect attempts with a
**1-second** delay between attempts. After the third failure it raises
`IOError`. Each new call to `connect_input()` resets the attempt
counter, so a consumer that catches the error and retries gets a fresh
3-attempt budget.

### Failure recovery

If a pointer-socket `send()` fails — typically because the TV closed
the socket from its side or the network blipped — `_send_pointer_command`
sets `_is_connected = False` and re-raises as `IOError`. The **next**
pointer call triggers a fresh lazy reconnect.

Reconnect requires the **main** socket to be alive (because
`connect_input()` issues an SSAP `getPointerInputSocket` request on the
main socket to get a new pointer URL). If the main socket is also dead,
the consumer must reconnect that first.

### Teardown

`await input_control.close()` (which calls `disconnect_input()`)
explicitly closes the pointer socket, clears `_pointer_websocket`, and
resets `_is_connected`.

**Auto-close as of v0.3.4.** When `connect_input()` succeeds, the
control registers its `disconnect_input` as a close-callback on the
client (via `WebOSClient.register_close_callback`). `await client.close()`
then awaits the registered teardown coroutine **before** tearing down
the main socket. This means:

- High-level `WebOSTV.close()` users: nothing changes — the wrapper
  already called `input.close()` explicitly, which is idempotent with
  the auto-registration.
- Low-level `WebOSClient` + bare `InputControl` users: previously had
  to remember to call `await input_control.close()` themselves before
  `await client.close()` or risk leaking the pointer-socket file
  descriptor. As of v0.3.4 the client closes the pointer socket
  automatically.

Registration is **idempotent** — if `connect_input()` runs multiple
times (lazy-reconnect path), the callback is registered only once.
Callback failures are caught and logged; they do not block the main
socket close.

If you want manual control (e.g. to close the pointer socket without
closing the main socket), `await input_control.close()` is still
available and removes the resource cleanly.

---

## 3. Wire format

The pointer socket uses a plain-text framed protocol — **not** JSON,
**not** SSAP. Each message is one or more `key:value` lines terminated
by a blank line:

```
type:<command-type>\n
<field1>:<value1>\n
<field2>:<value2>\n
\n
```

`type` is always present. Other fields depend on the command (see §4).
The TV silently ignores unrecognised fields, so a message with the
wrong field names succeeds at the WebSocket layer but has no effect on
the cursor — pre-v0.3.3 `move()` and `scroll()` calls were no-ops for
exactly this reason.

There is no acknowledgement frame; the call returns
`{"returnValue": True}` as soon as the WebSocket `send()` resolves.

### Register preamble — **not used**

Both [`pywebostv`](https://github.com/supersaiyanmode/PyWebOSTV)
upstream and [`lgtv2`](https://github.com/hobbyquaker/lgtv2) connect to
the pointer socket and start sending commands immediately. No
registration handshake. Pre-v0.3.3 sent a `register\n\n` preamble with
a misleading comment claiming pywebostv parity — that preamble was
removed in v0.3.3.

---

## 4. API surface

All methods below are auto-attached to `InputControl` instances by
`__init__`. Coordinate-bearing methods take **deltas**, not absolute
positions — webOS exposes no absolute-positioning endpoint.

### `move(dx: int, dy: int, drag: bool = False)`

Move the cursor by `(dx, dy)` pixels relative to its current position.
Positive `dx` moves right; positive `dy` moves down.

Wire format:

```
type:move\ndx:<dx>\ndy:<dy>\ndown:<0|1>\n\n
```

When `drag=True`, `down:1` is emitted — the pointer button is treated
as held down for the duration of the move (used for click-and-drag
gestures combined with a preceding `click(drag=True)` — see below).

**Naming change in v0.3.3.** Pre-v0.3.3 the signature was
`move(x, y, drag=False)`. Despite the names, the values have always
been treated as deltas — the rename matches the wire-format semantics
and the upstream `pywebostv` naming. Positional callers
(`await input_control.move(10, -5)`) are unaffected; keyword callers
using `move(x=10, y=-5)` need to update.

### `click(x=None, y=None, drag=False)`

Click at the **current cursor position**. webOS's protocol takes no
coordinates and no drag flag for click; the parameters are accepted
only for backwards compatibility with pre-v0.3.3 callers and are
ignored on the wire (a debug log line is emitted if any are passed).

To click at a specific location, call `move(dx, dy)` first to position
the cursor, then `click()`.

Wire format:

```
type:click\n\n
```

### `scroll(dx: int, dy: int)`

Send a scroll delta. Direction is encoded in the **sign** of `dy`:
positive scrolls down, negative scrolls up. `dx` is for horizontal
scroll where supported.

Wire format:

```
type:scroll\ndx:<dx>\ndy:<dy>\n\n
```

**Signature change in v0.3.3.** Pre-v0.3.3 the signature was
`scroll(x, y, wheel_direction)`. The `wheel_direction` parameter was
sent as a non-canonical `wheelDirection:<value>` field that webOS
ignored — direction has always been encoded in the sign of `dy`. The
v0.3.3 signature drops `wheel_direction` entirely. Any caller passing
three positional args breaks; the realistic fix is to drop the third
arg and adjust the sign of `dy` if needed.

### Button methods

Every entry in `BUTTON_COMMANDS` (e.g. `home`, `back`, `menu`, `enter`,
`volumeup`, `channeldown`, `red`, `play`, `num_0`–`num_9`, …) is
auto-attached as a no-arg coroutine method. Each first tries the
pointer socket:

```
type:button\nname:<NAME>\n\n
```

If the pointer socket is not connected or the send fails, the method
falls back to an SSAP request:

```
URI:     ssap://com.webos.service.networkinput/sendInputButton
payload: {"buttonName": "<NAME>"}
```

Either path produces the same effect on the TV. The pointer-socket
path is preferred because it has lower latency (no SSAP
request/response round-trip).

---

## 5. Migration from pre-v0.3.3

| Behaviour change | Caller impact |
|---|---|
| `move()` wire fields renamed `x`/`y`/`drag` → `dx`/`dy`/`down` | None for the wire (TV always saw the v0.3.3 fields as the only valid ones; old fields were silently dropped). Callers using `move(x=…, y=…)` keyword form must update keyword names. |
| `scroll()` wire fields renamed `x`/`y` → `dx`/`dy`; `wheelDirection` field removed | Callers using `scroll(x, y, wheel_direction)` positionally must drop the third arg and possibly flip the sign of `dy`. |
| `click()` wire stripped of `x`/`y`/`drag` fields | None — those fields never had any effect; the wire is now what it should always have been. Signature unchanged for back-compat (deprecated args still accepted, logged at debug). |
| `register\n\n` preamble removed from `connect_input()` | None — preamble was a no-op on every firmware we've tested. |

If you were *relying* on any of the pre-v0.3.3 buggy behaviour (your
cursor *did* move correctly, somehow, despite the wrong field names),
please file an issue — that would suggest the protocol varies by
firmware, in which case the v0.3.3 fix would need to be made
firmware-conditional rather than absolute.

---

## 6. References

- pywebostv upstream `InputControl.INPUT_COMMANDS` —
  https://github.com/supersaiyanmode/PyWebOSTV/blob/master/pywebostv/controls.py
  (canonical wire-field names — `dx`, `dy`, `down`; click takes no fields).
- lgtv2 `SpecializedSocket.send` —
  https://github.com/hobbyquaker/lgtv2/blob/master/index.js (Node
  reference implementation of the plain-text framed protocol).
- webOS forum thread *"Cursor socket help"* —
  https://forum.webostv.developer.lge.com/t/cursor-socket-help/3769
  (community-confirmed example: `type:button\nname:INFO\n\n`).
