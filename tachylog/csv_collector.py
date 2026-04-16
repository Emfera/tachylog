"""
CSV Collector für surveypipe.

Importiert fertige GNSS-Exportdateien (CSV) in die Staging-DB.
Unterstützt automatische Spalten-Erkennung für verschiedene Exportformate.

Unterstützte Spaltenbezeichnungen (case-insensitive):
  X/Rechtswert/Easting:   x, easting, rechtswert, rw, east, e
  Y/Hochwert/Northing:    y, northing, hochwert, hw, north, n
  Z/Höhe/Elevation:       z, elevation, height, hoehe, höhe, h, alt, altitude
  PID/Punktnummer:        pid, id, punkt, point, name, nr, no, number, punktnr

Trennzeichen: wird automatisch erkannt (Komma oder Semikolon).
"""

import csv
import io
import logging
import time
from pathlib import Path
from typing import Optional

from .staging import StagingDB, StagingPoint

logger = logging.getLogger(__name__)

# Bekannte Spaltennamen pro Typ (lowercase)
_X_NAMES = {"x", "easting", "rechtswert", "rw", "east", "e", "x_coord", "xcoord"}
_Y_NAMES = {"y", "northing", "hochwert", "hw", "north", "n", "y_coord", "ycoord"}
_Z_NAMES = {"z", "elevation", "height", "hoehe", "höhe", "h", "alt", "altitude",
            "z_coord", "zcoord", "elev", "hoe"}
_PID_NAMES = {"pid", "id", "punkt", "point", "name", "nr", "no", "number",
              "punktnr", "point_id", "pointid", "punktid", "ident"}


def _detect_separator(sample: str) -> str:
    """Erkennt das Trennzeichen (Komma oder Semikolon)."""
    commas = sample.count(",")
    semis = sample.count(";")
    return ";" if semis >= commas else ","


def _find_column(headers: list[str], candidates: set[str]) -> Optional[int]:
    """Findet den Index einer Spalte anhand bekannter Namen."""
    for i, h in enumerate(headers):
        if h.strip().lower() in candidates:
            return i
    return None


def detect_columns(headers: list[str]) -> dict:
    """
    Erkennt X/Y/Z/PID-Spalten aus einer Header-Zeile.
    Gibt ein Dict mit den Spalten-Indizes zurück.
    """
    h_lower = [h.strip().lower() for h in headers]
    return {
        "x":   _find_column(h_lower, _X_NAMES),
        "y":   _find_column(h_lower, _Y_NAMES),
        "z":   _find_column(h_lower, _Z_NAMES),
        "pid": _find_column(h_lower, _PID_NAMES),
    }


def import_csv(
    db: StagingDB,
    path: str | Path,
    pid_prefix: str = "GP",
    start_seq: int = 1,
    verbose: bool = True,
) -> dict:
    """
    Importiert eine CSV-Datei in die Staging-DB.

    Parameter:
      db          — Staging-Datenbank
      path        — Pfad zur CSV-Datei
      pid_prefix  — Präfix für auto-generierte PIDs wenn keine PID-Spalte vorhanden
                    (z.B. "GP" → "GP00010001", "GP00010002", ...)
      start_seq   — Startwert für die Sequenznummer bei auto-PIDs
      verbose     — Fortschritt ausgeben

    Gibt ein Dict zurück:
      {"imported": N, "skipped": N, "errors": [...], "columns": {...}}
    """
    path = Path(path)
    if not path.exists():
        return {"imported": 0, "skipped": 0, "errors": [f"Datei nicht gefunden: {path}"], "columns": {}}

    content = path.read_text(encoding="utf-8-sig")  # BOM-safe
    separator = _detect_separator(content[:1000])

    reader = csv.reader(io.StringIO(content), delimiter=separator)
    rows = list(reader)

    if not rows:
        return {"imported": 0, "skipped": 0, "errors": ["Leere Datei"], "columns": {}}

    # Header-Zeile
    headers = rows[0]
    cols = detect_columns(headers)

    # X und Y sind Pflichtfelder
    if cols["x"] is None or cols["y"] is None:
        return {
            "imported": 0, "skipped": 0,
            "errors": [f"X/Y-Spalten nicht erkannt. Gefundene Spalten: {headers}"],
            "columns": cols
        }

    # Z ist optional (0.0 wenn nicht vorhanden)
    # PID ist optional (wird auto-generiert)

    imported = 0
    skipped = 0
    errors = []
    seq = start_seq

    data_rows = rows[1:]

    for row_num, row in enumerate(data_rows, start=2):
        if not row or all(not cell.strip() for cell in row):
            skipped += 1
            continue

        try:
            x = float(row[cols["x"]].strip().replace(",", "."))
            y = float(row[cols["y"]].strip().replace(",", "."))
            z = float(row[cols["z"]].strip().replace(",", ".")) if cols["z"] is not None and cols["z"] < len(row) else 0.0

            # PID: aus Datei oder auto-generiert
            if cols["pid"] is not None and cols["pid"] < len(row):
                pid_raw = row[cols["pid"]].strip().upper()
                # PID auf 10 Zeichen prüfen
                if len(pid_raw) == 10:
                    pid = pid_raw
                elif len(pid_raw) <= 10:
                    # Zu kurz — auto-generieren
                    pid = f"{pid_prefix[:2].upper()}0001{seq:04d}"
                    seq += 1
                else:
                    pid = pid_raw[:10]  # Abschneiden
            else:
                # Keine PID-Spalte — auto-generieren
                pid = f"{pid_prefix[:2].upper()}0001{seq:04d}"
                seq += 1

            pt = StagingPoint(pid=pid, x=x, y=y, z=z, source="gnss")
            db.add_point(pt)
            imported += 1

        except (ValueError, IndexError) as e:
            errors.append(f"Zeile {row_num}: {e}")
            skipped += 1
            continue

    if verbose:
        col_names = {k: headers[v] if v is not None else "—" for k, v in cols.items()}
        print(f"  CSV Import: {imported} Punkte importiert, {skipped} übersprungen")
        print(f"  Erkannte Spalten: X={col_names['x']}, Y={col_names['y']}, "
              f"Z={col_names['z']}, PID={col_names['pid']}")
        if errors:
            print(f"  Fehler: {len(errors)}")
            for e in errors[:5]:
                print(f"    {e}")

    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "columns": {k: headers[v] if v is not None else None for k, v in cols.items()},
    }
