"""Scenario tests for blueprints/automation/mxz_coordinator.yaml.

Runs the blueprint in a real Home Assistant test instance: real helpers, the
real automation and template engines, and mock heads that apply each climate
command to their own state, the way a cloud head eventually reports it.
"""

from __future__ import annotations

import shutil
from datetime import timedelta
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

BLUEPRINT = Path(__file__).parent.parent / "blueprints" / "automation" / "mxz_coordinator.yaml"
ROOMS = ["living_room", "bedroom", "office"]
HEADS = [f"climate.{r}" for r in ROOMS]
SENSORS = [f"sensor.{r}_temperature" for r in ROOMS]
TARGETS = [f"input_number.{r}_target" for r in ROOMS]
ENABLES = [f"input_boolean.{r}_enable" for r in ROOMS]
HEAT_TOS = [f"input_number.{r}_heat_to" for r in ROOMS]
COOL_TOS = [f"input_number.{r}_cool_to" for r in ROOMS]


def slot_inputs(rooms: int) -> dict:
    """Fill room slots 1..rooms with ROOMS in order."""
    out = {}
    for n in range(rooms):
        out |= {f"room_{n + 1}_head": HEADS[n], f"room_{n + 1}_sensor": SENSORS[n],
                f"room_{n + 1}_target": TARGETS[n], f"room_{n + 1}_enable": ENABLES[n]}
    return out


def dual(i: int) -> dict:
    """Inputs that turn room slot i+1 into a dual-setpoint room (68 to 74)."""
    return {f"room_{i + 1}_target": "", f"room_{i + 1}_heat_to": HEAT_TOS[i],
            f"room_{i + 1}_cool_to": COOL_TOS[i]}


HEAD_ATTRS = {
    "hvac_modes": ["off", "heat", "cool", "dry", "heat_cool", "fan_only"],
    "fan_modes": ["auto", "1", "2", "3", "4", "5"],
    "fan_mode": "auto",
    "min_temp": 50,
    "max_temp": 90,
    "temperature": 70,
}


class Rig:
    def __init__(self, hass: HomeAssistant, freezer) -> None:
        self.hass = hass
        self.freezer = freezer
        self.calls: list[tuple[str, str, dict]] = []

    async def setup(self, rooms: int = 2, **overrides) -> None:
        hass = self.hass
        dest = Path(hass.config.path("blueprints/automation/mxz"))
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(BLUEPRINT, dest / "mxz_coordinator.yaml")

        assert await async_setup_component(hass, "input_boolean", {"input_boolean": {
            "mxz_enable": {"initial": True},
            **{f"{r}_enable": {"initial": True} for r in ROOMS},
        }})
        assert await async_setup_component(hass, "input_number", {"input_number": {
            **{f"{r}_target": {"min": 50, "max": 90, "initial": 70} for r in ROOMS},
            **{f"{r}_heat_to": {"min": 50, "max": 90, "initial": 68} for r in ROOMS},
            **{f"{r}_cool_to": {"min": 50, "max": 90, "initial": 74} for r in ROOMS},
        }})
        assert await async_setup_component(hass, "input_select", {"input_select": {
            "mxz_mode": {"options": ["cool", "heat"], "initial": "cool"},
        }})
        for head in HEADS:
            hass.states.async_set(head, "off", HEAD_ATTRS)
        for sensor in SENSORS:
            hass.states.async_set(sensor, "70", {"device_class": "temperature"})

        for service in ("set_hvac_mode", "set_temperature", "set_fan_mode"):
            hass.services.async_register("climate", service, self._handle)

        # The mode helper was just created, so let the mode-switch wait run out.
        self.tick(601)
        inputs = {
            **slot_inputs(rooms),
            "coordinator_enable": "input_boolean.mxz_enable",
            "mode_helper": "input_select.mxz_mode",
            "settle_seconds": 0,
            **overrides,
        }
        assert await async_setup_component(hass, "automation", {"automation": {
            "id": "mxz", "alias": "MXZ",
            "use_blueprint": {"path": "mxz/mxz_coordinator.yaml", "input": inputs},
        }})
        await hass.async_block_till_done()
        # A trigger that can't attach leaves the automation unavailable, not failed.
        assert hass.states.get("automation.mxz").state == "on"
        self.calls.clear()

    async def _handle(self, call: ServiceCall) -> None:
        for entity_id in call.data["entity_id"]:
            self.calls.append((entity_id, call.service, {
                k: v for k, v in call.data.items() if k != "entity_id"}))
            st = self.hass.states.get(entity_id)
            attrs = dict(st.attributes)
            state = st.state
            if "hvac_mode" in call.data:
                state = call.data["hvac_mode"]
            if "temperature" in call.data:
                attrs["temperature"] = call.data["temperature"]
            if "fan_mode" in call.data:
                attrs["fan_mode"] = call.data["fan_mode"]
            self.hass.states.async_set(entity_id, state, attrs)

    def tick(self, seconds: float) -> None:
        self.freezer.tick(timedelta(seconds=seconds))

    async def set(self, entity_id: str, state, attrs: dict | None = None) -> None:
        old = self.hass.states.get(entity_id)
        merged = {**(dict(old.attributes) if old else {}), **(attrs or {})}
        self.hass.states.async_set(entity_id, str(state), merged)
        await self.hass.async_block_till_done()

    async def run(self, after: float = 30) -> list[tuple[str, str, dict]]:
        """Advance the clock, run the automation once, return the calls it made."""
        self.tick(after)
        self.calls.clear()
        await self.hass.services.async_call(
            "automation", "trigger", {"entity_id": "automation.mxz"}, blocking=True)
        await self.hass.async_block_till_done()
        return list(self.calls)

    def head(self, i: int):
        return self.hass.states.get(HEADS[i])

    def mode(self) -> str:
        return self.hass.states.get("input_select.mxz_mode").state


