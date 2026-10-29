# MXZ Coordinator blueprint for cloud heads

A Home Assistant automation blueprint that ports the core decisions of
[MXZ Coordinator](https://github.com/dkpnw/ha-mxz-coordinator), the Home
Assistant integration, for heads that come into Home Assistant through a cloud
integration (MELCloud, Kumo Cloud) instead of CN105/ESPHome. It talks only to
`climate.*` entities, so any integration that offers `heat`, `cool`, and `off`
(ideally `fan_only`) works. No add-ons or custom integrations are needed.

Don't run it alongside the MXZ Coordinator integration, or any other automation
that controls the same heads.

## What it keeps

| Integration feature | Here |
| --- | --- |
| One shared heat/cool mode, picked from every room | Yes: same threshold (3 °F) and run-to-target latch (1 °F drift) |
| Standoff settled by room order, 10-minute wait between switches | Yes |
| Room temperature sensors drive the decision | Yes, plus a setpoint drive offset (below) |
| Satisfied/waiting room steps aside (`off_after_dry`, `fan_only`, `off`) | Yes |
| Fan boost ladder | Yes, built from the head's own `fan_modes` |
| Puts a head back after a remote press | Yes, on the next run |
| Weather lockouts with safety floor/ceiling | Yes, from an outdoor sensor or weather entity |
| Up to 8 heads | Up to 6 rooms |
| Dual setpoint (Heat to / Cool to) | Yes, per room, from two `input_number` helpers |
| Eco/away, standby hold, safety priority, freeze floor, own-remote rooms, lost-vote TTL, per-room thermostats | No |

## The local-sensor difference

CN105 heads can be fed your room sensor (`remote_temperature_source`). Cloud APIs
can't, so each head still runs on its own thermistor. The blueprint works around
it: while a room runs, its head gets **target + 2 °F** when heating or
**target − 2 °F** when cooling (Setpoint drive offset), so the head doesn't stop
early on its own reading. The blueprint decides when the room is done from
**your** sensor and parks the head. If your head reads far from the room, raise
the offset; `0` sends the bare target.

## Install

1. Create the helpers in [mxz_helpers.yaml](mxz_helpers.yaml), in YAML or the
   Helpers UI: a target `input_number` and an enable `input_boolean` for each
   room, `input_boolean.mxz_enable`, and `input_select.mxz_mode` with exactly the
   options `heat` and `cool`.
2. Copy [blueprints/automation/mxz_coordinator.yaml](blueprints/automation/mxz_coordinator.yaml)
   to `<config>/blueprints/automation/mxz/` and reload automations, or import it
   from its GitHub URL under **Settings → Automations & scenes → Blueprints →
   Import blueprint**.
3. Create an automation from it. Each room has its own section: pick its
   **head, temperature sensor, target, and enable** there. Room 1 has the highest
   priority: when rooms want opposite modes, the lowest-numbered room asking
   wins. Rooms 1 and 2 are required; fill rooms 3 to 6 only if you have them.
   If a room is only partly filled in, or one entity is used by two rooms, the
   automation does nothing and posts a notification saying which.
4. Turn on each room's enable, then `input_boolean.mxz_enable`.

**Dual setpoint.** A room can have a range instead of one target: leave its
**Target** blank and pick a **Heat to** and a **Cool to** `input_number`. The
room asks for heat below Heat to and for cool above Cool to (each past the same
threshold and drift as a single target), runs to whichever edge it started from,
and asks for nothing in between. The drive offset and fan boost measure from
that edge. Cool to must sit at least **Least gap between heat to and cool to**
(2 °F) above Heat to; a narrower pair makes the room ask for nothing, and the
trace says why. A room with both a Target and a Heat to/Cool to, or only half a
pair, gets the setup notification.

Each run's trace shows every room's slot, head, sensor, target, and enable, under
**Traces → Changed variables → plan**.

**Check each head's fan modes.** Fan boost steps through a head's own
`fan_modes` (minus `auto`) in the order the head lists them, lowest first, up to
**Highest fan step to use**. If a head's top mode is a loud boost such as
`powerful`, lower that setting. Heads with different fan lists get different
speeds at the same step.

## How it remembers

A blueprint has no memory of its own, so it reads it from entities:

| It needs to know | It reads |
| --- | --- |
| The shared mode | `input_select.mxz_mode`. Pick a mode there yourself to switch to it. |
| When the mode last switched | That helper's last change |
| Whether a room is mid-run | Whether its head is in the shared mode |
| How long a coil has dried | How long its head has been in `fan_only` |
| The current fan step | The head's current fan mode |

After a Home Assistant restart those clocks restart too: the mode can't switch
for the first 10 minutes, and a drying coil gets a full dry time again.

## Cloud caveats

- **Lag.** Cloud integrations poll, so a head's reported state can trail a
  command by minutes. After sending commands the blueprint waits 90 s (Wait
  after sending commands) and skips runs during it. Raise it if your heads
  report back more slowly.
- **Mid-run detection lags too.** Until a head reports its new mode, the
  blueprint treats its room as not yet running. That only matters if the room
  is already back inside its drift by then.
- **Stock AUTO must stay out of it.** Don't leave heads on `heat_cool`/auto; the
  blueprint puts enabled rooms back to its own mode.

## Development

```bash
pip install -r requirements_test.txt
pytest                                # runs the blueprint in a real HA test instance
```

## Credits and license

The decision logic is ported from
[dkpnw/ha-mxz-coordinator](https://github.com/dkpnw/ha-mxz-coordinator)
(MIT). See [NOTICE](NOTICE) for what was ported and upstream's license. This
project is [MIT](LICENSE) and is not affiliated with or supported by upstream.
