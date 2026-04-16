"""Tests für den GSI-Parser."""
import pytest
from tachylog.gsi_parser import parse_gsi_response, measurement_key, _gsi_to_float, _gsi_to_pid


class TestGsiToFloat:
    def test_positive(self):
        assert _gsi_to_float("+00123456") == pytest.approx(123.456)

    def test_negative(self):
        assert _gsi_to_float("-00123456") == pytest.approx(-123.456)

    def test_zero(self):
        assert _gsi_to_float("+00000000") == pytest.approx(0.0)

    def test_large(self):
        assert _gsi_to_float("+12345678") == pytest.approx(12345.678)


class TestGsiToPid:
    def test_alphanumeric(self):
        assert _gsi_to_pid("+00000FP1") == "FP1"

    def test_full_pid(self):
        assert _gsi_to_pid("+0FP00010001") == "FP00010001"

    def test_numeric(self):
        assert _gsi_to_pid("+00001234") == "1234"


class TestParseGsiResponse:
    def test_valid_response(self):
        raw = "%R1P,0,0:0,110001+00FP00010001 81..00+00123456 82..00+00654321 83..00+00001234"
        m = parse_gsi_response(raw)
        assert m is not None
        assert m.pid == "FP00010001"
        assert m.e == pytest.approx(123.456)
        assert m.n == pytest.approx(654.321)
        assert m.h == pytest.approx(1.234)

    def test_none_on_empty(self):
        assert parse_gsi_response("") is None

    def test_none_on_no_r1p(self):
        assert parse_gsi_response("some random string") is None

    def test_none_on_error_rc(self):
        raw = "%R1P,0,0:5,110001+00FP1 81..00+00123456 82..00+00654321 83..00+00001234"
        assert parse_gsi_response(raw) is None

    def test_warning_rc_ok(self):
        # RC 1283 ist ein bekanntes Warning, Messung trotzdem gültig
        raw = "%R1P,0,0:1283,110001+00FP1 81..00+00123456 82..00+00654321 83..00+00001234"
        m = parse_gsi_response(raw)
        assert m is not None


class TestMeasurementKey:
    def test_same_key(self):
        raw = "%R1P,0,0:0,110001+00FP1 81..00+00123456 82..00+00654321 83..00+00001234"
        m1 = parse_gsi_response(raw)
        m2 = parse_gsi_response(raw)
        assert measurement_key(m1) == measurement_key(m2)

    def test_different_pid(self):
        r1 = "%R1P,0,0:0,110001+00FP1 81..00+00123456 82..00+00654321 83..00+00001234"
        r2 = "%R1P,0,0:0,110001+00FP2 81..00+00123456 82..00+00654321 83..00+00001234"
        m1 = parse_gsi_response(r1)
        m2 = parse_gsi_response(r2)
        assert measurement_key(m1) != measurement_key(m2)
