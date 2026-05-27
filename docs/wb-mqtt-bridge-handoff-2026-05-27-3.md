# Note to another Claude — handoff #3: `InputControl.get_input()` returns nothing useful when foreground is an internal app (2026-05-27)

**Status:** Third handoff today. Previous two: `wb-mqtt-bridge-handoff-2026-05-27.md`
(prompted v0.3.0, subscription-lifecycle hardening) and `wb-mqtt-bridge-handoff-2026-05-27-2.md`
(prompted v0.3.1: `tvpower` URI flip + `get_volume` unwrap + `get_input` `inputId`
synthesis). Both v0.3.0 and v0.3.1 are confirmed working on hardware
(LG OLED77G1RLA, webOS 6.x).

This handoff is **research-first, no hardware capture available today** — the
user's family is watching TV; no more rack time. The library Claude is expected
to do the webOS-spec research independently and decide the right contract +
implementation based on the spec.

**The issue you're being asked to fix.** v0.3.1's `InputControl.get_input()`
synthesises `inputId` from `id` / `input_id` if missing. On the user's TV, **none
of those three keys is present** in the response — synthesis doesn't trigger, the
library returns the raw payload, and the consumer (wb-mqtt-bridge LG TV driver)
silently fails to populate `input_source` because its code does
`if "inputId" in payload`. We don't have the actual payload captured (silent fail
in the consumer, no DEBUG log line, no rack access today to re-instrument). You
need to figure out what the response *should* contain — from the spec, not from
trial and error against the user's TV.

---

## Captured evidence

**What we know:**

1. After v0.3.1 (installed + verified, version pinned in
   `wb-mqtt-bridge/backend/pyproject.toml` as `asyncwebostv==0.3.1`), on a
   webOS 6.x LG OLED77G1RLA, calling `InputControl.get_input()` at connect time
   returns a payload **without any of `inputId`, `id`, `input_id`**.

2. The library's synthesis (`controls.py:1205-1209`) does not trigger; the raw
   payload is returned unchanged.

3. The consumer's check `if "inputId" in input_info` is False; consumer silently
   returns and `input_source` stays `None`.

4. **Context at the time of the call:** the TV was foregrounded on
   `com.webos.app.hdmi2` (the webOS launcher's HDMI 2 app — the eMotiva XMC AVR
   on HDMI port 2). I.e. you'd expect `inputId='HDMI_2'` if anything sensible
   were being returned.

5. **What `list_inputs()` (companion call, `ssap://tv/getExternalInputList`)
   returned at the same time** — captured in full from the bridge log:

   ```python
   {'returnValue': True,
    'devices': [{'id': 'HDMI_1', 'label': 'HDMI 1', 'port': 1,
                 'connected': False, 'appId': 'com.webos.app.hdmi1', ...},
                {'id': 'HDMI_2', 'label': 'Emotiva XMC', 'port': 2,
                 'connected': True, 'appId': 'com.webos.app.hdmi2', ...},
                {'id': 'HDMI_3', 'label': 'HDMI 3', 'port': 3,
                 'connected': False, 'appId': 'com.webos.app.hdmi3', ...},
                ...]}
   ```
   So the library's expected `id` key DOES exist in `list_inputs()` device
   entries — but `get_input()`'s response (a different endpoint) apparently
   doesn't carry that key for the "currently active" input.

**What we do NOT know:**

- The actual shape of the `getCurrentExternalInput` response on this firmware.
  Could be `{returnValue: True}` (no input info at all), `{returnValue: True,
  appId: 'com.webos.app.hdmi2'}` (app id only), `{returnValue: False, errorCode:
  ..., errorText: ...}` (soft error), or something else firmware-version-specific.

- Whether webOS sends a *different* response when the foreground is an *internal
  app* (launcher, IVI, YouTube) vs an HDMI app — there's a real possibility that
  `getCurrentExternalInput` returns nothing meaningful when the foreground isn't
  an external input.

---

## Strong working hypothesis (validate against the spec)

webOS's foreground model has two layers:

- **Foreground app** (`getForegroundAppInfo` → `appId`): one of
  `com.webos.app.hdmi<N>` for HDMI inputs, `com.webos.app.home` for the
  launcher, `com.webos.app.livetv` for the tuner, OR any installed app id
  (`ivi`, `youtube.leanback.v4`, etc.).

- **Current external input** (`getCurrentExternalInput`): the HDMI/AV port the
  TV is currently rendering from. This is a *physical-input* concept and only
  has a meaningful value when the foreground app *is* an external-input viewer
  (`com.webos.app.hdmi<N>`).

