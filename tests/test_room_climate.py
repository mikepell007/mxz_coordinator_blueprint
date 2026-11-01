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
    }})
    hass.states.async_set(OFFICE_HEAD, "cool")
    hass.states.async_set(DEN_HEAD, "off")
    hass.states.async_set("sensor.office_motion_air_temperature_2", "72")
    hass.states.async_set("sensor.den_temperature", "71")

    assert await async_setup_component(hass, "climate", {})
    calls: list[Event] = []
    hass.bus.async_listen(
        EVENT_CALL_SERVICE, lambda e: calls.append(e) if e.data["domain"] == "climate" else None
    )

    den = {
        "use_blueprint": {"path": "mikepell007/mxz_room_climate.yaml", "input": {
            "head": DEN_HEAD, "sensor": "sensor.den_temperature", "enable": DEN_ENABLE,
            "heat_to": DEN_HEAT_TO, "cool_to": DEN_COOL_TO,
        }},
        "name": "Den Thermostat",
        "unique_id": "den_thermostat",
    }
    sample = yaml.safe_load(SAMPLE.read_text())["template"]
    assert await async_setup_component(hass, "template", {"template": [*sample, den]})
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
