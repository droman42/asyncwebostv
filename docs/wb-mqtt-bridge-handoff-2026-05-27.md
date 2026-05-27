# Note to another Claude — handoff from the wb-mqtt-bridge audit (2026-05-27)

**Status:** Handoff. Audit was conducted in the **sibling consumer repo**
`~/development/wb-mqtt-bridge` on 2026-05-27. **No code in this library has
been changed** as a result. This note summarises what was found, the one
required change, and other meaningful checks the audit suggests for
`asyncwebostv` itself.

**Why you're getting this note.** The user owns both this library and
`wb-mqtt-bridge` (a hexagonal-architecture FastAPI/MQTT bridge that drives
their LG TVs, among other devices, from a Wirenboard PLC). The bridge is
about to begin a per-driver on-hardware verification session. The LG TV
driver is the only one that depends on `asyncwebostv`, and the user
specifically asked for a deep audit of its notification/listener mechanism
before starting the HW pass.

**Who you are.** A Claude session about to work on `asyncwebostv`. Treat
this note as a research handoff — context + findings, not a code spec.
Verify each claim against the current source before acting on it.

---

## TL;DR

1. **Required change (HIGH severity, latent landmine):** `WebOSClient.close()`
   does not clear `self.waiters` and `self.subscribers`. Currently harmless
   (the only known consumer — the wb-mqtt-bridge LG TV driver — uses zero
   subscriptions today), but will silently corrupt state the moment any
   consumer adds subscriptions + a reconnect path. The bridge driver is
   poised to add at least `subscribe_power_state` shortly.

2. **One inconsistency** between `docs/subscription_spec.md` (says callbacks
   receive `(success: bool, payload: Any)`) and what the bridge-side audit
   observed in `asyncwebostv/connection.py:230–237` (looked like
   `callback(obj)` with the raw message dict). Either the spec is right and
   the connection-level wrapper unpacks elsewhere, or the spec is wrong.
   **Verify.** This is load-bearing — bridge-side handlers will be written
   against whatever the actual contract is.

3. **Several other meaningful checks** documented below — none are urgent,
   but they're worth doing once before consumer code starts to depend on
   them.

---

## Context from the wb-mqtt-bridge audit

### What the bridge does with this library today

- Driver: `wb-mqtt-bridge/backend/src/wb_mqtt_bridge/infrastructure/devices/lg_tv/driver.py` (~2571 lines).
- Uses `WebOSTV.connect()` / `client.register()` then reads volume / mute /
  current app / input source **once** in `_update_tv_state()` after connect.
- **Calls zero `subscribe_*` methods.** Pure polling at connect time.
  Result: state on the driver side drifts from reality the moment the user
  touches the physical remote or anything else changes on the TV side.
- After today's chokepoint work in the bridge (commit `386b544`+others),
  any state write in the driver routes through a single `update_state(...)`
  call that fires registered callbacks for both `state.db` persistence and
  Wirenboard MQTT publish. So if the driver adds `subscribe_*` callbacks
  that just call `self.update_state(field=value)`, persistence + WB UI
  sync work automatically. Adding subscriptions is the obvious next step.

### Why this matters for the library

The bridge is about to start using the library's subscription surface in
anger. **Right now, any latent bug in subscription teardown / reconnect /
callback lifecycle is invisible** because nobody triggers those paths. The
fixes and checks below are pre-emptive — get the library solid before the
consumer driver starts hitting it.

---

## The one required change

### `WebOSClient.close()` must clear `waiters` and `subscribers`

**File:** `asyncwebostv/connection.py` — `WebOSClient.close()` (around lines
187–199 as audited 2026-05-27; verify the line numbers).

**Current behaviour:** `close()` closes the WebSocket, cancels the
message-handling task (`self.task`), awaits its cancellation. **Does NOT
touch `self.waiters` or `self.subscribers`.**

**Why this is broken (latent):** The two dicts survive across a
disconnect+reconnect cycle. If a consumer:
1. Subscribes to volume changes (UUID `abc` → callback `cb1`),
2. Disconnects (close → task cancel; `waiters[abc] = (cb1, None)` survives,
   `subscribers["volume"] = abc` survives),
3. Reconnects (new `WebOSClient`? or same? — verify; the bridge driver
   currently creates a new client, but other consumers might reuse),
4. Subscribes again → new UUID `def` → callback `cb2`.

What happens depends on whether the same client is reused, but in either
case zombie callbacks in `waiters` are a footgun: they hold references that
prevent GC, they fire on any message whose ID matches, and they can write
state into objects that no longer exist on the consumer side. With the
bridge's new state-change chokepoint, a stale `cb1` firing after the
consumer thinks it unsubscribed would publish to MQTT topics under the
wrong device's identity. Not great.

