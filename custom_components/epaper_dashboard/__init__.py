"""e-Paper Dashboard Integration.

Rendert periodisch ein Layout-Template (gleiches JSON-Schema wie die C#-App
unter epaper_dashboard/EpaperDashboard) mit Live-Werten aus Home Assistant
und publiziert das Ergebnis retained per MQTT -- unabhaengig davon, ob die
C#-App gerade laeuft. Eine Config-Entry = ein e-Paper-Geraet; fuer mehrere
Geraete (42, 43, ...) einfach die Integration mehrfach hinzufuegen.
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_RETAIN,
    CONF_TEMPLATE_JSON,
    CONF_TOPIC_PREFIX,
    CONF_UPDATE_INTERVAL,
    DEFAULT_RETAIN,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .render import render

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["button", "number", "sensor"]


class EpaperRuntimeData:
    """Laufzeitdaten + periodischer Publish-Job je Config-Entry (Geraet)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.last_success: bool | None = None
        self.last_message: str = "Noch nicht ausgefuehrt"
        self.last_updated = None
        self._unsub_interval = None

    @property
    def _options(self) -> dict:
        # Optionen (spaeter via "Konfigurieren" geaendert) ueberschreiben die
        # urspruenglichen Einrichtungsdaten.
        return {**self.entry.data, **self.entry.options}

    async def publish_now(self, *_) -> None:
        opts = self._options

        try:
            template = json.loads(opts[CONF_TEMPLATE_JSON])
        except (json.JSONDecodeError, KeyError) as err:
            self.last_success = False
            self.last_message = f"Ungueltiges Template-JSON: {err}"
            _LOGGER.error(self.last_message)
            async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry.entry_id}_updated")
            return

        try:
            payload = await render(self.hass, template)
        except Exception as err:  # noqa: BLE001 - jeder Render-Fehler soll sichtbar werden, nicht die Integration abschiessen
            self.last_success = False
            self.last_message = f"Render-Fehler: {err}"
            _LOGGER.exception("Fehler beim Rendern des e-Paper-Templates (%s)", self.entry.title)
            async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry.entry_id}_updated")
            return

        topic = template.get("MqttTopic") or f"{opts[CONF_TOPIC_PREFIX].rstrip('/')}/state"
        retain = bool(opts.get(CONF_RETAIN, DEFAULT_RETAIN))

        try:
            await mqtt.async_publish(self.hass, topic, payload, qos=1, retain=retain)
        except Exception as err:  # noqa: BLE001
            self.last_success = False
            self.last_message = f"MQTT-Fehler: {err}"
            _LOGGER.exception("Fehler beim MQTT-Publish (%s)", self.entry.title)
            async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry.entry_id}_updated")
            return

        self.last_success = True
        self.last_updated = dt_util.utcnow()
        self.last_message = f"OK -> {topic} ({len(payload)} Bytes)"
        _LOGGER.debug("e-Paper-Payload gesendet (%s): %s", self.entry.title, self.last_message)
        async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry.entry_id}_updated")

    def start_interval(self) -> None:
        interval = max(10, int(self._options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)))
        self._unsub_interval = async_track_time_interval(
            self.hass, self.publish_now, timedelta(seconds=interval)
        )

    def stop_interval(self) -> None:
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    runtime = EpaperRuntimeData(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    runtime.start_interval()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Einmal gleich beim Start senden, nicht erst nach dem ersten Intervall
    # warten (nicht blockierend fuer den HA-Start).
    hass.async_create_task(runtime.publish_now())

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Nach Aenderungen ueber "Konfigurieren" (z.B. neues Template
    eingefuegt): Intervall neu starten + sofort einmal senden, damit die
    Aenderung nicht erst nach bis zu CONF_UPDATE_INTERVAL Sekunden wirkt."""
    runtime: EpaperRuntimeData = hass.data[DOMAIN][entry.entry_id]
    runtime.stop_interval()
    runtime.start_interval()
    hass.async_create_task(runtime.publish_now())


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime: EpaperRuntimeData = hass.data[DOMAIN].pop(entry.entry_id)
        runtime.stop_interval()
    return unload_ok
