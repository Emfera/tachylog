"""
Staging-Datenbank für surveypipe.

Die Staging-DB ist append-only: Rohdaten werden NIEMALS überschrieben oder gelöscht.
Jeder Messpunkt wird sofort nach Empfang gespeichert, ohne Interpretation.
Die Interpretation (PID-Parsing, Feature-Erzeugung) passiert erst beim Build.

Datenbank: SQLite (eine einzige .db Datei)
Schema:
  staging_points  — alle gesammelten Messpunkte
  build_runs      — Protokoll aller Build-Läufe
"""

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────
# Datenklassen
# ─────────────────────────────────────────────

@dataclass
class StagingPoint:
    """Ein einzelner Messpunkt im Staging."""
    pid: str           # Punkt-ID, z.B. "FP00010001"
    x: float           # Rechtswert / Easting
    y: float           # Hochwert / Northing
    z: float           # Höhe / Elevation
    source: str        # "geocom" oder "gnss"
    timestamp: float = field(default_factory=time.time)
    id: Optional[int] = None  # Auto-increment, wird von DB gesetzt

    def __post_init__(self):
        self.pid = self.pid.strip().upper()
        if len(self.pid) > 10:
            raise ValueError(f"PID zu lang: '{self.pid}' (max 10 Zeichen)")


@dataclass
class BuildRun:
    """Protokoll eines Build-Laufs."""
    timestamp: float
    points_in: int
    features_out: int
    errors: int
    output_path: str
    id: Optional[int] = None


# ─────────────────────────────────────────────
# Staging-Datenbank
# ─────────────────────────────────────────────

class StagingDB:
    """
    Verwaltet die Staging-Datenbank.

    Verwendung:
        db = StagingDB("staging.db")
        db.add_point(StagingPoint(pid="FP00010001", x=500000.0, y=160000.0, z=400.0, source="geocom"))
        punkte = db.get_all_points()
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        """Erstellt die Tabellen falls sie noch nicht existieren."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS staging_points (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                pid       TEXT    NOT NULL,
                x         REAL    NOT NULL,
                y         REAL    NOT NULL,
                z         REAL    NOT NULL,
                source    TEXT    NOT NULL DEFAULT 'geocom',
                timestamp REAL    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_staging_pid ON staging_points(pid);
            CREATE INDEX IF NOT EXISTS idx_staging_source ON staging_points(source);

            CREATE TABLE IF NOT EXISTS build_runs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    REAL    NOT NULL,
                points_in    INTEGER NOT NULL DEFAULT 0,
                features_out INTEGER NOT NULL DEFAULT 0,
                errors       INTEGER NOT NULL DEFAULT 0,
                output_path  TEXT    NOT NULL DEFAULT ''
            );
        """)
        self._conn.commit()

    def add_point(self, pt: StagingPoint) -> int:
        """
        Fügt einen Messpunkt hinzu. Gibt die neue ID zurück.
        Diese Operation ist immer append-only — niemals update oder delete.
        """
        cur = self._conn.execute(
            "INSERT INTO staging_points (pid, x, y, z, source, timestamp) VALUES (?,?,?,?,?,?)",
            (pt.pid, pt.x, pt.y, pt.z, pt.source, pt.timestamp)
        )
        self._conn.commit()
        return cur.lastrowid

    def get_all_points(self) -> list[StagingPoint]:
        """Gibt alle Punkte zurück, sortiert nach timestamp (älteste zuerst)."""
        rows = self._conn.execute(
            "SELECT * FROM staging_points ORDER BY timestamp ASC"
        ).fetchall()
        return [StagingPoint(
            id=r["id"], pid=r["pid"],
            x=r["x"], y=r["y"], z=r["z"],
            source=r["source"], timestamp=r["timestamp"]
        ) for r in rows]

    def get_stats(self) -> dict:
        """Gibt Statistiken zur Staging-DB zurück."""
        row = self._conn.execute("""
            SELECT
                COUNT(*)                                    AS total,
                SUM(CASE WHEN source='geocom' THEN 1 END)  AS geocom,
                SUM(CASE WHEN source='gnss'   THEN 1 END)  AS gnss,
                MIN(timestamp)                              AS first_ts,
                MAX(timestamp)                              AS last_ts
            FROM staging_points
        """).fetchone()

        return {
            "total":   row["total"]   or 0,
            "geocom":  row["geocom"]  or 0,
            "gnss":    row["gnss"]    or 0,
            "first":   row["first_ts"],
            "last":    row["last_ts"],
            "db_path": str(self.db_path),
        }

    def add_build_run(self, run: BuildRun) -> int:
        """Speichert einen Build-Lauf ins Protokoll."""
        cur = self._conn.execute(
            "INSERT INTO build_runs (timestamp, points_in, features_out, errors, output_path) VALUES (?,?,?,?,?)",
            (run.timestamp, run.points_in, run.features_out, run.errors, run.output_path)
        )
        self._conn.commit()
        return cur.lastrowid

    def get_build_runs(self) -> list[BuildRun]:
        """Gibt alle Build-Läufe zurück."""
        rows = self._conn.execute(
            "SELECT * FROM build_runs ORDER BY timestamp DESC"
        ).fetchall()
        return [BuildRun(
            id=r["id"], timestamp=r["timestamp"],
            points_in=r["points_in"], features_out=r["features_out"],
            errors=r["errors"], output_path=r["output_path"]
        ) for r in rows]

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
