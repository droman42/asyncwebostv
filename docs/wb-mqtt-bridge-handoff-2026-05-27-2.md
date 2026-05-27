# Note to another Claude — handoff #2 from the wb-mqtt-bridge HW rack session (2026-05-27)

**Status:** Second handoff, same day as the first
(`wb-mqtt-bridge-handoff-2026-05-27.md`). The first one prompted the v0.3.0
release (subscription-lifecycle hardening + spec/README overhaul). This one
captures **three bugs found during the very first on-hardware verification
pass** of the wb-mqtt-bridge LG TV driver against a live LG OLED77G1RLA
(2021 model, webOS 6.x — exact build not captured but it's current
production firmware). The bridge driver's `_setup_subscriptions()`
landed in 5a09fd1 and was exercised end-to-end today.

**One coherent root-cause story.** All three bugs are **payload-shape
contract mismatches between `docs/subscription_spec.md` (and the implicit
contract `controls.py` `cmd_info` entries promise) and the actual webOS
responses on current firmware.** The library's dispatch chain — verified
end-to-end during this session — is correct: messages arrive, get routed
to the right `waiters` slot, callback wrappers fire, the user callback is
called with `success=True`. What's wrong is that the **payload handed to
the user callback isn't shaped the way the docs say it is**. The
subscription mechanism, deduplication, lifecycle, and close-cleanup (which
v0.3.0 fixed) all work correctly.

**Who you are.** A Claude session about to work on `asyncwebostv`. The
first handoff established the file's conventions; this one builds on
that. Verify each captured payload against current source before acting —
firmware versions vary.

---

## TL;DR

| # | Endpoint | Symptom on the consumer | Library responsibility | Severity |
|---|---|---|---|---|
| 1 | `SystemControl.subscribe_power_state` | Subscribe call accepted; server immediately replies "Unknown error"; no events ever fire | **URI divergence** — current LG OLEDs moved the endpoint from `com.webos.service.power` to `com.webos.service.tvpower` (aiowebostv targets the new one) | HIGH — physical-remote power-off completely invisible |
| 2 | `MediaControl.subscribe_get_volume` | Events arrive at user callback with `success=True`; payload is `{volumeStatus: {...}, returnValue, callerId}` instead of the documented `{volume, muted, returnValue}` | **Payload shape** — spec doc promises flat shape; library passes raw webOS payload through without unwrapping the `volumeStatus` sub-dict | HIGH — physical-remote volume invisible |
| 3 | `InputControl.get_input()` (request, not subscription) | Returns a dict without an `inputId` key; consumer code looking up `payload["inputId"]` gets nothing | **Payload shape** — exact returned shape unknown; need to capture | MEDIUM — current HDMI input never tracked |

Bugs 2 and 3 are the same class. Bug 1 is different (URI not shape) but
shares the "library docs don't match current LG firmware reality" story.

---

## Bug 1 — `subscribe_power_state` URI divergence

### What the docs say

`docs/subscription_spec.md` § "Endpoint divergence on newer firmware"
already flags this as a TBD: "Newer webOS firmware (webOS 4.x+) appears
to have moved this endpoint to `ssap://com.webos.service.tvpower/power/
getPowerState`. ... We have not yet verified on hardware whether the
legacy URI still responds on webOS 5.x/6.x firmware. If subscriptions
silently stop arriving on a newer TV, this endpoint divergence is the
first thing to check."

**Hardware verification: NOW DONE.** The legacy URI is dead on the
user's webOS 6.x firmware. The TBD can be resolved.

### Captured evidence

User's bridge log, line at `2026-05-27 13:59:52,527` (9 ms after the
`subscribe` request was sent and acknowledged):

```
WARNING - Power-state subscription error for LG OLED77G1RLA: Unknown error.
```

Sequence: at `13:59:52,518` the bridge logged `Subscribed to power_state
updates for LG OLED77G1RLA` (meaning the library's `await subscribe_*()`
returned without throwing). 9 ms later webOS sent back an immediate
error response which the library correctly routed through the
`callback(False, "Unknown error")` path. After that — silence, even
across subsequent foreground-app and volume events that confirmed the
WebSocket itself was alive.

