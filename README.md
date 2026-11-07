# MXZ Coordinator blueprint for cloud heads

A Home Assistant automation blueprint that ports the core decisions of
[MXZ Coordinator](https://github.com/dkpnw/ha-mxz-coordinator), the Home
Assistant integration, for heads that come into Home Assistant through a cloud
integration (MELCloud, Kumo Cloud) instead of CN105/ESPHome. It talks only to
`climate.*` entities, so any integration that offers `heat`, `cool`, and `off`
(ideally `fan_only`) works. No add-ons or custom integrations are needed, except
for the optional [sample cards](#ui-components-optional).

Don't run it alongside the MXZ Coordinator integration, or any other automation
that controls the same heads.

Questions and feedback are welcome in the
[Blueprints Exchange thread](https://community.home-assistant.io/t/mitsubishi-mxz-multi-zone-mini-split-coordinator-blueprint/1032018)
on the Home Assistant forum.

## What it keeps

| Integration feature | Here |
| --- | --- |
| One shared heat/cool mode, picked from every room | Yes: same threshold (3 °F) and run-to-target latch (1 °F drift) |
| Standoff settled by room order, 10-minute wait between switches | Yes |
| Room temperature sensors drive the decision | Yes, plus a setpoint drive offset (below) |
| Satisfied/waiting room steps aside (fan to clean the coil then off, `fan_only`, or `off`) | Yes |
| Fan boost ladder | Yes, built from the head's own `fan_modes` |
| Puts a head back after a remote press | Yes, on the next run |
| Weather lockouts with safety floor/ceiling | Yes, from an outdoor sensor or weather entity |
| Up to 8 heads | Up to 6 rooms |
| Dual setpoint (Heat to / Cool to) | Yes, per room, from two `input_number` helpers |
| Doors and windows, or occupancy | New here: an open or empty room's head turns off and the room asks for nothing |
| Eco/away, standby hold, safety priority, freeze floor, own-remote rooms, lost-vote TTL, per-room thermostats | No |

## The local-sensor difference

CN105 heads can be fed your room sensor (`remote_temperature_source`). Cloud APIs
can't, so each head still runs on its own thermistor. The blueprint works around
it: while a room runs, its head gets **target + 2 °F** when heating or
**target − 2 °F** when cooling (Setpoint drive offset), so the head doesn't stop
early on its own reading. The blueprint decides when the room is done from
**your** sensor and parks the head. If your head reads far from the room, raise
the offset; `0` sends the bare target.

## Dependencies

- Home Assistant 2024.10.0 or later
- Climate entities for each room's indoor unit
- Input helpers as defined in [mxz_helpers.yaml](mxz_helpers.yaml)

## Install

1. Create the helpers in [mxz_helpers.yaml](mxz_helpers.yaml), in YAML or the
   Helpers UI: a target `input_number` and an enable `input_boolean` for each
   room, `input_boolean.mxz_enable`, and `input_select.mxz_mode` with exactly the
   options `heat` and `cool`.
2. Import the blueprint:

   [![Open your Home Assistant instance and show the blueprint import dialog with this blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fmikepell007%2Fmxz_coordinator_blueprint%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmxz_coordinator.yaml)

   Or under **Settings → Automations & scenes → Blueprints → Import
   blueprint**, paste `https://github.com/mikepell007/mxz_coordinator_blueprint/blob/main/blueprints/automation/mxz_coordinator.yaml`.

   Or copy [the file](blueprints/automation/mxz_coordinator.yaml) to
   `<config>/blueprints/automation/mxz/` and reload automations. Imported
   copies can pick up later versions with the blueprint's **Re-import
   blueprint** menu item.
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

**Doors and windows.** Give a room a **doors and windows** `binary_sensor`
that is on while any of them is open. For several contacts, make a group:
**Settings → Devices & services → Helpers → Create helper → Group → Binary
sensor group**, add the room's door and window sensors, and leave **All
entities** off so the group is on when any one is open (example in
[mxz_helpers.yaml](mxz_helpers.yaml)). Once it has been on for **Door or window
open delay** (60 s), the room's head is turned straight off, with no coil-clean
fan, and the room asks for nothing, so it can't flip the shared mode. If someone
turns the head on while it's open, the next run turns it off again. One group
can serve several rooms, such as an open plan living room and kitchen.

A stopped head doesn't start while a door or window is open, even before the
open delay, or until they have all been shut for **Door or window close delay**
(120 s). So a door opened over and over, carrying groceries in, stops the head
once and restarts it once. A head that is still running isn't stopped by
openings shorter than the open delay. Set the close delay to 0 to restart as
soon as everything is shut.

Both delays are checked on the 2-minute timer, so the head goes off, or back
on, up to 2 minutes after a delay ends.

**Occupancy instead.** Turn on a room's **invert doors and windows** and its
sensor works the other way round: pick an occupancy sensor, or a group of them,
and the room stops while it's off. The same delays apply, so the open delay is how
long the room must be empty before its head stops, and the close delay is how long
it must be occupied before a stopped head starts. They're shared with any rooms
using doors and windows. An empty room's head cleans its coil first if it was
cooling, unless **When a room is done or waiting** is Off. A sensor that is
unavailable stops nothing.

**Dry mode.** The heads' own Dry (dehumidify) mode is something you pick; the
blueprint never selects it. With a room's **allow Dry mode** off (the default), a
head put in Dry is taken out of it on the next run. Turn it on for a room and,
while that room is enabled, a head you put in Dry stays there:

- The blueprint sends it no mode, setpoint, or fan commands, and the room's target
  waits until the head leaves Dry.
- Dry runs the outdoor unit the cooling way, so it shares with rooms that are
  cooling. If no room is calling or mid-run, the head turns the shared mode to cool
  once the wait between switches allows. Any room's call beats it, and **No cooling
  at or below** stops it asking.
- If another room needs heat, the Dry head gets the same treatment as a cooling
  head that stops (coil clean, then off, with the default setting), and you get a
  notification. Dry doesn't turn back on by itself. Heat that is only the resting
  mode, with no room wanting it, stops nothing.
- Open doors and windows stop it as they stop any head, past the open delay.

Two limits from having no memory: a head you take out of Dry directly to `off`
stays off with no coil clean (leave it in `fan_only` to get one), and a mode switch
caused by a Dry head starts the wait between switches like any other, so a room
calling for heat right after it waits too.

Each run's trace shows every room's slot, head, sensor, target, and enable, under
**Traces → Changed variables → plan**.

**Check each head's fan modes.** Fan boost steps through a head's own
`fan_modes` (minus `auto`) in the order the head lists them, lowest first, up to
**Highest fan step to use**. If a head's top mode is a loud boost such as
`powerful`, lower that setting. Heads with different fan lists get different
speeds at the same step.

**Coil clean is not dry mode.** After cooling, the blueprint can run a head's
fan for a while to clean the coil (**Coil clean time**), using `fan_only`. That's
separate from the head's own `dry` mode, above.

**Upgrading from a version that called this "dry":** the setting's saved names
changed, and an old automation keeps loading but skips the clean, so heads go
straight to off after cooling. Open the automation, pick **When a room is done or
waiting** again, set **Coil clean time** if you'd changed it, and save.

## How it remembers

A blueprint has no memory of its own, so it reads it from entities:

| It needs to know | It reads |
| --- | --- |
| The shared mode | `input_select.mxz_mode`. Pick a mode there yourself to switch to it. |
| When the mode last switched | That helper's last change |
| Whether a room is mid-run | Whether its head is in the shared mode |
| How long a coil has been cleaning | How long its head has been in `fan_only` |
| The current fan step | The head's current fan mode |

After a Home Assistant restart those clocks restart too: the mode can't switch
for the first 10 minutes, and a coil being cleaned gets a full clean time again.

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

## UI components (optional)

These give a room a thermostat-style card. The coordinator doesn't need them.

- [blueprints/template/mxz_room_climate.yaml](blueprints/template/mxz_room_climate.yaml)
  makes one thermostat entity per room, from the same helpers the room's slot uses.
  It works for single-target and dual-setpoint rooms.
- [ui/configuration_card.yaml](ui/configuration_card.yaml) is the config for one
  room.
- [ui/mushroom-climate-card.yaml](ui/mushroom-climate-card.yaml) is the card. It
  needs [Mushroom](https://github.com/piitaya/lovelace-mushroom), a custom card.

1. Import the thermostat blueprint:

   [![Open your Home Assistant instance and show the blueprint import dialog with this blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fmikepell007%2Fmxz_coordinator_blueprint%2Fblob%2Fmain%2Fblueprints%2Ftemplate%2Fmxz_room_climate.yaml)

   If Home Assistant says `Unsupported domain`, nothing in your config uses
   `template:` yet. Copy [the file](blueprints/template/mxz_room_climate.yaml) to
   `<config>/blueprints/template/mikepell007/mxz_room_climate.yaml` instead. This
   is a separate blueprint from the coordinator, which stays where it is.
2. Add one block per room to your config, in a package or under your existing
   `template:` key, following the sample. The sample's `path` matches the location
   above. A dual-setpoint room has `heat_to` and
   `cool_to` instead of `target`. Each room needs its own `name` and `unique_id`;
   the `name` sets the entity ID, such as `climate.virtual_office_climate`.
3. Restart if this config is the first to use `template:`. Otherwise reload
   **Template entities** under **Developer Tools → YAML**, which you also do after
   editing the blueprint or a room's block.
4. For each room, add a card to a dashboard, choose **Manual**, paste in the
   Mushroom sample, and set its `entity`.

**Upgrading from `climate_template`:** versions of the sample before 1.1.0 used that
custom integration. See the [changelog](CHANGELOG.md) for the steps. In short, remove
the old entries and entities, then check each new entity's ID: it may end in `_2`.

**Using the card.** The small button beside the bottom bar switches the bar between
the temperature control and off/auto:

- Off and auto only turn the room's enable `input_boolean` off and on. Auto doesn't
  put the head in its own auto mode; the coordinator still picks heat or cool. After
  off, the head does what **A disabled room's head** says.
- The temperature control sets the room's target, or its Heat to and Cool to. In a
  dual-setpoint room, moving one side pushes the other to keep the least gap, up to
  the limits of the range. Home Assistant refuses a Heat to above Cool to outright, so
  move them in steps. The block's optional `min_gap` input sets the gap (2 by default);
  keep it at or above **Least gap between heat to and cool to** in the automation.
- The card's mode stays Auto while the room is enabled. A badge on its icon shows
  heating, cooling, or drying, and idle for anything else, including a coil clean.
- The range is fixed at 64–86 °F in the blueprint.
- **Head online.** To see when a head drops off the network, add the **Ping (ICMP)**
  integration under **Settings → Devices & services → Add integration** with the
  head's Wi-Fi adapter address. Give the adapter a fixed address (a DHCP reservation
  in your router) so the sensor keeps pinging the right device. Then add the sensor's
  `binary_sensor` to the room's block as `online`. While it's off, the card's icon is
  a Wi-Fi-off symbol; leave `icon` out of the card, or it replaces this. The
  thermostat's `head_online` attribute says the same for other cards. The coordinator
  doesn't use it.

The thermostat blueprint was tested on Home Assistant 2026.10.4. Earlier versions
may not have template climate entities.

## Versions

The blueprint's name ends in its version, so the blueprint list shows which one you
have. To update, re-import the blueprint, then check [CHANGELOG.md](CHANGELOG.md):
a major version change says what to re-save.

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
