"""Publish-Pfad ueber Home Assistants EIGENE MQTT-Integration
(homeassistant.components.mqtt) -- Alternative zu mqtt_client.py fuer
Nutzer, die MQTT in HA bereits eingerichtet haben und keine zweiten
Zugangsdaten pflegen wollen.

Bewusst als eigenes, schmales Modul mit lokalem Import (nicht auf
Modulebene): homeassistant.components.mqtt ist nur sinnvoll ladbar, wenn
die MQTT-Integration tatsaechlich installiert ist. Ein Modulebene-Import
wuerde unnoetig Kopplung erzeugen, wenn ein Nutzer nur den
"custom"-Broker-Pfad (mqtt_client.py) nutzt und HAs eigenes MQTT gar nicht
eingerichtet hat.

Ist HAs MQTT-Integration nicht eingerichtet, wirft async_publish() eine
Exception -- wird von EpaperRuntimeData.publish_now() (siehe __init__.py)
bereits generisch abgefangen und als Fehlermeldung im Status-Sensor
angezeigt, kein Extra-Handling hier noetig.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant


async def async_publish(hass: HomeAssistant, topic: str, payload: str, retain: bool) -> None:
    from homeassistant.components import mqtt as ha_mqtt  # lokal, siehe Docstring

    await ha_mqtt.async_publish(hass, topic, payload, qos=1, retain=retain)
