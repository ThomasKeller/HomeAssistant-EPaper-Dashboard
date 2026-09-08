"""Konstanten fuer die e-Paper Dashboard Integration."""

DOMAIN = "epaper_dashboard"

CONF_DEVICE_NAME = "device_name"
CONF_TOPIC_PREFIX = "topic_prefix"
CONF_TEMPLATE_JSON = "template_json"
CONF_RETAIN = "retain"

# Sende-Intervall: tagsueber CONF_DAY_INTERVAL, nachts (zwischen
# CONF_NIGHT_START und CONF_DAY_START) CONF_NIGHT_INTERVAL. Steuert sowohl,
# wie oft das Plugin neu rendert + sendet, als auch (ueber das config-Topic,
# gleiche Semantik wie die "Schlafintervall"-Number-Entity in number.py) das
# Schlafintervall des Geraets selbst -- sonst wuerde das Geraet nachts
# weiterhin im Tages-Takt aufwachen, ohne echten Akku-Vorteil. Fester Takt
# (kein Bezug zum tatsaechlichen Aufwachzeitpunkt des Geraets), damit die
# retained State-Nachricht bei einem spontanen Sofort-Refresh (z.B. Taster)
# nie aelter als ein Intervall ist.
CONF_DAY_INTERVAL = "day_interval"
CONF_NIGHT_INTERVAL = "night_interval"
CONF_NIGHT_START = "night_start"
CONF_DAY_START = "day_start"

DEFAULT_DAY_INTERVAL = 300  # Sekunden, wie RefreshIntervalSeconds in der C#-App
DEFAULT_NIGHT_INTERVAL = 3600
DEFAULT_NIGHT_START = "22:00:00"
DEFAULT_DAY_START = "06:00:00"
DEFAULT_RETAIN = True

# Muss zu SLEEP_INTERVAL_MIN_S/MAX_S in esp8266_epaper/src/config.h passen.
SLEEP_INTERVAL_MIN_S = 60
SLEEP_INTERVAL_MAX_S = 28800  # 8 Stunden
DEFAULT_SLEEP_INTERVAL_S = 600

CONFIG_TOPIC_SUFFIX = "config"

SIGNAL_TEMPLATE_UPDATED = f"{DOMAIN}_template_updated"
