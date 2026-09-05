"""Status-Sensor 'Letztes Update' je Geraet -- Zeitpunkt + Erfolg/Fehler-
Meldung des letzten Publish-Versuchs, analog zu RefreshStatus in der
C#-App (DashboardRefreshService.cs)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([EpaperStatusSensor(hass, entry)])


class EpaperStatusSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Letztes Update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_last_update"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass, f"{DOMAIN}_{self._entry.entry_id}_updated", self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self):
        runtime = self._hass.data[DOMAIN][self._entry.entry_id]
        return runtime.last_updated

    @property
    def extra_state_attributes(self) -> dict:
        runtime = self._hass.data[DOMAIN][self._entry.entry_id]
        return {
            "erfolgreich": runtime.last_success,
            "meldung": runtime.last_message,
        }
