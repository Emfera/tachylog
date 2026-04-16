# tachyflow — Konzept & Architekturplan

**Universität Wien · Archäologische Feldvermessung**
**Stand:** 2025 | **Zielgruppe:** Entwickler/Archäologe im Feldkontext

---

## Inhaltsverzeichnis

1. [Pipeline-Architektur (Gesamtbild)](#1-pipeline-architektur-gesamtbild)
2. [EPSG-Konzept](#2-epsg-konzept)
3. [GNSS-Quelle: Emlid Reach Integration](#3-gnss-quelle-emlid-reach-integration)
4. [PID-Format: freies Format, Downstream entscheidet](#4-pid-format-freies-format-downstream-entscheidet)
5. [Schema-Dateien: Optionale Gültigkeitsprüfung](#5-schema-dateien-optionale-gültigkeitsprüfung)
6. [tachyflow UI-Konzept](#6-tachyflow-ui-konzept)
7. [Sofortige Bugs zu fixen](#7-sofortige-bugs-zu-fixen)
8. [Entwicklungs-Roadmap](#8-entwicklungs-roadmap)

---

## 1. Pipeline-Architektur (Gesamtbild)

### 1.1 Überblick

Das System besteht aus zwei Datenquellen (Totalstation und GNSS-Rover), einem gemeinsamen Sammel- und Speicher-Layer (tachyflow als primäre Benutzeroberfläche, tachylog als CLI-Fallback) sowie klar definierten Ausgabeformaten für nachgelagerte Tools. **tachyflow und tachylog interpretieren PIDs nicht** — sie speichern den PID-String unverändert so wie er vom Instrument kommt. Die Auflösung des PID-Formats in Geometrien und Features ist ausschließlich Aufgabe der Downstream-Tools (Gladiator_2, AS4QGIS).

### 1.2 ASCII-Diagramm

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                          DATENQUELLEN (Feld)                                ║
╠═══════════════════════════╦════════════════════════════════════════════════╣
║   Leica TS07               ║   Emlid Reach RS2 / RX                        ║
║   (Totalstation)           ║   (GNSS-Rover)                                ║
║                            ║                                                ║
║  Bluetooth / USB-Serial    ║   Option A: Emlid Flow → CSV-Export           ║
║        ↓                   ║   Option B: NMEA-Stream via TCP/UDP           ║
║  TCP-Bridge (GeoMax        ║   Option C: Emlid ReachView API               ║
║  Zipp20 / eigener          ║        ↓                                       ║
║  BT-to-TCP-Adapter)        ║   CSV-Import / NMEA-Parser (tachyflow)        ║
║        ↓                   ║        ↓                                       ║
║  GSI-String über TCP       ║   Normalisierter Punkt-Datensatz               ║
║  %R1Q,2115:\r\n            ║   {pid, easting, northing, elevation,          ║
║  → GSI8/16-Response        ║    source: "gnss", timestamp}                  ║
╚═══════════════════════════╩════════════════════════════════════════════════╝
           ↓                                      ↓
╔══════════════════════════════════════════════════════════════════════════════╗
║                    SAMMEL- UND VERARBEITUNGS-LAYER                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  tachyflow (primär — Web-UI, Tablet/Laptop im Feld)                         ║
║  ┌────────────────────────────────────────────────────────────────────────┐ ║
║  │ Session-Konfiguration: Name, EPSG-Code, Ausgabeformate, Quelle(n)     │ ║
║  │ Collector-Thread(s): TS07-TCP-Collector + GNSS-Collector (parallel)   │ ║
║  │ Normalisierungsschicht: gemeinsames Point-Schema für alle Quellen     │ ║
║  │ SQLite (sql.js): sessions + points (mit epsg_code, source-Feld)       │ ║
║  │ WebSocket: Live-Updates → React-Frontend                               │ ║
║  │ Export-Engine: CSV / GeoJSON / GeoPackage mit EPSG-Metadaten          │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
║                                                                              ║
║  tachylog (CLI-Fallback / TS07-only / Offline-Skript)                       ║
║  ┌────────────────────────────────────────────────────────────────────────┐ ║
║  │ collector.py → gsi_parser.py → staging.py (SQLite)                    │ ║
║  │ output.py: CSV / GSI / GeoJSON / GeoPackage                            │ ║
║  │ Kein pid_parser.py, kein feature_builder.py (entfallen)                │ ║
║  └────────────────────────────────────────────────────────────────────────┘ ║
╚══════════════════════════════════════════════════════════════════════════════╝
           ↓
╔══════════════════════════════════════════════════════════════════════════════╗
║                         AUSGABE-FORMATE                                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  CSV (AS4QGIS- und Gladiator_2-kompatibel)                                  ║
║  └─ Dateiname: aufnahme_20250615_epsg31256.csv                              ║
║  └─ Header: # EPSG:31256 | Session: aufnahme_20250615 | Source: ts07+gnss  ║
║  └─ Spalten: point_id, code, easting, northing, elevation, timestamp,       ║
║              source, epsg_code                                               ║
║                                                                              ║
║  GeoJSON (RFC 7946-konform mit CRS-Erweiterung)                             ║
║  └─ Dateiname: aufnahme_20250615_epsg31256.geojson                          ║
║  └─ crs: {"type":"name","properties":{"name":"urn:ogc:def:crs:EPSG::31256"}}║
║                                                                              ║
║  GeoPackage (OGC-konform)                                                   ║
║  └─ Dateiname: aufnahme_20250615_epsg31256.gpkg                             ║
║  └─ gpkg_spatial_ref_sys: korrekte EPSG-Einträge (nicht hardcodiert 4326)  ║
║                                                                              ║
║  GSI (Rohformat, Archivzwecke)                                              ║
║  └─ Dateiname: aufnahme_20250615.gsi                                        ║
║  └─ Kein EPSG-Feld (Format unterstützt es nicht), Session-Kommentar reicht ║
╚══════════════════════════════════════════════════════════════════════════════╝
           ↓
╔══════════════════════════════════════════════════════════════════════════════╗
║                         DOWNSTREAM-TOOLS                                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Gladiator_2 (QGIS-Plugin) — primäres Downstream-Tool                      ║
║  └─ PID-Format: CCSSSSNNNN (z.B. OT00010001)                               ║
║  └─ Objektbildung: Codes → Punkte / Linien / Polygone                      ║
║  └─ Import: CSV (point_id, code, easting, northing, elevation)              ║
║                                                                              ║
║  AS4QGIS (QGIS-Plugin) — alternatives Downstream-Tool                      ║
║  └─ Delimited Text Import mit EPSG aus Dateiname / Header                   ║
║  └─ Spaltenformat: point_id, code, easting, northing, elevation             ║
║                                                                              ║
║  Eigene QGIS-Pipeline                                                        ║
║  └─ GeoPackage direkt laden, CRS automatisch aus srs_id erkannt             ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### 1.3 Normalisiertes Point-Schema (intern)

Alle Quellen erzeugen denselben Datensatz:

```typescript
interface NormalizedPoint {
  id: number;                    // DB-Autoincrement
  session_id: number;            // FK → sessions
  point_id: string;              // PID — opaker String vom Instrument, unverändert
  code: string;                  // Archäologischer Code (aus PID extrahiert oder separat)
  easting: number;               // E-Koordinate (unverändert vom Gerät)
  northing: number;              // N-Koordinate (unverändert vom Gerät)
  elevation: number;             // Höhe (unverändert vom Gerät)
  timestamp: string;             // ISO 8601
  source: "ts07" | "gnss";       // Herkunft des Punktes
  raw: string | null;            // Roh-String (GSI-Zeile oder NMEA-Satz)
  epsg_code: number;             // Aus Session übernommen (z.B. 31256)
}
```

**Wichtig:** `point_id` wird nicht geparst, nicht validiert und nicht interpretiert. tachyflow und tachylog sind Sammler — kein PID-Format ist vorgeschrieben. Die Länge des PID-Strings wird nicht geprüft.

---

## 2. EPSG-Konzept

### 2.1 Grundprinzip

tachyflow ist **kein Transformations-Tool**. Koordinaten kommen so wie sie vom Gerät geliefert werden. Der EPSG-Code ist reine Metadaten-Angabe, die dem Benutzer und den nachgelagerten Tools mitteilt, in welchem Koordinatensystem die Daten vorliegen.

### 2.2 Eingabe (tachyflow UI)

Der EPSG-Code wird einmalig beim **Erstellen einer Session** angegeben:

```
[ Session-Setup ]
  Name:       aufnahme_schnitt_a
  Datum:      2025-06-15 (auto)
  EPSG-Code:  [31256]  ← Pflichtfeld mit Dropdown-Vorschlägen
                          (31256 = MGI/Austria GK M31 — vorausgewählt)
                          (31255 = MGI/Austria GK M28)
                          (custom: Freitext-Eingabe)
  Quellen:    [✓] TS07  [ ] GNSS
  Formate:    [✓] CSV  [✓] GeoJSON  [ ] GeoPackage  [ ] GSI
```

Wichtig: Der EPSG-Code ist nach Session-Start **nicht mehr editierbar** (verhindert inkonsistente Datensätze mid-session).

### 2.3 Speicherung in SQLite

**Tabelle: sessions**

```sql
CREATE TABLE sessions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  epsg_code   INTEGER NOT NULL,     -- z.B. 31256
  started_at  TEXT NOT NULL,        -- ISO 8601
  ended_at    TEXT,
  sources     TEXT,                 -- JSON: ["ts07","gnss"]
  formats     TEXT                  -- JSON: ["csv","geojson"]
);
```

**Tabelle: points**

```sql
CREATE TABLE points (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id  INTEGER NOT NULL REFERENCES sessions(id),
  point_id    TEXT NOT NULL,        -- opaker String, keine Längenvalidierung
  code        TEXT,
  easting     REAL NOT NULL,
  northing    REAL NOT NULL,
  elevation   REAL NOT NULL,
  timestamp   TEXT NOT NULL,
  source      TEXT NOT NULL,        -- "ts07" oder "gnss"
  raw         TEXT,
  epsg_code   INTEGER NOT NULL      -- Kopie aus Session für Standalone-Zugriff
);
```

Der `epsg_code` wird redundant in jedem Punkt gespeichert, damit ein Export ohne Session-Kontext möglich ist (z.B. wenn nur die points-Tabelle exportiert wird).

### 2.4 Einbettung in Ausgabeformate

#### CSV

Dateiname: `{session_name}_epsg{epsg_code}.csv`

```
# tachyflow export | session: aufnahme_schnitt_a | epsg: 31256 | date: 2025-06-15
# source: ts07+gnss
point_id,code,easting,northing,elevation,timestamp,source,epsg_code
OT00010001,OT,688432.123,340521.456,287.34,2025-06-15T09:14:22Z,ts07,31256
OT00010002,OT,688433.001,340522.100,287.31,2025-06-15T09:14:55Z,ts07,31256
```

Strategie:
- **Dateiname-Suffix** `_epsg31256` → für AS4QGIS- und Gladiator_2-Workflow erkennbar
- **Kommentar-Header** (Zeilen mit `#`) → wird von den meisten CSV-Tools ignoriert, aber ist menschenlesbar
- **Spalte `epsg_code`** → maschinenlesbar, kann von Skripten ausgewertet werden

#### GeoJSON

```json
{
  "type": "FeatureCollection",
  "crs": {
    "type": "name",
    "properties": {
      "name": "urn:ogc:def:crs:EPSG::31256"
    }
  },
  "properties": {
    "tachyflow_session": "aufnahme_schnitt_a",
    "epsg_code": 31256,
    "exported_at": "2025-06-15T18:00:00Z"
  },
  "features": [...]
}
```

Hinweis: RFC 7946 depreciert das `crs`-Feld, da es WGS84 voraussetzt. Für lokale Koordinatensysteme (MGI, Gauß-Krüger) ist WGS84 falsch — der `crs`-Eintrag nach alter GeoJSON-Spec (IETF RFC) ist hier pragmatisch notwendig und wird von QGIS, GDAL und den meisten GIS-Tools korrekt interpretiert. Dies ist zu dokumentieren.

#### GeoPackage

```python
# Korrekte EPSG-Einbettung (Bug-Fix für tachylog)
import sqlite3

def write_gpkg_srs(conn, epsg_code):
    # Lookup: echter WKT-String für den EPSG-Code
    # Nicht hardcodiert 4326!
    conn.execute("""
        INSERT OR REPLACE INTO gpkg_spatial_ref_sys
        (srs_name, srs_id, organization, organization_coordsys_id, definition)
        VALUES (?, ?, 'EPSG', ?, ?)
    """, (f"EPSG:{epsg_code}", epsg_code, epsg_code, get_wkt_for_epsg(epsg_code)))
```

Die Funktion `get_wkt_for_epsg()` kann via `pyproj` (`CRS.from_epsg(code).to_wkt()`) implementiert werden. In tachyflow (Node.js) via `proj4` oder `@turf/projection`.

#### GSI

Das GSI-Format hat kein natives Metadaten-Feld für CRS. Lösung: EPSG-Code im GSI-Kommentarfeld der ersten Zeile (falls das Format einen Kommentar-Header erlaubt) oder im Dateinamen. Kein weiterer Handlungsbedarf — GSI ist Archivformat.

---

## 3. GNSS-Quelle: Emlid Reach Integration

### 3.1 Optionen im Überblick

| Option | Bezeichnung | Beschreibung |
|--------|------------|--------------|
| A | CSV-Import | Emlid Flow exportiert CSV, User importiert manuell in tachyflow |
| B | NMEA-Stream | Emlid Reach streamt NMEA via TCP/UDP, tachyflow liest direkt |
| C | ReachView3-API | Emlid-proprietäre HTTP-API (undokumentiert) |
| D | NTRIP/RTCM-Feed | Nur Korrekturdaten, keine Positions-Ausgabe — irrelevant |

### 3.2 Detailbewertung

#### Option A: Emlid Flow → CSV-Import (empfohlen für Phase 1)

**Workflow:**
1. Messung in Emlid Flow durchführen (wie bisher)
2. CSV exportieren aus Emlid Flow
3. In tachyflow: "GNSS-Import" → CSV hochladen → Points werden der aktiven Session hinzugefügt

**Emlid Flow CSV-Format (bekannt):**
```
id,name,easting,northing,elevation,timestamp,source
1,FP0001,688432.123,340521.456,287.34,2025-06-15T09:14:22Z,emlid_reach
```

**Mapping auf tachyflow-Schema:**
- `name` → `point_id` (Benutzer gibt PID im gewünschten Format ein — Gladiator_2 oder AS4QGIS)
- `easting/northing/elevation` → direkt übernommen
- `source` → fest "gnss"
- `epsg_code` → aus aktiver Session

**Bewertung:**
- Robustheit: ★★★★★ (kein Live-Netzwerk nötig, kein Protokoll-Parsing)
- Komplexität: ★★★★★ (simpler CSV-Parser, ein Import-Button)
- Benutzerfreundlichkeit: ★★★ (manueller Export-Schritt, asynchron zur TS07-Erfassung)
- **Geeignet als sofortige Lösung für Phase 1 und 2**

#### Option B: NMEA-Stream via TCP/UDP (empfohlen für Phase 2)

**Workflow:**
- Emlid Reach RS2/RX sendet NMEA-0183 via TCP auf konfigurierbarem Port (Standard: 9001)
- tachyflow öffnet zusätzlichen TCP-Client neben dem TS07-Collector
- Parsed NMEA GGA/GGK-Sätze → normalisierter Point-Datensatz

**Relevante NMEA-Sätze:**
```
$GPGGA,091422.00,4805.3987,N,01553.2687,E,4,12,0.8,287.34,M,...*checksum
```
- `GGA`: Position (lat/lon WGS84) + Höhe → **Problem: immer WGS84, nicht lokales Gitternetz**
- `GGK`: Leica-proprietäre Erweiterung mit kartesischen Koordinaten
- `GNS`: Multi-GNSS-Erweiterung

**Kritisches Problem mit Option B:**
NMEA gibt Koordinaten in WGS84 (Grad/Minuten). Für lokales Gitternetz (MGI) wäre eine Transformation nötig — aber Transformationen sind explizit ausgeschlossen. 

**Ausnahme:** Der Emlid Reach kann im ReachView3 so konfiguriert werden, dass er im Ausgabeformat "lokale Koordinaten" streamt, wenn ein lokales Koordinatensystem eingestellt ist. Dies ist geräteseitig möglich, aber erfordert Setup am Gerät.

Alternative: NMEA-Stream mit WGS84 empfangen, als `source: "gnss"` speichern, EPSG-Code auf 4326 setzen für GNSS-Punkte — dann aber zwei verschiedene CRS in einer Session, was AS4QGIS nicht unterstützt.

**Bewertung:**
- Robustheit: ★★★ (WiFi/BT-Verbindung nötig, Verbindungsabbrüche)
- Komplexität: ★★★ (NMEA-Parser implementieren, CRS-Problem lösen)
- Benutzerfreundlichkeit: ★★★★ (Echtzeit-Integration, kein manueller Export)
- **Geeignet für Phase 2, nur wenn lokale Koordinaten-Ausgabe am Gerät konfiguriert**

#### Option C: Emlid ReachView3-API

**Status:** Nicht öffentlich dokumentiert. Emlid bietet keine offizielle REST-API für Dritte.

**Bewertung:**
- Robustheit: ★ (nicht supportet, kann sich ändern)
- Komplexität: ★ (Reverse-Engineering nötig)
- Benutzerfreundlichkeit: potenziell hoch
- **Nicht empfohlen — zu fragil**

### 3.3 Empfehlung

**Phase 1:** Option A (CSV-Import). Kein Code für NMEA-Parsing nötig, funktioniert sofort, robust.

**Phase 2:** Option B, aber nur wenn:
1. Am Emlid-Gerät lokale Koordinaten-Ausgabe konfiguriert ist (MGI GK), oder
2. GNSS-Punkte explizit als WGS84 gespeichert werden (separate EPSG 4326 pro GNSS-Punkt) und die Ausgabe entsprechend getrennt oder transformiert wird — was dann doch ein Transformations-Feature wäre.

**Pragmatische Empfehlung:** Option A bleibt auch in Phase 2 vollständig nutzbar. Der manuelle Export-Schritt aus Emlid Flow ist im Feldkontext kein wesentlicher Mehraufwand, wenn die Messung ohnehin in zwei Phasen (TS07-Erfassung und GNSS-Verdichtung) abläuft.

---

## 4. PID-Format: freies Format, Downstream entscheidet

### 4.1 Grundprinzip

**tachylog und tachyflow verwenden kein vorgeschriebenes PID-Format.**

Der PID ist ein opaker String, den das Instrument liefert. tachylog und tachyflow speichern ihn unverändert. Es gibt keinen Parser, keine Validierung und keine Interpretation des PID-Inhalts. Das Downstream-Tool (Gladiator_2, AS4QGIS oder eine eigene QGIS-Pipeline) entscheidet, wie der PID zu lesen ist und welche Geometrien daraus zu bauen sind.

**Konsequenz für tachylog-Code:**

| Datei | Status |
|-------|--------|
| `pid_parser.py` | **entfällt komplett** |
| `feature_builder.py` | **entfällt komplett** (Geometriebau = Aufgabe von Downstream-Tools) |
| `code_table.py` | **entfällt komplett** |
| `cli.py` — `validate`-Befehl | **entfällt** |
| `cli.py` — `codes`-Befehl | **entfällt** |
| `gsi_parser.py` | bleibt, `_gsi_to_pid()` entfernt nur führende Nullen/Sonderzeichen, prüft kein Format |
| `staging.py` | `StagingPoint.pid` bleibt `TEXT NOT NULL`, keine Längenvalidierung |
| `collector.py` | bleibt unverändert |
| `output.py` | bleibt unverändert |
| `connection.py` | bleibt (bereinigt, toter Code entfernt) |
| `cli.py` | reduziert auf: `collect`, `import`, `build`, `info` |

### 4.2 Gladiator_2-Format: empfohlenes PID-Format für den Feldvermesser

**Gladiator_2** ist ein QGIS-Plugin für Ausgrabungsdokumentation und das primäre Downstream-Tool dieser Pipeline. Es erwartet PIDs im Format `CCSSSSNNNN`:

```
Format: CCSSSSNNNN
         ││    └──── 4-stellige Sequenznummer (0001, 0002, …)
         │└───────── 4-stellige SE-ID (Stratigraphische Einheit / Feature)
         └─────────── 2-Buchstaben-Code (semantischer Typ, s. Tabelle unten)

Beispiel: OT00010001  →  Outline Top, SE 0001, Punkt 1
          BL00370003  →  Break Line, SE 0037, Punkt 3
          FP00120001  →  Find Point, SE 0012, Punkt 1
```

**Warum Gladiator-Format für den Feldvermesser besser ist als AS4QGIS:**
- `OT00010001` ist intuitiver als `0001A03001` (AS4QGIS)
- Der Code ist semantisch lesbar (nicht numerisch kodiert)
- Der Geometrietyp steckt im Code selbst — kein Shape-Type-Zahlenschlüssel nötig
- Kürzere Eindenkhilfe, weniger Eingabefehler am Instrument

Eine vollständige Referenz mit Codetabelle und Objektbildungsregeln findet sich in **Anhang D**.

### 4.3 AS4QGIS-Format: alternatives PID-Format

AS4QGIS verwendet das Format `XXXXYZZ###` (4-stellige Feature-Nummer, Container-Buchstabe, 2-stelliger Shape-Type-Code, 3-stellige Sequenznummer). Es bleibt als zweites unterstütztes Downstream-Tool bestehen.

Da tachyflow und tachylog keine PIDs interpretieren, ist die exportierte CSV (`point_id`, `code`, `easting`, `northing`, `elevation`) für beide Tools verwendbar — das Downstream-Tool wählt der Benutzer. Eine vollständige Formatreferenz findet sich in **Anhang B**.

### 4.4 Praxis-Empfehlung

Für neue Projekte: **Gladiator_2-Format verwenden** (`CCSSSSNNNN`). Der laminierte Feldspickzettel in Anhang D gibt die wichtigsten Codes auf einen Blick.

Für Projekte, die bereits AS4QGIS-Daten haben oder AS4QGIS als QGIS-Plugin nutzen: **AS4QGIS-Format beibehalten** (`XXXXYZZ###`). tachyflow unterstützt beides ohne Anpassung.

---

## 5. Schema-Dateien: Optionale Gültigkeitsprüfung

### 5.1 Grundprinzip

tachylog speichert immer alle Messungen — unabhängig von PID-Format oder Code. Schemata sind **optional und nicht-blockierend**: sie ermöglichen Warnungen im Feld ("unbekannter Code"), aber nie einen Abbruch oder Datenverlust.

Das Schema beschreibt ein Downstream-Tool: welches PID-Format es erwartet, welche Codes es kennt, welche Geometrie jedem Code zugeordnet ist. Die Schema-Datei ist das maschinenlesbare Äquivalent des Feldspickzettels.

### 5.2 Schema-Dateiformat (JSON)

```json
{
  "name": "Gladiator_2",
  "version": "1.0",
  "pid_format": "CCSSSSNNNN",
  "pid_length": 10,
  "codes": [
    { "code": "OT", "geometry": "polygon", "label": "Outline Top" },
    { "code": "OB", "geometry": "polygon", "label": "Outline Bottom" },
    { "code": "ST", "geometry": "point",   "label": "Surface Top" },
    { "code": "SB", "geometry": "point",   "label": "Surface Bottom" },
    { "code": "BL", "geometry": "line",    "label": "Break Line" },
    { "code": "LE", "geometry": "polygon", "label": "Limits Excavation" },
    { "code": "HP", "geometry": "point",   "label": "Survey Point" },
    { "code": "CP", "geometry": "point",   "label": "Control Point" },
    { "code": "CL", "geometry": "line",    "label": "Crosssection Line" },
    { "code": "PP", "geometry": "point",   "label": "Photogrammetric Point" },
    { "code": "PD", "geometry": "point",   "label": "Photogrammetric Detail Point" },
    { "code": "DL", "geometry": "line",    "label": "Diverse Line" },
    { "code": "RP", "geometry": "point",   "label": "Reference Point" },
    { "code": "TP", "geometry": "point",   "label": "Temporary Point" },
    { "code": "FP", "geometry": "point",   "label": "Find Point" },
    { "code": "PS", "geometry": "point",   "label": "Point Sample" }
  ],
  "grouping": {
    "key": ["code", "se_id"],
    "sequence_field": "seq"
  },
  "export": {
    "csv_columns": ["point_id", "code", "easting", "northing", "elevation"],
    "filename_suffix": true
  }
}
```

Ein zweites Schema `archsurv4qgis.json` beschreibt das AS4QGIS-Format mit identischer Struktur, aber anderen Codes (`pid_format: "XXXXYZZ001"`, `pid_length: 10`).

### 5.3 Schema-Bibliothek im Repository

```
tachylog/schemas/
  gladiator2.json       ← Standard für Uni Wien
  archsurv4qgis.json    ← Alternative
  free.json             ← Kein Schema, reine Sammlung (Default wenn kein --schema angegeben)
```

`free.json` enthält nur `{"name": "free", "pid_length": null, "codes": []}` — signalisiert: keine Prüfung.

### 5.4 Verwendung in tachylog (CLI)

```bash
# Ohne Schema — alles wird gespeichert, keine Prüfung (Default)
tachylog collect --port tcp://localhost:4444 --db aufnahme.db

# Mit Schema — Warnungen bei unbekanntem Code oder falscher PID-Länge
tachylog collect --port tcp://localhost:4444 --db aufnahme.db \
  --schema schemas/gladiator2.json
```

Was die Prüfung macht (nur Warnungen, kein Abbruch):
- PID-Länge stimmt nicht → `[WARN] PID 'LE01' hat 4 statt 10 Zeichen`
- Code unbekannt → `[WARN] Code 'XX' nicht in Schema 'Gladiator_2'`
- PID-Format stimmt nicht (Regex) → `[WARN] PID 'ABC123' entspricht nicht Format CCSSSSNNNN`

Was sie **nicht** macht:
- Messung verwerfen oder überspringen
- Collector stoppen oder pausieren
- Fehler ausgeben (immer nur Warnungen)

Warnungen werden in der Feldanzeige angezeigt und optional in eine Log-Datei geschrieben (`--log warn.log`).

### 5.5 Schema-Validator (Implementierung)

Ein schlankes Python-Modul `schema_validator.py`:

```python
# tachylog/schema_validator.py
import json, re
from dataclasses import dataclass
from typing import Optional

@dataclass
class SchemaDef:
    name: str
    pid_length: Optional[int]       # None = keine Längenbeschränkung
    pid_pattern: Optional[re.Pattern] # None = kein Regex
    known_codes: set[str]           # Leere Menge = keine Code-Prüfung
    code_geometry: dict[str, str]   # code → "point" | "line" | "polygon"

    @classmethod
    def load(cls, path: str) -> "SchemaDef":
        data = json.loads(open(path).read())
        pid_len = data.get("pid_length")
        pid_fmt = data.get("pid_format")
        codes = data.get("codes", [])
        return cls(
            name=data.get("name", "unnamed"),
            pid_length=pid_len,
            pid_pattern=_compile_pattern(pid_fmt) if pid_fmt else None,
            known_codes={c["code"].upper() for c in codes},
            code_geometry={c["code"].upper(): c["geometry"] for c in codes},
        )

    @classmethod
    def free(cls) -> "SchemaDef":
        """Kein Schema — keine Prüfung."""
        return cls(name="free", pid_length=None, pid_pattern=None,
                   known_codes=set(), code_geometry={})

    def validate(self, pid: str) -> list[str]:
        """Gibt Liste von Warnungen zurück (leer = alles ok)."""
        warnings = []
        if self.pid_length and len(pid) != self.pid_length:
            warnings.append(
                f"PID '{pid}' hat {len(pid)} statt {self.pid_length} Zeichen"
            )
        if self.pid_pattern and not self.pid_pattern.match(pid):
            warnings.append(f"PID '{pid}' entspricht nicht Format {self.name}")
        if self.known_codes:
            code = pid[:2].upper() if len(pid) >= 2 else pid.upper()
            if code not in self.known_codes:
                warnings.append(f"Code '{code}' nicht in Schema '{self.name}'")
        return warnings

def _compile_pattern(fmt: str) -> re.Pattern:
    """Konvertiert PID-Format-String in Regex. C=Buchstabe, S/N=Ziffer."""
    mapping = {"C": "[A-Z]", "S": r"\d", "N": r"\d", "X": r"\d", "Y": "[A-Z]", "Z": r"\d"}
    pattern = "".join(mapping.get(c, re.escape(c)) for c in fmt)
    return re.compile(f"^{pattern}$", re.IGNORECASE)
```

Integration in `collector.py`: nach erfolgreichem GSI-Parse wird `schema.validate(measurement.pid)` aufgerufen. Warnungen werden auf stdout ausgegeben (mit Zeitstempel), Messung wird trotzdem gespeichert.

### 5.6 Verwendung in tachyflow (Phase 2+)

In Phase 1 ist das Schema noch nicht in tachyflow integriert. Die Schema-Datei kann aber bereits mitgeliefert werden. In Phase 2:

- **Session-Setup**: Dropdown "Zielschema" (`Gladiator_2` / `AS4QGIS` / `Kein Schema`)
- **Live-Karte**: Farbcodierung nach Geometrietyp (Polygon-Codes → orange, Linien → blau, Punkte → grau)
- **Punktliste**: Warnungs-Icon bei PIDs die nicht dem Schema entsprechen
- **Export**: Schema-Name in CSV-Kommentar-Header und GeoPackage-Metadaten

Das Schema steuert also nicht nur Validierung, sondern auch UI-Darstellung und Export-Metadaten.

---

## 6. tachyflow UI-Konzept

### 6.1 Leitbild

Orientierung an der Sammelphase von Emlid Flow: **klare, große Bedienelemente, minimale Kognitionslast im Feld** (Sonne, Handschuhe, geteilte Aufmerksamkeit). Kein Gerätekonfigurations-Tool — nur Datensammlung und Überblick.

### 6.2 Screen-Struktur

```
┌─────────────────────────────────────────────────┐
│  [≡]  tachyflow          Session: schnitt_a  [•] │  ← Header
├─────────────────────────────────────────────────┤
│                                                 │
│           [SCREEN-CONTENT]                      │
│                                                 │
├─────────────────────────────────────────────────┤
│  [Session]   [Karte]   [Punkte]   [Export]      │  ← Bottom-Nav
└─────────────────────────────────────────────────┘
```

### 6.3 Screens im Detail

#### Screen 1: Session-Setup (Start-Screen)

**Essential:**
- Session-Name (Textfeld, auto-vorgeschlagen: Datum+Ort)
- EPSG-Code (Dropdown mit Favoriten + Freitext)
- Datenquelle(n): TS07 (TCP-Host, Port) / GNSS (CSV-Import)
- Ausgabeformate: CSV, GeoJSON, GeoPackage, GSI (Checkboxen)
- [Session starten]-Button (groß, prominent)

**Nice-to-have:**
- Letzte Session als Vorlage laden
- Verbindungstest vor Session-Start (Ping an TS07-TCP-Bridge)

**Explizit NICHT rein:**
- Gerätekonfiguration (Leica-Einstellungen, GNSS-Korrekturdaten)
- Netzwerk-Diagnose-Tools
- Benutzer-/Rechteverwaltung

#### Screen 2: Live-Karte (Haupt-Screen während Messung)

**Essential:**
- Canvas 2D mit allen bisher gemessenen Punkten als **Scatter-Plot** (Punkte, keine Feature-Gruppierung)
- Letzter gemessener Punkt hervorgehoben (größerer Kreis, andere Farbe)
- Session-Status: [●] LIVE / [○] Verbindung getrennt
- Punktzähler: "47 Punkte gespeichert"
- Quellen-Indikator: TS07 / GNSS (mit farblicher Unterscheidung)
- Echtzeit-Koordinatenanzeige des letzten Punktes (E/N/H)

**Nice-to-have:**
- Zoom/Pan-Gesten
- Maßstabsbalken

**Explizit NICHT rein:**
- Hintergrundkarte (kein Internet im Feld, falsches CRS)
- Messung manuell starten/stoppen (Polling läuft kontinuierlich)
- Attribute editieren
- Feature-Linien / Polygon-Rekonstruktion (Objektbildung = Downstream-Aufgabe)

#### Screen 3: Punktliste

**Essential:**
- Tabellarische Liste aller Punkte der aktuellen Session
- Spalten: #, point_id, code, E, N, H, Quelle (Icon), Zeit
- Neuester Punkt oben (auto-scroll)
- Suchfeld / Filter nach PID oder Code

**Nice-to-have:**
- Einzelpunkt löschen (mit Bestätigung)

**Explizit NICHT rein:**
- Koordinaten editieren
- Neupunkte manuell eingeben (das ist Sache des Instruments)
- PID-Formatvalidierung (kein Parser vorhanden)

#### Screen 4: GNSS-Import

**Essential:**
- "CSV-Datei wählen"-Button (Datei-Browser)
- Vorschau der importierten Punkte (erste 10 Zeilen)
- Spalten-Mapping-Dialog (falls Spaltenbezeichnungen abweichen)
- [Import bestätigen]-Button

**Nice-to-have:**
- Duplikat-Erkennung (gleiche PID bereits in Session)
- Zusammenfassung nach Import: "12 Punkte importiert, 0 Fehler"

#### Screen 5: Export

**Essential:**
- Ausgabeformate-Auswahl (vorbelegt aus Session-Einstellungen)
- Dateiname-Vorschau (inkl. EPSG-Suffix)
- [Exportieren]-Button
- Download-Link / Datei-Öffnen nach Export

**Nice-to-have:**
- Export-Verlauf (letzte 5 Exporte mit Zeitstempel)
- Direkt-Share via OS (Android/iOS Share-Sheet)

#### Globale UI-Elemente

**Essential:**
- Verbindungs-Status dauerhaft sichtbar (Header)
- Session beenden / neue Session starten (immer erreichbar)

**Nice-to-have:**
- Dark Mode (Nacht-Ausgrabungen)
- Sprachauswahl (DE/EN)

**Explizit NICHT rein:**
- Benutzerverwaltung / Login
- Cloud-Sync (Offline-first ist Pflicht)
- Gerätekonfiguration (Leica-Menü, Emlid-Setup)
- CRS-Transformation
- Post-Processing (Objektbildung → ausschließlich Downstream-Tools)

---

## 7. Sofortige Bugs zu fixen

### Priorität 1 — Blockiert produktiven Einsatz

#### Bug 1: GeoPackage srs_id hardcodiert auf 4326 (tachylog/output.py)

**Problem:** GeoPackage wird mit `srs_id=4326` (WGS84) erstellt, obwohl lokale Gitterkoordinaten (z.B. MGI EPSG:31256) vorliegen. Jedes GIS-Tool interpretiert die Koordinaten im falschen CRS.

**Fix:**
```python
# output.py
import pyproj

def get_wkt_for_epsg(epsg_code: int) -> str:
    crs = pyproj.CRS.from_epsg(epsg_code)
    return crs.to_wkt()

def write_to_geopackage(points, epsg_code: int, output_path: str):
    conn = sqlite3.connect(output_path)
    # gpkg_spatial_ref_sys korrekt befüllen
    conn.execute("""
        INSERT OR REPLACE INTO gpkg_spatial_ref_sys
        (srs_name, srs_id, organization, organization_coordsys_id, definition, description)
        VALUES (?, ?, 'EPSG', ?, ?, '')
    """, (f"EPSG:{epsg_code}", epsg_code, epsg_code, get_wkt_for_epsg(epsg_code)))
    # Layer mit korrekter srs_id registrieren
    conn.execute("""
        INSERT INTO gpkg_contents (table_name, data_type, srs_id)
        VALUES ('points', 'features', ?)
    """, (epsg_code,))
```

**Aufwand:** 2–4 Stunden

#### Bug 2: GeoJSON ohne CRS (tachylog/output.py)

**Problem:** Exportiertes GeoJSON hat kein `crs`-Feld. RFC 7946 impliziert WGS84 — lokale Koordinaten werden von GIS-Tools im falschen CRS angezeigt.

**Fix:**
```python
# output.py — GeoJSON-Export
def write_geojson(points, epsg_code: int, output_path: str):
    feature_collection = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {
                "name": f"urn:ogc:def:crs:EPSG::{epsg_code}"
            }
        },
        "features": [point_to_feature(p) for p in points]
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(feature_collection, f, ensure_ascii=False, indent=2)
```

**Aufwand:** 1–2 Stunden

#### Bug 3: TotalstationConnection toter Code (tachylog/connection.py)

**Problem:** `TotalstationConnection` ist definiert aber wird nirgendwo verwendet — collector.py implementiert die TCP-Verbindung redundant inline. Führt zu Verwirrung und doppeltem Code.

**Fix:** Entweder `connection.py` löschen und dokumentieren dass collector.py die Verbindung direkt hält, oder collector.py refaktorieren um `TotalstationConnection` zu verwenden. Da der Polling-Loop sehr einfach ist, ist Löschen die pragmatischere Option.

**Aufwand:** 30 Minuten

### Priorität 2 — Sollte vor erstem Produktivbetrieb behoben sein

#### Bug 4: EPSG-Code fehlt in tachyflow-Session (tachyflow/server/storage.ts)

**Problem:** Die Session-Tabelle in tachyflow speichert keinen EPSG-Code. Alle Exporte haben kein CRS.

**Fix:** Schema-Migration hinzufügen:
```typescript
// storage.ts
db.run(`ALTER TABLE sessions ADD COLUMN epsg_code INTEGER DEFAULT 31256`);
```
Und Session-Erstellungs-Dialog um EPSG-Pflichtfeld erweitern.

**Aufwand:** 3–5 Stunden (Schema + UI + Export-Logic)

#### Bug 5: CSV-Export ohne AS4QGIS-kompatible Spalten (tachyflow)

**Problem:** Aktueller CSV-Export hat möglicherweise andere Spaltenbezeichnungen als AS4QGIS und Gladiator_2 erwarten (`point_id`, `code`, `easting`, `northing`, `elevation`).

**Fix:** Export-Funktion auf Standardspaltenformat ausrichten. Kommentar-Header mit EPSG hinzufügen.

**Aufwand:** 1–2 Stunden

---

## 8. Entwicklungs-Roadmap

### Phase 1: Minimal Viable Field Tool

**Ziel:** Erste echte Grabung mit tachyflow als TS07-Datensammler und manuellem GNSS-CSV-Import. Ausgabe Gladiator_2- und AS4QGIS-kompatibel.

**Voraussetzungen (Bugs müssen gefixt sein):**
- [x] Bug 1: GeoPackage CRS korrekt
- [x] Bug 2: GeoJSON CRS korrekt
- [x] Bug 4: EPSG-Code in tachyflow-Session
- [x] Bug 5: CSV-Spalten kompatibel

**Neue Features:**
1. **EPSG-Code in Session-Setup** (Pflichtfeld, Dropdown mit MGI-Varianten)
2. **EPSG in alle Exportformate** (CSV-Header + Spalte + Dateiname-Suffix, GeoJSON crs, GeoPackage srs_id)
3. **GNSS-CSV-Import** (Screen 4): Datei hochladen, Vorschau, Import in aktive Session
4. **tachylog bereinigen**: pid_parser.py, feature_builder.py, code_table.py entfernen; validate- und codes-Befehl aus CLI entfernen
5. **Export testen** (Endabnahme: CSV direkt in Gladiator_2 und AS4QGIS laden, CRS stimmt)

**Deliverable:** tachyflow v0.1 — läuft auf Laptop im Feld, TS07 via TCP-Bridge, GNSS via CSV-Import, Export als `aufnahme_epsg31256.csv` direkt in Gladiator_2 und AS4QGIS ladbar.

**Zeitschätzung:** 2–3 Wochen Entwicklung (1 Entwickler, Teilzeit)

---

### Phase 2: Homogenisierte GNSS+TS Pipeline

**Ziel:** Echtzeit-NMEA-Integration (wenn möglich), robustere Session-Verwaltung, Mobile-taugliche UI.

**Features:**
1. **NMEA-TCP-Collector** (Option B): paralleler Collector-Thread für Emlid NMEA-Stream, wenn Gerät auf lokale Koordinaten konfiguriert ist
2. **Quellen-Indikator in Karte**: TS07-Punkte (blau) vs. GNSS-Punkte (grün), farblich unterschieden
3. **Session-History**: Liste vergangener Sessions, nachträglicher Export möglich
4. **Verbindungs-Reconnect**: automatischer Reconnect bei TCP-Trennung (Kabelwackler im Feld)
5. **tachylog CLI-Parität**: tachylog erhält EPSG-Parameter und Standardexport-Spaltenformat

**Deliverable:** tachyflow v0.2 — GNSS-Echtzeit-Option verfügbar, UI auf Tablet-Nutzung optimiert (große Buttons, Dark Mode), Session-History vorhanden.

**Zeitschätzung:** 4–6 Wochen

---

### Phase 3: GeoPackage-Export mit Layer-Struktur (Gladiator-Logik)

**Ziel:** Optionaler GeoPackage-Export-Kanal mit Objektbildung nach Gladiator_2-Logik direkt aus tachylog/tachyflow. Das Gladiator_2-Format ist bekannt (`CCSSSSNNNN`), Phase 3 implementiert es als Export-Option — nicht als interne Datenstruktur.

**Features:**
1. **GeoPackage-Export mit Layer-Struktur**: Punkte aus der Datenbank werden nach Gladiator-Codes gruppiert und als separate Layer exportiert:
   - Punkt-Layer: ST, SB, HP, CP, RP, TP, FP, PS, PP, PD
   - Linien-Layer: BL, CL, DL (Punkte sortiert nach Sequenz, gruppiert nach `code + se_id`)
   - Polygon-Layer: OT, OB, LE (Punktgruppen → Ring → Polygon)
2. **Export-Templates**: vorkonfigurierte Profile ("Gladiator_2 GeoPackage", "AS4QGIS Standard", "Archiv")
3. **Offline-Dokumentation**: eingebettete Hilfe im UI (Gladiator-Codetabelle, EPSG-Tabelle für Österreich)
4. **Automatischer Test-Suite**: Integrationstests mit synthetischen GSI-Strings, bekannten Koordinaten, EPSG-Verifikation

**Hinweis:** Die Objektbildungslogik (Linien/Polygone aus Punktgruppen) lebt ausschließlich im GeoPackage-Export-Modul — nicht in collector.py, staging.py oder der Live-Karte. Die interne Datenstruktur bleibt immer eine flache Punkttabelle.

**Deliverable:** tachyflow v1.0 — produktionsreif für Regeleinsatz, GeoPackage-Export mit vollständiger Gladiator_2-Layer-Struktur, vollständig dokumentiert.

**Zeitschätzung:** 6–10 Wochen

---

## Anhang A: EPSG-Codes für Österreich (Referenz)

| EPSG | Name | Anwendung |
|------|------|-----------|
| 31256 | MGI / Austria GK M31 | Wien, NÖ, Burgenland (bevorzugt) |
| 31255 | MGI / Austria GK M28 | Vorarlberg, Tirol, Salzburg West |
| 31257 | MGI / Austria GK M34 | Kärnten, Steiermark Ost |
| 31258 | MGI / Austria GK Central | Gesamtösterreich-Übersicht |
| 4326 | WGS84 | GNSS-Rohkoordinaten (nur wenn keine lokale CRS konfiguriert) |

---

## Anhang B: AS4QGIS PID-Format Kurzreferenz (Alternative)

> **Hinweis:** AS4QGIS ist ein alternatives Downstream-Tool. Für neue Projekte wird das Gladiator_2-Format (Anhang D) empfohlen. tachyflow akzeptiert beide Formate ohne Anpassung — die Wahl liegt beim Benutzer.

```
Format: XXXXYZZ###
         │   ││  └── 3-stellige Sequenznummer (001, 002, …)
         │   │└───── 2-stelliger Shape-Type-Code
         │   └────── Container-Buchstabe (A–Z, meist A)
         └────────── 4-stellige Feature-Nummer (0001–9999)

Shape-Type-Codes:
  00 = section nail       61 = posthole
  01 = heights            71 = finds (point)
  02 = polyline           72 = finds (area)
  03 = polygon            73 = finds (section)
  51 = sample (point)     81 = 3D marker
  52 = sample (area)      91 = trench (boundary)
  53 = sample (section)   92 = trench (area)
                          93 = trench (section)

Beispiele:
  0037A03001  → Feature 37, Container A, Polygon, Punkt 1
  0012A02005  → Feature 12, Container A, Polyline, Punkt 5
  0001A01001  → Feature 1, Container A, Höhenpunkt 1
  0099A61001  → Feature 99, Container A, Posthole, Punkt 1
```

---

## Anhang C: Bekannte Einschränkungen & offene Fragen

1. **Emlid NMEA mit lokalen Koordinaten:** Ob der Emlid Reach RS2/RX NMEA-Sätze mit MGI-Koordinaten ausgeben kann (nicht nur WGS84) muss am Gerät verifiziert werden. Emlid ReachView3 erlaubt lokale CS-Konfiguration, aber NMEA-Ausgabe-Verhalten variiert je nach Firmware-Version.

2. **tachyflow auf Mobile:** Express+React läuft im Browser, damit theoretisch auf jedem Gerät. Auf Android-Tablets (Feldtauglichkeit: Panasonic Toughpad, Samsung Xcover) muss die Touch-UI getestet werden. Dateidownload via Browser funktioniert auf Android eingeschränkt.

3. **TCP-Bridge-Setup:** Die Bluetooth-zu-TCP-Bridge für den TS07 ist ein externes System. Ihre Konfiguration (welcher BT-Adapter, welche Software) ist nicht Teil von tachyflow, muss aber in der Felddokumentation beschrieben werden.

4. **sql.js vs. bessere SQLite-Alternative:** sql.js (WebAssembly SQLite) ist im Browser-Kontext akzeptabel, hat aber Einschränkungen bei größeren Datenmengen und fehlendem WAL-Mode. Für tachyflow als Electron-App oder Node.js-Server (ohne Browser) wäre `better-sqlite3` robuster. Mittelfristig erwägen.

---

## Anhang D: Gladiator_2 Codetabelle & Objektbildung (Feldspickzettel)

### D.1 PID-Format

```
Format: CCSSSSNNNN
         ││    └──── 4-stellige Sequenznummer (0001–9999)
         │└───────── 4-stellige SE-ID / Feature-ID (0001–9999)
         └─────────── 2-Buchstaben-Code (s. Tabelle unten)

Beispiele:
  OT00010001  →  Outline Top, SE 0001, Punkt 1
  OT00010002  →  Outline Top, SE 0001, Punkt 2  (nächster Polygonpunkt)
  SB00370001  →  Surface Bottom, SE 0037, Punkt 1
  BL00050003  →  Break Line, SE 0005, Punkt 3
  FP00120001  →  Find Point, SE 0012, Fund 1
  HP00000001  →  Survey Point (Standpunkt), SE 0000, Punkt 1
```

### D.2 Codetabelle

| Code | Bedeutung | Geometrietyp | Eingabe am Instrument |
|------|-----------|--------------|----------------------|
| OT | Outline Top | Polygon | Kontur Oberkante |
| OB | Outline Bottom | Polygon | Kontur Unterkante |
| ST | Surface Top | Punkt | Oberflächenpunkt oben |
| SB | Surface Bottom | Punkt | Oberflächenpunkt unten |
| BL | Break Line | Linie | Bruchlinie |
| LE | Limits Excavation | Polygon | Grabungsgrenze |
| HP | Survey Point | Punkt | Standpunkt / Hilfspunkt |
| CP | Control Point | Punkt | Kontrollpunkt |
| CL | Crosssection Line | Linie | Profilschnittlinie |
| PP | Photogrammetric Point | Punkt | Photogrammetrie-Pass-Punkt |
| PD | Photogrammetric Detail Point | Punkt | Photogrammetrie-Detail |
| DL | Diverse Line | Linie | Sonstige Linie |
| RP | Reference Point | Punkt | Referenzpunkt |
| TP | Temporary Point | Punkt | Temporärer Hilfspunkt |
| FP | Find Point | Punkt | Fundpunkt |
| PS | Point Sample | Punkt | Probenpunkt |

### D.3 Objektbildung in Gladiator_2

**Punkte** (direkt als Punktfeatures, keine Gruppierung nötig):
`ST`, `SB`, `HP`, `CP`, `RP`, `TP`, `FP`, `PS`, `PP`, `PD`

**Linien** (Punkte werden nach Sequenznummer sortiert und zu einer Linie verbunden):
`BL`, `CL`, `DL`
→ Gruppierungsschlüssel: `code + se_id` (z.B. alle `BL0005xxxx` → eine Break Line für SE 0005)

**Polygone** (Punktgruppe wird zu einem geschlossenen Ring → Polygon):
`OT`, `OB`, `LE`
→ Gruppierungsschlüssel: `code + se_id` (z.B. alle `OT0001xxxx` → ein Polygon für SE 0001)
→ Reihenfolge: nach Sequenznummer; letzter Punkt wird mit erstem verbunden

### D.4 Feldeingabe-Tipps

```
Checkliste vor der Messung:
  □ SE-ID für den heutigen Befund notieren (z.B. 0037)
  □ Instrument: PID-Eingabe auf CCSSSSNNNN prüfen
  □ Sequenznummer bei neuer SE von 0001 starten

Häufige Fehler vermeiden:
  ✗ OT00370001, OT00370003  (Sequenzlücke → Polygon unvollständig)
  ✗ OT00370001, OB00370002  (Code-Mix innerhalb einer Sequenz)
  ✓ OT00370001, OT00370002, OT00370003  (lückenlose Sequenz, gleicher Code)

Mehrere SEs am selben Tag:
  OT00370001 … OT0037000n  →  Polygon SE 0037
  OT00380001 … OT0038000n  →  Polygon SE 0038  (neue SE-ID, Sequenz neu bei 0001)
```