**Required fix:**

```python
async def close(self):
    # ... existing close logic ...
    # ADD: clear subscription bookkeeping so stale waiters can't fire on a
    # reconnected client, and so any new subscribe_*() starts from a clean
    # slate. Harmless today; required by any consumer adding subscriptions.
    self.waiters.clear()
    self.subscribers.clear()
```

(Exact placement: after the task is cancelled + awaited, before `close()`
returns. Verify what other state lives next to these dicts and whether
anything else needs the same treatment — e.g. `_clear_old_waiters()`
machinery, registration-callback cleanup.)

**Lock-it-in test (also required):**

Add a test in `tests/` that does:
1. `client = WebOSClient(...); await client.connect(); await client.register(...)`.
2. Subscribe to something (e.g. `await media.subscribe_get_volume(cb)`).
3. Assert `client.waiters` and `client.subscribers` are non-empty.
4. `await client.close()`.
5. Assert **both dicts are empty.**

This test fails today (verify before fixing — TDD-ish) and should fail in
future if anyone re-introduces the bug.

---

## Other meaningful checks (do these once, none are urgent)

### Check 1 — Verify callback signature: `(success, payload)` vs raw `obj`?

**The audit found a discrepancy** between two parts of the codebase:

- `docs/subscription_spec.md` says the callback signature is
  `async def callback(success: bool, payload: Any) -> None:` — the success
  flag separates errors from valid events.
- The runtime audit looked at `asyncwebostv/connection.py:230–237` and
  reported the wrapper as `callback(obj)` (raw message dict, no success
  unpacking).

**Both can be true** if the per-control `subscribe_*` methods in
`controls.py` wrap the user callback with one that does the `(success,
payload)` unpacking before delegating to the user's callback. The spec then
describes the *user-facing* contract while the connection-level wrapper
sees only `(obj)`.

**Action:** Trace one subscription end-to-end — pick `MediaControl.subscribe_get_volume`
(`controls.py:269` per the audit) — and document the actual call chain
from `client._process_message` to the user's callback. If the spec is
accurate, add a comment to `_process_message` pointing at where the
unpacking happens. If the spec is wrong, fix the spec (`docs/subscription_spec.md`)
and also flag this back to the consumer so the bridge driver doesn't write
its callbacks against the wrong signature.

### Check 2 — `unsubscribe_<method>()` actually sends `cancelSubscribe`?

webOS subscriptions are stateful on the TV side. A consumer who only
removes a local subscription record but doesn't send `{"type": "unsubscribe"}`
to the server leaves the server merrily sending events into a socket that
no longer wants them — server-side log noise, potentially state bloat in
long-running connections.

**Action:** Verify that `WebOSClient.unsubscribe(uid)` (in `connection.py`,
around the area audited as 189–191 for `close()`) actually sends the
protocol-level `unsubscribe` message in addition to removing from
`subscribers` and `waiters` dicts. If it doesn't, add it. The webOS spec
documents the `unsubscribe` message type — see e.g. the LG WebOS API
reference pages for `subscribe` / `unsubscribe` semantics.

### Check 3 — Document the ping/pong=disabled decision

The library has `ping_interval=None` (or equivalent) on the WebSocket
connection. This was done to fix LG TV power-off detection — earlier
versions had ping/pong race against subscription-message parsing,
specifically the power-state subscription's standby-transition message.

**Action:** Add a code comment **at the websockets-connect call site**
explaining this so a future change can't silently re-enable pings without
understanding the regression risk. Something like:

```python
# Do NOT add ping_interval. Pings race against webOS subscription
# messages (particularly power-state standby transitions), causing
# events to be dropped mid-frame. If you want a keepalive, do it at
# the application layer (e.g. periodic system.info() poll).
ws = await websockets.connect(uri, ping_interval=None, ...)
```

This mirrors the wb-mqtt-bridge `[[hexagonal-law-for-all-changes]]` memory
pattern: "don't undo prior fixes without understanding why."

### Check 4 — Concurrent connect/disconnect safety

The audit mentioned a `_connecting` flag (or similar) preventing concurrent
`connect()` calls from racing. **Verify it actually works** — specifically:

- Two concurrent `await client.connect()` calls. Does the second one wait
  for the first, return early, or race?
- `await client.connect()` interleaved with `await client.close()` from a
  different task. What happens to in-flight messages? Is the
  message-handling task cleanly cancelled?
- Reconnect immediately after close — does any state from the prior
  connection (waiters, subscribers, the cancelled task itself) interfere?

These are unit-test-shaped questions. Add tests if there aren't any.

### Check 5 — Subscription survival across reconnect — what's the contract?

If a consumer subscribes, the connection drops, and they call `connect()`
again, what's supposed to happen?