### Root cause

The cmd_info entry in `controls.py` for `SystemControl.power_state`
targets:

```
ssap://com.webos.service.power/power/getPowerState
```

On current LG OLEDs the service has moved to `com.webos.service.tvpower`.
`aiowebostv` (home-assistant-libs) targets the new URI; `pywebostv`
upstream targets the old. The library currently follows pywebostv.

### Recommended fix

**Flip the URI** to the new endpoint:

```python
"power_state": {
    "uri": "ssap://com.webos.service.tvpower/power/getPowerState",
    "subscription": True,
    ...
}
```

The old URI is dead on every webOS version that's likely to be in active
use (webOS 4.x+ — i.e. anything from 2018 onward). For pre-2018 TVs the
legacy URI may still respond, but that's a vanishing minority. If you
want belt-and-suspenders, expose **both** as separate methods:

```python
"power_state":        { "uri": "ssap://com.webos.service.tvpower/...", ... },
"power_state_legacy": { "uri": "ssap://com.webos.service.power/...",   ... },
```

…and document the version mapping in `subscription_spec.md`. That lets
consumers choose. But for the practical fix today, just flip the URI —
the legacy URI is the rarer case in 2026.

Update `docs/subscription_spec.md` § "Power State Subscription" to use
the new URI and remove the "Endpoint divergence on newer firmware" TBD
section (resolved).

### Test

The existing close-cleanup test patterns don't cover URI correctness
because there's no mock LG TV to respond. Pragmatic answer: add a unit
test that asserts the URI string itself, so a future "let me just bump
this back to pywebostv-style" change is caught:

```python
def test_power_state_uses_modern_tvpower_endpoint():
    assert SystemControl.COMMANDS["power_state"]["uri"] == \
        "ssap://com.webos.service.tvpower/power/getPowerState"
```

---

## Bug 2 — Volume subscription payload-shape mismatch

### What the docs say

`docs/subscription_spec.md` § "Volume Subscription":

```python
{
    "volume": 25,        # Current volume level (0-100)
    "muted": false,      # Whether audio is muted
    "returnValue": true  # Success indicator
}
```

### Captured evidence

User's bridge log, **seven** consecutive volume-up presses on the
physical remote (each a separate subscription event with the same
subscription `id`):

```
2026-05-27 14:02:40,248 - asyncwebostv.connection - DEBUG - Received message:
  {'type': 'response', 'id': 'bb8c99d0-39c7-4ad1-961c-58461b569ea2',
   'payload': {'volumeStatus': {'cause': 'volumeUp', 'mode': 'normal',
                                'adjustVolume': True, 'activeStatus': True,
                                'muteStatus': False, 'volume': 14,
                                'soundOutput': 'tv_speaker', 'maxVolume': 100},
               'returnValue': True, 'callerId': 'com.webos.platformstarfish'}}
```

(volumes 14, 15, 16, 17, 18, 19, 20 — one per remote keypress.)

### What the dispatch chain did with that payload

Verified by reading `connection.py:240-263` + `connection.py:435-451` +
`controls.py:206-233` against the user's bridge driver:

1. `_process_message(obj)` finds the message id in `waiters`, calls the
   client-level subscription `wrapper(obj)`.
2. `wrapper(obj)` does `await callback(obj["payload"])` — passes the
   inner `payload` dict to the next layer.
3. `controls.py` per-control `callback_wrapper(payload)` runs
   `standard_validation(payload)` — passes (`returnValue: True`) — then
   `await callback(True, return_fn(payload))`. For `get_volume`,
   `return_fn` defaults to identity (no `return` key in `cmd_info`).
4. User callback receives `(True, {'volumeStatus': {...}, 'returnValue':
   True, 'callerId': '...'})`.

The user callback (bridge-side, in `lg_tv/driver.py:_on_volume_change`)
does `payload.get("volume")` and `payload.get("muted")` per the spec
doc — both return `None`. No state update happens. **Seven events
silently dropped.**

