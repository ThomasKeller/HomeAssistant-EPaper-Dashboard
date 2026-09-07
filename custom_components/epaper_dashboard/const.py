"""Konstanten fuer die e-Paper Dashboard Integration."""

DOMAIN = "epaper_dashboard"

CONF_DEVICE_NAME = "device_name"
CONF_TOPIC_PREFIX = "topic_prefix"
CONF_TEMPLATE_JSON = "template_json"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_RETAIN = "retain"
CONF_MQTT_SOURCE = "mqtt_source"
CONF_MQTT_HOST = "mqtt_host"
CONF_MQTT_PORT = "mqtt_port"
CONF_MQTT_USERNAME = "mqtt_username"
CONF_MQTT_PASSWORD = "mqtt_password"

# CONF_MQTT_SOURCE-Werte:
#   "ha"     = Home Assistants eigene MQTT-Integration verwenden
#              (homeassistant.components.mqtt) -- setzt voraus, dass die in
#              HA eingerichtet ist.
#   "custom" = eigener Broker, Zugangsdaten aus CONF_MQTT_HOST/.../PASSWORD
#              (eigenstaendiger paho-mqtt-Client, siehe mqtt_client.py) --
#              funktioniert unabhaengig davon, ob HA selbst MQTT konfiguriert hat.
MQTT_SOURCE_HA = "ha"
MQTT_SOURCE_CUSTOM = "custom"

DEFAULT_UPDATE_INTERVAL = 300  # Sekunden, wie RefreshIntervalSeconds in der C#-App
DEFAULT_RETAIN = True
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_SOURCE = MQTT_SOURCE_CUSTOM

# Muss zu SLEEP_INTERVAL_MIN_S/MAX_S in esp8266_epaper/src/config.h passen.
SLEEP_INTERVAL_MIN_S = 60
SLEEP_INTERVAL_MAX_S = 28800  # 8 Stunden
DEFAULT_SLEEP_INTERVAL_S = 600

CONFIG_TOPIC_SUFFIX = "config"

SIGNAL_TEMPLATE_UPDATED = f"{DOMAIN}_template_updated"