If the user is on **the launcher or an internal app like IVI**,
`getCurrentExternalInput` may legitimately have *no* current external input to
report. The previous-selected HDMI port is still "remembered" by the TV (and
used for wake-resume), but isn't the *active* input. So:

| Foreground app          | `getCurrentExternalInput` (hypothesis)                  |
|-------------------------|----------------------------------------------------------|
| `com.webos.app.hdmi2`   | should return something identifying HDMI_2               |
| `com.webos.app.hdmi1`   | should return something identifying HDMI_1               |
| `com.webos.app.home`    | should return empty / no-current-input / error           |
| `ivi` / `youtube.*` / … | should return empty / no-current-input / error           |
| `com.webos.app.livetv`  | depends on tuner state, separate semantics               |

**This is the consumer's working model.** The hypothesis is consistent with what
we've observed but is not spec-confirmed. **Your first task is to confirm or
refute it against the webOS spec.**

---

## webOS research task

1. **Find the spec for `ssap://tv/getCurrentExternalInput`.** Primary source: the
   LG webOS TV developer reference at
   <https://webostv.developer.lge.com/develop/references/luna-service-api>. Also
   useful: the Luna service introspection — call the service's `describe`
   method via the WebSocket and see what it self-documents. Secondary sources:
   the pywebostv upstream README/tests, aiowebostv source, and the LG
   developer-forum threads where edge cases get discussed.

2. **Document the actual response shape for each foreground-app class.** Even
   without rack access today, the spec or pywebostv/aiowebostv should give
   enough evidence to characterise:
   - Response when foreground is `com.webos.app.hdmi<N>` (HDMI input active).
   - Response when foreground is `com.webos.app.home` (launcher).
   - Response when foreground is an installed-app id (IVI, YouTube, etc.).
   - Response when no foreground (TV in some transitional state — does this
     even happen?).

3. **Find the canonical "identify the current input" pattern that production
   peers use.** Specifically check:
   - `aiowebostv` (home-assistant-libs): how does the HA webostv integration
     determine the current input? Does it use `getCurrentExternalInput`, or does
     it derive from `getForegroundAppInfo`'s `appId` (matching against
     `com.webos.app.hdmi<N>`)?
   - `pywebostv` upstream: same question.
   - If both derive from foreground-app rather than `getCurrentExternalInput`,
     that's a strong signal that `get_input()` is the wrong endpoint for this
     use case, and the library should de-emphasise it.

