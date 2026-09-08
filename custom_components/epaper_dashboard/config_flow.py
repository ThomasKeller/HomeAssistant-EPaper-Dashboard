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
    CONF_DAY_INTERVAL,
    CONF_DAY_START,
    CONF_DEVICE_NAME,
    CONF_NIGHT_INTERVAL,
    CONF_NIGHT_START,
    CONF_RETAIN,
    CONF_STATE_REFRESH_INTERVAL,
    CONF_TEMPLATE_JSON,
    CONF_TOPIC_PREFIX,
    DEFAULT_DAY_INTERVAL,
    DEFAULT_DAY_START,
    DEFAULT_NIGHT_INTERVAL,
    DEFAULT_NIGHT_START,
    DEFAULT_RETAIN,
    DEFAULT_STATE_REFRESH_INTERVAL_S,
    DOMAIN,
)

ERROR_INVALID_JSON = "invalid_json"


def _validate_template_json(value: str) -> None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as err:
        raise vol.Invalid(ERROR_INVALID_JSON) from err
    if not isinstance(parsed, dict) or "Elements" not in parsed:
        raise vol.Invalid(ERROR_INVALID_JSON)


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    """Liefert ein errors-Dict (leer = alles ok)."""
    errors: dict[str, str] = {}
    try:
        _validate_template_json(user_input[CONF_TEMPLATE_JSON])
    except vol.Invalid:
        errors["base"] = ERROR_INVALID_JSON
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
                CONF_TEMPLATE_JSON, default=defaults.get(CONF_TEMPLATE_JSON, "")
            ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
            vol.Required(
                CONF_STATE_REFRESH_INTERVAL,
                default=defaults.get(CONF_STATE_REFRESH_INTERVAL, DEFAULT_STATE_REFRESH_INTERVAL_S),
            ): vol.All(vol.Coerce(int), vol.Range(min=5)),
            vol.Required(
                CONF_DAY_INTERVAL,
                default=defaults.get(CONF_DAY_INTERVAL, DEFAULT_DAY_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=10)),
            vol.Required(
                CONF_NIGHT_INTERVAL,
                default=defaults.get(CONF_NIGHT_INTERVAL, DEFAULT_NIGHT_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=10)),
            vol.Required(
                CONF_NIGHT_START, default=defaults.get(CONF_NIGHT_START, DEFAULT_NIGHT_START)
            ): selector.TimeSelector(),
            vol.Required(
                CONF_DAY_START, default=defaults.get(CONF_DAY_START, DEFAULT_DAY_START)
            ): selector.TimeSelector(),
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
    Layout-Aenderungen im Editor neu einfuegen, oder Intervalle/Retain
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
