"""Publish/Subscribe ueber Home Assistants EIGENE MQTT-Integration
(homeassistant.components.mqtt). Einziger unterstuetzter MQTT-Weg -- der
fruehere "eigener Broker"-Pfad (mqtt_client.py) wurde entfernt.

Bewusst mit lokalem Import (nicht auf Modulebene): homeassistant.components.mqtt
ist nur sinnvoll ladbar, wenn die MQTT-Integration tatsaechlich installiert
ist.

async_publish() wirft eine Exception, wenn HAs MQTT-Integration nicht
eingerichtet ist -- wird von EpaperRuntimeData.publish_now() (siehe
__init__.py) bereits generisch abgefangen und als Fehlermeldung im
Status-Sensor angezeigt.

async_subscribe() wird von den Batterie-Sensor-Entities (sensor.py)
genutzt, um die vom Geraet retained veroeffentlichten battery_percent/
battery_voltage-Topics live mitzulesen.
"""
from __future__ import annotations

from typing import Callable

from homeassistant.core import HomeAssistant


async def async_publish(hass: HomeAssistant, topic: str, payload: str, retain: bool) -> None:
    from homeassistant.components import mqtt as ha_mqtt  # lokal, siehe Docstring

    await ha_mqtt.async_publish(hass, topic, payload, qos=1, retain=retain)


async def async_subscribe(hass: HomeAssistant, topic: str, msg_callback: Callable) -> Callable[[], None]:
    """Abonniert `topic`, ruft `msg_callback(msg)` bei jeder Nachricht auf.
    Gibt eine Unsubscribe-Funktion zurueck (analog zu
    homeassistant.helpers.event.async_track_*)."""
    from homeassistant.components import mqtt as ha_mqtt  # lokal, siehe Docstring

    return await ha_mqtt.async_subscribe(hass, topic, msg_callback, qos=1)
