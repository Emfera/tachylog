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
        # GSI16, Unit 06 (0.1mm): Wert / 10000 = Meter
        # 11112846 / 10000 = 1111.2846
        raw = "%R1P,0,0:0,110001+00FP00010001 81..06+00011112846 82..06+00007350902 83..06+00000054191"
        m = parse_gsi_response(raw)
        assert m is not None
        assert m.pid == "FP00010001"
        assert m.e == pytest.approx(1111.2846)
        assert m.n == pytest.approx(735.0902)
        assert m.h == pytest.approx(5.4191)

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
    def test_polling_repeat_is_duplicate(self):
        """Gleicher Raw-String = Gerät hat keine neue Messung → Duplikat."""
        raw = "%R1P,0,0:0,110001+00FP1 81..00+00123456 82..00+00654321 83..00+00001234"
        m1 = parse_gsi_response(raw)
        m2 = parse_gsi_response(raw)
        assert measurement_key(m1) == measurement_key(m2)

    def test_different_pid_is_new(self):
        r1 = "%R1P,0,0:0,110001+00FP1 81..00+00123456 82..00+00654321 83..00+00001234"
        r2 = "%R1P,0,0:0,110001+00FP2 81..00+00123456 82..00+00654321 83..00+00001234"
        m1 = parse_gsi_response(r1)
        m2 = parse_gsi_response(r2)
        assert measurement_key(m1) != measurement_key(m2)

    def test_same_pid_same_coords_is_new(self):
        """Gleiche PID, gleiche Koordinaten — aber anderer Raw-String
        (z.B. Leerzeichen, Sequenz) = neue Messung, darf nicht gedroppt werden."""
        # Minimal unterschiedliche Raw-Strings (verschiedene Whitespace-Trenner)
        r1 = "%R1P,0,0:0,110001+00FP1 81..00+00123456 82..00+00654321 83..00+00001234"
        r2 = "%R1P,0,0:0,110001+00FP1  81..00+00123456 82..00+00654321 83..00+00001234"
        m1 = parse_gsi_response(r1)
        m2 = parse_gsi_response(r2)
        assert measurement_key(m1) != measurement_key(m2)

    def test_received_at_default(self):
        """received_at ist 0.0 wenn vom Parser gesetzt (Collector setzt es später)."""
        raw = "%R1P,0,0:0,110001+00FP1 81..00+00123456 82..00+00654321 83..00+00001234"
        m = parse_gsi_response(raw)
        assert m.received_at == 0.0
