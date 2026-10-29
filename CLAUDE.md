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
| `LICENSE`, `NOTICE` | MIT for this repo; upstream's MIT notice and what was ported, at which commit. |

## Commands

```bash
pip install -r requirements_test.txt   # into a venv; the system Python has no HA
pytest
```

Run `pytest` after every blueprint change. Last run on HA 2026.10.4 with Python 3.14.

## How the logic maps to upstream

The `plan` template ports these functions from upstream's
`custom_components/mxz_coordinator/logic.py`, as of commit `f30a9aa` (tag v3.12.1).
Keep the behavior in step. When upstream releases, diff `logic.py` and `const.py`
from that commit, port what matters, and update the commit in `NOTICE` and here.

- `call` macro ← `room_call` / `call_edges` (cool checked first; lockouts move an edge out to the floor/ceiling)
- engage block ← `engage_with_latch` (drift to start, band 0 to run to target, direction flip → satisfied)
- shared-mode block ← `shared_mode` (standoff → first calling room in slot order; `min_switch_seconds` dwell; resting mode)
- fan block ← `fan_for_delta` (step thresholds are `fan_step` × 1/2/3/4 up and × 0.5/1.5/2.5/3.5 down)
- `act` chain ← `head_action`

Input defaults match upstream's °F defaults (`const.py`): drift 1, threshold 3,
dwell 600 s, idle `off_after_dry` with 10 min coil dry, fan thresholds 1/2/3/4 up and
0.5/1.5/2.5/3.5 down, clamp 59–88.

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
- Not ported: eco/away, standby hold, dual setpoint, safety priority, freeze floor,
  own-remote rooms, per-room thermostat entities.

## Blueprint specifics

- **No memory of its own; state comes from entities.** Shared mode = the
  `input_select` helper, switch clock = its `last_changed`, run-to-target latch =
  the head being in heat/cool, coil dry timer = the head's time in `fan_only`, fan
  step = the head's current `fan_mode`. Don't add helpers for these without a reason;
  fewer helpers is the point.
- **Variables come back as Python literals, not JSON.** End `plan` with a bare
  dict (`{{ {...} }}`). `| tojson` makes `true`/`null`, which fails literal parsing,
  and `plan` silently becomes a string.
- **Rooms are six fixed slots** (`room_N_head/sensor/target/enable`; 1–2 required,
  3–6 default `""`). `slots` gathers them, `rooms_cfg` keeps slots with a head, and
  `config_ok` rejects partly filled slots (`incomplete`) and entities used by two
  rooms (`duplicates`); the plan loop skips rooms when it's false so the notification
  can run. Slot number is priority. Adding a slot means touching the inputs, the four
  triggers, and `slots`; nothing in `plan` changes.
- **Room triggers are `state_changed` event triggers, not state triggers.** A state
  trigger on an optional slot saved as `""` or `null` (filled, then cleared in the UI)
  leaves the whole automation `unavailable`; an event trigger filtering
  `event_data.entity_id` doesn't care. Verified on HA 2026.10.4. They also fire on
  attribute-only changes, which `mode: single` and the settle delay absorb.
- Each plan room carries `slot`, `sensor`, `target_entity`, and `enable_entity` so the
  trace shows the pairing. Keep them when changing the plan.
- `tests/test_blueprint.py` asserts `automation.mxz` is `on` after setup: a blueprint
  that fails to load or attach leaves it `unavailable` without failing setup.
- Jinja macros don't see outer `set` variables; pass everything in as arguments (see `call`).
- Tests set `settle_seconds: 0`.
- No `source_url` yet: add the real GitHub raw/blob URL once the repo is pushed, so
  the import and update buttons work.

## Testing limits

`tests/test_blueprint.py` runs the real automation and template engines, but with mock
heads that report instantly. It doesn't cover cloud timing or real Mitsubishi heads.
Say so when reporting a change as done.
