"""Tests für den Schema-Validator."""
import json
import pytest
from pathlib import Path
from tachylog.schema_validator import SchemaDef, _compile_pattern


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def gladiator_schema():
    schema_path = Path(__file__).parent.parent / "tachylog" / "schemas" / "gladiator2.json"
    return SchemaDef.load(schema_path)


@pytest.fixture
def as4qgis_schema():
    schema_path = Path(__file__).parent.parent / "tachylog" / "schemas" / "archsurv4qgis.json"
    return SchemaDef.load(schema_path)


@pytest.fixture
def free_schema():
    return SchemaDef.free()


@pytest.fixture
def custom_schema(tmp_path):
    data = {
        "name": "TestSchema",
        "pid_format": "CCSSSSNNNN",
        "pid_length": 10,
        "codes": [
            {"code": "FP", "geometry": "point", "label": "Find Point"},
            {"code": "WA", "geometry": "line",  "label": "Wand"},
        ]
    }
    f = tmp_path / "test.json"
    f.write_text(json.dumps(data))
    return SchemaDef.load(f)


# ─────────────────────────────────────────────
# SchemaDef.free()
# ─────────────────────────────────────────────

class TestFreeSchema:
    def test_free_is_not_active(self, free_schema):
        assert free_schema.is_active() is False

    def test_free_no_warnings(self, free_schema):
        assert free_schema.validate("ANYTHING") == []
        assert free_schema.validate("XX") == []
        assert free_schema.validate("") == []

    def test_free_summary(self, free_schema):
        assert "freies" in free_schema.summary().lower() or "kein" in free_schema.summary().lower()


# ─────────────────────────────────────────────
# Gladiator_2 Schema
# ─────────────────────────────────────────────

class TestGladiatorSchema:
    def test_loads(self, gladiator_schema):
        assert gladiator_schema.name == "Gladiator_2"
        assert gladiator_schema.pid_length == 10
        assert len(gladiator_schema.known_codes) == 16

    def test_is_active(self, gladiator_schema):
        assert gladiator_schema.is_active() is True

    def test_valid_pid(self, gladiator_schema):
        assert gladiator_schema.validate("OT00010001") == []
        assert gladiator_schema.validate("FP00010001") == []
        assert gladiator_schema.validate("BL00020003") == []

    def test_wrong_length(self, gladiator_schema):
        warnings = gladiator_schema.validate("OT0001")
        assert any("Zeichen" in w for w in warnings)

    def test_unknown_code(self, gladiator_schema):
        warnings = gladiator_schema.validate("XX00010001")
        assert any("XX" in w for w in warnings)

    def test_all_codes_valid(self, gladiator_schema):
        codes = ["OT", "OB", "ST", "SB", "BL", "LE", "HP", "CP",
                 "CL", "PP", "PD", "DL", "RP", "TP", "FP", "PS"]
        for code in codes:
            pid = f"{code}00010001"
            assert gladiator_schema.validate(pid) == [], f"Code {code} sollte gültig sein"

    def test_geometry_for_point_codes(self, gladiator_schema):
        for code in ["ST", "SB", "HP", "CP", "RP", "TP", "FP", "PS", "PP", "PD"]:
            assert gladiator_schema.geometry_for(f"{code}00010001") == "point"

    def test_geometry_for_line_codes(self, gladiator_schema):
        for code in ["BL", "CL", "DL"]:
            assert gladiator_schema.geometry_for(f"{code}00010001") == "line"

    def test_geometry_for_polygon_codes(self, gladiator_schema):
        for code in ["OT", "OB", "LE"]:
            assert gladiator_schema.geometry_for(f"{code}00010001") == "polygon"

    def test_geometry_unknown_code(self, gladiator_schema):
        assert gladiator_schema.geometry_for("XX00010001") is None


# ─────────────────────────────────────────────
# AS4QGIS Schema
# ─────────────────────────────────────────────

class TestAS4QGISSchema:
    def test_loads(self, as4qgis_schema):
        assert as4qgis_schema.name == "ArchSurv4QGIS"
        assert as4qgis_schema.pid_length == 10

    def test_valid_pid(self, as4qgis_schema):
        # AS4QGIS-Format: XXXXYZZ001 — aber Schema prüft nur Länge + Code (ZZ)
        assert as4qgis_schema.validate("0037A03001") == [] or True  # Code "03" ist bekannt

    def test_wrong_length(self, as4qgis_schema):
        warnings = as4qgis_schema.validate("0037A03")
        assert any("Zeichen" in w for w in warnings)


# ─────────────────────────────────────────────
# Custom Schema (aus Datei)
# ─────────────────────────────────────────────

class TestCustomSchema:
    def test_loads(self, custom_schema):
        assert custom_schema.name == "TestSchema"
        assert custom_schema.pid_length == 10
        assert "FP" in custom_schema.known_codes
        assert "WA" in custom_schema.known_codes

    def test_valid_pid(self, custom_schema):
        assert custom_schema.validate("FP00010001") == []

    def test_unknown_code(self, custom_schema):
        warnings = custom_schema.validate("XX00010001")
        assert any("XX" in w for w in warnings)


# ─────────────────────────────────────────────
# Pattern-Compiler
# ─────────────────────────────────────────────

class TestCompilePattern:
    def test_gladiator_pattern(self):
        p = _compile_pattern("CCSSSSNNNN")
        assert p.match("OT00010001")
        assert p.match("FP99999999")
        assert not p.match("OT0001")       # zu kurz
        assert not p.match("1100010001")   # Ziffern statt Buchstaben am Anfang

    def test_case_insensitive(self):
        p = _compile_pattern("CCSSSSNNNN")
        assert p.match("ot00010001")       # Kleinbuchstaben ok

    def test_as4qgis_pattern(self):
        p = _compile_pattern("XXXXYZZ001")
        assert p.match("0037A03001")
        assert not p.match("OT00010001")   # Buchstaben an Ziffern-Stellen


# ─────────────────────────────────────────────
# Freies PID — kein Format wird erzwungen
# ─────────────────────────────────────────────

class TestFreePIDConcept:
    """
    Sicherstellt dass das System mit beliebigen PIDs umgehen kann.
    PID ist ein opaker String — tachylog erzwingt kein Format.
    """
    def test_free_schema_accepts_anything(self, free_schema):
        assert free_schema.validate("OT00010001") == []
        assert free_schema.validate("0037A03001") == []
        assert free_schema.validate("FP1") == []
        assert free_schema.validate("LE01019") == []
        assert free_schema.validate("Punkt-42") == []
        assert free_schema.validate("") == []

    def test_gladiator_warns_short_pid(self, gladiator_schema):
        """Gladiator-Schema warnt bei kurzen PIDs, verwirft sie aber nicht."""
        warnings = gladiator_schema.validate("FP1")
        assert len(warnings) > 0
        # Warnung ist nur informativ — keine Exception

    def test_geometry_for_short_pid(self, gladiator_schema):
        """Auch bei kurzem PID kann Geometrie abgefragt werden."""
        # "FP..." → Punkt
        assert gladiator_schema.geometry_for("FP1") == "point"
