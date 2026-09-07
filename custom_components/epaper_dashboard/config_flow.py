"""Config Flow: ein e-Paper-Geraet pro Config-Entry. Fuer mehrere Geraete
(42, 43, ...) die Integration einfach mehrfach ueber "Integration
hinzufuegen" einrichten -- HAs idiomatisches Muster fuer Multi-Geraet-
Integrationen, kein eigenes Multi-Device-UI noetig."""
from __future__ import annotations

import json
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_NAME,
    CONF_MQTT_HOST,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_SOURCE,
    CONF_MQTT_USERNAME,
    CONF_RETAIN,
    CONF_TEMPLATE_JSON,
    CONF_TOPIC_PREFIX,
    CONF_UPDATE_INTERVAL,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_SOURCE,
    DEFAULT_RETAIN,
    DEFAULT_UPDATE_INTERVAL,
    MQTT_SOURCE_CUSTOM,
    MQTT_SOURCE_HA,
    DOMAIN,
)

ERROR_INVALID_JSON = "invalid_json"
ERROR_MISSING_MQTT_HOST = "missing_mqtt_host"

_MQTT_SOURCE_OPTIONS = [
    selector.SelectOptionDict(value=MQTT_SOURCE_CUSTOM, label="Eigener Broker (Adresse unten eintragen)"),
    selector.SelectOptionDict(value=MQTT_SOURCE_HA, label="Home Assistants eigene MQTT-Integration verwenden"),
]


def _validate_template_json(value: str) -> None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as err:
        raise vol.Invalid(ERROR_INVALID_JSON) from err
    if not isinstance(parsed, dict) or "Elements" not in parsed:
        raise vol.Invalid(ERROR_INVALID_JSON)


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    """Liefert ein errors-Dict (leer = alles ok). mqtt_host ist nur bei
    Source "custom" Pflicht -- bei "ha" wird Home Assistants eigene
    MQTT-Verbindung genutzt, da braucht es keine eigene Broker-Adresse."""
    errors: dict[str, str] = {}
    try:
        _validate_template_json(user_input[CONF_TEMPLATE_JSON])
    except vol.Invalid:
        errors["base"] = ERROR_INVALID_JSON

    if user_input.get(CONF_MQTT_SOURCE) == MQTT_SOURCE_CUSTOM and not user_input.get(CONF_MQTT_HOST):
        errors[CONF_MQTT_HOST] = ERROR_MISSING_MQTT_HOST

    return errors


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_DEVICE_NAME, default=defaults.get(CONF_DEVICE_NAME, "")): str,
            vol.Required(
                CONF_TOPIC_PREFIX, default=defaults.get(CONF_TOPIC_PREFIX, "epaper/42")
            ): str,
            vol.Required(
                CONF_MQTT_SOURCE, default=defaults.get(CONF_MQTT_SOURCE, DEFAULT_MQTT_SOURCE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(options=_MQTT_SOURCE_OPTIONS, mode=selector.SelectSelectorMode.DROPDOWN)
            ),
            vol.Optional(
                CONF_MQTT_HOST, default=defaults.get(CONF_MQTT_HOST, "")
            ): str,
            vol.Required(
                CONF_MQTT_PORT, default=defaults.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT)
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Optional(
                CONF_MQTT_USERNAME, default=defaults.get(CONF_MQTT_USERNAME, "")
            ): str,
            vol.Optional(
                CONF_MQTT_PASSWORD, default=defaults.get(CONF_MQTT_PASSWORD, "")
            ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Required(
                CONF_TEMPLATE_JSON, default=defaults.get(CONF_TEMPLATE_JSON, "")
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Required(
                CONF_UPDATE_INTERVAL,
                default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=10)),
            vol.Required(CONF_RETAIN, default=defaults.get(CONF_RETAIN, DEFAULT_RETAIN)): bool,
        }
    )


class EpaperDashboardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                await self.async_set_unique_id(user_input[CONF_TOPIC_PREFIX])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"e-Paper {user_input[CONF_DEVICE_NAME]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> EpaperDashboardOptionsFlow:
        return EpaperDashboardOptionsFlow(config_entry)


class EpaperDashboardOptionsFlow(config_entries.OptionsFlow):
    """Ueber "Konfigurieren" erreichbar -- hier das Template nach
    Layout-Aenderungen im Editor neu einfuegen, oder Intervall/Retain
    anpassen."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        current = {**self._entry.data, **self._entry.options}

        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init", data_schema=_schema(user_input or current), errors=errors
        )
