"""MQTT-Publish, wahlweise ueber Home Assistants eigene MQTT-Integration
oder einen eigenstaendigen Broker (CONF_MQTT_SOURCE, per Geraet waehlbar).

- "custom": eigenstaendiger paho-mqtt-Client, Broker-Adresse/Zugangsdaten
  aus der Config-Entry, analog zu MqttPublisher.cs in der C#-App und
  epaper_mqtt.py. Kurzlebige Verbindung pro Publish (verbinden -> senden ->
  trennen) -- fuer periodische retained Publishes einfacher und robuster
  als eine dauerhaft gehaltene Verbindung mit Reconnect-Logik. Funktioniert
  unabhaengig davon, ob Home Assistant selbst MQTT eingerichtet hat.
- "ha": nutzt die von Home Assistant bereits verwaltete MQTT-Verbindung
  (siehe ha_mqtt.py) -- praktisch, wenn dort schon Zugangsdaten hinterlegt
  sind und man die nicht doppelt pflegen will.

async_publish_for_entry() ist der gemeinsame Einstiegspunkt fuer beide
Pfade, genutzt von __init__.py (periodischer Publish) und number.py
(Schlafintervall-Config-Topic).
"""
from __future__ import annotations

import logging
from functools import partial

import paho.mqtt.publish as mqtt_publish

from homeassistant.core import HomeAssistant

from . import ha_mqtt
from .const import (
    CONF_MQTT_HOST,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_SOURCE,
    CONF_MQTT_USERNAME,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_SOURCE,
    MQTT_SOURCE_HA,
)

_LOGGER = logging.getLogger(__name__)


async def async_publish_for_entry(
    hass: HomeAssistant, opts: dict, topic: str, payload: str, retain: bool
) -> None:
    """Publiziert gemaess CONF_MQTT_SOURCE der Config-Entry -- "ha" (Home
    Assistants eigene MQTT-Integration) oder "custom" (eigener Broker)."""
    source = opts.get(CONF_MQTT_SOURCE, DEFAULT_MQTT_SOURCE)

    if source == MQTT_SOURCE_HA:
        await ha_mqtt.async_publish(hass, topic, payload, retain)
        return

    await async_publish(
        hass,
        host=opts[CONF_MQTT_HOST],
        port=int(opts.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT)),
        topic=topic,
        payload=payload,
        username=opts.get(CONF_MQTT_USERNAME) or None,
        password=opts.get(CONF_MQTT_PASSWORD) or None,
        retain=retain,
    )


def _publish_sync(
    host: str,
    port: int,
    topic: str,
    payload: str,
    *,
    username: str | None,
    password: str | None,
    retain: bool,
    qos: int = 1,
    timeout: int = 10,
) -> None:
    auth = {"username": username, "password": password or ""} if username else None
    mqtt_publish.single(
        topic,
        payload=payload,
        qos=qos,
        retain=retain,
        hostname=host,
        port=port,
        auth=auth,
        keepalive=timeout,
    )


async def async_publish(
    hass: HomeAssistant,
    *,
    host: str,
    port: int,
    topic: str,
    payload: str,
    username: str | None = None,
    password: str | None = None,
    retain: bool = False,
) -> None:
    """paho-mqtt ist blockierend/synchron -- ueber den Executor ausfuehren,
    damit der Home-Assistant-Event-Loop nicht blockiert."""
    _LOGGER.debug("MQTT-Publish an %s:%s topic=%s retain=%s", host, port, topic, retain)
    await hass.async_add_executor_job(
        partial(
            _publish_sync,
            host,
            port,
            topic,
            payload,
            username=username,
            password=password,
            retain=retain,
        )
    )
