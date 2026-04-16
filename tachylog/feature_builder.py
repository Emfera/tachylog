"""
Feature-Builder für surveypipe.

Liest Punkte aus der Staging-DB, gruppiert sie nach Feature (code + se_id),
sortiert nach Sequenz und erzeugt Geometrien:
  - PointZ    für point-Codes
  - LineStringZ für line-Codes (≥2 Punkte)
  - PolygonZ  für polygon-Codes (≥3 Punkte, automatisch geschlossen)

Output: GeoPackage (.gpkg) mit 3 Layern:
  survey_points   → alle Punkt-Features
  survey_lines    → alle Linien-Features
  survey_polygons → alle Polygon-Features

Das GeoPackage ist OGC-konform und direkt in QGIS ladbar.
Es enthält zusätzlich für jeden Feature: code, se_id, description, pid_list.

Der Build ist IDEMPOTENT: mehrfaches Ausführen erzeugt immer dasselbe Ergebnis.
"""

import struct
import sqlite3
import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .staging import StagingDB, StagingPoint, BuildRun
from .pid_parser import parse_pid, ParsedPID
from .code_table import CodeTable, GeomType

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# WKB-Geometrie-Erzeugung (ohne GDAL!)
# ─────────────────────────────────────────────
# WKB = Well-Known Binary, das Standard-Format für Geometrien in GeoPackage

def _pack_double(v: float) -> bytes:
    return struct.pack("<d", v)

def _wkb_point_z(x: float, y: float, z: float) -> bytes:
    """Erzeugt WKB für einen PointZ."""
    return (
        b'\x01'           # Little-endian
        + struct.pack("<I", 1001)  # wkbPointZ
        + _pack_double(x)
        + _pack_double(y)
        + _pack_double(z)
    )

def _wkb_linestring_z(coords: list[tuple[float, float, float]]) -> bytes:
    """Erzeugt WKB für einen LineStringZ."""
    n = len(coords)
    body = struct.pack("<I", n)
    for x, y, z in coords:
        body += _pack_double(x) + _pack_double(y) + _pack_double(z)
    return b'\x01' + struct.pack("<I", 1002) + body  # wkbLineStringZ

def _wkb_polygon_z(coords: list[tuple[float, float, float]]) -> bytes:
    """Erzeugt WKB für einen PolygonZ (ein Ring, automatisch geschlossen)."""
    ring = list(coords)
    if ring[0] != ring[-1]:
        ring.append(ring[0])  # Schließen
    n = len(ring)
    body = struct.pack("<I", 1)   # Anzahl Ringe
    body += struct.pack("<I", n)  # Punkte im Ring
    for x, y, z in ring:
        body += _pack_double(x) + _pack_double(y) + _pack_double(z)
    return b'\x01' + struct.pack("<I", 1003) + body  # wkbPolygonZ

def _gpkg_geom(wkb: bytes) -> bytes:
    """Verpackt WKB in einen GeoPackage-Geometrie-Header (GPKG Standard)."""
    # GeoPackage Header: Magic(2) + Version(1) + Flags(1) + SRS_ID(4)
    header = b'GP' + b'\x00' + b'\x01' + struct.pack("<i", 4326)
    return header + wkb


# ─────────────────────────────────────────────
# Build-Ergebnis
# ─────────────────────────────────────────────

@dataclass
class BuildResult:
    """Ergebnis eines Build-Laufs."""
    output_path: str
    points_built: int = 0
    lines_built: int = 0
    polygons_built: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_s: float = 0.0

    @property
    def total_features(self) -> int:
        return self.points_built + self.lines_built + self.polygons_built


# ─────────────────────────────────────────────
# Builder
# ─────────────────────────────────────────────

