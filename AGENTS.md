# mxz_coordinator_blueprint: MXZ Coordinator as an HA blueprint

A Home Assistant automation blueprint that ports the core decisions of the upstream
integration [dkpnw/ha-mxz-coordinator](https://github.com/dkpnw/ha-mxz-coordinator)
for Mitsubishi heads that reach HA through a cloud integration (MELCloud, Kumo Cloud)
instead of CN105/ESPHome. It is a standalone project, not a fork, and shares no code
files with upstream. Credit and upstream's license are in `NOTICE`; keep that file
when copying anything else from upstream.

## Layout

| Path | What it is |
| --- | --- |
| `blueprints/automation/mxz_coordinator.yaml` | The blueprint: six room slots, all logic in one Jinja `plan` variable; the actions apply `plan.commands`. |
| `tests/test_blueprint.py` | Runs the blueprint in a real HA test instance (`pytest-homeassistant-custom-component`) with mock heads that apply commands to their own state. |
| `mxz_helpers.yaml` | Example HA helpers: per-room targets and enables, `input_boolean.mxz_enable`, and `input_select.mxz_mode`. |
| `README.md` | User-facing setup and caveats. |
| `CHANGELOG.md` | One entry per version, with the rules for choosing the number and upgrade steps for major versions. |
| `LICENSE`, `NOTICE` | MIT for this repo; upstream's MIT notice and what was ported, at which commit. |

## Commands

```bash
pip install -r requirements_test.txt   # into a venv; the system Python has no HA
pytest
```

Run `pytest` after every blueprint change. Last run on HA 2026.10.4 with Python 3.14.

## Versioning

The version lives in the blueprint's `name` (`... v1.0.0`), because HA's blueprint
schema rejects a `version` key. Keep it out of the file name: saved automations
point at the path. Each release bumps `name` and adds a `CHANGELOG.md` entry (a test
checks the two match), then merges to `main`, and the merge commit is tagged
`vX.Y.Z`. Renaming or removing an input or a select value is a major version.

## How the logic maps to upstream

The `plan` template ports these functions from upstream's
`custom_components/mxz_coordinator/logic.py`, as of commit `f30a9aa` (tag v3.12.1).
Keep the behavior in step. When upstream releases, diff `logic.py` and `const.py`
from that commit, port what matters, and update the commit in `NOTICE` and here.

- `call` macro ← `room_call` / `call_edges` (cool checked first; lockouts move an edge out to the floor/ceiling). It takes `ht`/`ct`, the heat and cool side targets: Heat to / Cool to in a dual-setpoint room, the one target twice otherwise, as upstream's `heat_target`/`cool_target`.
- engage block ← `engage_with_latch` (drift to start, band 0 to run to target, direction flip → satisfied)
- shared-mode block ← `shared_mode` (standoff → first calling room in slot order; `min_switch_seconds` dwell; resting mode)
- fan block ← `fan_for_delta` (step thresholds are `fan_step` × 1/2/3/4 up and × 0.5/1.5/2.5/3.5 down)
- `act` chain ← `head_action`
- `in_dry`, `dry_vote`, `dry_parked` ← Allow Dry mode from upstream's open PR 56 (`coordinator.py` `_in_dry`, `_dry_settle`; `logic.py` `arbitrate`'s `engaged` gate for ordinary votes), at its commit `b177920`, version 3.15.0, unreleased. Recheck against upstream once it merges.
- setpoint `want` ← `setpoints` side choice (Heat to while heating, Cool to while cooling); fan `delta` ← `range_delta`

