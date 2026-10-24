# tachylog

**GSI-Datenlogger für Leica Flexline Totalstationen**

> [!NOTE]
> **Status: Proof of Concept – wird nicht weiterentwickelt** (Stand Oktober 2026)
>
> tachylog war ein Vorläufer von **[OASP](https://github.com/Emfera/OASP)** (Open Archaeological Surveying Pipeline) und bleibt als Dokumentation der Versuche öffentlich. Der Code funktioniert wie beschrieben, wird aber nicht mehr gepflegt. Weiterentwickelt wird in [Emfera/OASP](https://github.com/Emfera/OASP); Experimente und Stand: [emfera.github.io/OASP](https://emfera.github.io/OASP/).

## Einordnung

Getestet wurde, ob ein Android-Handy die GSI-Ausgabe eines Leica TS07 über Bluetooth zuverlässig mitschreiben kann (Python-CLI unter Termux, Bluetooth über die App „BT/TCP Bridge“). Antwort: ja – aber die Einrichtung im Feld (zwei Apps, Termux, Bridge) war zu umständlich.

**In OASP übernommen:**
- Das Instrument behält die Kontrolle; der Logger hört nur zu (Auslösung am Tachymeter, wie bei Emlid Flow).
- PID wird unverändert gespeichert; Codeprüfung nur als Warnung, nie als Verwerfen.
- Rohdaten exakt wie vom Instrument (GSI) neben aufbereiteten Formaten.
- EPSG-Code nur als Metadatum, keine Transformation.
- Duplikat-Erkennung über die Rohzeile: Nachmessung am selben Punkt ist kein Duplikat.

**Bewusst nicht übernommen:**
- Termux + Bridge-App: ersetzt durch Web Serial im Browser (OASP Capture, Experiment C0) – keine Installation nötig.
- Python-CLI im Feld; die Weiterverarbeitung liegt in OASP Review.

**Bekannter Fehler, nicht mehr behoben:** Die EPSG-Codes sind in Code und Doku falsch beschriftet („31256 = M31, 31255 = M28, 31257 = M34“). Richtig ist: **31254 = GK M28, 31255 = GK M31, 31256 = GK M34** (31257–31259 sind die BMN-Varianten mit anderem Rechtswert-Offset). Der Standardwert 31256 ist also M34 (Ostösterreich), nicht M31. Da nur das Metadatum betroffen ist, nicht die Koordinaten, stimmen bestehende Messdaten; die EPSG-Angabe in alten Exporten bitte prüfen.

---

tachylog empfängt Messungen in Echtzeit von Leica Flexline Totalstationen (TS02, TS06, TS07, TS09, TS10, TS11, TS16) über Bluetooth und speichert sie in strukturierten Ausgabeformaten — als schlankes Kommandozeilen-Werkzeug für die Feldarbeit.

Konzeptionell vergleichbar mit **Emlid Flow** für GNSS-Rover: tachylog ist das Eingangstor für TS-Daten, ohne Auswertung, ohne Einschränkung der weiteren Pipeline.

---

## Konzept

```
TS07 (GSI16) → Bluetooth SPP → BT/TCP Bridge → tachylog → CSV / SQLite / GSI / GeoJSON
```

- Das **Instrument** behält die volle Kontrolle: PID eingeben, Messung auslösen
- tachylog **lauscht** und speichert jeden empfangenen Messpunkt
- **PID ist ein freier String** — tachylog erzwingt kein Format. Der Vermesser wählt am Gerät, ob er z.B. Gladiator (OT00010001), AS4QGIS (OT1001) oder eigene Bezeichner verwendet
- Keine Stationierung, keine Auswertung — das ist Aufgabe der nachgelagerten Pipeline

---

## Ausgabeformate

| Format | Option | Verwendung |
|---|---|---|
| SQLite | `--db aufnahme.db` | Für weitere Verarbeitung |
| CSV | `--csv aufnahme.csv` | Emlid Flow kompatibel, Excel, QGIS |
| GSI | `--gsi aufnahme.gsi` | Rohformat exakt wie vom Instrument |
| GeoJSON | `--geojson aufnahme.geojson` | Web-GIS, QGIS, eigene Skripte |

Alle Formate können **gleichzeitig** aktiv sein.

---

## PID-Schemata (optional)

Zur Gültigkeitsprüfung der PIDs im Feld können optionale Schema-Dateien geladen werden.
Die Prüfung ist **nicht-blockierend** — unbekannte Codes erzeugen nur Warnungen, Messungen werden nie verworfen.

Mitgelieferte Schemata:

| Schema | Datei | Format |
|---|---|---|
| Gladiator_2 | `schemas/gladiator2.json` | CCSSSSNNNN (empfohlen am Gerät) |
| ArchSurv4QGIS | `schemas/archsurv4qgis.json` | XXXXYZZ001 |
| Frei | `schemas/free.json` | Alle PIDs erlaubt (Standard) |

```bash
# Mit Schema-Validierung
tachylog collect --db aufnahme.db --schema schemas/gladiator2.json

# Verfügbare Schemata anzeigen
tachylog schemas

# Post-hoc-Check einer bestehenden Datenbank
tachylog validate aufnahme.db --schema schemas/gladiator2.json
```

---

## Installation

### Android (Termux)

```bash
pkg update && pkg install python git
pip install git+https://github.com/Emfera/tachylog.git
```

### Desktop (Linux/macOS/Windows)

```bash
pip install git+https://github.com/Emfera/tachylog.git
```

---

## Voraussetzungen (Android)

1. **Termux** — von F-Droid installieren (stable)
2. **BT/TCP Bridge** (Marek Masár) — aus dem Play Store
   - Device A: Totalstation via Bluetooth SPP verbinden
   - Device B: TCP Server `127.0.0.1:4444` starten
3. **TS07 Einstellungen**: Daten → Ausgabe → Interface, GSI16, Maske 1

---

## Verwendung

### Feldaufnahme starten

```bash
# Standard: SQLite
tachylog collect --port tcp://localhost:4444 --db aufnahme.db

# CSV (Emlid Flow kompatibel)
tachylog collect --port tcp://localhost:4444 --csv aufnahme.csv

# Alle Formate gleichzeitig
tachylog collect --port tcp://localhost:4444 \
  --db aufnahme.db \
  --csv aufnahme.csv \
  --gsi aufnahme.gsi \
  --geojson aufnahme.geojson

# Mit PID-Schema-Validierung (Warnungen, nicht blockierend)
tachylog collect --db aufnahme.db --schema schemas/gladiator2.json
```

Ausgabe während der Aufnahme:
```
  tachylog — GSI Collector
  Port:  tcp://localhost:4444
  SQLite → aufnahme.db

  Bedienung: Alles am Instrument (TS07)
  PID eingeben + Messung auslösen → tachylog speichert automatisch
  Beenden: Ctrl+C

  Verbinde mit tcp://localhost:4444... ✓
  Warte auf Messungen...

  [   1] OT00010001   E=   11112.846  N=    7350.902  H=   54.191
  [   2] OT00010002   E=   11122.148  N=    7347.049  H=   54.179
```

### CSV importieren (z.B. von GNSS-Rover)

```bash
tachylog import punkte.csv --db aufnahme.db
```

### Datenbank-Info

```bash
tachylog info aufnahme.db
```

---

## Workflow im Feld

```
1. Stationierung am TS07
   → Datenausgabe: Intern
   → Freie Stationierung durchführen (Orientierung bleibt gespeichert)

2. Umschalten am TS07 (ca. 10 Sekunden)
   → Daten → Ausgabe → Interface, GSI16, Maske 1

3. BT/TCP Bridge starten
   → Bluetooth verbinden → TCP Server starten

4. tachylog collect starten
   → Punkte messen → sofort in alle Ausgaben geschrieben

5. Export / Weiterverarbeitung
   → CSV direkt in QGIS oder Emlid Flow
   → SQLite für eigene Pipeline / Downstream-Tools
```

---

## Kompatibilität

Getestet mit: **Leica TS07 (R500)**

Sollte funktionieren mit allen Leica Flexline Totalstationen die GSI über die serielle Schnittstelle ausgeben:
TS02, TS06, TS07, TS09, TS10, TS11, TS16

GSI-Masken: Maske 1 (Word-Indizes 21/22/31) und andere Masken (81/82/83) werden automatisch erkannt.

---

## Lizenz

MIT — Martin Fera, Universität Wien
