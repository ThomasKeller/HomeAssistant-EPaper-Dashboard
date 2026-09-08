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
   - **Tages-Intervall**: wie oft tagsueber neu gerendert + gesendet wird,
     in Sekunden (Minimum 10)
   - **Nacht-Intervall**: wie oft nachts neu gerendert + gesendet wird
   - **Nacht-Beginn** / **Tag-Beginn**: Uhrzeiten, ab wann das jeweilige
     Intervall gilt (Nacht-Beginn darf ueber Mitternacht hinausgehen, z.B.
     22:00 - 06:00)
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

## Tag/Nacht-Intervall + zeitoptimiertes Senden

Statt eines starren Sende-Timers verfolgt die Integration zwei Ziele
gleichzeitig:

1. **Tag/Nacht-Intervall**: zwischen Nacht-Beginn und Tag-Beginn gilt das
   Nacht-Intervall, sonst das Tages-Intervall -- sowohl fuers eigene
   Rendern+Senden als auch (automatisch, per `config`-Topic-Push bei jedem
   Zyklus) fuers Schlafintervall des Geraets selbst. Ohne diese Kopplung
   wuerde das Geraet nachts weiterhin im Tages-Takt aufwachen und nur
   oefter denselben Inhalt abholen, ohne echten Akku-Vorteil.
2. **Zeitoptimiertes Senden**: die Integration abonniert den `status`-Topic
   des Geraets (`{Topic-Praefix}/status`) und merkt sich den Zeitpunkt der
   letzten Nachricht -- das ist, wann das Geraet zuletzt aufgewacht ist.
   Der naechste Sendezeitpunkt wird auf **Sende-Vorlauf** (konfigurierbar,
   Default 30s -- siehe `wake_lead_s` in den Einstellungen) VOR dem daraus
   vorhergesagten naechsten Aufwachen gelegt (letzter Status-Zeitpunkt +
   aktuelles Intervall), statt auf einen von der HA-Startzeit abhaengigen,
   moeglicherweise schlecht getakteten festen Timer. Beispiel: Intervall 10
   Minuten, Vorlauf 60s, letzter Status 12:10 -> Senden 12:19, sodass eine
   frische retained Nachricht bereitliegt, wenn das Geraet um ca. 12:20
   erneut aufwacht. Realistischer Wert nach Messungen am echten Geraet
   (WLAN-Fast-Reconnect + MQTT-Connect lag durchgehend bei 2-10s): 30s
   Default, mit Marge fuer gelegentlich langsamere Zyklen und RTC-Drift.
   Bevor der erste Status gesehen wurde (z.B. direkt nach einem
   HA-Neustart), greift der normale Intervall-Takt ab jetzt als Fallback.

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
  letzten Sendeversuchs (Attribute `erfolgreich`/`meldung`).

## Architektur / Wartungshinweis

Die Integration nutzt **ausschliesslich** Home Assistants eigene
MQTT-Integration (`ha_mqtt.py`, `manifest.json` hat
`"dependencies": ["mqtt"]`) -- ein fruehrer eigenstaendiger
`paho-mqtt`-Client fuer einen frei waehlbaren Broker (`mqtt_client.py`)
wurde entfernt: das zeitoptimierte Senden (s.o.) braucht ein dauerhaftes
Abonnement des `status`-Topics, das der damalige kurzlebige
Publish-Only-Client nicht bieten konnte. Ist HAs MQTT-Integration nicht
eingerichtet, verweigert Home Assistant dank der harten Abhaengigkeit das
Laden mit einer klaren Fehlermeldung, statt erst zur Laufzeit zu scheitern.

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
