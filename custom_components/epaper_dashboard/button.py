"""'Jetzt senden'-Button je e-Paper-Geraet -- loest einen sofortigen Render +
Publish aus, ohne auf das naechste Intervall zu warten."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([EpaperPublishNowButton(hass, entry)])


class EpaperPublishNowButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Jetzt senden"
    _attr_icon = "mdi:refresh"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_publish_now"
        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        runtime = self._hass.data[DOMAIN][self._entry.entry_id]
        await runtime.publish_now()