Input defaults match upstream's °F defaults (`const.py`): drift 1, threshold 3,
dwell 600 s, idle `off_after_clean` (upstream's `off_after_dry`) with 10 min coil clean, fan thresholds 1/2/3/4 up and
0.5/1.5/2.5/3.5 down, clamp 59–88, dual-setpoint least gap 2.

## Deliberate differences (don't "fix" these toward upstream)

- **Setpoint drive offset.** Cloud heads can't take a remote temperature, so a
  running head gets target ± `drive_offset` and the blueprint parks it when the room
  sensor reaches target. Upstream sends the target itself.
- **Settle delay instead of delivery tracking.** Cloud state lags, so after sending
  commands the run waits `settle_seconds`, and `mode: single` drops triggers meanwhile.
  That is the rate limit and the guard against re-sending before the head reports.
- Parks are emitted before runs, so the outdoor unit isn't asked for both directions at once.
- An unavailable head's room makes no demand (no lost-vote TTL).
- Up to 6 rooms (upstream allows 8).
- **Dual setpoint is two helpers, not a climate range.** Upstream refuses or
  pushes a too-narrow write (`resolve_range`); helpers can't be constrained, so a
  pair under `dual_min_gap` makes the room ask for nothing (`problem` says why).
  No midpoint target, `shift_range`, or switching a room between single and dual
  at runtime; which kind a room is comes from which inputs are filled.
- **Doors and windows are ours, not upstream's.** A room's optional `open`
  binary_sensor, on for `open_delay_seconds` (measured from its `last_changed`),
  makes the room `open`: `call` gets `en` false (no demand, no engage) and the
  `act` chain picks `off`, with no coil clean. `held` is a stopped head (not in
  heat/cool) whose sensor is on but not yet `open`, or off for under
  `close_delay_seconds`: it gets no demand or engage and `act` `hold` (no
  command), so it can't start; a running head is never held. With no memory, the
  blueprint can't tell whether a closed door's last opening was long enough to
  count, so the close delay applies after any opening, but only to stopped heads.
  Ordered after "disabled", so a disabled room's `leave` still wins. Not in
  `duplicates`: one group may serve several rooms. A delay running out isn't a
  state change, so the 2-minute time pattern is what notices it.
- **Allow Dry has no memory either.** `in_dry` is read from the head each run, so
  the coil clean follows only a park from Dry (`act` sees `in_dry`), not someone
  taking the head to `off` themselves (upstream owes a clean then). A switch caused
  by a Dry vote restarts the dwell (upstream exempts vote flips), because the helper's
  `last_changed` can't say who moved it. Parks repeat if the head still reports Dry
  after the settle delay; the notification has a per-slot id, so that replaces it
  rather than stacking. Open doors and windows beat Dry (`in_dry` needs not `open`;
  `held` needs not `in_dry`). Upstream's manual fan hold has no counterpart: fan
  step is already the head's current `fan_mode`.
- Not ported: eco/away, standby hold, safety priority, freeze floor,
  own-remote rooms, per-room thermostat entities.

## Blueprint specifics

- **No memory of its own; state comes from entities.** Shared mode = the
  `input_select` helper, switch clock = its `last_changed`, run-to-target latch =
  the head being in heat/cool, coil clean timer = the head's time in `fan_only`, fan
  step = the head's current `fan_mode`. Don't add helpers for these without a reason;
  fewer helpers is the point.
- **Variables come back as Python literals, not JSON.** End `plan` with a bare
  dict (`{{ {...} }}`). `| tojson` makes `true`/`null`, which fails literal parsing,
  and `plan` silently becomes a string.
- **Rooms are six fixed slots** (`room_N_head/sensor/target/heat_to/cool_to/enable/open/allow_dry`;
  head, sensor, and enable required in 1–2, everything else default `""`, and
  `allow_dry` default false). A room
  has a target or a Heat to/Cool to pair, never both; `dual` in the plan is "no
  target". `slots` gathers them, `rooms_cfg` keeps slots with a head, and
  `config_ok` rejects partly filled slots (`incomplete`) and entities used twice
  (`duplicates`; target, heat to, and cool to are one pool); the plan loop skips
  rooms when it's false so the notification can run. Slot number is priority.
  Adding a slot means touching the inputs, the seven triggers, and `slots`; nothing
  in `plan` changes.
- **Room triggers are `state_changed` event triggers, not state triggers.** A state
  trigger on an optional slot saved as `""` or `null` (filled, then cleared in the UI)
  leaves the whole automation `unavailable`; an event trigger filtering
  `event_data.entity_id` doesn't care. Verified on HA 2026.10.4. They also fire on
  attribute-only changes, which `mode: single` and the settle delay absorb.
- Each plan room carries `slot`, `sensor`, `target_entity`, `heat_to_entity`,
  `cool_to_entity`, `enable_entity`, and `open_entity` so the trace shows the pairing. Keep them when changing the plan.
- `tests/test_blueprint.py` asserts `automation.mxz` is `on` after setup: a blueprint
  that fails to load or attach leaves it `unavailable` without failing setup.
- Jinja macros don't see outer `set` variables; pass everything in as arguments (see `call`).
- Tests set `settle_seconds: 0`.
- **"Clean", not "dry".** Mitsubishi calls running the fan after cooling "clean";
  "dry" is a separate head mode (`hvac_mode: dry`) that the blueprint never selects.
  Use "clean" in text and identifiers (`off_after_clean`, `coil_clean_minutes`).
  Upstream's `off_after_dry` is the same behavior, so expect that name when diffing.
- `source_url` and the README's import badge point at the blueprint on GitHub
  (`mikepell007/mxz_coordinator_blueprint`, branch `main`). Re-import pulls from
  there, so what's on `main` is what users get; rename or move the file and both
  need updating (the badge's `blueprint_url` is URL-encoded).

## Testing limits

`tests/test_blueprint.py` runs the real automation and template engines, but with mock
heads that report instantly. It doesn't cover cloud timing or real Mitsubishi heads.
Say so when reporting a change as done.
