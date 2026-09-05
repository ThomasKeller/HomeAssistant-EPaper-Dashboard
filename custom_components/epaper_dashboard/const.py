"""Konstanten fuer die e-Paper Dashboard Integration."""

DOMAIN = "epaper_dashboard"

CONF_DEVICE_NAME = "device_name"
CONF_TOPIC_PREFIX = "topic_prefix"
CONF_TEMPLATE_JSON = "template_json"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_RETAIN = "retain"

DEFAULT_UPDATE_INTERVAL = 300  # Sekunden, wie RefreshIntervalSeconds in der C#-App
DEFAULT_RETAIN = True

# Muss zu SLEEP_INTERVAL_MIN_S/MAX_S in esp8266_epaper/src/config.h passen.
SLEEP_INTERVAL_MIN_S = 60
SLEEP_INTERVAL_MAX_S = 28800  # 8 Stunden
DEFAULT_SLEEP_INTERVAL_S = 600

CONFIG_TOPIC_SUFFIX = "config"

SIGNAL_TEMPLATE_UPDATED = f"{DOMAIN}_template_updated"