### Root cause

`cmd_info` for `get_volume` in `controls.py`:

```python
"get_volume": {
    "uri": "ssap://audio/getVolume",
    "validation": standard_validation,
    "subscription": True,
},
```

No `return` function — so `return_fn` defaults to `lambda x: x`. The
library passes the raw webOS payload through unchanged. The webOS
payload has its real values wrapped in a `volumeStatus` sub-dict, and
the mute field is called `muteStatus` (not `muted`). Spec promises
the flat shape; reality is wrapped.

### Recommended fix

Add a `return` function that unwraps `volumeStatus` and normalizes
`muteStatus` → `muted`, matching what `subscription_spec.md` documents.
Defensive: handle both shapes so a future firmware that flattens doesn't
break:

```python
def _unwrap_volume(p):
    """Unwrap webOS getVolume payload to match the documented flat contract.

    Newer firmware (webOS 4.x+ at least) returns:
        {'volumeStatus': {'volume': N, 'muteStatus': bool, 'soundOutput': str,
                          'cause': str, 'mode': str, 'maxVolume': int, ...},
         'returnValue': True, 'callerId': str}

    Older firmware may return the documented flat shape directly. Handle both."""
    if not isinstance(p, dict):
        return p
    vs = p.get("volumeStatus")
    if isinstance(vs, dict):
        return {
            "volume":      vs.get("volume", p.get("volume")),
            "muted":       vs.get("muteStatus", p.get("muted")),
            "soundOutput": vs.get("soundOutput", p.get("soundOutput")),
            "returnValue": p.get("returnValue", True),
        }
    return p  # already flat (or unknown shape — pass through)


"get_volume": {
    "uri": "ssap://audio/getVolume",
    "validation": standard_validation,
    "subscription": True,
    "return": _unwrap_volume,
},
```

This makes the library deliver on its documented contract. Consumers
written against `subscription_spec.md` (like the bridge driver) Just
Work without per-consumer workarounds.

Note: `subscribe_get_audio_output` and `subscribe_get_sound_output` may
have similar wrapper issues — both target `ssap://audio/getSoundOutput`.
Audit those too (capture a real payload first; don't speculate).

### Test

```python
def test_get_volume_return_unwraps_volume_status_wrapper():
    """Real webOS payloads wrap volume + mute inside a volumeStatus sub-dict
    and rename `muted` → `muteStatus`. The library's `return` function must
    normalize to the documented {volume, muted, returnValue} shape."""
    real_webos_payload = {
        "volumeStatus": {
            "cause": "volumeUp",
            "mode": "normal",
            "adjustVolume": True,
            "activeStatus": True,
            "muteStatus": False,
            "volume": 20,
            "soundOutput": "tv_speaker",
            "maxVolume": 100,
        },
        "returnValue": True,
        "callerId": "com.webos.platformstarfish",
    }
    out = _unwrap_volume(real_webos_payload)
    assert out["volume"] == 20
    assert out["muted"] is False
    assert out["returnValue"] is True


def test_get_volume_return_passes_flat_payload_through():
    """If a (hypothetical) firmware returns the documented flat shape directly,
    don't mangle it."""
    flat = {"volume": 30, "muted": True, "returnValue": True}
    assert _unwrap_volume(flat) == flat
```

---

## Bug 3 — `InputControl.get_input()` response shape

### Symptom

The bridge driver's `_update_input_source()` (a one-shot poll at connect
time, not a subscription) does:

```python
input_info = await self.input_control.get_input()
if input_info and "inputId" in input_info:
    self.update_state(input_source=input_info.get("inputId"))
```

The `if` branch never fires (no log line, no exception raised — just
returned False). So the bridge's `input_source` field stayed `None`
across the entire session even though the TV was demonstrably on
HDMI_2 (confirmed by the foreground_app subscription seeing
`com.webos.app.hdmi2`).

### Captured evidence — partial

The companion call `list_inputs()` ran a few ms earlier and we have its
full payload:

