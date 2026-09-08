"""e-Paper Dashboard Integration.

Rendert ein Layout-Template (gleiches JSON-Schema wie die C#-App unter
epaper_dashboard/EpaperDashboard) mit Live-Werten aus Home Assistant und
publiziert das Ergebnis retained per MQTT -- unabhaengig davon, ob die
C#-App gerade laeuft. Eine Config-Entry = ein e-Paper-Geraet; fuer mehrere
Geraete (42, 43, ...) einfach die Integration mehrfach hinzufuegen.

Sende-Takt: tagsueber CONF_DAY_INTERVAL, nachts (zwischen CONF_NIGHT_START
und CONF_DAY_START) CONF_NIGHT_INTERVAL -- steuert sowohl, wie oft neu
gerendert wird, als auch (ueber das config-Topic) das Schlafintervall des
Geraets selbst. Statt eines starren Intervall-Timers wird der Status-Topic
des Geraets abonniert: der Sende-Zeitpunkt wird auf CONF_WAKE_LEAD Sekunden
vor dem aus dem letzten Aufwachzeitpunkt + aktuellem Intervall vorhergesagten
naechsten Aufwachen gelegt, damit eine moeglichst frische retained Nachricht
bereitliegt, wenn das Geraet tatsaechlich aufwacht.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from . import ha_mqtt
from .const import (
    CONF_DAY_INTERVAL,
    CONF_DAY_START,
    CONF_NIGHT_INTERVAL,
    CONF_NIGHT_START,
    CONF_RETAIN,
    CONF_TEMPLATE_JSON,
    CONF_TOPIC_PREFIX,
    CONF_WAKE_LEAD,
    DEFAULT_DAY_INTERVAL,
    DEFAULT_DAY_START,
    DEFAULT_NIGHT_INTERVAL,
    DEFAULT_NIGHT_START,
    DEFAULT_RETAIN,
    DEFAULT_WAKE_LEAD_S,
    DOMAIN,
)
from .render import render

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["button", "number", "sensor"]


def _parse_time(value: str, fallback: str) -> time:
    return dt_util.parse_time(value) or dt_util.parse_time(fallback)


def _is_night(now: time, night_start: time, day_start: time) -> bool:
    """True, wenn `now` im Fenster [night_start, day_start) liegt. Deckt
    den ueblichen Fall ab, dass das Fenster ueber Mitternacht hinweggeht
    (night_start > day_start, z.B. 22:00 - 06:00)."""
    if night_start == day_start:
        return False  # Nacht-Fenster deaktiviert (kein Unterschied)
    if night_start < day_start:
        return night_start <= now < day_start
    return now >= night_start or now < day_start


class EpaperRuntimeData:
    """Laufzeitdaten + Publish-Scheduling je Config-Entry (Geraet)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.last_success: bool | None = None
        self.last_message: str = "Noch nicht ausgefuehrt"
        self.last_updated = None
        self.last_device_status_at: datetime | None = None
        self._unsub_timer = None
        self._unsub_status = None

    @property
    def _options(self) -> dict:
        # Optionen (spaeter via "Konfigurieren" geaendert) ueberschreiben die
        # urspruenglichen Einrichtungsdaten.
        return {**self.entry.data, **self.entry.options}

    @property
    def _prefix(self) -> str:
        return self._options.get(CONF_TOPIC_PREFIX, "").rstrip("/")

    @property
    def _status_topic(self) -> str:
        return f"{self._prefix}/status"

    @property
    def _config_topic(self) -> str:
        return f"{self._prefix}/config"

    def _effective_interval_s(self) -> int:
        opts = self._options
        now = dt_util.now().time()
        night_start = _parse_time(opts.get(CONF_NIGHT_START, DEFAULT_NIGHT_START), DEFAULT_NIGHT_START)
        day_start = _parse_time(opts.get(CONF_DAY_START, DEFAULT_DAY_START), DEFAULT_DAY_START)
        if _is_night(now, night_start, day_start):
            return max(10, int(opts.get(CONF_NIGHT_INTERVAL, DEFAULT_NIGHT_INTERVAL)))
        return max(10, int(opts.get(CONF_DAY_INTERVAL, DEFAULT_DAY_INTERVAL)))

    def _wake_lead_s(self) -> int:
        return max(1, int(self._options.get(CONF_WAKE_LEAD, DEFAULT_WAKE_LEAD_S)))

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

        topic = template.get("MqttTopic") or f"{self._prefix}/state"
        retain = bool(opts.get(CONF_RETAIN, DEFAULT_RETAIN))

        try:
            await ha_mqtt.async_publish(self.hass, topic, payload, retain)
        except Exception as err:  # noqa: BLE001
            self.last_success = False
            self.last_message = f"MQTT-Fehler: {err}"
            _LOGGER.exception("Fehler beim MQTT-Publish (%s)", self.entry.title)
            async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry.entry_id}_updated")
            return

        # Schlafintervall des Geraets an Tag/Nacht anpassen (gleiche
        # Semantik wie die "Schlafintervall"-Number-Entity in number.py) --
        # haelt Geraet und Plugin synchron, sonst wuerde das Geraet nachts
        # weiterhin im Tages-Takt aufwachen, ohne echten Akku-Vorteil. Ein
        # Fehler hier soll den bereits erfolgreichen State-Publish nicht
        # als Fehlschlag melden.
        effective_interval = self._effective_interval_s()
        try:
            await ha_mqtt.async_publish(self.hass, self._config_topic, str(effective_interval), True)
            async_dispatcher_send(
                self.hass, f"{DOMAIN}_{self.entry.entry_id}_interval_pushed", effective_interval
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Fehler beim Senden des Schlafintervalls (%s)", self.entry.title)

        self.last_success = True
        self.last_updated = dt_util.utcnow()
        self.last_message = f"OK -> {topic} ({len(payload)} Bytes)"
        _LOGGER.debug("e-Paper-Payload gesendet (%s): %s", self.entry.title, self.last_message)
        async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry.entry_id}_updated")

    @callback
    def _on_status_message(self, msg) -> None:
        """Neue Status-Nachricht vom Geraet (Wake-Signal) -> Zeitpunkt
        merken und Zeitplan mit der jetzt genaueren Vorhersage neu
        berechnen."""
        self.last_device_status_at = dt_util.utcnow()
        self._schedule_next()

    def _predict_delay_s(self) -> float:
        """Sekunden bis zum naechsten Sende-Zeitpunkt: CONF_WAKE_LEAD vor dem
        vorhergesagten naechsten Aufwachen (letzter Status-Zeitpunkt +
        aktuelles Intervall), falls bereits ein Status gesehen wurde --
        sonst der normale Intervall-Takt ab jetzt (z.B. direkt nach einem
        HA-Neustart, bevor das Geraet zum ersten Mal aufgewacht ist)."""
        interval = self._effective_interval_s()
        if self.last_device_status_at is None:
            return float(interval)

        predicted_wake = self.last_device_status_at + timedelta(seconds=interval)
        target = predicted_wake - timedelta(seconds=self._wake_lead_s())
        delay = (target - dt_util.utcnow()).total_seconds()
        return max(0.0, delay)

    def _schedule_next(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
        delay = self._predict_delay_s()
        self._unsub_timer = async_call_later(self.hass, delay, self._fire_scheduled)

    async def _fire_scheduled(self, _now) -> None:
        self._unsub_timer = None
        await self.publish_now()
        self._schedule_next()

    async def async_start(self) -> None:
        self._unsub_status = await ha_mqtt.async_subscribe(
            self.hass, self._status_topic, self._on_status_message
        )
        self._schedule_next()

    def async_stop(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None
        if self._unsub_status is not None:
            self._unsub_status()
            self._unsub_status = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    runtime = EpaperRuntimeData(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await runtime.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Einmal gleich beim Start senden, nicht erst auf den ersten Status vom
    # Geraet oder das erste Intervall warten (nicht blockierend fuer den
    # HA-Start).
    hass.async_create_task(runtime.publish_now())

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Nach Aenderungen ueber "Konfigurieren" (z.B. neues Template
    eingefuegt, Intervalle/Zeiten geaendert): Zeitplan neu starten + sofort
    einmal senden, damit die Aenderung nicht erst spaeter wirkt."""
    runtime: EpaperRuntimeData = hass.data[DOMAIN][entry.entry_id]
    runtime.async_stop()
    await runtime.async_start()
    hass.async_create_task(runtime.publish_now())


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime: EpaperRuntimeData = hass.data[DOMAIN].pop(entry.entry_id)
        runtime.async_stop()
    return unload_ok
