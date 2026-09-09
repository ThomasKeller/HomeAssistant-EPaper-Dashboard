"""Konstanten fuer die e-Paper Dashboard Integration."""

DOMAIN = "epaper_dashboard"

CONF_DEVICE_NAME = "device_name"
CONF_TOPIC_PREFIX = "topic_prefix"
CONF_TEMPLATE_JSON = "template_json"
CONF_RETAIN = "retain"

# Zwei getrennte Anliegen, zwei getrennte Takte:
#
# 1. Geraete-Schlafintervall (Akkulaufzeit): tagsueber CONF_DAY_INTERVAL,
#    nachts (zwischen CONF_NIGHT_START und CONF_DAY_START)
#    CONF_NIGHT_INTERVAL. Wird bei jedem State-Refresh-Zyklus (s.u.) ans
#    config-Topic gesendet (gleiche Semantik wie die "Schlafintervall"-
#    Number-Entity in number.py) -- sonst wuerde das Geraet nachts
#    weiterhin im Tages-Takt aufwachen, ohne echten Akku-Vorteil.
# 2. State-Aktualisierung (Datenfrische): CONF_STATE_REFRESH_INTERVAL,
#    typischerweise viel kuerzer als das Schlafintervall. Damit ist der
#    Inhalt des retained state-Topics nie aelter als dieser Wert, egal
#    wann das Geraet tatsaechlich aufwacht (regulaer oder spontan per
#    Taster) -- waere State-Refresh an das (viel laengere)
#    Schlafintervall gekoppelt, koennte ein spontaner Sofort-Refresh
#    veraltete Werte abholen.
CONF_DAY_INTERVAL = "day_interval"
CONF_NIGHT_INTERVAL = "night_interval"
CONF_NIGHT_START = "night_start"
CONF_DAY_START = "day_start"
CONF_STATE_REFRESH_INTERVAL = "state_refresh_interval_s"

DEFAULT_DAY_INTERVAL = 300  # Sekunden, wie RefreshIntervalSeconds in der C#-App
DEFAULT_NIGHT_INTERVAL = 3600
DEFAULT_NIGHT_START = "22:00:00"
DEFAULT_DAY_START = "06:00:00"
DEFAULT_STATE_REFRESH_INTERVAL_S = 30
DEFAULT_RETAIN = True

# Muss zu SLEEP_INTERVAL_MIN_S/MAX_S in esp8266_epaper/src/config.h passen.
SLEEP_INTERVAL_MIN_S = 60
SLEEP_INTERVAL_MAX_S = 28800  # 8 Stunden
DEFAULT_SLEEP_INTERVAL_S = 600

CONFIG_TOPIC_SUFFIX = "config"
BATTERY_PERCENT_TOPIC_SUFFIX = "battery_percent"
BATTERY_VOLTAGE_TOPIC_SUFFIX = "battery_voltage"

SIGNAL_TEMPLATE_UPDATED = f"{DOMAIN}_template_updated"