```python
{'returnValue': True,
 'devices': [{'id': 'HDMI_1', 'label': 'HDMI 1', 'port': 1,
              'connected': False, 'appId': 'com.webos.app.hdmi1', ...},
             {'id': 'HDMI_2', 'label': 'Emotiva XMC', 'port': 2,
              'connected': True, 'appId': 'com.webos.app.hdmi2', ...},
             ...]}
```

Note: the key is `id`, not `inputId`. So **if `get_input()` returns a
similarly-shaped single-input dict, the key is probably `id`** — but we
don't actually have the captured payload because the bridge's poll
returned silently when `"inputId" not in payload`.

The library Claude should reproduce this against the user's TV (or any
webOS 4.x+ TV) — quickest path: add a temporary `logger.debug(repr(payload))`
inside `WebOSControlBase.request` for one test run, capture the
`get_input()` response, then design the unwrap accordingly. Or look at
how aiowebostv handles `get_input` (likely the same shape).

### Recommended fix (pending the captured payload)

Same pattern as Bug 2: add a `return` function to the `get_input`
cmd_info entry that maps the actual response key (`id` / `appId` /
whatever) to a stable, documented field name. Update
`subscription_spec.md` (or wherever `get_input` is documented) to match.

Bridge driver currently looks for `inputId`. If you settle on a
different name in the library normalisation (`id`, `input_id`, `app_id`,
...), please tell the bridge so the consumer keeps matching the
contract. My weak preference, for symmetry with the docs that talk
about "inputs": call it `input_id` in the normalised payload (matches
`devices: [{id: HDMI_2}]` semantically — the "id of the input").

### Test

Same shape as Bug 2 — once the real payload is captured, lock in the
unwrap with a parametrized test covering wrapped + flat shapes.

---

## The pattern + recommended audit scope

All three are **library-side contract bugs at the webOS protocol
boundary**: spec docs and `cmd_info` defaults describe one shape, real
LG firmware delivers another. Three fixes in three places is OK; **a
single-pass audit of every entry in `controls.py` cmd_info dicts is
better**:

1. For each entry with `"subscription": True` or any documented response
   shape — capture a **real payload** against a current-firmware LG TV
   (the user has webOS 6.x on an OLED77G1RLA — likely the only LG
   running here, but most current LGs are this generation).
