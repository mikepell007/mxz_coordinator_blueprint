"""Tests for blueprints/template/mxz_room_climate.yaml and the sample that uses it.

Runs the real template engine with helpers and a mock head. It doesn't render the
Mushroom card.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import unquote

import pytest
import yaml
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

ROOT = Path(__file__).parent.parent
BLUEPRINT = ROOT / "blueprints" / "template" / "mxz_room_climate.yaml"
SAMPLE = ROOT / "ui" / "configuration_card.yaml"

OFFICE = "climate.virtual_office_climate"
OFFICE_HEAD = "climate.office_home_office"
OFFICE_ENABLE = "input_boolean.mxz_home_office_enable"
OFFICE_TARGET = "input_number.mxz_home_office_target"
DEN = "climate.den_thermostat"
DEN_HEAD = "climate.den"
DEN_ENABLE = "input_boolean.den_enable"
DEN_HEAT_TO = "input_number.den_heat_to"
DEN_COOL_TO = "input_number.den_cool_to"
DEN_PING = "binary_sensor.den_head_ping"
LOFT = "climate.loft_thermostat"
LOFT_HEAT_TO = "input_number.loft_heat_to"
LOFT_COOL_TO = "input_number.loft_cool_to"


@pytest.fixture
async def climate_calls(hass: HomeAssistant) -> list[Event]:
    """Set up the sample's office room and a dual-setpoint den; return climate service calls."""
    dest = Path(hass.config.path("blueprints/template/mikepell007"))
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(BLUEPRINT, dest / "mxz_room_climate.yaml")

    number = {"min": 50, "max": 90}
    assert await async_setup_component(hass, "input_boolean", {"input_boolean": {
        "mxz_home_office_enable": {"initial": True},
        "den_enable": {"initial": False},
    }})
    assert await async_setup_component(hass, "input_number", {"input_number": {
        "mxz_home_office_target": {**number, "initial": 70},
        "den_heat_to": {**number, "initial": 68},
        "den_cool_to": {**number, "initial": 74},
        "loft_heat_to": {**number, "initial": 68},
        "loft_cool_to": {**number, "initial": 74},
    }})
    hass.states.async_set(OFFICE_HEAD, "cool")
    hass.states.async_set(DEN_HEAD, "off")
    hass.states.async_set("sensor.office_motion_air_temperature_2", "72")
    hass.states.async_set("sensor.den_temperature", "71")
    hass.states.async_set(DEN_PING, "on")

    assert await async_setup_component(hass, "climate", {})
    calls: list[Event] = []
    hass.bus.async_listen(
        EVENT_CALL_SERVICE, lambda e: calls.append(e) if e.data["domain"] == "climate" else None
    )

    den = {
        "use_blueprint": {"path": "mikepell007/mxz_room_climate.yaml", "input": {
            "head": DEN_HEAD, "sensor": "sensor.den_temperature", "enable": DEN_ENABLE,
            "heat_to": DEN_HEAT_TO, "cool_to": DEN_COOL_TO, "online": DEN_PING,
        }},
        "name": "Den Thermostat",
        "unique_id": "den_thermostat",
    }
    loft = {
        "use_blueprint": {"path": "mikepell007/mxz_room_climate.yaml", "input": {
            "head": DEN_HEAD, "sensor": "sensor.den_temperature", "enable": DEN_ENABLE,
            "heat_to": LOFT_HEAT_TO, "cool_to": LOFT_COOL_TO, "min_gap": 4,
        }},
        "name": "Loft Thermostat",
        "unique_id": "loft_thermostat",
    }
    sample = yaml.safe_load(SAMPLE.read_text())["template"]
    assert await async_setup_component(hass, "template", {"template": [*sample, den, loft]})
    await hass.async_block_till_done()
    return calls


async def call(hass: HomeAssistant, service: str, **data: object) -> None:
    await hass.services.async_call("climate", service, data, blocking=True)
    await hass.async_block_till_done()