class FeatureBuilder:
    """
    Liest Staging-Punkte und erzeugt ein GeoPackage.

    Verwendung:
        builder = FeatureBuilder(staging_db, code_table)
        result = builder.build("output.gpkg")
        print(f"{result.total_features} Features erzeugt")
    """

    def __init__(self, staging: StagingDB, codes: Optional[CodeTable] = None):
        self.staging = staging
        self.codes = codes or CodeTable()

    def build(self, output_path: str | Path) -> BuildResult:
        """
        Liest alle Staging-Punkte und schreibt ein GeoPackage.
        Gibt ein BuildResult-Objekt zurück.
        """
        t0 = time.time()
        output_path = Path(output_path)
        result = BuildResult(output_path=str(output_path))

        # Punkte aus Staging laden
        all_points = self.staging.get_all_points()
        logger.info(f"Build: {len(all_points)} Punkte aus Staging geladen")

        if not all_points:
            result.warnings.append("Keine Punkte in der Staging-Datenbank")
            return result

        # Punkte parsen und nach Feature gruppieren
        features = self._group_by_feature(all_points, result)

        # GeoPackage schreiben
        self._write_gpkg(output_path, features, result)

        # Build-Lauf protokollieren
        result.duration_s = time.time() - t0
        self.staging.add_build_run(BuildRun(
            timestamp=time.time(),
            points_in=len(all_points),
            features_out=result.total_features,
            errors=len(result.errors),
            output_path=str(output_path),
        ))

        logger.info(
            f"Build fertig: {result.points_built}P + {result.lines_built}L + "
            f"{result.polygons_built}Poly = {result.total_features} Features "
            f"({result.duration_s:.2f}s)"
        )
        return result

    def _group_by_feature(self, points: list[StagingPoint], result: BuildResult) -> dict:
        """
        Gruppiert Punkte nach Feature (code, se_id) und sortiert nach seq.
        Ungültige PIDs werden übersprungen (mit Warnung).
        """
        groups: dict[tuple, dict] = {}

        for pt in points:
            parsed = parse_pid(pt.pid)
            if parsed is None:
                result.warnings.append(f"Ungültige PID übersprungen: '{pt.pid}'")
                continue

            code_def = self.codes.get(parsed.code)
            if code_def is None:
                result.warnings.append(
                    f"Unbekannter Code '{parsed.code}' in PID '{pt.pid}' — als Punkt behandelt"
                )
                # Unbekannte Codes als Punkt speichern
                from .code_table import CodeDef, GeomType
                code_def = CodeDef(code=parsed.code, geom=GeomType.POINT,
                                   description=f"Unbekannter Code {parsed.code}")

            key = parsed.feature_key
            if key not in groups:
                groups[key] = {
                    "code_def": code_def,
                    "parsed_points": [],
                }
            groups[key]["parsed_points"].append((parsed, pt))

        # Nach Sequenz sortieren
        for key, feat in groups.items():
            feat["parsed_points"].sort(key=lambda x: x[0].seq)

        return groups

    def _write_gpkg(self, path: Path, features: dict, result: BuildResult):
        """Schreibt das GeoPackage (SQLite-Datei)."""
        # Vorhandene Datei überschreiben (Build ist idempotent)
        if path.exists():
            path.unlink()

        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA application_id = 0x47504b47")  # 'GPKG'
        conn.execute("PRAGMA user_version = 10300")

        # GeoPackage Pflicht-Tabellen
        conn.executescript("""
            CREATE TABLE gpkg_spatial_ref_sys (
                srs_name TEXT NOT NULL, srs_id INTEGER NOT NULL PRIMARY KEY,
                organization TEXT NOT NULL, organization_coordsys_id INTEGER NOT NULL,
                definition TEXT NOT NULL, description TEXT
            );
            CREATE TABLE gpkg_contents (
                table_name TEXT NOT NULL PRIMARY KEY, data_type TEXT NOT NULL,
                identifier TEXT, description TEXT DEFAULT '',
                last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                min_x REAL, min_y REAL, max_x REAL, max_y REAL, srs_id INTEGER,
                CONSTRAINT fk_gc_r_srs_id FOREIGN KEY (srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id)
            );
            CREATE TABLE gpkg_geometry_columns (
                table_name TEXT NOT NULL, column_name TEXT NOT NULL,
                geometry_type_name TEXT NOT NULL, srs_id INTEGER NOT NULL,
                z TINYINT NOT NULL, m TINYINT NOT NULL,
                CONSTRAINT pk_geom_cols PRIMARY KEY (table_name, column_name)
            );
        """)

        # WGS84 SRS eintragen (Standardreferenz)
        conn.execute("""
            INSERT OR IGNORE INTO gpkg_spatial_ref_sys VALUES
            ('WGS 84 Geographic 3D', 4326, 'EPSG', 4326,
             'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],
              PRIMEM["Greenwich",0],UNIT["degree",0.017453292519943295]]', 'WGS84')
        """)

        # Feature-Layer anlegen
        self._create_layer(conn, "survey_points",   "POINTZ")
        self._create_layer(conn, "survey_lines",    "LINESTRINGZ")
        self._create_layer(conn, "survey_polygons", "POLYGONZ")

        # Features einfügen
        for key, feat in features.items():
            code_def = feat["code_def"]
            parsed_points: list[tuple[ParsedPID, StagingPoint]] = feat["parsed_points"]
            coords = [(pt.x, pt.y, pt.z) for _, pt in parsed_points]
            pid_list = ",".join(p.raw for p, _ in parsed_points)
            se_id = key[1]
            description = code_def.description

            if code_def.geom == GeomType.POINT:
                # Jeden Punkt einzeln einfügen
                for parsed, pt in parsed_points:
                    geom = _gpkg_geom(_wkb_point_z(pt.x, pt.y, pt.z))
                    conn.execute(
                        "INSERT INTO survey_points (geom, code, se_id, description, pid) VALUES (?,?,?,?,?)",
                        (geom, code_def.code, se_id, description, parsed.raw)
                    )
                    result.points_built += 1

            elif code_def.geom == GeomType.LINE:
                if len(coords) < 2:
                    result.warnings.append(
                        f"Linie {code_def.code}{se_id:04d}: Nur {len(coords)} Punkt(e) — braucht ≥2"
                    )
                    continue
                geom = _gpkg_geom(_wkb_linestring_z(coords))
                conn.execute(
                    "INSERT INTO survey_lines (geom, code, se_id, description, pid_list, point_count) VALUES (?,?,?,?,?,?)",
                    (geom, code_def.code, se_id, description, pid_list, len(coords))
                )
                result.lines_built += 1

            elif code_def.geom == GeomType.POLYGON:
                if len(coords) < 3:
                    result.warnings.append(
                        f"Polygon {code_def.code}{se_id:04d}: Nur {len(coords)} Punkt(e) — braucht ≥3"
                    )
                    continue
                geom = _gpkg_geom(_wkb_polygon_z(coords))
                conn.execute(
                    "INSERT INTO survey_polygons (geom, code, se_id, description, pid_list, point_count) VALUES (?,?,?,?,?,?)",
                    (geom, code_def.code, se_id, description, pid_list, len(coords))
                )
                result.polygons_built += 1

        conn.commit()
        conn.close()

    def _create_layer(self, conn: sqlite3.Connection, table: str, geom_type: str):
        """Erstellt einen Feature-Layer im GeoPackage."""
        if geom_type == "POINTZ":
            extra_cols = "pid TEXT"
        else:
            extra_cols = "pid_list TEXT, point_count INTEGER"

        conn.execute(f"""
            CREATE TABLE {table} (
                fid         INTEGER PRIMARY KEY AUTOINCREMENT,
                geom        BLOB,
                code        TEXT NOT NULL,
                se_id       INTEGER NOT NULL,
                description TEXT,
                {extra_cols}
            )
        """)
        conn.execute(
            "INSERT INTO gpkg_contents (table_name, data_type, identifier, description, last_change, srs_id) VALUES (?,?,?,?,strftime('%Y-%m-%dT%H:%M:%fZ','now'),?)",
            (table, "features", table, "", 4326)
        )
        conn.execute(
            "INSERT INTO gpkg_geometry_columns VALUES (?,?,?,?,?,?)",
            (table, "geom", geom_type, 4326, 1, 0)
        )


def build_geopackage(points, output_path: str, crs: int = 4326) -> dict:
    """
    Wrapper-Funktion: Baut ein GeoPackage aus einer Liste von StagingPoints.
    Gibt {"points": n, "lines": n, "polygons": n} zurück.
    """
    builder = FeatureBuilder(output_path, crs=crs)
    result = builder.build(points)
    return {
        "points": result.point_count,
        "lines": result.line_count,
        "polygons": result.polygon_count,
    }