@pytest.fixture
def expected_lingering_timers() -> bool:
    """The blueprint's every-2-minutes trigger leaves a timer scheduled."""
    return True


@pytest.fixture
async def rig(hass: HomeAssistant, freezer) -> Rig:
    r = Rig(hass, freezer)
    await r.setup()
    return r


async def test_room_near_target_does_nothing(rig: Rig) -> None:
    await rig.set(SENSORS[0], 70.5)
    await rig.set(SENSORS[1], 69.5)
    assert await rig.run() == []
    assert rig.head(0).state == rig.head(1).state == "off"


async def test_scenario(rig: Rig) -> None:
    # A room 4° below target asks for heat; the mode flips and the head runs
    # with the drive offset and the fan at the top of its ladder.
    await rig.set(SENSORS[1], 66)
    await rig.run()
    assert rig.mode() == "heat"
    bed = rig.head(1)
    assert bed.state == "heat"
    assert bed.attributes["temperature"] == 72
    assert bed.attributes["fan_mode"] == "5"
    assert rig.head(0).state == "off"

    # Standoff: the priority room wants cool, but the mode-switch wait holds heat.
    await rig.set(SENSORS[0], 74)
    await rig.run()
    assert rig.mode() == "heat"

    # After the wait the first room wins; the other room's head steps aside.
    await rig.run(after=600)
    assert rig.mode() == "cool"
    assert rig.head(0).state == "cool"
    assert rig.head(0).attributes["temperature"] == 68
    assert rig.head(1).state == "off"  # it was heating, so no coil dry

    # Inside its drift but still above target: it keeps running, fan eased down.
    await rig.set(SENSORS[0], 70.4)
    await rig.run()
    assert rig.head(0).state == "cool"
    assert rig.head(0).attributes["fan_mode"] == "1"

    # At target: the coil dries on fan_only. The waiting room keeps waiting
    # until the switch wait passes.
    await rig.set(SENSORS[0], 70)
    await rig.run()
    assert rig.head(0).state == "fan_only"
    assert rig.mode() == "cool"

    # Ten minutes later: dry done, head off; the bedroom is served.
    await rig.run(after=601)
    assert rig.head(0).state == "off"
    assert rig.mode() == "heat"
    assert rig.head(1).state == "heat"

    # Someone sets the head to heat_cool by remote: it's put back.
    await rig.set(HEADS[1], "heat_cool")
    await rig.run()
    assert rig.head(1).state == "heat"

    # Steady state sends nothing.
    assert await rig.run() == []

    # A sensor that drops out stops the room's run.
    await rig.set(SENSORS[1], "unavailable")
    await rig.run()
    assert rig.head(1).state == "off"


