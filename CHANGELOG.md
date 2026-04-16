# Changelog

## [1.1.0] — 2026-04-16

### Neu

- **Freies PID-Format** — tachylog speichert die PID unverändert als opaken String.
  Kein Format wird erzwungen oder validiert. Der Vermesser wählt am Instrument
  ob er Gladiator (OT00010001), AS4QGIS (OT1001) oder eigene Bezeichner verwendet.

- **Schema-Validator** (`tachylog/schema_validator.py`) — optionale, nicht-blockierende
  PID-Validierung. Unbekannte Codes oder falsche Länge erzeugen nur Warnungen;
  Messungen werden nie verworfen.

- **Mitgelieferte Schemata** (`tachylog/schemas/`):
  - `gladiator2.json` — Gladiator_2 CCSSSSNNNN (16 Codes, empfohlen am Gerät)
  - `archsurv4qgis.json` — ArchSurv4QGIS XXXXYZZ001
  - `free.json` — kein Schema, alle PIDs erlaubt (Standard)

- **`--schema` Option** für `tachylog collect` — lädt ein Schema zur Laufzeit.
- **`tachylog schemas`** — listet alle verfügbaren Schema-Dateien.
- **`tachylog validate`** — post-hoc PID-Check einer bestehenden Datenbank.

- **GeoJSON CRS-Tag** — GeoJSON-Ausgaben enthalten jetzt ein korrektes `crs`-Feld:
  `{"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::31256"}}`.

- **`--epsg` Option** für `tachylog collect` — EPSG-Code wird als Metadatum
  in die GeoJSON-Ausgabe geschrieben (keine Koordinatentransformation).
  Standard: 31256 (MGI / Austria GK M31).

- **Android Startskript** (`start.sh`) — startet tachyflow und tachylog in einer
  Session, prüft Voraussetzungen, baut tachyflow automatisch beim ersten Start.
  Parameter: `[AUFNAHME] [SCHEMA] [EPSG]`.

- **Termux:Widget Support** — Ein-Tipp-Start vom Android-Homescreen:
  - `tachylog.sh` — Widget-Wrapper für `~/.shortcuts/`
  - `setup-widget.sh` — einmaliges Setup-Skript (Ordner, Permissions, Shortcut-Dialog)
  - `start.sh --widget` — überspringt interaktive Prompts, öffnet Browser automatisch

- **`KONZEPT.md`** — vollständiges Konzeptdokument: Pipeline-Architektur,
  EPSG-Konzept, GNSS-Integration, Schema-Design, UI-Konzept, Roadmap,
  Gladiator Feldkatalog.

### Fixes

- **Duplikat-Erkennung** — Key war `pid + Koordinaten`, jetzt `raw` (exakter
  GSI-String). Nachmessungen am selben Punkt (gleiche PID, gleiche Koordinaten)
  wurden vorher still verworfen — jetzt korrekt gespeichert.

- **Poll-Intervall** — Standard-Wert von 0,5 s auf 0,2 s korrigiert (5 Hz, wie
  in der Spec definiert).

- **Baudrate** — `ConnectionConfig` Standard von 9600 auf 115200 korrigiert
  (korrekt für Leica Flexline Totalstationen).

- **GSI Unit-Code** — Unit 06 (÷10000, GSI16 Koordinaten) und Unit 03 (÷1000,
  GSI8) werden korrekt erkannt und angewendet.

- **GSI Masken** — Maske 2 (Word-Indizes 81/82/83, Koordinaten) wird jetzt vor
  Maske 1 (21/22/31, Winkel) geprüft; verhindert falsche Koordinaten bei
  gemischten Masken.

### Entfernt

- `pid_parser.py`, `feature_builder.py`, `code_table.py` — PID-Parsing und
  Feature-Erzeugung sind Aufgabe der Downstream-Tools (Gladiator, AS4QGIS, QGIS).

- `TotalstationConnection` (`connection.py`) — dead code; der Collector baut
  TCP-Verbindungen direkt über `socket.socket()`. `ConnectionConfig` bleibt.

- `geocom_constants.py` — wurde nur von `TotalstationConnection` verwendet.

- `BuildRun`, `build_runs`-Tabelle (`staging.py`) — kein `tachylog build`-Befehl
  mehr vorhanden.

- `tests/test_pid.py`, `tests/test_build.py`, `tests/test_geocom.py` — testen
  entfernte Module.

- `fiona` / `shapely` Abhängigkeiten — kein GDAL auf Android/Termux verfügbar.

### Tests

- `tests/test_schema_validator.py` — neu, vollständige Abdeckung von `SchemaDef`.
- `tests/test_connection.py` — neu, testet nur noch `ConnectionConfig`.
- `tests/test_staging.py` — `test_pid_is_opaque` ersetzt `test_invalid_pid_too_long`.
- `tests/test_gsi_parser.py` — Testdaten auf korrekten GSI16 Unit 06 umgestellt.
- Alle 59 Tests grün.

---

## [1.0.0] — 2026-04-15

Erste Veröffentlichung.
