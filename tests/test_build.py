"""Tests für den Feature-Builder (GeoPackage-Erzeugung)."""
import pytest
import sqlite3
from pathlib import Path
from tachylog.staging import StagingDB, StagingPoint
from tachylog.feature_builder import FeatureBuilder
from tachylog.code_table import CodeTable


@pytest.fixture
def db_with_points(tmp_path):
    """Staging-DB mit verschiedenen Test-Punkten."""
    db = StagingDB(tmp_path / "staging.db")
    points = [
        # Einzelpunkte (FP = Fundpunkt)
        StagingPoint(pid="FP00010001", x=500000.0, y=160000.0, z=400.0, source="geocom"),
        StagingPoint(pid="FP00010002", x=500001.0, y=160001.0, z=401.0, source="geocom"),
        # Linie (WA = Wand)
        StagingPoint(pid="WA00020001", x=500010.0, y=160010.0, z=400.0, source="geocom"),
        StagingPoint(pid="WA00020002", x=500020.0, y=160010.0, z=400.0, source="geocom"),
        StagingPoint(pid="WA00020003", x=500030.0, y=160010.0, z=400.0, source="geocom"),
        # Polygon (BF = Befund)
        StagingPoint(pid="BF00030001", x=500100.0, y=160100.0, z=399.0, source="geocom"),
        StagingPoint(pid="BF00030002", x=500110.0, y=160100.0, z=399.0, source="geocom"),
        StagingPoint(pid="BF00030003", x=500110.0, y=160110.0, z=399.0, source="geocom"),
        StagingPoint(pid="BF00030004", x=500100.0, y=160110.0, z=399.0, source="geocom"),
    ]
    for p in points:
        db.add_point(p)
    yield db
    db.close()


class TestFeatureBuilder:
    def test_build_creates_gpkg(self, db_with_points, tmp_path):
        output = tmp_path / "output.gpkg"
        builder = FeatureBuilder(db_with_points)
        result = builder.build(output)

        assert output.exists()
        assert result.total_features > 0
        assert not result.errors

    def test_point_features(self, db_with_points, tmp_path):
        output = tmp_path / "output.gpkg"
        builder = FeatureBuilder(db_with_points)
        result = builder.build(output)

        assert result.points_built == 2   # FP00010001, FP00010002

    def test_line_features(self, db_with_points, tmp_path):
        output = tmp_path / "output.gpkg"
        builder = FeatureBuilder(db_with_points)
        result = builder.build(output)

        assert result.lines_built == 1   # WA00020001-003

    def test_polygon_features(self, db_with_points, tmp_path):
        output = tmp_path / "output.gpkg"
        builder = FeatureBuilder(db_with_points)
        result = builder.build(output)

        assert result.polygons_built == 1  # BF00030001-004

    def test_gpkg_has_correct_tables(self, db_with_points, tmp_path):
        output = tmp_path / "output.gpkg"
        FeatureBuilder(db_with_points).build(output)

        conn = sqlite3.connect(str(output))
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "survey_points" in tables
        assert "survey_lines" in tables
        assert "survey_polygons" in tables
        assert "gpkg_contents" in tables
        conn.close()

    def test_idempotent(self, db_with_points, tmp_path):
        """Mehrfaches Ausführen erzeugt dasselbe Ergebnis."""
        output = tmp_path / "output.gpkg"
        builder = FeatureBuilder(db_with_points)
        r1 = builder.build(output)
        r2 = builder.build(output)

        assert r1.total_features == r2.total_features
        assert r1.points_built == r2.points_built

    def test_too_few_points_for_line(self, tmp_path):
        """Linie mit nur 1 Punkt → Warnung, kein Fehler."""
        db = StagingDB(tmp_path / "s.db")
        db.add_point(StagingPoint(pid="WA00010001", x=0.0, y=0.0, z=0.0, source="geocom"))

        output = tmp_path / "o.gpkg"
        result = FeatureBuilder(db).build(output)
        assert result.lines_built == 0
        assert any("Linie" in w for w in result.warnings)
        db.close()

    def test_unknown_code_treated_as_point(self, tmp_path):
        """Unbekannter Code → Warnung + als Punkt gespeichert."""
        db = StagingDB(tmp_path / "s.db")
        db.add_point(StagingPoint(pid="XX00010001", x=0.0, y=0.0, z=0.0, source="geocom"))

        output = tmp_path / "o.gpkg"
        result = FeatureBuilder(db).build(output)
        assert result.points_built == 1
        assert any("Unbekannter Code" in w for w in result.warnings)
        db.close()
