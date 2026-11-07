# Changelog

Versions are `MAJOR.MINOR.PATCH`, judged by what happens to someone who re-imports
the blueprint:

- **Major:** a saved automation needs re-saving or behaves differently, such as a
  renamed or removed input, or a changed select value. The entry says what to do.
- **Minor:** a new feature that changes nothing until it's turned on.
- **Patch:** a bug fix or wording change.

## 1.4.0 (2026-11-07)

Saved coordinator automations need nothing: re-importing the blueprint changes only
its version number.

- The room thermostat has a new optional **Head online sensor** input, such as a Ping
  sensor for the head's Wi-Fi adapter. While that sensor is off, the thermostat's
  icon, and so the card's, is a Wi-Fi-off symbol. A `head_online` attribute (true,
  false, or none) carries the same thing for other cards.
- The thermostat's icon is now set by the blueprint: `mdi:thermostat`, the same as
  before, unless the head is offline.

To pick this up, replace your copy of `mxz_room_climate.yaml`, add `online` to each
room's block if you want it, and reload **Template entities**. A card that sets its
own `icon` won't show the change.

## 1.3.0 (2026-11-03)

Saved automations need nothing: re-importing the blueprint adds an option that is
off until you turn it on.

- Each room has a new **invert doors and windows** option, for an occupancy sensor
  or group in place of doors and windows. With it on, the room stops while the
  sensor is off, once it has been off for **Door or window open delay**, and a
  stopped head starts again once the sensor has been on for **Door or window close
  delay**. Those delays are shared with the rooms that use doors and windows.
- An empty room's head cleans its coil first if it was cooling, unless **When a
  room is done or waiting** is Off. An open window still turns a head straight off.
- A sensor that is unavailable or unknown still stops nothing, inverted or not.

## 1.2.0 (2026-11-01)

Saved coordinator automations need nothing: re-importing the blueprint changes only
its version number.

- The room thermostat now keeps Heat to and Cool to apart. Changing one side moves the
  other if the two would come closer than the new **Least gap between heat to and cool
  to** input (2 by default), so a card can no longer leave a room asking for nothing.
  Set it at or above the same setting in the automation.
- The thermostat now writes the pair in a safe order, so the automation can't park a
  running head because it read the pair between two writes.

To pick this up, replace your copy of `mxz_room_climate.yaml` and reload **Template
entities**.

## 1.1.0 (2026-11-01)

Saved coordinator automations need nothing: re-importing the blueprint changes only
its version number.

- A new optional room thermostat blueprint,
  `blueprints/template/mxz_room_climate.yaml`, makes one thermostat entity per room
  for dashboard cards, without a custom integration. It works for single-target and
  dual-setpoint rooms, and each room is one short block of YAML.
- The Mushroom card's bottom bar now switches between the temperature control and an
  off/auto toggle for the room's enable. Off and auto no longer send anything to the
  head, which fixes the `HVAC mode auto is not valid` error.
- The thermostat's mode now stays Auto while the room is enabled, and a badge on the
  card shows heating, cooling, or drying.
- Removed the `dynamic-*` sample cards and `DYNAMIC_CONTROLS.md`, which relied on a
  Mushroom option that doesn't exist.

**Upgrading from the `climate_template` sample:** skip this if you never set up the
samples in `ui/`. The thermostat is now a different entity, so it needs moving by hand:

1. Add the new blueprint and your rooms' blocks, as in the README's UI components
   section. The new blueprint sits beside the coordinator and doesn't replace it.
2. Remove the old `platform: climate_template` entries, then restart.
3. Under **Settings → Devices & services → Entities**, delete each old thermostat,
   which now shows as unavailable. A card still pointing at one shows unavailable too.
4. Check each new thermostat's entity ID. It ends in `_2` if the old entity was
   holding the ID, and deleting the old one doesn't change that. Either rename it to
   the old ID or point its card at the new one.
5. In each card, add `hvac_modes` and remove `collapsible_controls` and `tap_action`,
   as in `ui/mushroom-climate-card.yaml`.
6. You can then remove the `climate_template` integration.

Heat and cool can no longer be picked on the thermostat, and it no longer has a fan
mode. The temperature range is fixed at 64–86 °F in the blueprint.

## 1.0.0 (2026-10-30)

First numbered version. It includes:

- One shared heat or cool mode for up to six rooms, ported from the core logic of
  [ha-mxz-coordinator](https://github.com/dkpnw/ha-mxz-coordinator).
- Dual setpoint rooms, using Heat to and Cool to helpers.
- A doors and windows sensor per room, with open and close delays.
- Allow Dry mode per room, off by default. It follows upstream's open pull request
  56, which isn't merged yet.
- An import badge in the README, with `source_url` pointing at GitHub.

**Upgrading from an unnumbered copy:** "dry" was renamed to "clean" for running the
fan after cooling, because Dry is a separate head mode. The saved names changed
(`off_after_dry` to `off_after_clean`, `coil_dry_minutes` to `coil_clean_minutes`).
An old automation keeps loading but skips the clean, so heads go straight to off
after cooling. Open the automation, pick **When a room is done or waiting** again,
set **Coil clean time** if you'd changed it, and save.
