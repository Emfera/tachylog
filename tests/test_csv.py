"""Tests für den CSV-Collector."""
import pytest
from pathlib import Path
from tachylog.staging import StagingDB
from tachylog.csv_collector import import_csv, detect_columns


class TestDetectColumns:
    def test_standard_names(self):
        cols = detect_columns(["x", "y", "z", "pid"])
        assert cols["x"] == 0
        assert cols["y"] == 1
        assert cols["z"] == 2
        assert cols["pid"] == 3

    def test_german_names(self):
        cols = detect_columns(["Rechtswert", "Hochwert", "Hoehe", "Punkt"])
        assert cols["x"] == 0
        assert cols["y"] == 1
        assert cols["z"] == 2
        assert cols["pid"] == 3

    def test_english_names(self):
        cols = detect_columns(["easting", "northing", "elevation", "name"])
        assert cols["x"] == 0
        assert cols["y"] == 1
        assert cols["z"] == 2
        assert cols["pid"] == 3

    def test_missing_z(self):
        cols = detect_columns(["x", "y", "id"])
        assert cols["x"] == 0
        assert cols["y"] == 1
        assert cols["z"] is None
        assert cols["pid"] == 2


class TestImportCSV:
    def test_comma_separator(self, tmp_path):
        csv = tmp_path / "test.csv"
        csv.write_text("pid,x,y,z\nFP00010001,500000.0,160000.0,400.0\n")

        db = StagingDB(tmp_path / "s.db")
        result = import_csv(db, csv, verbose=False)
        assert result["imported"] == 1
        assert result["skipped"] == 0
        db.close()

    def test_semicolon_separator(self, tmp_path):
        csv = tmp_path / "test.csv"
        csv.write_text("Rechtswert;Hochwert;Hoehe;Punkt\n500000.0;160000.0;400.0;FP00010001\n")

        db = StagingDB(tmp_path / "s.db")
        result = import_csv(db, csv, verbose=False)
        assert result["imported"] == 1
        db.close()

    def test_auto_pid(self, tmp_path):
        """CSV ohne PID-Spalte → PIDs werden auto-generiert."""
        csv = tmp_path / "test.csv"
        csv.write_text("x,y,z\n500000.0,160000.0,400.0\n500001.0,160001.0,401.0\n")

        db = StagingDB(tmp_path / "s.db")
        result = import_csv(db, csv, pid_prefix="GP", verbose=False)
        assert result["imported"] == 2
        points = db.get_all_points()
        assert points[0].pid.startswith("GP")
        db.close()

    def test_missing_xy(self, tmp_path):
        csv = tmp_path / "bad.csv"
        csv.write_text("col1,col2\n1,2\n")

        db = StagingDB(tmp_path / "s.db")
        result = import_csv(db, csv, verbose=False)
        assert result["imported"] == 0
        assert result["errors"]
        db.close()

    def test_empty_rows_skipped(self, tmp_path):
        csv = tmp_path / "test.csv"
        csv.write_text("x,y,z\n500000.0,160000.0,400.0\n\n500001.0,160001.0,401.0\n")

        db = StagingDB(tmp_path / "s.db")
        result = import_csv(db, csv, verbose=False)
        assert result["imported"] == 2
        db.close()
