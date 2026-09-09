# e-Paper Dashboard -- Home-Assistant-Integration

Eigenstaendige Home-Assistant-Integration, die ein Layout-Template
(identisches JSON-Schema wie die C#-App unter [../epaper_dashboard/](../epaper_dashboard/README.md))
periodisch selbst rendert und retained per MQTT sendet -- unabhaengig davon,
ob die C#-App gerade laeuft. Sinnvoll, sobald das Setup produktiv laufen soll:
Home Assistant ist ohnehin dauerhaft an, die C#-App war bisher nur ein
interaktiv gestartetes Test-/Editier-Werkzeug.

**Ein Geraet = eine Integrations-Instanz.** Fuer mehrere e-Paper-Displays
(aktuell "42", kuenftig weitere) die Integration einfach mehrfach ueber
"Integration hinzufuegen" einrichten -- Home Assistants uebliches Muster fuer
Multi-Geraet-Integrationen, jedes Geraet erscheint als eigene Geraetekarte.

## Installation

1. Ordner `custom_components/epaper_dashboard/` in das `custom_components/`-
   Verzeichnis eurer Home-Assistant-Konfiguration kopieren (liegt neben
   `configuration.yaml`; existiert der Ordner `custom_components/` noch
   nicht, anlegen).
2. Home Assistant neu starten.
3. Einstellungen -> Geraete & Dienste -> Integration hinzufuegen ->
   "e-Paper Dashboard" suchen.

## Einrichtung pro Geraet

1. Im e-Paper-Dashboard-Editor (C#-App) das Layout wie gewohnt bauen, dann
   Button **"Template-JSON kopieren"** -> landet in der Zwischenablage.
2. In Home Assistant beim Hinzufuegen der Integration einfuegen:
   - **Geraete-Name**: z.B. `42`
   - **MQTT-Topic-Praefix**: z.B. `epaper/42` (ohne `/state`/`/config`/`/status`
     am Ende)
   - **Template-JSON**: die kopierte JSON aus Schritt 1
   - **State-Aktualisierung**: wie oft neu gerendert + ans `state`-Topic
     gesendet wird, in Sekunden (Minimum 5, Default 30) -- unabhaengig vom
     Schlafintervall des Geraets, siehe Abschnitt unten
   - **Schlafintervall tagsueber / nachts**: wie lange das Geraet
     zwischen zwei Aufwach-Zyklen schlaeft, in Sekunden (Minimum 10)
   - **Nacht-Beginn** / **Tag-Beginn**: Uhrzeiten, ab wann das jeweilige
     Schlafintervall gilt (Nacht-Beginn darf ueber Mitternacht
     hinausgehen, z.B. 22:00 - 06:00)
   - **Retained senden**: fuer die Deep-Sleep/PIR/Taster-Firmware **an
     lassen** (Geraet schlaeft die meiste Zeit, siehe
     [esp8266_epaper/README.md](../esp8266_epaper/README.md) Abschnitt
     "Akkubetrieb"). Fuer die alwayson-Firmware kann es aus bleiben.

   **Voraussetzung**: Home Assistants eigene MQTT-Integration muss
   eingerichtet sein (Einstellungen -> Geraete & Dienste -> MQTT). Die
   Integration nutzt ausschliesslich diese Verbindung -- ein eigener
   Broker-Zugang wird nicht mehr unterstuetzt (siehe Architektur-Abschnitt
   unten, warum).

Das Ziel-Topic fuer den Batch-Payload kommt aus `MqttTopic` im Template
selbst (z.B. `epaper/42/state`), nicht aus dem Topic-Praefix -- der Praefix
wird nur fuers `config`-Topic (Schlafintervall, s.u.) verwendet.

### Template aktualisieren

Nach Layout-Aenderungen im Editor: Integration -> **Konfigurieren** ->
neues "Template-JSON kopieren"-Ergebnis einfuegen -> Absenden. Der naechste
Sendezyklus startet sofort mit dem neuen Layout, kein Neustart noetig.

## Zwei getrennte Takte: State-Aktualisierung vs. Geraete-Schlafintervall

Zwei unabhaengige Anliegen, zwei unabhaengige Einstellungen:

1. **State-Aktualisierung** (`state_refresh_interval_s`, Default 30s):
   wie oft das Plugin neu rendert und ans `state`-Topic sendet. Bewusst
   **viel kuerzer** als das Schlafintervall des Geraets, damit die
   retained Nachricht bei JEDEM Aufwachen frisch ist -- auch bei einem
   spontanen Sofort-Refresh (z.B. Taster-Wake), nicht nur beim naechsten
   regulaeren Schlafzyklus. Mit 30s ist der Inhalt hoechstens 30 Sekunden
   alt, egal wann das Geraet tatsaechlich aufwacht.
2. **Schlafintervall des Geraets** (Tag/Nacht, `day_interval` /
   `night_interval` zwischen `night_start` und `day_start`): wie lange das
   Geraet zwischen zwei Aufwach-Zyklen schlaeft (Akkulaufzeit). Wird bei
   jedem State-Refresh-Zyklus automatisch ans `config`-Topic gesendet.
   Ohne die Tag/Nacht-Unterscheidung wuerde das Geraet nachts weiterhin im
   Tages-Takt aufwachen, ohne echten Akku-Vorteil.

Diese beiden Takte sind bewusst entkoppelt: haette das Plugin nur EINEN
gemeinsamen Takt (fruehere Version), muesste er entweder kurz genug fuers
Geraet sein (schlecht fuer die Akkulaufzeit) oder lang genug fuers
Schlafintervall (dann kann ein spontaner Sofort-Refresh veraltete Werte
abholen).

Die "Schlafintervall"-Number-Entity (s.u.) bleibt als manueller Override
nutzbar, wird aber vom naechsten automatischen Zyklus wieder auf den
Tag/Nacht-passenden Wert zurueckgesetzt -- kein dauerhaftes Ueberschreiben.

## Was die Integration je Geraet anlegt

- **Button "Jetzt senden"**: sofortiger Render + Publish, ohne aufs naechste
  Intervall zu warten (Pendant zum "Speichern & jetzt senden"-Button in der
  C#-App).
- **Number "Schlafintervall"**: manueller, voruebergehender Override des
  Geraete-Schlafintervalls (siehe oben) -- publiziert retained eine rohe
  Zahl in Sekunden auf `{Topic-Praefix}/config` (z.B. `epaper/42/config`),
  exakt das Format, das `handleConfigMessage()` in `main_deepsleep.cpp` /
  `main_button.cpp` erwartet.
- **Sensor "Letztes Update"**: Zeitstempel + Erfolg/Fehlermeldung des
  letzten Sendeversuchs DIESER Integration (Attribute
  `erfolgreich`/`meldung`). Sagt nichts darueber aus, ob das Geraet die
  Nachricht je abgeholt hat.
- **Sensor "Batterie"** (`device_class: battery`, %) / **"Batteriespannung"**
  (`device_class: voltage`, V, standardmaessig deaktiviert): liest die vom
  Geraet selbst retained veroeffentlichten Topics
  `{Topic-Praefix}/battery_percent` / `{Topic-Praefix}/battery_voltage`
  (siehe `MQTT_TOPIC_BATTERY_PERCENT`/`_VOLTAGE` in
  `esp32_epaper/src/config.h`) -- echte Geraete-Werte als reine Zahl,
  direkt in HA-Automationen nutzbar (z.B. "wenn Batterie < 20%"), ohne
  Text-Parsing der bisherigen `status`-Zeile
  (`"battery: 4.18V (100%)"`, bleibt zusaetzlich als Debug-Info bestehen).
  Retained, daher sofort mit dem letzten bekannten Wert verfuegbar, auch
  waehrend das Geraet schlaeft oder direkt nach einem HA-Neustart.

## Architektur / Wartungshinweis

Die Integration nutzt **ausschliesslich** Home Assistants eigene
MQTT-Integration (`ha_mqtt.py`, `manifest.json` hat
`"dependencies": ["mqtt"]`) -- ein fruehrer eigenstaendiger
`paho-mqtt`-Client fuer einen frei waehlbaren Broker (`mqtt_client.py`)
wurde entfernt. Ist HAs MQTT-Integration nicht eingerichtet, verweigert
Home Assistant dank der harten Abhaengigkeit das Laden mit einer klaren
Fehlermeldung, statt erst zur Laufzeit zu scheitern.

`render.py` ist ein **manueller Python-Port** von
`PayloadBuilder.cs`/`GfxTextLayout.cs`/`GfxFonts.cs`/`WeatherConditions.cs`
aus der C#-App -- inklusive:

- ESP8266/GFX- vs. Pi/PIL-Text-Engine-Unterscheidung (`size` als
  Skalierungsfaktor vs. Pixelgroesse)
- Grad-Zeichen-Workaround ("°" -> kleiner gezeichneter Kreis, siehe
  Chat-Historie zu `GfxTextLayout.cs`)
- Wetter-Vorhersage ueber den `weather.get_forecasts`-Service (direkt als
  Home-Assistant-Service aufrufbar, kein REST-Umweg noetig wie in der
  C#-App)
- "Sende-Zeitpunkt"-Bindings (.NET-Datumsformat wie `HH:mm` wird nach
  `strftime` uebersetzt, siehe `dotnet_format_to_strftime()`)
- **Bild-Elemente** (im C#-Editor hochgeladene Grafiken, `ImageBase64`):
  bei `TextEngine`="gfx" werden sie identisch zur C#-App
  (`ImageConverter.ConvertTo1Bpp`) per manuellem Nearest-Neighbor-
  Sampling + Floyd-Steinberg-Dithering (bzw. Schwellwert) in eine rohe
  1-Bit-Bitmap umgewandelt -- `_convert_to_1bpp()` ist byteidentisch zur
  C#-Version verifiziert (siehe Session-Historie), benoetigt aber
  **Pillow** (`manifest.json` `requirements`), da HA es nicht immer
  automatisch mitbringt.
- **Nachkommastellen** (`Binding.Decimals`, im Editor bei der jeweiligen
  Bindung einstellbar): rundet den HA-Rohwert (z.B. `1147.4765`) VOR dem
  Einsetzen in `Format` auf N Nachkommastellen (`0` = ganze Zahl, leer =
  unveraendert). Bewusst kein eingebetteter Format-Code wie `{0:0.00}`
  direkt im `Format`-Feld -- der wuerde bei String-Werten in C# wirkungslos
  bleiben und in Python eine andere, inkompatible Mini-Sprache verwenden.
  `_apply_decimals()` in `render.py` ist das gepruefte Aequivalent zu
  `ApplyDecimals()` in `PayloadBuilder.cs`.

**Wird die Render-Logik in der C#-App geaendert** (neue Font, neue
Binding-Quelle, geaendertes Protokoll-Feld), **muss `render.py` manuell
nachgezogen werden** -- die beiden Implementierungen sind komplett getrennt,
es gibt keine gemeinsame Codebasis. Verifiziert wurde die Aequivalenz durch
Abgleich der Ausgabe beider Renderer gegen dieselben Live-HA-Daten (siehe
Session-Historie) -- bei Aenderungen empfiehlt sich derselbe Abgleich.

## Home-Assistant-Version

Getestet gegen die REST-API-Semantik von `weather.get_forecasts`
(HA >= 2023.9, aeltere Versionen haben Vorhersagen noch als
State-Attribut). Config-Flow/Options-Flow nutzen `voluptuous` +
`homeassistant.helpers.selector`, Standard seit mehreren Jahren stabil.
