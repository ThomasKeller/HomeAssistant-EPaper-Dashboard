"""Konstanten fuer die e-Paper Dashboard Integration."""

DOMAIN = "epaper_dashboard"

CONF_DEVICE_NAME = "device_name"
CONF_TOPIC_PREFIX = "topic_prefix"
CONF_TEMPLATE_JSON = "template_json"
CONF_RETAIN = "retain"

# Sende-/Wake-Intervall: tagsueber CONF_DAY_INTERVAL, nachts (zwischen
# CONF_NIGHT_START und CONF_DAY_START) CONF_NIGHT_INTERVAL. Steuert sowohl,
# wie oft das Plugin neu rendert + sendet, als auch (ueber das config-Topic,
# gleiche Semantik wie die "Schlafintervall"-Number-Entity in number.py) das
# Schlafintervall des Geraets selbst -- sonst wuerde das Geraet nachts
# weiterhin im Tages-Takt aufwachen, ohne echten Akku-Vorteil. Beide
# muessen gleich sein, damit die Aufwach-Vorhersage (WAKE_LEAD_S) stimmt.
CONF_DAY_INTERVAL = "day_interval"
CONF_NIGHT_INTERVAL = "night_interval"
CONF_NIGHT_START = "night_start"
CONF_DAY_START = "day_start"

# Vorlauf vor dem vorhergesagten naechsten Aufwachen des Geraets (letzter
# Status-Zeitpunkt + aktuelles Intervall), siehe _predict_delay_s() in
# __init__.py. Am realen Geraet gemessene Wach-Zeit (WLAN-Fast-Reconnect +
# MQTT-Connect + Subscribe) lag durchgehend bei 2-10s -- 30s Default laesst
# Marge fuer gelegentlich langsamere Zyklen (WLAN-Cache ungueltig) und
# RTC-Timer-Drift bei laengeren Intervallen.
CONF_WAKE_LEAD = "wake_lead_s"

DEFAULT_DAY_INTERVAL = 300  # Sekunden, wie RefreshIntervalSeconds in der C#-App
DEFAULT_NIGHT_INTERVAL = 3600
DEFAULT_NIGHT_START = "22:00:00"
DEFAULT_DAY_START = "06:00:00"
DEFAULT_WAKE_LEAD_S = 30
DEFAULT_RETAIN = True

# Muss zu SLEEP_INTERVAL_MIN_S/MAX_S in esp8266_epaper/src/config.h passen.
SLEEP_INTERVAL_MIN_S = 60
SLEEP_INTERVAL_MAX_S = 28800  # 8 Stunden
DEFAULT_SLEEP_INTERVAL_S = 600

CONFIG_TOPIC_SUFFIX = "config"
STATUS_TOPIC_SUFFIX = "status"

SIGNAL_TEMPLATE_UPDATED = f"{DOMAIN}_template_updated"