async def test_reports_a_single_target_room(hass: HomeAssistant, climate_calls) -> None:
    state = hass.states.get(OFFICE)
    assert state.state == "auto"
    assert state.attributes["hvac_modes"] == ["off", "auto"]
    assert state.attributes["hvac_action"] == "cooling"
    assert state.attributes["current_temperature"] == 72
    assert state.attributes["temperature"] == 70
    assert state.attributes["target_temp_low"] is None
    assert state.attributes["target_temp_high"] is None


async def test_reports_a_dual_setpoint_room(hass: HomeAssistant, climate_calls) -> None:
    state = hass.states.get(DEN)
    assert state.state == "off"
    assert state.attributes["hvac_action"] == "off"
    assert state.attributes["temperature"] is None
    assert state.attributes["target_temp_low"] == 68
    assert state.attributes["target_temp_high"] == 74


@pytest.mark.parametrize(
    ("ping", "icon", "online"),
    [("on", "mdi:thermostat", True), ("off", "mdi:wifi-off", False),
     ("unavailable", "mdi:thermostat", None)],
)
async def test_icon_shows_the_head_offline(
    hass: HomeAssistant, climate_calls, ping, icon, online
) -> None:
    hass.states.async_set(DEN_PING, ping)
    await hass.async_block_till_done()
    state = hass.states.get(DEN)
    assert state.attributes["icon"] == icon
    assert state.attributes["head_online"] is online


async def test_no_online_sensor_keeps_the_usual_icon(hass: HomeAssistant, climate_calls) -> None:
    state = hass.states.get(OFFICE)
    assert state.attributes["icon"] == "mdi:thermostat"
    assert state.attributes["head_online"] is None


@pytest.mark.parametrize(
    ("head", "action"),
    [("heat", "heating"), ("cool", "cooling"), ("dry", "drying"),
     ("fan_only", "idle"), ("off", "idle"), ("unavailable", "idle")],
)
async def test_action_follows_the_head(hass: HomeAssistant, climate_calls, head, action) -> None:
    hass.states.async_set(OFFICE_HEAD, head)
    await hass.async_block_till_done()
    assert hass.states.get(OFFICE).state == "auto"
    assert hass.states.get(OFFICE).attributes["hvac_action"] == action


async def test_modes_change_only_the_enable(hass: HomeAssistant, climate_calls) -> None:
    await call(hass, "set_hvac_mode", entity_id=OFFICE, hvac_mode="off")
    assert hass.states.get(OFFICE_ENABLE).state == "off"
    assert hass.states.get(OFFICE).state == "off"
    await call(hass, "set_hvac_mode", entity_id=OFFICE, hvac_mode="auto")
    assert hass.states.get(OFFICE_ENABLE).state == "on"
    assert hass.states.get(OFFICE).state == "auto"
    assert len(climate_calls) == 2
    assert all(c.data["service_data"]["entity_id"] == OFFICE for c in climate_calls)


async def test_temperature_sets_the_rooms_helpers(hass: HomeAssistant, climate_calls) -> None:
    await call(hass, "set_temperature", entity_id=OFFICE, temperature=75)
    assert float(hass.states.get(OFFICE_TARGET).state) == 75
    assert hass.states.get(OFFICE).attributes["temperature"] == 75

    await call(hass, "set_temperature", entity_id=DEN, target_temp_low=66, target_temp_high=78)
    assert float(hass.states.get(DEN_HEAT_TO).state) == 66
    assert float(hass.states.get(DEN_COOL_TO).state) == 78


def pair(hass: HomeAssistant, heat_to: str = DEN_HEAT_TO, cool_to: str = DEN_COOL_TO) -> tuple:
    return float(hass.states.get(heat_to).state), float(hass.states.get(cool_to).state)


async def card_sets(hass: HomeAssistant, entity: str, side: str, value: float) -> None:
    """Change one side the way the Mushroom card does: it also sends the other's value."""
    attrs = hass.states.get(entity).attributes
    await call(hass, "set_temperature", entity_id=entity, **{
        "target_temp_low": attrs["target_temp_low"],
        "target_temp_high": attrs["target_temp_high"],
        side: value,
    })


