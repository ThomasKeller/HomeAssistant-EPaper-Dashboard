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


# GfxFonts.cs CharWidths -- exakte xAdvance-Werte je Zeichen 0x20-0x7E
# (Index 0 = 0x20), direkt aus den GFXglyph-Tabellen der Adafruit-GFX-Font-
# Header extrahiert. Grund: AvgCharWidthPx ist ein Mittelwert ueber ALLE
# druckbaren Zeichen, aber schmale Satzzeichen wie "." sind bei
# proportionalen Schriften deutlich schmaler als der Durchschnitt (z.B.
# sans12: Ziffer=13px, Punkt=6px). Bei Werten wie "20.1" summiert eine reine
# Laengen*Mittelwert-Schaetzung den Punkt faelschlich mit ~12px statt 6px
# auf und schiebt den Grad-Kreis dadurch sichtbar zu weit von der Zahl weg.
# pico/tomthumb/builtin bewusst nicht enthalten (siehe GfxFonts.cs).
CHAR_WIDTHS: dict[str, list[int]] = {
    "sans9": [5, 6, 6, 10, 10, 16, 12, 4, 6, 6, 7, 11, 5, 6, 5, 5, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 5, 5, 11, 11, 11, 10, 18, 12, 12, 13, 13, 11, 11, 14, 13, 5, 10, 12, 10, 15, 13, 14, 12, 14, 13, 12, 11, 13, 12, 17, 12, 12, 11, 5, 5, 5, 8, 10, 5, 10, 10, 9, 10, 10, 5, 10, 10, 4, 4, 9, 4, 15, 10, 10, 10, 10, 6, 9, 5, 10, 9, 13, 9, 9, 9, 6, 4, 6, 9],
    "sans12": [6, 8, 8, 13, 13, 21, 16, 5, 8, 8, 9, 14, 7, 8, 6, 7, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 6, 6, 14, 14, 14, 13, 24, 16, 16, 17, 17, 15, 14, 18, 17, 7, 13, 16, 14, 20, 18, 19, 16, 19, 17, 16, 15, 17, 15, 22, 16, 16, 15, 7, 7, 7, 11, 13, 6, 13, 13, 12, 13, 13, 7, 13, 13, 5, 6, 12, 5, 19, 13, 13, 13, 13, 8, 12, 7, 13, 12, 17, 11, 11, 12, 8, 6, 8, 12],
    "sans18": [9, 12, 12, 19, 19, 31, 23, 7, 12, 12, 14, 20, 10, 12, 9, 10, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 9, 9, 20, 20, 20, 19, 36, 23, 23, 25, 24, 22, 21, 27, 25, 10, 18, 24, 20, 30, 26, 27, 23, 27, 25, 23, 22, 25, 23, 33, 23, 24, 22, 10, 10, 10, 16, 19, 9, 19, 20, 18, 20, 19, 10, 19, 19, 8, 9, 18, 7, 28, 19, 19, 20, 20, 12, 17, 10, 19, 17, 25, 17, 17, 17, 12, 9, 12, 18],
    "sans24": [12, 16, 16, 26, 26, 42, 31, 9, 16, 16, 18, 27, 13, 16, 12, 13, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 12, 12, 27, 27, 27, 26, 48, 31, 31, 33, 33, 30, 28, 36, 34, 13, 25, 32, 26, 40, 34, 37, 31, 37, 33, 31, 30, 34, 30, 44, 31, 32, 29, 13, 13, 13, 22, 26, 12, 26, 26, 24, 26, 25, 13, 26, 25, 10, 11, 24, 10, 38, 25, 25, 26, 26, 16, 23, 13, 25, 23, 34, 22, 22, 23, 16, 12, 16, 24],
    "sans12b": [7, 8, 11, 13, 13, 21, 17, 6, 8, 8, 9, 14, 6, 8, 6, 7, 13, 14, 13, 13, 13, 13, 13, 13, 13, 13, 6, 6, 14, 14, 14, 15, 23, 17, 17, 17, 17, 16, 15, 18, 18, 7, 14, 17, 15, 21, 18, 19, 16, 19, 17, 16, 15, 18, 16, 23, 16, 15, 15, 8, 7, 8, 14, 13, 6, 14, 15, 13, 15, 14, 8, 15, 14, 7, 7, 14, 6, 21, 15, 15, 15, 15, 9, 13, 8, 15, 13, 19, 13, 13, 12, 9, 7, 9, 12],
    "sans18b": [10, 12, 17, 19, 19, 31, 25, 9, 12, 12, 14, 20, 9, 12, 9, 10, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 9, 9, 20, 20, 20, 21, 34, 24, 25, 25, 25, 23, 22, 27, 26, 11, 20, 25, 22, 30, 26, 27, 24, 27, 25, 24, 23, 26, 23, 34, 24, 22, 21, 12, 10, 12, 20, 19, 9, 20, 22, 20, 22, 20, 12, 21, 21, 10, 10, 20, 9, 31, 21, 21, 22, 22, 14, 19, 12, 21, 19, 27, 19, 19, 18, 14, 10, 14, 18],
    "sans24b": [13, 16, 22, 26, 26, 42, 34, 12, 16, 16, 18, 27, 12, 16, 12, 13, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 12, 12, 27, 27, 27, 29, 46, 33, 33, 34, 34, 31, 30, 36, 35, 15, 27, 34, 29, 41, 35, 37, 32, 37, 34, 32, 30, 35, 31, 45, 32, 30, 29, 16, 13, 16, 27, 26, 12, 27, 29, 26, 29, 27, 16, 29, 28, 13, 13, 27, 13, 42, 29, 29, 29, 29, 18, 26, 16, 29, 25, 37, 26, 26, 24, 18, 13, 18, 23],
    "mono9": [11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11],
    "mono12": [14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
    "mono12b": [14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 15, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14],
    "serif12": [6, 8, 10, 12, 12, 20, 19, 5, 8, 8, 12, 14, 6, 8, 6, 7, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 6, 6, 14, 14, 14, 11, 21, 17, 15, 16, 17, 15, 14, 17, 17, 8, 9, 17, 15, 21, 17, 17, 14, 17, 16, 13, 15, 17, 17, 23, 17, 17, 15, 8, 7, 8, 11, 12, 6, 10, 12, 11, 12, 11, 9, 11, 12, 7, 8, 12, 6, 19, 12, 12, 12, 12, 8, 9, 7, 12, 11, 16, 12, 11, 10, 12, 5, 12, 12],
    "serif18b": [9, 12, 19, 17, 17, 35, 29, 10, 12, 12, 18, 24, 9, 12, 9, 10, 18, 18, 17, 18, 18, 18, 18, 17, 17, 18, 12, 12, 24, 24, 24, 18, 33, 25, 23, 25, 26, 23, 22, 27, 27, 14, 18, 27, 23, 33, 25, 27, 22, 27, 25, 20, 23, 25, 25, 34, 25, 25, 23, 12, 10, 12, 20, 17, 12, 18, 19, 15, 19, 16, 14, 17, 19, 10, 14, 19, 10, 29, 19, 18, 19, 19, 15, 14, 12, 20, 17, 25, 18, 17, 16, 14, 8, 14, 18],
}


def _text_width_px(text: str, font_key: str | None, size: int) -> int:
    """GfxFonts.cs TextWidthPx -- exakte Breite via CHAR_WIDTHS, sonst
    AvgCharWidthPx-Mittelwert je unbekanntem Zeichen."""
    size = max(1, size)
    widths = CHAR_WIDTHS.get(font_key or "default")
    _, avg_char_w = _gfx_font(font_key)
    if widths is None:
        return len(text) * avg_char_w * size

    total = 0
    for ch in text:
        idx = ord(ch) - 0x20
        total += widths[idx] if 0 <= idx < len(widths) else avg_char_w
    return total * size


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
# "text"-Ops aufgeteilt. Position ueber _text_width_px berechnet, das die
# tatsaechliche, aus den Adafruit-GFX-Font-Headern gemessene Breite jedes
# einzelnen Zeichens aufsummiert (siehe CHAR_WIDTHS) - nicht nur einen
# Durchschnittswert mal Zeichenanzahl. Wichtig, weil z.B. "." deutlich
# schmaler ist als der Durchschnitt und eine reine Mittelwert-Schaetzung den
# Kreis bei Werten wie "20.1°" sichtbar zu weit von der Zahl weg schieben
# wuerde.
# ---------------------------------------------------------------------------
def split_gfx_text(text: str, font_key: str | None, size: int, x: int, y: int) -> list[tuple]:
    preview_px, _ = _gfx_font(font_key)
    if "°" not in text:
        return [("text", x, text)]

    parts = text.split("°")
    cursor_x = x
    size = max(1, size)
    radius = max(1, (preview_px * size) // 6)
    # Kleiner optischer Zwischenraum vor dem Kreis: eine rein exakte
    # Aneinanderreihung (Zeichenende = Kreis-Anfang) wirkt am echten Geraet
    # zu gedraengt, da ein echtes "°"-Glyph auch einen eigenen Randabstand
    # haette. Skaliert mit der Schriftgroesse (= Radius), am Geraet
    # gegengeprueft (07.09.2026).
    gap = radius

    segments: list[tuple] = []
    for i, part in enumerate(parts):
        if part:
            segments.append(("text", cursor_x, part))
            cursor_x += _text_width_px(part, font_key, size)
        if i < len(parts) - 1:
            cursor_x += gap
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


def _apply_decimals(raw: str, decimals: int | None) -> str:
    """Rundet raw auf `decimals` Nachkommastellen, falls es sich als Zahl
    parsen laesst (sonst unveraendert -- z.B. Text-Werte wie Wetter-
    "condition"). None = keine Rundung. 1:1-Aequivalent zu
    PayloadBuilder.cs ApplyDecimals() -- sprachneutraler, expliziter Weg
    statt eingebetteter Format-Codes wie "{0:0.00}" (die bei einem
    String-Argument in C# wirkungslos wären und in Python eine andere
    Mini-Sprache haetten)."""
    if decimals is None:
        return raw
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return raw
    n = max(0, min(10, int(decimals)))
    return f"{round(value, n):.{n}f}"


def _assign_formatted(el: dict, binding: dict, raw: str) -> None:
    raw = _apply_decimals(raw, binding.get("Decimals"))

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
# Nur Felder schreiben, die vom Firmware-Default abweichen oder in der
# aktuellen Konstellation ueberhaupt gelesen werden (z.B. outline_width bei
# fill=True - siehe cmdRectangle/cmdCircle in epaper_core.h, das liest
# outline_width nur im nicht gefuellten Zweig). Defaults siehe epaper_core.h
# (ESP, "gfx") bzw. epaper_mqtt.py (Pi, "pil"). 1:1-Aequivalent zu
# PayloadBuilder.cs BuildTextOps/BuildOp/BuildRectangleOp/... .
def _build_text_ops(el: dict, text_engine: str) -> list[dict]:
    text = el.get("Text") or ""

    if text_engine != "gfx":
        op: dict = {"action": "text", "x": el["X"], "y": el["Y"], "text": text}
        size = el.get("Size", 24)
        if size != 24:  # Pi-Default: epaper_mqtt.py size|24
            op["size"] = size
        return [op]

    font_key = el.get("Font") or "default"
    size = max(1, int(el.get("Size", 1) or 1))

    ops: list[dict] = []
    for seg in split_gfx_text(text, font_key, size, el["X"], el["Y"]):
        if seg[0] == "text":
            _, run_x, run_text = seg
            op = {"action": "text", "x": run_x, "y": el["Y"], "text": run_text}
            if size != 1:  # ESP-Default: epaper_core.h size|1
                op["size"] = size
            if font_key and font_key != "default":
                op["font"] = font_key
            ops.append(op)
        else:
            _, cx, cy, radius = seg
            # Immer fill=False/outline_width=1 (Default) -> beide entfallen.
            ops.append({"action": "circle", "x": cx, "y": cy, "radius": radius})
    return ops


def _build_op(el: dict, text_engine: str) -> dict:
    el_type = el["Type"]
    if el_type == "rectangle":
        op = {
            "action": "rectangle", "x": el["X"], "y": el["Y"],
            "width": el.get("Width", 0), "height": el.get("Height", 0),
        }
        fill = bool(el.get("Fill", False))
        outline_width = el.get("OutlineWidth", 1)
        if fill:
            op["fill"] = True
        elif outline_width != 1:
            op["outline_width"] = outline_width
        return op
    if el_type == "line":
        op = {"action": "line", "x1": el["X"], "y1": el["Y"], "x2": el.get("X2", 0), "y2": el.get("Y2", 0)}
        width = el.get("OutlineWidth", 1)
        if width != 1:
            op["width"] = width
        return op
    if el_type == "circle":
        op = {"action": "circle", "x": el["X"], "y": el["Y"], "radius": el.get("Radius", 20)}
        fill = bool(el.get("Fill", False))
        outline_width = el.get("OutlineWidth", 1)
        if fill:
            op["fill"] = True
        elif outline_width != 1:
            op["outline_width"] = outline_width
        return op
    if el_type == "progress":
        percent = max(0, min(100, round(float(el.get("Percent", 0) or 0))))
        return {
            "action": "progress", "x": el["X"], "y": el["Y"],
            "width": el.get("Width", 0), "height": el.get("Height", 0), "percent": percent,
        }
    if el_type == "qrcode":
        # Firmware-Default fuer "scale" unterscheidet sich je Plattform:
        # ESP (epaper_core.h): 3, Pi (epaper_mqtt.py): 4.
        scale_default = 3 if text_engine == "gfx" else 4
        op = {"action": "qrcode", "x": el["X"], "y": el["Y"], "data": el.get("Data", "")}
        scale = el.get("Scale", scale_default)
        if scale != scale_default:
            op["scale"] = scale
        border = el.get("Border", 2)
        if border != 2:
            op["border"] = border
        ec = el.get("Ec", "M")
        if ec and ec != "M":
            op["ec"] = ec
        return op
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
            ops.append(_build_op(el, text_engine))

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
