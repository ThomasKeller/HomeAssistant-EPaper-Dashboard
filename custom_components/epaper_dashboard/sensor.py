"""Sensoren je Geraet:

- 'Letztes Update': Zeitpunkt + Erfolg/Fehlermeldung des letzten
  Publish-Versuchs DIESER Integration, analog zu RefreshStatus in der
  C#-App (DashboardRefreshService.cs). Sagt nichts darueber aus, ob das
  Geraet die Nachricht je abgeholt hat.
- 'Batterie' / 'Batteriespannung': liest die vom Geraet selbst retained
  veroeffentlichten battery_percent/battery_voltage-Topics (siehe
  MQTT_TOPIC_BATTERY_PERCENT/_VOLTAGE in esp32_epaper/src/config.h) --
  echte Geraete-Werte, nicht von dieser Integration erzeugt. Retained,
  daher zeigt der Sensor sofort den letzten bekannten Stand, auch waehrend
  das Geraet schlaeft oder nach einem HA-Neustart.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ha_mqtt
from .const import (
    BATTERY_PERCENT_TOPIC_SUFFIX,
    BATTERY_VOLTAGE_TOPIC_SUFFIX,
    CONF_TOPIC_PREFIX,
    DOMAIN,
)
from .entity import device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        [
            EpaperStatusSensor(hass, entry),
            EpaperBatteryPercentSensor(hass, entry),
            EpaperBatteryVoltageSensor(hass, entry),
        ]
    )


class EpaperStatusSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Letztes Update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_last_update"
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass, f"{DOMAIN}_{self._entry.entry_id}_updated", self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self):
        runtime = self._hass.data[DOMAIN][self._entry.entry_id]
        return runtime.last_updated

    @property
    def extra_state_attributes(self) -> dict:
        runtime = self._hass.data[DOMAIN][self._entry.entry_id]
        return {
            "erfolgreich": runtime.last_success,
            "meldung": runtime.last_message,
        }


class _EpaperMqttTopicSensor(SensorEntity):
    """Basisklasse: liest den Wert eines einzelnen retained MQTT-Topics des
    Geraets als Float. Kein eigener Publish, rein passiv."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, topic_suffix: str) -> None:
        self._hass = hass
        self._entry = entry
        self._topic_suffix = topic_suffix
        self._attr_device_info = device_info(entry)
        self._unsub_mqtt = None
        self._value: float | None = None

    @property
    def _topic(self) -> str:
        opts = {**self._entry.data, **self._entry.options}
        prefix = opts.get(CONF_TOPIC_PREFIX, "").rstrip("/")
        return f"{prefix}/{self._topic_suffix}"

    async def async_added_to_hass(self) -> None:
        self._unsub_mqtt = await ha_mqtt.async_subscribe(self._hass, self._topic, self._on_message)
        self.async_on_remove(self._unsub_mqtt)

    @callback
    def _on_message(self, msg) -> None:
        try:
            self._value = float(msg.payload)
        except (TypeError, ValueError):
            return
        self.async_write_ha_state()

    @property
    def native_value(self):
        return self._value


class EpaperBatteryPercentSensor(_EpaperMqttTopicSensor):
    _attr_name = "Batterie"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, BATTERY_PERCENT_TOPIC_SUFFIX)
        self._attr_unique_id = f"{entry.entry_id}_battery_percent"


class EpaperBatteryVoltageSensor(_EpaperMqttTopicSensor):
    _attr_name = "Batteriespannung"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "V"
    _attr_entity_registry_enabled_default = False  # optional/diagnostisch, Prozent reicht fuer die meisten

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, BATTERY_VOLTAGE_TOPIC_SUFFIX)
        self._attr_unique_id = f"{entry.entry_id}_battery_voltage"
