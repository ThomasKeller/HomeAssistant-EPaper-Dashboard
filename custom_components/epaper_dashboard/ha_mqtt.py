"""Publish ueber Home Assistants EIGENE MQTT-Integration
(homeassistant.components.mqtt). Einziger unterstuetzter MQTT-Weg -- der
fruehere "eigener Broker"-Pfad (mqtt_client.py) wurde entfernt.

Bewusst mit lokalem Import (nicht auf Modulebene): homeassistant.components.mqtt
ist nur sinnvoll ladbar, wenn die MQTT-Integration tatsaechlich installiert
ist.

Wirft eine Exception, wenn HAs MQTT-Integration nicht eingerichtet ist --
wird von EpaperRuntimeData.publish_now() (siehe __init__.py) bereits
generisch abgefangen und als Fehlermeldung im Status-Sensor angezeigt.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant


async def async_publish(hass: HomeAssistant, topic: str, payload: str, retain: bool) -> None:
    from homeassistant.components import mqtt as ha_mqtt  # lokal, siehe Docstring

    await ha_mqtt.async_publish(hass, topic, payload, qos=1, retain=retain)