4. **Decide the right library contract.** Three plausible designs:

   - **(A) `get_input()` returns whatever webOS returns, documented as "may be
     empty when no external input is active"** — minimal change; spec the
     consumer to handle empty / no-`inputId` payloads explicitly. Update the
     docstring and `subscription_spec.md` to say so. (Note: there's no current
     "subscription" spec entry for `get_input` — it's only a request method.)

   - **(B) `get_input()` returns a normalised dict that always contains
     `inputId` — derived from `getForegroundAppInfo` (parsing
     `com.webos.app.hdmi<N>` → `HDMI_<N>`) when `getCurrentExternalInput` is
     empty/silent.** Hides the webOS quirk behind a single canonical API. Risk:
     a single library call now hits two endpoints, increasing latency + failure
     surface. But matches what aiowebostv probably does.

   - **(C) Add a new method `get_current_input_app() -> Optional[str]`** that
     returns the foreground app id and lets the consumer do the
     `com.webos.app.hdmi<N>` → `HDMI_<N>` derivation. Deprecate
     `get_input()` (or keep it as raw passthrough with a docstring note).
     Cleanest layering; consumer-side derivation is one regex.

   Choose the one that matches what production peers do, with a preference for
   the simplest API surface. Pick whichever you can defend against the spec.

5. **The "subtle question" the consumer raised** (and they explicitly want
   webOS-spec input here, not opinion): **when the foreground is an internal
   app (launcher / IVI), what should `input_source` semantically be —
   `None` (truthful: no external input active), or the last-remembered HDMI
   port (useful: "which HDMI is selected underneath the launcher")?**

   Look at how webOS itself models this — is there a "last selected external
   input" concept exposed by the API? Does
   `getCurrentExternalInput` return the last-remembered value, or only the
   currently-active one? aiowebostv's behaviour here is also worth checking —
   what value does HA's "Source" sensor show when the LG TV is on an internal
   app? **The consumer wants the library's choice to follow webOS's own
   model**, whatever that turns out to be.

---

## Suggested order of work

1. **Spec research first.** Don't write code until you've answered: what
   does `getCurrentExternalInput` actually return for each foreground class,
   and what do peer libraries do? File the findings inline in this doc (append a
   "Findings 2026-05-XX" section) before changing code. The findings inform the
   choice between contracts (A)/(B)/(C) above.

2. **Pick one of (A)/(B)/(C)**, document the choice + rationale in
   `docs/subscription_spec.md` (new "Current External Input" section, or extend
   whatever input doc exists), and implement.

3. **Tests.** Whatever shape you choose, lock it in with a unit test using a
   captured-payload fixture. If you can find a real payload from peer projects'
   test fixtures, use that; otherwise build the fixture from what the spec
   documents.

4. **Bump to 0.3.2.** Patch-level — additive fix to a contract that was
   partial in 0.3.1.

---

## What the consumer (wb-mqtt-bridge) will do once this lands

- Bump `asyncwebostv` pin in `backend/pyproject.toml` (0.3.1 → 0.3.2).
- Adapt `_update_input_source()` in
  `wb-mqtt-bridge/backend/src/wb_mqtt_bridge/infrastructure/devices/lg_tv/driver.py`
  (around line 932 in the current HEAD) to match whichever contract you choose:
  - (A) → still check `"inputId" in input_info` but accept empty payload as
    "internal-app foreground; input_source=None"; add a fallback to derive from
    `current_app` for HDMI cases.
  - (B) → trust the synthesised value directly; `_update_input_source()` becomes
    a one-line wrapper around the library call.
  - (C) → drop `_update_input_source()` entirely; derive `input_source` from
    `current_app` inside `_on_foreground_app_change()` (the existing subscription
    callback — single source of truth).

The consumer's strong preference is for **(C)** because it makes the
foreground-app subscription the single source of truth for both `current_app`
and `input_source`, eliminating a separate poll round-trip per connect.
**But the consumer wants whichever contract the library ends up shipping** —
they'll adapt.

- Re-verify on hardware at the next rack session: confirm `input_source`
  populates correctly when the TV is on an HDMI app, and is `None` (or
  whatever the new contract specifies) when on an internal app.

---

## Out of scope for this handoff (do NOT investigate)

- **HDMI-CEC OneTouchPlay behaviour** — the consumer observed that WoL wake
  always lands on HDMI2 on this TV regardless of last-selected input, while
  physical-remote wake resumes to the actually-last-selected input. Working
  theory is that the eMotiva XMC AVR (always-on, on HDMI2) claims the display
  via CEC OneTouchPlay during the WoL wake sequence; physical-remote wake
  completes its resume before CEC renegotiation. This is **not a library
  concern** — the library does WoL via raw magic packet; CEC happens entirely
  TV-side. Don't chase it.

- **The "subtle question" about `None` vs last-remembered HDMI** — answer it
  via webOS spec research (item 5 above), don't decide on opinion alone.

- **Subscription on `getCurrentExternalInput`** — webOS may or may not support
  it. If it does, that's a nice-to-have follow-up but not part of this fix.
  The bridge's foreground_app subscription already provides input-change
  detection via the `com.webos.app.hdmi<N>` foreground transitions.

---

## Reference

- Bridge driver site: `wb-mqtt-bridge/backend/src/wb_mqtt_bridge/infrastructure/devices/lg_tv/driver.py`
  — `_update_input_source()` around line 932. Reads
  `input_info = await self.input_control.get_input()` then `if input_info and
  "inputId" in input_info: self.update_state(input_source=...)`.
- Library current state: `asyncwebostv/asyncwebostv/controls.py` —
  `InputControl.get_input()` at lines 1191–1210 (v0.3.1's `inputId` synthesis).
- Previous handoffs (in this same docs/ directory):
  `wb-mqtt-bridge-handoff-2026-05-27.md` → v0.3.0 work.
  `wb-mqtt-bridge-handoff-2026-05-27-2.md` → v0.3.1 work.

Good luck. The spec is the answer here.

---

## Findings — 2026-05-27 (library Claude, post-spec research)

### Finding 1: LG officially states no current-input API exists

On the LG webOS developer forum thread
[*Get/set Current source in LG WebOS TV Programatically/API*](https://forum.webostv.developer.lge.com/t/get-set-current-source-in-lg-webos-tv-programatically-api/16338),
LG developer **narae0.kim** responded:

> *"Currently, no APIs for getting TV input information are provided."*

This is the authoritative answer. There is no "get current input" endpoint
in the documented webOS SSAP/Luna API. The community has no published
alternative endpoint either.

### Finding 2: `ssap://tv/getCurrentExternalInput` is non-canonical

- [`pywebostv` upstream](https://github.com/supersaiyanmode/PyWebOSTV)
  has **no implementation** of `get_input` / `getCurrentExternalInput`.
  Its `InputControl` covers IME (keyboard) and pointer/remote buttons
  only; its `SourceControl` exposes only `list_sources` (the LIST
  endpoint) and `set_source` (the switch endpoint).
- The endpoint URI `ssap://tv/getCurrentExternalInput` exists in our
  fork's `InputControl.get_input()` and `SourceControl.get_source_info`
  cmd_info entry, but appears to have been added during the async port
  rather than inherited from upstream. The HW behaviour we're seeing on
  webOS 6.x (subscribe succeeds, response carries no input identifier)
  is consistent with this being an unofficial / firmware-version-
  sensitive endpoint.

### Finding 3: aiowebostv derives "current input" from the foreground app

The production library
[`aiowebostv`](https://github.com/home-assistant-libs/aiowebostv) (which
the Home Assistant LG webOS integration uses on every modern LG OLED)
implements:

```python
async def get_input(self) -> dict[str, Any] | None:
    """Get current input."""
    return await self.get_current_app()
```

…where `get_current_app()` calls `ssap://com.webos.applicationManager/
getForegroundAppInfo` and returns the `appId` field. **`getCurrentExternalInput`
is not used anywhere in aiowebostv.** The library stores the raw `app_id`
(e.g. `"com.webos.app.hdmi2"`) as `current_app_id`; it does NOT parse it
into a human-readable HDMI port name. The HA integration above maps the
app id to a display label by looking it up in the cached `list_inputs()`
device entries (which carry both `id: HDMI_2` and `appId:
com.webos.app.hdmi2` per device).

### Finding 4: Foreground-app payload is well-documented and known

From handoff #2, real captured `ApplicationControl.subscribe_get_current`
payload on this same TV:
`{subscribed, appId, returnValue, windowId, processId}`. The one-shot
`getForegroundAppInfo` request returns the same shape. `appId` at root
is reliable.

### Finding 5: "Last-remembered HDMI" is not API-exposed

LG's quote rules this out: no current-input API means no "last selected
input" API either. Tracking "which HDMI is selected underneath an
internal-app foreground" would have to be done locally by the consumer
(remember the last `com.webos.app.hdmi<N>` they saw before the internal
app took over). The library cannot provide a more truthful answer than
webOS itself does.

### Conclusion + recommendation

The spec/peer evidence is unanimous: **derive current input from the
foreground app**, do not call `getCurrentExternalInput`. The endpoint
is non-canonical, undocumented, and (HW-confirmed) doesn't carry the
expected identifier on current firmware. Continuing to call it is
strictly worse than calling `getForegroundAppInfo`.

**Recommendation: hybrid B/C.** Refactor `InputControl.get_input()` so
that the *user-facing contract* matches the documented "always contains
`inputId` when an HDMI is active" shape (Option B's API surface), but
implement it by calling `getForegroundAppInfo` and parsing `appId`
(Option C's mechanism). Specifically:

- `get_input()` calls `ssap://com.webos.applicationManager/getForegroundAppInfo`,
  extracts `appId`, parses `com.webos.app.hdmi(\d+)` → `HDMI_<N>`.
- Returns `{"inputId": "HDMI_2", "appId": "com.webos.app.hdmi2",
  "returnValue": True}` when foreground is an HDMI app; returns the raw
  payload **without** an `inputId` key when foreground is anything else.
- Expose a small public helper `app_id_to_input_id(app_id)` so consumers
  that derive `input_source` inside their own foreground-app
  subscription callback (the consumer's stated preference) can use the
  exact same parsing without re-implementing it.

This satisfies the consumer's stated preference (single derivation in
their foreground-app callback) while keeping `get_input()` working for
anyone reading the spec literally. The library becomes the canonical
home of the parsing rule.

**On the subtle question (item 5):** when foreground is an internal
app, the library should report **no `inputId`** (key omitted) — matching
webOS's own model (no current-input API → no current input to report).
Consumers who want a "last-remembered HDMI" semantic must track it
themselves; the library cannot synthesise it truthfully.

