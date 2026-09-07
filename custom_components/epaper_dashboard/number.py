"""'Schlafintervall'-Number-Entity je Geraet.

Publiziert retained auf {prefix}/config -- gleiche Semantik wie
MQTT_TOPIC_CONFIG in main_deepsleep.cpp/main_button.cpp: eine ROHE
Dezimalzahl in Sekunden, KEIN JSON (siehe handleConfigMessage() in
esp8266_epaper/src/main_deepsleep.cpp). Wie das state-Topic MUSS das
retained gesendet werden -- das Geraet abonniert config nur ganz kurz beim
Aufwachen.
"""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import mqtt_client
from .const import (
    CONF_TOPIC_PREFIX,
    DEFAULT_SLEEP_INTERVAL_S,
    SLEEP_INTERVAL_MAX_S,
    SLEEP_INTERVAL_MIN_S,
)
from .entity import device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([EpaperSleepIntervalNumber(hass, entry)])


class EpaperSleepIntervalNumber(NumberEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = "Schlafintervall"
    _attr_icon = "mdi:sleep"
    _attr_native_min_value = SLEEP_INTERVAL_MIN_S
    _attr_native_max_value = SLEEP_INTERVAL_MAX_S
    _attr_native_step = 10
    _attr_native_unit_of_measurement = "s"
    _attr_mode = NumberMode.BOX

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_sleep_interval"
        self._attr_device_info = device_info(entry)
        self._attr_native_value = DEFAULT_SLEEP_INTERVAL_S

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            try:
                self._attr_native_value = float(last_state.state)
            except (TypeError, ValueError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        opts = {**self._entry.data, **self._entry.options}
        prefix = opts.get(CONF_TOPIC_PREFIX, "").rstrip("/")
        await mqtt_client.async_publish_for_entry(
            self._hass, opts, f"{prefix}/config", str(int(value)), True
        )
        self.async_write_ha_state()
