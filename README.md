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
| Satisfied/waiting room steps aside (fan to clean the coil then off, `fan_only`, or `off`) | Yes |
| Fan boost ladder | Yes, built from the head's own `fan_modes` |
| Puts a head back after a remote press | Yes, on the next run |
| Weather lockouts with safety floor/ceiling | Yes, from an outdoor sensor or weather entity |
| Up to 8 heads | Up to 6 rooms |
| Dual setpoint (Heat to / Cool to) | Yes, per room, from two `input_number` helpers |
| Doors and windows | New here: an open room's head turns off and the room asks for nothing |
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
2. Import the blueprint:

   [![Open your Home Assistant instance and show the blueprint import dialog with this blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fmikepell007%2Fmxz_coordinator_blueprint%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fmxz_coordinator.yaml)

   Or under **Settings → Automations & scenes → Blueprints → Import
   blueprint**, paste `https://github.com/mikepell007/mxz_coordinator_blueprint/blob/main/blueprints/automation/mxz_coordinator.yaml`.

## UI Components

This repository includes sample UI components for easier interaction:

1. **Configuration Card** (`ui/configuration-card.yaml`): A climate template that 
   integrates with the coordinator, handling both single and dual setpoint modes
2. **Mushroom Climate Card** (`ui/mushroom-climate-card.yaml`): A Mushroom 
   custom card for visualizing and controlling the virtual climate entity

### Installation of UI Components

1. Place `configuration-card.yaml` in your `config/packages` directory or create it via the UI
2. Place `mushroom-climate-card.yaml` in your `config/ui` directory or create it via the UI
3. The mushroom card requires the [Mushroom](https://github.com/piitaya/lovelace-mushroom) 
   custom integration to be installed in Home Assistant

## Dynamic Temperature Controls Enhancement

The MXZ Coordinator supports both single setpoint and dual setpoint rooms. For a more dynamic UI experience, you can implement dynamic temperature controls that adapt based on the room's configuration:

### Implementation Approach

To create dynamic temperature controls:
1. Create separate climate entities for each room type (single vs dual setpoint)
2. Use conditional templates in your UI to detect which controls should be shown
3. Implement logic that checks if `input_number.room_heat_to` and `input_number.room_cool_to` are configured

### Sample Dynamic Card Implementation

```yaml
# Example of a dynamic card that can show either single or dual setpoint controls
type: custom:mushroom-climate-card
entity: climate.virtual_office_climate
show_temperature_control: true
collapsible_controls: true
tap_action:
  action: call-service
  service: input_boolean.toggle
  target:
    entity_id: input_boolean.mxz_home_office_enable
```

### UI Detection Logic

The blueprint's configuration determines whether a room uses single or dual setpoint:
- **Single Setpoint**: Room has `input_number.room_target` configured (and heat_to and cool_to are empty)
- **Dual Setpoint**: Room has both `input_number.room_heat_to` and `input_number.room_cool_to` configured

This detection is handled at the blueprint level, but UI cards can be designed to adapt their display accordingly.

## Dependencies

- Home Assistant 2024.10.0 or later
- Climate entities for each room's indoor unit
- Input helpers as defined in [mxz_helpers.yaml](mxz_helpers.yaml)
- Optional: Mushroom custom card integration for enhanced UI experience

## Enhancement: Dynamic Temperature Controls

This repository supports both single setpoint and dual setpoint rooms. The implementation of dynamic temperature controls in UI cards is left to the user's preference, but we provide documentation on how to implement this feature.

For more information about implementing dynamic temperature controls that adapt based on room configuration, see [DYNAMIC_CONTROLS.md](DYNAMIC_CONTROLS.md).
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

## Versions

The blueprint's name ends in its version, so the blueprint list shows which one you
have. To update, re-import the blueprint, then check [CHANGELOG.md](CHANGELOG.md):
a major version change says what to re-save.

## Development

```bash
pip install -r requirements_test.txt
pytest                                # runs the blueprint in a real HA test instance
```

## UI Components

This repository includes sample UI components for easier interaction:

1. **Configuration Card** (`ui/configuration-card.yaml`): A climate template that 
   integrates with the coordinator, handling both single and dual setpoint modes
2. **Mushroom Climate Card** (`ui/mushroom-climate-card.yaml`): A Mushroom 
   custom card for visualizing and controlling the virtual climate entity
3. **Dynamic Temperature Card** (`ui/dynamic-temperature-card.yaml`): An example 
   of how to implement dynamic temperature controls that adapt based on room configuration

### Installation of UI Components

1. Place `configuration-card.yaml` in your `config/packages` directory or create it via the UI
2. Place `mushroom-climate-card.yaml` in your `config/ui` directory or create it via the UI
3. Place `dynamic-temperature-card.yaml` in your `config/ui` directory for dynamic controls
4. The mushroom card requires the [Mushroom](https://github.com/piitaya/lovelace-mushroom) 
   custom integration to be installed in Home Assistant

## Dynamic Temperature Controls Enhancement

This repository supports both single setpoint and dual setpoint rooms. The implementation of dynamic temperature controls in UI cards is left to the user's preference, but we provide documentation on how to implement this feature.

For more information about implementing dynamic temperature controls that adapt based on room configuration, see [DYNAMIC_CONTROLS.md](DYNAMIC_CONTROLS.md).

## Credits and license

The decision logic is ported from
[dkpnw/ha-mxz-coordinator](https://github.com/dkpnw/ha-mxz-coordinator)
(MIT). See [NOTICE](NOTICE) for what was ported and upstream's license. This
project is [MIT](LICENSE) and is not affiliated with or supported by upstream.
