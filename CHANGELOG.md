# Changelog

Versions are `MAJOR.MINOR.PATCH`, judged by what happens to someone who re-imports
the blueprint:

- **Major:** a saved automation needs re-saving or behaves differently, such as a
  renamed or removed input, or a changed select value. The entry says what to do.
- **Minor:** a new feature that changes nothing until it's turned on.
- **Patch:** a bug fix or wording change.

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
