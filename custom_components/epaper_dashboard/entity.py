"""Gemeinsame DeviceInfo-Hilfsfunktion fuer alle Plattformen (button/number/
sensor) -- gruppiert sie unter einer Home-Assistant-Geraetekarte je
Config-Entry, damit jedes e-Paper-Geraet (42, kuenftig 43, ...) als eigenes
Geraet erscheint."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_DEVICE_NAME, DOMAIN


def device_info(entry: ConfigEntry) -> DeviceInfo:
    device_name = entry.data.get(CONF_DEVICE_NAME, entry.title)
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"e-Paper {device_name}",
        manufacturer="Waveshare (Custom-Firmware)",
        model="e-Paper Display",
    )
