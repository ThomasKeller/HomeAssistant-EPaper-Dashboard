"""Rendert ein Layout-Template (identisches JSON-Schema wie die C#-App unter
epaper_dashboard/) zu einem MQTT-Batch-Payload fuer epaper_core.h /
epaper_mqtt.py.

1:1-Python-Port von:
  - epaper_dashboard/EpaperDashboard/Services/PayloadBuilder.cs
  - epaper_dashboard/EpaperDashboard/Models/GfxTextLayout.cs
  - epaper_dashboard/EpaperDashboard/Models/GfxFonts.cs
  - epaper_dashboard/EpaperDashboard/Models/WeatherConditions.cs

Bei Aenderungen an der Protokoll-Logik in der C#-App IMMER auch hier
nachziehen, sonst laufen die beiden Renderer auseinander.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GfxFonts.cs -- (preview_pixel_size, avg_char_width_px) je Font-Key.
# avg_char_width_px ist der reale, aus den Adafruit-GFX-Font-Headern
# gemessene Mittelwert aller xAdvance-Werte 0x20-0x7E (siehe GfxFonts.cs-
# Kommentar) -- Naeherung fuer die Grad-Zeichen-Ersatzkreis-Position.
# ---------------------------------------------------------------------------
GFX_FONTS: dict[str, tuple[int, int]] = {
    "default":  (16, 12),
    "sans9":    (12, 9),
    "sans12":   (16, 12),
    "sans18":   (24, 18),
    "sans24":   (32, 24),
    "sans12b":  (16, 13),
    "sans18b":  (24, 19),
    "sans24b":  (32, 26),
    "mono9":    (12, 11),
    "mono12":   (16, 14),
    "mono12b":  (16, 14),
    "serif12":  (16, 12),
    "serif18b": (24, 19),
    "pico":     (5, 4),
    "tomthumb": (6, 4),
    "builtin":  (8, 6),
}


def _gfx_font(key: str | None) -> tuple[int, int]:
    return GFX_FONTS.get(key or "default", GFX_FONTS["default"])


# WeatherConditions.cs
WEATHER_CONDITIONS_DE: dict[str, str] = {
    "clear-night": "Klar",
    "cloudy": "Bewoelkt",
    "exceptional": "Extrem",
    "fog": "Nebel",
    "hail": "Hagel",
    "lightning": "Gewitter",
    "lightning-rainy": "Gewitter",
    "partlycloudy": "Wolkig",
    "pouring": "Regen+",
    "rainy": "Regen",
    "snowy": "Schnee",
    "snowy-rainy": "SchneeR",
    "sunny": "Sonnig",
    "windy": "Windig",
    "windy-variant": "Windig",
}


# ---------------------------------------------------------------------------
# GfxTextLayout.cs -- "°" ist in keiner GFX-Schriftart enthalten und wuerde
# als UTF-8-Doppelbyte ohnehin byteweise falsch gezeichnet -- wird durch
# einen kleinen gezeichneten Kreis ersetzt, Text drumherum in mehrere
# "text"-Ops aufgeteilt. Position ueber die durchschnittliche Zeichenbreite
# der Schriftart geschaetzt (keine exakten Glyphenbreiten -- bei gebundenen
# Werten aendert sich die Zeichenzahl ohnehin bei jedem Refresh).
# ---------------------------------------------------------------------------
def split_gfx_text(text: str, font_key: str | None, size: int, x: int, y: int) -> list[tuple]:
    preview_px, avg_char_w = _gfx_font(font_key)
    if "°" not in text:
        return [("text", x, text)]

    parts = text.split("°")
    cursor_x = x
    size = max(1, size)
    char_width = max(1, avg_char_w * size)
    radius = max(1, (preview_px * size) // 6)

    segments: list[tuple] = []
    for i, part in enumerate(parts):
        if part:
            segments.append(("text", cursor_x, part))
            cursor_x += len(part) * char_width
        if i < len(parts) - 1:
            segments.append(("circle", cursor_x + radius, y + radius, radius))
            cursor_x += radius * 2 + 1
    return segments


# ---------------------------------------------------------------------------
# .NET-Custom-Datumsformat (z.B. "HH:mm", "dd.MM. HH:mm") -> strftime.
# Deckt die in dieser App ueblichen Tokens ab (Jahr/Monat/Tag/Stunde/Minute/
# Sekunde/AM-Pattern + 'literal' in Anfuehrungszeichen). Exotischere .NET-
# Tokens (z.B. Wochentagsnamen "dddd") werden NICHT uebersetzt.
# ---------------------------------------------------------------------------
_DOTNET_TOKEN_RE = re.compile(r"yyyy|yy|MM|M|dd|d|HH|H|hh|h|mm|m|ss|s|tt|'[^']*'")
_DOTNET_TOKEN_MAP = {
    "yyyy": "%Y", "yy": "%y",
    "MM": "%m", "M": "%m",
    "dd": "%d", "d": "%d",
    "HH": "%H", "H": "%H",
    "hh": "%I", "h": "%I",
    "mm": "%M", "m": "%M",
    "ss": "%S", "s": "%S",
    "tt": "%p",
}


def dotnet_format_to_strftime(fmt: str) -> str:
    def repl(m: re.Match) -> str:
        tok = m.group(0)
        if tok.startswith("'") and tok.endswith("'"):
            return tok[1:-1].replace("%", "%%")
        return _DOTNET_TOKEN_MAP.get(tok, tok)

    return _DOTNET_TOKEN_RE.sub(repl, fmt)


# ---------------------------------------------------------------------------
# PayloadBuilder.cs ApplyBinding/AssignFormatted/AssignToTarget
# ---------------------------------------------------------------------------
def _assign_to_target(el: dict, target_field: str, raw: str, formatted: str) -> None:
    if target_field == "percent":
        try:
            el["Percent"] = float(raw)
        except (TypeError, ValueError):
            pass
    elif target_field == "data":
        el["Data"] = formatted
    else:
        el["Text"] = formatted


def _assign_formatted(el: dict, binding: dict, raw: str) -> None:
    fmt = binding.get("Format") or "{0}"
    try:
        formatted = fmt.format(raw)
    except (KeyError, IndexError, ValueError):
        formatted = raw
    _assign_to_target(el, binding.get("TargetField", "text"), raw, formatted)


def _apply_entity_binding(hass: HomeAssistant, el: dict, binding: dict) -> None:
    entity_id = binding.get("EntityId")
    if not entity_id:
        return
    state = hass.states.get(entity_id)
    if state is None:
        return

    attribute = binding.get("Attribute")
    if attribute:
        raw = state.attributes.get(attribute)
        raw = state.state if raw is None else raw
    else:
        raw = state.state

    _assign_formatted(el, binding, str(raw))


def _apply_forecast_binding(el: dict, binding: dict, forecasts: dict[str, list[dict]]) -> None:
    entity_id = binding.get("EntityId")
    if not entity_id:
        return
    days = forecasts.get(entity_id)
    if not days:
        return

    offset = int(binding.get("ForecastDayOffset", 0) or 0)
    if offset < 0 or offset >= len(days):
        return

    field = binding.get("ForecastField") or "temperature"
    day = days[offset]
    if field not in day or day[field] is None:
        return

    raw = str(day[field])
    if field == "condition":
        raw = WEATHER_CONDITIONS_DE.get(raw, raw)

    _assign_formatted(el, binding, raw)


def _apply_now_binding(el: dict, binding: dict) -> None:
    now = datetime.now()
    dotnet_fmt = binding.get("Format") or "HH:mm"
    try:
        formatted = now.strftime(dotnet_format_to_strftime(dotnet_fmt))
    except (ValueError, TypeError):
        formatted = now.strftime("%H:%M")
    _assign_to_target(el, binding.get("TargetField", "text"), formatted, formatted)


# ---------------------------------------------------------------------------
# HomeAssistantClient.GetForecastAsync -- weather.get_forecasts Service-Call.
# In HA direkt als Service verfuegbar, kein REST-Umweg noetig.
# ---------------------------------------------------------------------------
async def _fetch_forecasts(hass: HomeAssistant, entity_ids: set[str]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for entity_id in entity_ids:
        try:
            response = await hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": entity_id, "type": "daily"},
                blocking=True,
                return_response=True,
            )
        except Exception as err:  # noqa: BLE001 - Forecast-Fehler sollen den Rest nicht blockieren
            _LOGGER.warning("Forecast-Abruf fuer %s fehlgeschlagen: %s", entity_id, err)
            continue

        entry = (response or {}).get(entity_id)
        forecast = (entry or {}).get("forecast")
        if forecast:
            result[entity_id] = forecast
    return result


# ---------------------------------------------------------------------------
# PayloadBuilder.cs ResolveBindings
# ---------------------------------------------------------------------------
async def resolve_template(hass: HomeAssistant, template: dict) -> dict:
    """Liefert eine Kopie des Templates mit aufgeloesten Bindungen."""
    elements = template.get("Elements", [])

    forecast_entity_ids = {
        el["Binding"]["EntityId"]
        for el in elements
        if el.get("Binding")
        and el["Binding"].get("Source") == "forecast"
        and el["Binding"].get("EntityId")
    }
    forecasts = await _fetch_forecasts(hass, forecast_entity_ids) if forecast_entity_ids else {}

    resolved: list[dict] = []
    for el in elements:
        el_copy = dict(el)
        binding = el_copy.get("Binding")
        if binding:
            source = binding.get("Source", "entity")
            if source == "now":
                _apply_now_binding(el_copy, binding)
            elif source == "forecast":
                _apply_forecast_binding(el_copy, binding, forecasts)
            else:
                _apply_entity_binding(hass, el_copy, binding)
        resolved.append(el_copy)

    out = dict(template)
    out["Elements"] = resolved
    return out


# ---------------------------------------------------------------------------
# PayloadBuilder.cs BuildTextOps / BuildOp / Build
# ---------------------------------------------------------------------------
def _build_text_ops(el: dict, text_engine: str) -> list[dict]:
    text = el.get("Text") or ""

    if text_engine != "gfx":
        return [{"action": "text", "x": el["X"], "y": el["Y"], "text": text, "size": el.get("Size", 24)}]

    font_key = el.get("Font") or "default"
    size = max(1, int(el.get("Size", 1) or 1))

    ops: list[dict] = []
    for seg in split_gfx_text(text, font_key, size, el["X"], el["Y"]):
        if seg[0] == "text":
            _, run_x, run_text = seg
            ops.append({
                "action": "text", "x": run_x, "y": el["Y"], "text": run_text,
                "size": size, "font": font_key,
            })
        else:
            _, cx, cy, radius = seg
            ops.append({
                "action": "circle", "x": cx, "y": cy, "radius": radius,
                "fill": False, "outline_width": 1,
            })
    return ops


def _build_op(el: dict) -> dict:
    el_type = el["Type"]
    if el_type == "rectangle":
        return {
            "action": "rectangle", "x": el["X"], "y": el["Y"],
            "width": el.get("Width", 0), "height": el.get("Height", 0),
            "fill": bool(el.get("Fill", False)), "outline_width": el.get("OutlineWidth", 1),
        }
    if el_type == "line":
        return {
            "action": "line", "x1": el["X"], "y1": el["Y"],
            "x2": el.get("X2", 0), "y2": el.get("Y2", 0), "width": el.get("OutlineWidth", 1),
        }
    if el_type == "circle":
        return {
            "action": "circle", "x": el["X"], "y": el["Y"], "radius": el.get("Radius", 20),
            "fill": bool(el.get("Fill", False)), "outline_width": el.get("OutlineWidth", 1),
        }
    if el_type == "progress":
        percent = max(0, min(100, round(float(el.get("Percent", 0) or 0))))
        return {
            "action": "progress", "x": el["X"], "y": el["Y"],
            "width": el.get("Width", 0), "height": el.get("Height", 0), "percent": percent,
        }
    if el_type == "qrcode":
        return {
            "action": "qrcode", "x": el["X"], "y": el["Y"], "data": el.get("Data", ""),
            "scale": el.get("Scale", 4), "border": el.get("Border", 2), "ec": el.get("Ec", "M"),
        }
    if el_type == "clear_area":
        return {
            "action": "clear_area", "x": el["X"], "y": el["Y"],
            "width": el.get("Width", 0), "height": el.get("Height", 0),
        }
    if el_type == "image":
        return {"action": "image", "x": el["X"], "y": el["Y"], "path": el.get("Path", "")}
    raise ValueError(f"Unbekannter Elementtyp: {el_type}")


def build_payload(resolved_template: dict) -> str:
    """Baut das kompakte Batch-JSON, exakt kompatibel zu epaper_core.h /
    epaper_mqtt.py -- gleiche Feldnamen/-reihenfolge wie PayloadBuilder.cs."""
    text_engine = resolved_template.get("TextEngine", "gfx")

    ops: list[dict] = []
    if resolved_template.get("ClearFirst", True):
        ops.append({"action": "clear"})

    for el in resolved_template.get("Elements", []):
        if el["Type"] == "text":
            ops.extend(_build_text_ops(el, text_engine))
        else:
            ops.append(_build_op(el))

    payload = {
        "action": "batch",
        "mode": resolved_template.get("RefreshMode", "full"),
        "ops": ops,
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


async def render(hass: HomeAssistant, template: dict) -> str:
    """Bindungen aufloesen + Payload bauen -- der komplette Renderpfad."""
    resolved = await resolve_template(hass, template)
    return build_payload(resolved)