async def test_disabled_room_and_coordinator(rig: Rig) -> None:
    await rig.set(SENSORS[1], 66)
    await rig.run()
    assert rig.head(1).state == "heat"

    await rig.set(ENABLES[1], "off")
    await rig.run()
    assert rig.head(1).state == "off"

    # Coordinator off: re-enabling the room changes nothing.
    await rig.set("input_boolean.mxz_enable", "off")
    await rig.set(ENABLES[1], "on")
    assert await rig.run() == []
    assert rig.head(1).state == "off"


async def test_heat_lockout(hass: HomeAssistant, freezer) -> None:
    rig = Rig(hass, freezer)
    await rig.setup(outdoor="sensor.outdoor")
    await rig.set("sensor.outdoor", 75, {"device_class": "temperature"})
    await rig.set(SENSORS[1], 66)
    await rig.run()
    assert rig.head(1).state == "off"  # warm day: no heating at 66
    await rig.set(SENSORS[1], 57)
    await rig.run()
    assert rig.head(1).state == "heat"  # below the safety floor: heat anyway


async def capture_notes(hass: HomeAssistant) -> list[dict]:
    notes: list[dict] = []

    async def capture(call: ServiceCall) -> None:
        notes.append(dict(call.data))

    hass.services.async_register("persistent_notification", "create", capture)
    return notes


async def test_third_room_and_priority(hass: HomeAssistant, freezer) -> None:
    rig = Rig(hass, freezer)
    await rig.setup(rooms=3)
    # Rooms 2 and 3 want heat, room 3 most of all; then room 1 wants cool and,
    # as slot 1, wins the standoff once the switch wait passes.
    await rig.set(SENSORS[1], 66)
    await rig.set(SENSORS[2], 65)
    await rig.run()
    assert rig.mode() == "heat"
    assert rig.head(1).state == rig.head(2).state == "heat"
    await rig.set(SENSORS[0], 74)
    await rig.run(after=601)
    assert rig.mode() == "cool"
    assert [rig.head(i).state for i in range(3)] == ["cool", "off", "off"]


@pytest.mark.parametrize("blank", ["", None])
async def test_cleared_optional_room_is_ignored(hass: HomeAssistant, freezer, blank) -> None:
    rig = Rig(hass, freezer)
    cleared = {f"room_3_{k}": blank for k in ("head", "sensor", "target", "enable")}
    await rig.setup(**cleared)
    await rig.set(SENSORS[1], 66)
    await rig.run()
    assert rig.head(1).state == "heat"
    assert rig.head(2).state == "off"  # not in any slot


async def test_partly_filled_room_notifies(hass: HomeAssistant, freezer) -> None:
    notes = await capture_notes(hass)
    rig = Rig(hass, freezer)
    await rig.setup(room_3_head=HEADS[2])
    await rig.set(SENSORS[1], 66)
    assert await rig.run() == []
    assert notes[-1]["notification_id"] == "mxz_coordinator_blueprint"
    assert "Room 3: each room needs a head, sensor" in notes[-1]["message"]


async def test_shared_sensor_notifies(hass: HomeAssistant, freezer) -> None:
    notes = await capture_notes(hass)
    rig = Rig(hass, freezer)
    await rig.setup(room_2_sensor=SENSORS[0])
    assert await rig.run() == []
    assert f"Used by more than one room: {SENSORS[0]}" in notes[-1]["message"]


async def test_sensor_change_alone_triggers_a_run(hass: HomeAssistant, freezer) -> None:
    rig = Rig(hass, freezer)
    await rig.setup(rooms=3)
    await rig.set(SENSORS[2], 65)  # room 3's sensor; no explicit run
    assert rig.head(2).state == "heat"


