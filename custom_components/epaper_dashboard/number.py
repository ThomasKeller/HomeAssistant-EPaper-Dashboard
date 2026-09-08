"""'Schlafintervall'-Number-Entity je Geraet.

Publiziert retained auf {prefix}/config -- gleiche Semantik wie
MQTT_TOPIC_CONFIG in main_deepsleep.cpp/main_button.cpp: eine ROHE
Dezimalzahl in Sekunden, KEIN JSON (siehe handleConfigMessage() in
esp8266_epaper/src/main_deepsleep.cpp). Wie das state-Topic MUSS das
retained gesendet werden -- das Geraet abonniert config nur ganz kurz beim
Aufwachen.

WICHTIG: Seit der Tag/Nacht-Intervallsteuerung (siehe __init__.py) sendet
die Integration bei JEDEM Publish-Zyklus automatisch das gerade passende
Intervall an dieses Topic -- eine manuelle Aenderung hier ist also nur ein
voruebergehender Override bis zum naechsten automatischen Zyklus, kein
dauerhaftes Ueberschreiben. Die Anzeige wird per Dispatcher-Signal
synchron gehalten, damit sie nach einem automatischen Push nicht veraltet
wirkt.
"""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import ha_mqtt
from .const import (
    CONF_TOPIC_PREFIX,
    DEFAULT_SLEEP_INTERVAL_S,
    DOMAIN,
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
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass, f"{DOMAIN}_{self._entry.entry_id}_interval_pushed", self._handle_auto_push
            )
        )

    @callback
    def _handle_auto_push(self, interval_s: int) -> None:
        """Der automatische Tag/Nacht-Zeitplan hat ein Intervall gesendet
        -- Anzeige synchron halten, kein erneutes Publish (waere ein
        redundanter Kreis)."""
        self._attr_native_value = interval_s
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        opts = {**self._entry.data, **self._entry.options}
        prefix = opts.get(CONF_TOPIC_PREFIX, "").rstrip("/")
        await ha_mqtt.async_publish(self._hass, f"{prefix}/config", str(int(value)), True)
        self.async_write_ha_state()
