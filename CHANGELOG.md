# Changelog

Versions are `MAJOR.MINOR.PATCH`, judged by what happens to someone who re-imports
the blueprint:

- **Major:** a saved automation needs re-saving or behaves differently, such as a
  renamed or removed input, or a changed select value. The entry says what to do.
- **Minor:** a new feature that changes nothing until it's turned on.
- **Patch:** a bug fix or wording change.

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
