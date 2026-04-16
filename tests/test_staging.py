"""Tests für die Staging-Datenbank."""
import pytest
import time
from pathlib import Path
from tachylog.staging import StagingDB, StagingPoint, BuildRun


@pytest.fixture
def tmp_db(tmp_path):
    """Temporäre Datenbank für Tests."""
    db = StagingDB(tmp_path / "test.db")
    yield db
    db.close()


class TestStagingDB:
    def test_add_and_retrieve(self, tmp_db):
        pt = StagingPoint(pid="FP00010001", x=500000.0, y=160000.0, z=400.0, source="geocom")
        pt_id = tmp_db.add_point(pt)
        assert pt_id == 1

        points = tmp_db.get_all_points()
        assert len(points) == 1
        assert points[0].pid == "FP00010001"
        assert abs(points[0].x - 500000.0) < 0.001

    def test_append_only(self, tmp_db):
        """Punkte werden nur hinzugefügt, nie überschrieben."""
        for i in range(5):
            tmp_db.add_point(StagingPoint(
                pid=f"FP0001{i+1:04d}", x=float(i), y=float(i), z=0.0, source="geocom"
            ))
        assert len(tmp_db.get_all_points()) == 5

    def test_stats(self, tmp_db):
        tmp_db.add_point(StagingPoint(pid="FP00010001", x=1.0, y=2.0, z=3.0, source="geocom"))
        tmp_db.add_point(StagingPoint(pid="GP00010001", x=4.0, y=5.0, z=6.0, source="gnss"))

        stats = tmp_db.get_stats()
        assert stats["total"] == 2
        assert stats["geocom"] == 1
        assert stats["gnss"] == 1

    def test_invalid_pid_too_long(self):
        with pytest.raises(ValueError):
            StagingPoint(pid="TOOLONGPID123", x=0.0, y=0.0, z=0.0, source="geocom")

    def test_build_run(self, tmp_db):
        run = BuildRun(timestamp=time.time(), points_in=10, features_out=5, errors=0, output_path="out.gpkg")
        run_id = tmp_db.add_build_run(run)
        assert run_id == 1

        runs = tmp_db.get_build_runs()
        assert len(runs) == 1
        assert runs[0].features_out == 5

    def test_context_manager(self, tmp_path):
        with StagingDB(tmp_path / "ctx.db") as db:
            db.add_point(StagingPoint(pid="FP00010001", x=1.0, y=2.0, z=3.0, source="geocom"))
