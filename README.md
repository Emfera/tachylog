# tachylog

**GSI-Datenlogger für Leica Flexline Totalstationen**

tachylog empfängt Messungen in Echtzeit von Leica Flexline Totalstationen (TS02, TS06, TS07, TS09, TS10, TS11, TS16) über Bluetooth und speichert sie in strukturierten Ausgabeformaten — als schlankes Kommandozeilen-Werkzeug für die Feldarbeit.

Konzeptionell vergleichbar mit **Emlid Flow** für GNSS-Rover: tachylog ist das Eingangstor für TS-Daten, ohne Auswertung, ohne Einschränkung der weiteren Pipeline.

---

## Konzept

```
TS07 (GSI16) → Bluetooth SPP → BT/TCP Bridge → tachylog → CSV / SQLite / GSI / GeoJSON
```

- Das **Instrument** behält die volle Kontrolle: PID eingeben, Messung auslösen
- tachylog **lauscht** und speichert jeden empfangenen Messpunkt
- Keine Stationierung, keine Auswertung — das ist Aufgabe der nachgelagerten Pipeline

---

## Ausgabeformate

| Format | Option | Verwendung |
|---|---|---|
| SQLite | `--db aufnahme.db` | Für weitere Verarbeitung, GeoPackage-Export |
| CSV | `--csv aufnahme.csv` | Emlid Flow kompatibel, Excel, QGIS |
| GSI | `--gsi aufnahme.gsi` | Rohformat exakt wie vom Instrument |
| GeoJSON | `--geojson aufnahme.geojson` | Web-GIS, QGIS, eigene Skripte |
| GeoPackage | `tachylog build` | Aus SQLite, für QGIS (Punkte, Linien, Flächen) |

Alle Formate können **gleichzeitig** aktiv sein.

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
```

Ausgabe während der Aufnahme:
```
  tachylog — GSI Collector
  Port:  tcp://localhost:4444
  SQLite → aufnahme.db
  CSV    → aufnahme.csv

  Bedienung: Alles am Instrument (TS07)
  PID eingeben + Messung auslösen → tachylog speichert automatisch
  Beenden: Ctrl+C

  Verbinde mit tcp://localhost:4444... ✓
  Warte auf Messungen...

  [   1] LE01023      E=   11112.846  N=    7350.902  H=   54.191
  [   2] LE01024      E=   11122.148  N=    7347.049  H=   54.179
```

### GeoPackage für QGIS bauen

```bash
tachylog build aufnahme.db ausgabe.gpkg
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
   → CSV direkt in QGIS oder eigene Pipeline
   → tachylog build → GeoPackage für QGIS
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
