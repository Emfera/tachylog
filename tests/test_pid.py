"""Tests für PID-Parser."""
import pytest
from tachylog.pid_parser import parse_pid, is_valid_pid, validate_pid_sequence


class TestParsePID:
    def test_valid_pid(self):
        p = parse_pid("FP00010001")
        assert p is not None
        assert p.code == "FP"
        assert p.se_id == 1
        assert p.seq == 1

    def test_valid_uppercase(self):
        p = parse_pid("wa00020003")  # Kleinbuchstaben werden konvertiert
        assert p is not None
        assert p.code == "WA"
        assert p.se_id == 2
        assert p.seq == 3

    def test_valid_max_values(self):
        p = parse_pid("BF99999999")
        assert p is not None
        assert p.se_id == 9999
        assert p.seq == 9999

    def test_invalid_short(self):
        assert parse_pid("FP") is None
        assert parse_pid("FP0001") is None

    def test_invalid_long(self):
        assert parse_pid("FP000100011") is None  # 11 Zeichen

    def test_invalid_seq_zero(self):
        assert parse_pid("FP00010000") is None  # Seq=0 ungültig

    def test_invalid_empty(self):
        assert parse_pid("") is None
        assert parse_pid(None) is None

    def test_feature_key(self):
        p = parse_pid("WA00020003")
        assert p.feature_key == ("WA", 2)


class TestValidatePIDSequence:
    def test_valid_sequence(self):
        pids = ["FP00010001", "FP00010002", "FP00010003"]
        result = validate_pid_sequence(pids)
        assert len(result["valid"]) == 3
        assert len(result["invalid"]) == 0
        assert len(result["warnings"]) == 0

    def test_invalid_pid(self):
        pids = ["FP00010001", "INVALID", "FP00010002"]
        result = validate_pid_sequence(pids)
        assert len(result["valid"]) == 2
        assert "INVALID" in result["invalid"]

    def test_sequence_gap(self):
        pids = ["WA00010001", "WA00010003"]  # Lücke bei 2
        result = validate_pid_sequence(pids)
        assert len(result["warnings"]) > 0
        assert "Sequenzlücke" in result["warnings"][0]

    def test_multiple_features(self):
        pids = ["FP00010001", "WA00020001", "WA00020002", "FP00010002"]
        result = validate_pid_sequence(pids)
        assert len(result["features"]) == 2
        assert ("FP", 1) in result["features"]
        assert ("WA", 2) in result["features"]
