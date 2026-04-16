"""
tachylog — Ausgabe-Manager

Schreibt Messungen gleichzeitig in alle aktiven Ausgabeformate:

  SQLite   — strukturierte Datenbank, für weitere Verarbeitung
  CSV      — kompatibel mit QGIS, Excel, Emlid Flow, eigenen Skripten
  GSI      — Rohformat exakt wie vom Instrument gesendet
  GeoJSON  — für Web-GIS, QGIS, jede moderne GIS-Software

Verwendung:
  manager = OutputManager(db="aufnahme.db", csv="aufnahme.csv", gsi="aufnahme.gsi")
  manager.open()
  manager.write(measurement)
  manager.close()

  # Oder als Context Manager:
  with OutputManager(db="aufnahme.db", csv="aufnahme.csv") as out:
      out.write(measurement)
"""

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .gsi_parser import GSIMeasurement
from .staging import StagingDB, StagingPoint

logger = logging.getLogger(__name__)

# CSV-Header — kompatibel mit Emlid Flow CSV-Format
CSV_HEADER = ["id", "name", "easting", "northing", "elevation", "timestamp", "source"]


class OutputManager:
    """
    Verwaltet alle aktiven Ausgabeformate gleichzeitig.

    Jede Messung wird in einem einzigen write()-Aufruf
    in alle aktiven Ausgaben geschrieben.
    """

    def __init__(
        self,
        db: Optional[str] = None,
        csv_path: Optional[str] = None,
        gsi_path: Optional[str] = None,
        geojson_path: Optional[str] = None,
    ):
        self.db_path = db
        self.csv_path = csv_path
        self.gsi_path = gsi_path
        self.geojson_path = geojson_path

        # Interne Handles (werden in open() gesetzt)
        self._db: Optional[StagingDB] = None
        self._csv_file = None
        self._csv_writer = None
        self._gsi_file = None
        self._geojson_file = None
        self._geojson_features = []
        self._counter = 0

    def open(self):
        """Öffnet alle aktiven Ausgaben."""
        if self.db_path:
            self._db = StagingDB(self.db_path)
            logger.debug(f"SQLite: {self.db_path}")

        if self.csv_path:
            self._csv_file = open(self.csv_path, "w", newline="", encoding="utf-8")
            self._csv_writer = csv.DictWriter(
                self._csv_file, fieldnames=CSV_HEADER
            )
            self._csv_writer.writeheader()
            self._csv_file.flush()
            logger.debug(f"CSV: {self.csv_path}")

        if self.gsi_path:
            self._gsi_file = open(self.gsi_path, "w", encoding="ascii")
            logger.debug(f"GSI: {self.gsi_path}")

        if self.geojson_path:
            # GeoJSON wird am Ende geschrieben (Feature Collection)
            self._geojson_features = []
            logger.debug(f"GeoJSON: {self.geojson_path}")

    def write(self, measurement: GSIMeasurement):
        """Schreibt eine Messung in alle aktiven Ausgaben."""
        self._counter += 1
        ts = datetime.now(timezone.utc).isoformat()

        # SQLite
        if self._db is not None:
            point = StagingPoint(
                pid=measurement.pid,
                x=measurement.e,
                y=measurement.n,
                z=measurement.h,
                source="geocom_gsi",
            )
            self._db.add_point(point)

        # CSV (Emlid Flow kompatibel)
        if self._csv_writer is not None:
            self._csv_writer.writerow({
                "id": self._counter,
                "name": measurement.pid,
                "easting": f"{measurement.e:.3f}",
                "northing": f"{measurement.n:.3f}",
                "elevation": f"{measurement.h:.3f}",
                "timestamp": ts,
                "source": "tachylog_gsi",
            })
            self._csv_file.flush()

        # GSI (Rohformat)
        if self._gsi_file is not None:
            self._gsi_file.write(measurement.raw + "\n")
            self._gsi_file.flush()

        # GeoJSON (im Speicher, wird bei close() geschrieben)
        if self.geojson_path is not None:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [measurement.e, measurement.n, measurement.h],
                },
                "properties": {
                    "id": self._counter,
                    "name": measurement.pid,
                    "easting": measurement.e,
                    "northing": measurement.n,
                    "elevation": measurement.h,
                    "timestamp": ts,
                    "source": "tachylog_gsi",
                },
            }
            self._geojson_features.append(feature)

    def close(self):
        """Schließt alle Ausgaben und schreibt GeoJSON."""
        if self._db is not None:
            self._db.close()
            self._db = None

        if self._csv_file is not None:
            self._csv_file.close()
            self._csv_file = None

        if self._gsi_file is not None:
            self._gsi_file.close()
            self._gsi_file = None

        if self.geojson_path and self._geojson_features is not None:
            collection = {
                "type": "FeatureCollection",
                "features": self._geojson_features,
            }
            with open(self.geojson_path, "w", encoding="utf-8") as f:
                json.dump(collection, f, indent=2, ensure_ascii=False)
            logger.debug(f"GeoJSON geschrieben: {self.geojson_path}")

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def count(self) -> int:
        """Anzahl gespeicherter Punkte in dieser Session."""
        return self._counter

    def active_outputs(self) -> list:
        """Liste der aktiven Ausgabeformate (für Anzeige)."""
        active = []
        if self.db_path:
            active.append(f"SQLite → {self.db_path}")
        if self.csv_path:
            active.append(f"CSV    → {self.csv_path}")
        if self.gsi_path:
            active.append(f"GSI    → {self.gsi_path}")
        if self.geojson_path:
            active.append(f"GeoJSON→ {self.geojson_path}")
        return active
