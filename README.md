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
   - **MQTT-Topic-Praefix**: z.B. `epaper/42` (ohne `/state`/`/config` am Ende)
   - **MQTT-Verbindung**: Auswahl zwischen
     - *Eigener Broker*: Host/Port/Benutzername/Passwort direkt hier
       eintragen (dieselben Werte wie in
       `epaper_dashboard/EpaperDashboard/appsettings.json` bei der C#-App).
       Verbindet sich selbst (`paho-mqtt`), unabhaengig davon ob Home
       Assistant selbst MQTT eingerichtet hat.
     - *Home Assistants eigene MQTT-Integration verwenden*: nutzt die in
       HA unter Einstellungen -> Geraete & Dienste -> MQTT bereits
       hinterlegte Verbindung -- keine doppelte Pflege von Zugangsdaten,
       setzt aber voraus, dass diese Integration dort eingerichtet ist.
   - **Template-JSON**: die kopierte JSON aus Schritt 1
   - **Sende-Intervall**: wie oft neu gerendert + an den Broker gesendet
     wird, in Sekunden (Minimum 10)
   - **Retained senden**: fuer die Deep-Sleep/PIR/Taster-Firmware **an
     lassen** (Geraet schlaeft die meiste Zeit, siehe
     [esp8266_epaper/README.md](../esp8266_epaper/README.md) Abschnitt
     "Akkubetrieb"). Fuer die alwayson-Firmware kann es aus bleiben.

Das Ziel-Topic fuer den Batch-Payload kommt aus `MqttTopic` im Template
selbst (z.B. `epaper/42/state`), nicht aus dem Topic-Praefix -- der Praefix
wird nur fuers `config`-Topic (Schlafintervall, s.u.) verwendet.

### Template aktualisieren

Nach Layout-Aenderungen im Editor: Integration -> **Konfigurieren** ->
neues "Template-JSON kopieren"-Ergebnis einfuegen -> Absenden. Der naechste
Sendezyklus startet sofort mit dem neuen Layout, kein Neustart noetig.

## Was die Integration je Geraet anlegt

- **Button "Jetzt senden"**: sofortiger Render + Publish, ohne aufs naechste
  Intervall zu warten (Pendant zum "Speichern & jetzt senden"-Button in der
  C#-App).
- **Number "Schlafintervall"**: setzt das Schlafintervall der
  Deep-Sleep/PIR/Taster-Firmware. Publiziert retained eine rohe Zahl in
  Sekunden auf `{Topic-Praefix}/config` (z.B. `epaper/42/config`) -- exakt
  das Format, das `handleConfigMessage()` in `main_deepsleep.cpp` /
  `main_button.cpp` erwartet. **Wichtig**: auch dieses Topic braucht
  retain=true (macht die Integration automatisch), aus demselben Grund wie
  beim state-Topic -- das Geraet abonniert `config` nur kurz beim Aufwachen.
- **Sensor "Letztes Update"**: Zeitstempel + Erfolg/Fehlermeldung des
  letzten Sendeversuchs (Attribute `erfolgreich`/`meldung`).

## Architektur / Wartungshinweis

`mqtt_client.py` ist ein eigenstaendiger MQTT-Client (`paho-mqtt`,
kurzlebige Verbindung pro Publish -- verbinden, senden, trennen, analog zu
`MqttPublisher.cs`). Bewusst **keine** Abhaengigkeit von Home Assistants
eigener MQTT-Integration (`manifest.json` hat kein
`"dependencies": ["mqtt"]` mehr): haengt die Integration daran und ist die
in eurer HA-Instanz nicht eingerichtet, scheitert das Laden komplett --
inklusive aller anderen Einstellungen, die dann nie erreichbar sind.

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