async def test_dual_setpoint_room(hass: HomeAssistant, freezer) -> None:
    rig = Rig(hass, freezer)
    await rig.setup(**dual(1))
    # Anywhere from Heat to (68) to Cool to (74), and inside the demand band
    # past either, the room asks for nothing.
    for temp in (66, 70, 76):
        await rig.set(SENSORS[1], temp)
        assert await rig.run() == []

    # Past Heat to by more than the threshold: heat, driven from Heat to, the
    # fan boosted by the distance below Heat to.
    await rig.set(SENSORS[1], 64)
    await rig.run()
    assert rig.mode() == "heat"
    bed = rig.head(1)
    assert (bed.state, bed.attributes["temperature"], bed.attributes["fan_mode"]) == ("heat", 70, "5")

    # It runs to Heat to, not to the middle of the range.
    await rig.set(SENSORS[1], 67.5)
    await rig.run()
    assert rig.head(1).state == "heat"
    await rig.set(SENSORS[1], 68)
    await rig.run()
    assert rig.head(1).state == "off"

    # Past Cool to by more than the threshold: cool once the switch wait
    # passes, driven from Cool to, and run down to Cool to.
    await rig.set(SENSORS[1], 78)
    await rig.run(after=601)
    assert rig.mode() == "cool"
    bed = rig.head(1)
    assert (bed.state, bed.attributes["temperature"], bed.attributes["fan_mode"]) == ("cool", 72, "5")
    await rig.set(SENSORS[1], 74.5)
    await rig.run()
    assert rig.head(1).state == "cool"
    await rig.set(SENSORS[1], 74)
    await rig.run()
    assert rig.head(1).state == "fan_only"


async def test_dual_and_single_rooms_share_the_mode(hass: HomeAssistant, freezer) -> None:
    rig = Rig(hass, freezer)
    await rig.setup(**dual(1))
    # The single-target room asks for cool; the dual room, at 72, is content.
    await rig.set(SENSORS[0], 74)
    await rig.set(SENSORS[1], 72)
    await rig.run()
    assert rig.mode() == "cool"
    assert (rig.head(0).state, rig.head(1).state) == ("cool", "off")


async def test_dual_gap_too_narrow_asks_for_nothing(hass: HomeAssistant, freezer) -> None:
    rig = Rig(hass, freezer)
    await rig.setup(**dual(1))
    await rig.set(HEAT_TOS[1], 70)
    await rig.set(COOL_TOS[1], 71)
    await rig.set(SENSORS[1], 60)
    await rig.run()
    assert rig.head(1).state == "off"
    # Widening it to the least gap (2) lets the room run again.
    await rig.set(COOL_TOS[1], 72)
    await rig.run()
    assert rig.head(1).state == "heat"


@pytest.mark.parametrize("extra", [
    {"room_2_heat_to": HEAT_TOS[1]},                          # target and half a pair
    {"room_2_target": "", "room_2_heat_to": HEAT_TOS[1]},     # half a pair
    {"room_2_heat_to": HEAT_TOS[1], "room_2_cool_to": COOL_TOS[1]},  # both kinds
])
async def test_mixed_targets_notify(hass: HomeAssistant, freezer, extra) -> None:
    notes = await capture_notes(hass)
    rig = Rig(hass, freezer)
    await rig.setup(**extra)
    await rig.set(SENSORS[1], 60)
    assert await rig.run() == []
    assert "Room 2: each room needs a head, sensor" in notes[-1]["message"]


async def test_target_shared_with_heat_to_notifies(hass: HomeAssistant, freezer) -> None:
    notes = await capture_notes(hass)
    rig = Rig(hass, freezer)
    await rig.setup(**(dual(1) | {"room_2_heat_to": TARGETS[0]}))
    assert await rig.run() == []
    assert f"Used by more than one room: {TARGETS[0]}" in notes[-1]["message"]


OPEN = "binary_sensor.bedroom_openings"


async def test_open_window_stops_the_room(hass: HomeAssistant, freezer) -> None:
    rig = Rig(hass, freezer)
    await rig.set(OPEN, "off")
    await rig.setup(room_2_open=OPEN, open_delay_seconds=60)
    await rig.set(SENSORS[1], 66)
    await rig.run()
    assert rig.head(1).state == "heat"

    # Opened: nothing until the open delay passes, then straight off (no coil dry).
    await rig.set(OPEN, "on")
    await rig.run(after=30)
    assert rig.head(1).state == "heat"
    await rig.run(after=31)
    assert rig.head(1).state == "off"

    # Turned back on by remote while it's open: turned off again.
    await rig.set(HEADS[1], "heat")
    await rig.run()
    assert rig.head(1).state == "off"

    # Closed: the head stays off until the close delay (120 s default) passes.
    await rig.set(OPEN, "off")
    await rig.run(after=1)
    assert rig.head(1).state == "off"
    await rig.run(after=120)
    assert rig.head(1).state == "heat"