@pytest.mark.parametrize(
    ("start", "side", "value", "expected"),
    [
        ((68, 74), "target_temp_low", 66, (66, 74)),    # room to spare: the other side stays
        ((68, 74), "target_temp_high", 78, (68, 78)),
        ((68, 74), "target_temp_low", 72, (72, 74)),    # exactly the gap: the other side stays
        ((68, 74), "target_temp_low", 73, (73, 75)),    # too close: Cool to is pushed up
        ((68, 74), "target_temp_low", 74, (74, 76)),    # level: still pushed
        ((68, 74), "target_temp_high", 69, (67, 69)),   # too close: Heat to is pushed down
        ((84, 86), "target_temp_low", 85, (84, 86)),    # no room above: held back by the top
        ((64, 66), "target_temp_high", 65, (64, 66)),   # no room below: held back by the bottom
    ],
)
async def test_card_keeps_the_gap(
    hass: HomeAssistant, climate_calls, start, side, value, expected
) -> None:
    await call(hass, "set_temperature", entity_id=DEN, target_temp_low=start[0], target_temp_high=start[1])
    assert pair(hass) == start
    await card_sets(hass, DEN, side, value)
    assert pair(hass) == expected
    state = hass.states.get(DEN)
    assert (state.attributes["target_temp_low"], state.attributes["target_temp_high"]) == expected


async def test_home_assistant_refuses_heat_to_above_cool_to(hass: HomeAssistant, climate_calls) -> None:
    with pytest.raises(ServiceValidationError):
        await card_sets(hass, DEN, "target_temp_low", 80)
    assert pair(hass) == (68, 74)


async def test_gap_is_configurable(hass: HomeAssistant, climate_calls) -> None:
    await card_sets(hass, LOFT, "target_temp_low", 72)
    assert pair(hass, LOFT_HEAT_TO, LOFT_COOL_TO) == (72, 76)


@pytest.mark.parametrize(
    ("start", "end"),
    [((68, 74), (76, 80)), ((76, 80), (66, 70)), ((68, 74), (70, 72)), ((68, 74), (64, 80))],
)
async def test_pair_is_never_too_close_while_writing(
    hass: HomeAssistant, climate_calls, start, end
) -> None:
    """The automation reacts to each write, so it mustn't see a narrow pair between them."""
    await call(hass, "set_temperature", entity_id=DEN, target_temp_low=start[0], target_temp_high=start[1])
    seen: list[tuple] = []
    hass.bus.async_listen(
        "state_changed",
        lambda e: seen.append(pair(hass)) if e.data["entity_id"] in (DEN_HEAT_TO, DEN_COOL_TO) else None,
    )
    await call(hass, "set_temperature", entity_id=DEN, target_temp_low=end[0], target_temp_high=end[1])
    assert pair(hass) == end
    assert seen
    assert all(cool - heat >= 2 for heat, cool in seen)


def readme_import_urls() -> dict[str, str]:
    """The blueprint URL inside each of the README's import badges, by file name."""
    urls = re.findall(r"blueprint_url=([^)\s]+)", (ROOT / "README.md").read_text())
    return {url.rsplit("/", 1)[1]: url for url in map(unquote, urls)}


@pytest.mark.parametrize(
    ("domain", "local"),
    [("automation", ROOT / "blueprints" / "automation" / "mxz_coordinator.yaml"),
     ("template", BLUEPRINT)],
)
async def test_readme_import_badge(
    hass: HomeAssistant, hass_ws_client, aioclient_mock, domain: str, local: Path
) -> None:
    """Each badge's URL imports through HA's importer to the path the docs give."""
    url = readme_import_urls()[local.name]
    assert url == (
        "https://github.com/mikepell007/mxz_coordinator_blueprint/blob/main/"
        f"blueprints/{domain}/{local.name}"
    )
    assert f"source_url: {url}\n" in local.read_text()

    raw = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    aioclient_mock.get(raw, text=local.read_text())
    assert await async_setup_component(hass, "blueprint", {})
    assert await async_setup_component(hass, domain, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "blueprint/import", "url": url})
    result = (await client.receive_json())["result"]
    assert result["blueprint"]["metadata"]["domain"] == domain
    assert result["suggested_filename"] == f"mikepell007/{local.stem}"
    assert not result["validation_errors"]