- Option A: the library auto-resubscribes (tracks active subscriptions,
  reissues them on reconnect).
- Option B: the consumer is responsible for tracking and re-subscribing.
- Option C: undefined / "don't do that."

**Whichever is the intent, document it** in `docs/subscription_spec.md`.
The bridge driver needs to know which model to write against. If the answer
is B (consumer-responsibility), the wb-mqtt-bridge LG TV driver will track
subscription handles and re-subscribe in its own reconnect path — fine, but
needs a clear doc statement to anchor the driver design.

The `advance_subscriptions.md` roadmap doesn't seem to cover this; worth
adding.

### Check 6 — `ApplicationControl.subscribe_get_foreground_app_info`?

The audit noted that `ApplicationControl` in `controls.py` does NOT have a
`subscription: True` marker on `get_foreground_app_info`, even though
webOS does support subscribing to that endpoint (Home Assistant and others
use it for "current app" tracking).

**Action:** Verify on the hardware whether `ssap://com.webos.applicationManager/getForegroundAppInfo`
actually accepts `{"subscribe": true}` on current webOS versions (the user
has LG OLEDs — likely webOS 4.x or 5.x). If yes, add the
`"subscription": True` marker and confirm a `subscribe_get_foreground_app_info`
method gets dynamically generated. If no, document why it's excluded.

### Check 7 — webOS power-state value mapping

`SystemControl.subscribe_power_state` (the canonical pain point for LG TV
integrations) delivers power state events with values that aren't a simple
on/off — possible values include "Active", "Active Standby", "Screen Off",
"Suspend", and combinations of `state` + `processing` fields.

**Action:** Once hardware verification on the bridge side produces the
actual values observed in each transition (TV-remote-off, app-driven
power-off, network-loss, etc.), document them in
`docs/subscription_spec.md` under the power-state section — what each
value means, what consumers should map them to. This isn't urgent; it's a
follow-up after the bridge HW pass. Note this as a "TBD" placeholder for
now if you want.

### Check 8 — Callback-error containment

When a subscription callback throws an exception, the audit noted the
library catches + logs it at `connection.py:230–237` (or thereabouts) and
the listening task continues. That's defensible. **No action required.**
The bridge has been warned that a consistently-throwing callback will
silently spam logs forever — they can add their own circuit-breaker on
their side if it ever becomes a real problem. **Do not preemptively add
an auto-unsubscribe-after-N-failures mechanism** — it's a sledgehammer
that hides real bugs. Logging is fine.

---

## Reference: where the wb-mqtt-bridge audit lives

- Branch/main of the bridge repo at commit `42b3606` or later has a §6
  Revision Log entry summarising the state-sync chokepoint work that
  preceded this audit.
- The Explore agent's full audit report is in the conversation transcript
  of the 2026-05-27 session (not yet committed anywhere as a doc).
- The bridge's state-change chokepoint pattern (relevant to how subscription
  callbacks should write state) is documented in
  `wb-mqtt-bridge/docs/action_plan.md §6` and in the bridge's memory at
  `~/.claude/projects/-home-droman42-development-wb-mqtt-bridge/memory/state-sync-chokepoint.md`.

## Reference: existing library docs you should already know

- `docs/subscription_spec.md` — formal spec of the subscription API.
- `docs/advance_subscriptions.md` — roadmap for more subscriptions.
- `docs/code_review.md` — pywebostv → asyncwebostv migration summary.
- `docs/async_migration_spec.md` — original migration spec.
- `docs/SSL_spec.md` — secure-connection design.

---

## Suggested order of work

1. **Required:** Fix the `close()` cleanup + write the regression test
   (Check above the line). Small, defensive, unblocks future consumer
   subscriptions.
2. **High-value:** Resolve the `(success, payload)` vs `obj` callback
   signature discrepancy (Check 1) — the bridge driver needs to know which
   it is. Trivial investigation, then either fix the spec or add a comment.
3. **Medium:** Verify `unsubscribe()` sends `cancelSubscribe` (Check 2).
4. **Medium:** Add the ping/pong=disabled code comment (Check 3).
5. **Low / batch:** Concurrent connect safety (Check 4), reconnect-and-
   subscriptions contract (Check 5), foreground-app subscription marker
   (Check 6).
6. **Defer until bridge HW data arrives:** Power-state value mapping doc
   (Check 7).
7. **Do nothing:** Callback-error circuit-breaker (Check 8).

If you take on items 1+2, you've cleared the path for the bridge to add
subscriptions safely. Everything else is polish.

**Do not refactor the subscription API surface** — the `subscribe_*` /
`unsubscribe_*` shape is what the bridge will write against. Any change
there needs a coordinated update on the bridge side.

**Do not re-enable WebSocket pings** under any circumstances — see Check 3.

Good luck.