async def test_close_delay_zero_resumes_at_once(hass: HomeAssistant, freezer) -> None:
    rig = Rig(hass, freezer)
    await rig.set(OPEN, "on")
    await rig.setup(room_2_open=OPEN, open_delay_seconds=0, close_delay_seconds=0)
    await rig.set(SENSORS[1], 66)
    await rig.run()
    assert rig.head(1).state == "off"
    await rig.set(OPEN, "off")
    await rig.run(after=1)
    assert rig.head(1).state == "heat"


async def test_groceries(hass: HomeAssistant, freezer) -> None:
    """A door opened and closed over and over."""
    rig = Rig(hass, freezer)
    await rig.set(OPEN, "off")
    await rig.setup(room_2_open=OPEN, open_delay_seconds=60, close_delay_seconds=120)
    await rig.set(SENSORS[1], 66)
    await rig.run()
    assert rig.head(1).state == "heat"

    # Short trips, each under the open delay: the running head keeps running.
    for _ in range(3):
        await rig.set(OPEN, "on")
        await rig.run(after=20)
        await rig.set(OPEN, "off")
        await rig.run(after=20)
        assert rig.head(1).state == "heat"

    # A long one stops it; then more short trips don't restart it.
    await rig.set(OPEN, "on")
    await rig.run(after=61)
    assert rig.head(1).state == "off"
    for _ in range(3):
        await rig.set(OPEN, "off")
        await rig.run(after=40)
        assert rig.head(1).state == "off"
        await rig.set(OPEN, "on")
        await rig.run(after=20)
        assert rig.head(1).state == "off"

    # Shut for good: it restarts once the close delay has passed.
    await rig.set(OPEN, "off")
    await rig.run(after=60)
    assert rig.head(1).state == "off"
    await rig.run(after=61)
    assert rig.head(1).state == "heat"


async def test_held_room_doesnt_flip_the_mode(hass: HomeAssistant, freezer) -> None:
    rig = Rig(hass, freezer)
    await rig.set(OPEN, "off")
    await rig.setup(room_2_open=OPEN, close_delay_seconds=120)
    await rig.set(OPEN, "on")
    await rig.set(OPEN, "off")  # just closed; the head is off
    await rig.set(SENSORS[1], 60)
    await rig.run(after=1)
    assert rig.mode() == "cool"
    assert rig.head(1).state == "off"


async def test_open_room_makes_no_demand(hass: HomeAssistant, freezer) -> None:
    rig = Rig(hass, freezer)
    await rig.set(OPEN, "on")
    await rig.setup(room_2_open=OPEN, open_delay_seconds=0)
    await rig.set(SENSORS[1], 60)
    await rig.run()
    assert rig.mode() == "cool"  # its heat call doesn't flip the shared mode
    assert rig.head(1).state == "off"


async def test_cooling_room_opened_skips_coil_dry(hass: HomeAssistant, freezer) -> None:
    rig = Rig(hass, freezer)
    await rig.set(OPEN, "off")
    await rig.setup(room_1_open=OPEN, open_delay_seconds=0)
    await rig.set(SENSORS[0], 74)
    await rig.run()
    assert rig.head(0).state == "cool"
    await rig.set(OPEN, "on")
    await rig.run()
    assert rig.head(0).state == "off"


async def test_one_openings_group_for_two_rooms(hass: HomeAssistant, freezer) -> None:
    notes = await capture_notes(hass)
    rig = Rig(hass, freezer)
    await rig.set(OPEN, "on")
    await rig.setup(room_1_open=OPEN, room_2_open=OPEN, open_delay_seconds=0)
    await rig.set(SENSORS[0], 76)
    await rig.set(SENSORS[1], 76)
    await rig.run()
    assert notes == []  # sharing an openings sensor is allowed
    assert rig.head(0).state == rig.head(1).state == "off"


async def test_open_sensor_alone_is_a_partly_filled_room(hass: HomeAssistant, freezer) -> None:
    notes = await capture_notes(hass)
    rig = Rig(hass, freezer)
    await rig.setup(room_3_open=OPEN)
    assert await rig.run() == []
    assert "Room 3: each room needs a head, sensor" in notes[-1]["message"]