2. Compare to the documented shape in `docs/subscription_spec.md`.
3. If mismatch — add a `return` function that normalises to the
   documented shape (defensive: handle both shapes so old firmware
   doesn't break).
4. Or update the doc if reality is cleaner than the docs claim.

The user's bridge driver (`infrastructure/devices/lg_tv/driver.py`)
follows the documented contract. After this fix, no driver-side
workaround needed.

**Endpoints worth auditing as part of the same pass:**

- `MediaControl.subscribe_get_volume` — Bug 2 (KNOWN, evidence above).
- `MediaControl.subscribe_get_audio_output` — same URI as Bug 2; might
  share the wrapper issue.
- `MediaControl.subscribe_get_sound_output` — same URI; same suspicion.
- `MediaControl.get_volume` (non-subscription request) — same shape as
  Bug 2's subscription payload? Probably yes — same URI.
- `MediaControl.get_mute` — likely also returns `{muteStatus: bool}` not
  `{muted: bool}`.
- `SystemControl.power_state` — Bug 1 (URI flip).
- `InputControl.get_input` — Bug 3 (KNOWN, partial evidence).
- `InputControl.list_inputs` — payload key is `devices: [{id, label,
  port, connected, appId, ...}]`. Whatever the documented contract is
  for `list_inputs`, verify it matches.
- `ApplicationControl.subscribe_get_current` — worked correctly during
  the rack pass (payload was `{subscribed, appId, returnValue, windowId,
  processId}` and the bridge's `_on_foreground_app_change` extracted
  `appId` cleanly). No bug; just confirm the documented contract still
  matches.
- `TvControl.subscribe_get_current_channel` — not exercised today; worth
  checking but no evidence either way.

---

## Hardware context

- **TV**: LG OLED77G1RLA (2021 OLED Gallery G1 series, 77″).
- **Firmware**: webOS 6.x (exact build not captured; current production
  firmware as of 2026-05-27).
- **Subscriptions exercised**: `get_volume` (Bug 2 hit), `power_state`
  (Bug 1 hit), `get_current` foreground app (worked correctly — no bug).
- **One-shot requests exercised**: `get_input` (Bug 3 hit),
  `list_inputs` (worked, payload captured), `get_volume` poll at connect
  (worked at the call level but probably hit the same shape mismatch
  silently — bridge logged `volume=0` because the unwrap failed).
- **Dispatch chain verified working**: `_process_message` → `waiters`
  lookup → `wrapper(obj)` → `callback_wrapper(payload)` →
  `user_callback(success, payload)`. Subscription IDs are stable across
  multiple events (same UUID receives all 7 volume-up events). v0.3.0
  `close()`-cleanup not exercised yet (no reconnect during this pass).

---

## Reference

- First handoff (v0.3.0 driver): `docs/wb-mqtt-bridge-handoff-2026-05-27.md`.
- Bridge-side driver (after subscription wiring in commit 5a09fd1):
  `~/development/wb-mqtt-bridge/backend/src/wb_mqtt_bridge/infrastructure/devices/lg_tv/driver.py`
  — see `_on_volume_change`, `_on_power_state_change`,
  `_on_foreground_app_change` for what the consumer-side callbacks look
  like; they're written against the documented contract.
- aiowebostv (production peer, targets modern LG OLEDs):
  https://github.com/home-assistant-libs/aiowebostv — useful reference
  for both the `tvpower` URI and any payload-unwrapping logic they had
  to add for the same reasons.
- pywebostv upstream (synchronous parent): targets the older URI; useful
  to compare what changed.

---

## Suggested order of work

1. **Bug 1 (URI flip)** — single-line `cmd_info` change + URI-assertion
   test + spec-doc update. ~15 minutes. Unblocks power-state detection
   on every modern LG TV.
2. **Bug 2 (volume unwrap)** — add `return` function for `get_volume` +
   parametrized test + audit `get_mute` / `get_audio_output` /
   `get_sound_output` for the same pattern (capture real payloads first).
   ~30 minutes if no surprises.
3. **Bug 3 (input shape)** — capture the real `get_input()` payload
   first, then mirror the Bug 2 pattern. ~20 minutes.
4. **Pattern audit** — sweep every remaining `cmd_info` entry; for each
   one a consumer might call against current firmware, capture real
   payload, compare to doc, add `return` if needed. Bound this so it
   doesn't sprawl — only entries that wb-mqtt-bridge actually uses
   today are urgent.
5. Bump `pyproject.toml` to **0.3.1** (patch — additive fixes to a
   contract the library already documented). Update `__version__`. Tag
   + push. The bridge will bump its pin.

**Do NOT change the spec-documented user-callback contract.** The bridge
driver and any other consumer are written against
`subscription_spec.md`'s `(success, payload-with-flat-shape)` contract.
The fix should make reality match the spec, not the other way around.

**Do NOT re-enable WebSocket pings** under any circumstances — the v0.3.0
comment in `connect()` explains why; this remains absolute.

---

## What the bridge will do once this lands

- Bump `asyncwebostv` pin in `backend/pyproject.toml` (0.3.0 → new).
- Verify the existing `_on_volume_change` callback fires on physical
  remote presses (no driver code change needed if the library normalises
  per the spec).
- Verify `_on_power_state_change` fires when the user presses the TV's
  physical power button (URI flip is what makes this finally work).
- Verify the input-source field is populated at connect time (no
  subscription for this one, just the poll inside `_update_tv_state`).
- File a follow-up note here documenting any further mismatches found
  during the rest of the §5.1 #7 per-driver HW pass (eMotiva, IR fleet,
  etc. don't use this library, but if other LG-driven gear surfaces a
  fourth contract bug, you'll hear about it).

Good luck.
