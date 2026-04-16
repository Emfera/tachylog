"""Tests für GeoCOM-Protokoll: Konstanten, Parser, Befehlsaufbau."""
import pytest
from tachylog.geocom_constants import RC, RPC, TMC_MODE, build_request, parse_response


class TestRC:
    def test_ok(self):
        assert RC.is_ok(0) is True
        assert RC.is_ok(1) is False

    def test_warning(self):
        assert RC.is_warning(1288) is True   # TMC_ACCURACY_GUARANTEE
        assert RC.is_warning(1283) is True   # TMC_NO_FULL_CORR
        assert RC.is_warning(0) is False

    def test_fatal(self):
        assert RC.is_fatal(1) is True        # UNDEFINED
        assert RC.is_fatal(0) is False
        assert RC.is_fatal(1288) is False    # Warning, kein Fehler

    def test_describe(self):
        assert "OK" in RC.describe(0)
        assert "Timeout" in RC.describe(6)
        assert "Unbekannter Code" in RC.describe(9999)


class TestBuildRequest:
    def test_no_params(self):
        r = build_request(RPC.COM_GET_SW_VERSION)
        assert r == "%R1Q,5003:\r\n"

    def test_with_params(self):
        r = build_request(RPC.TMC_DO_MEASURE, 11, 1)
        assert r == "%R1Q,2008:11,1\r\n"

    def test_get_coordinate(self):
        r = build_request(RPC.TMC_GET_COORDINATE, 0, 1, 0)
        assert r == "%R1Q,2082:0,1,0\r\n"


class TestParseResponse:
    def test_version_response(self):
        raw = "%R1P,0,0:0,3359283"
        result = parse_response(raw)
        assert result["rc"] == 0
        assert result["values"] == [3359283]

    def test_coordinate_response(self):
        raw = "%R1P,0,0:0,500123.456,160234.789,412.300"
        result = parse_response(raw)
        assert result["rc"] == 0
        assert len(result["values"]) == 3
        assert abs(result["values"][0] - 500123.456) < 0.001
        assert abs(result["values"][1] - 160234.789) < 0.001
        assert abs(result["values"][2] - 412.300) < 0.001

    def test_error_response(self):
        raw = "%R1P,0,0:3,0,0"
        result = parse_response(raw)
        assert result["rc"] == 3   # IVRESULT

    def test_warning_response(self):
        raw = "%R1P,0,0:1288,500000.0,160000.0,400.0"
        result = parse_response(raw)
        assert result["rc"] == 1288
        assert RC.is_warning(result["rc"])

    def test_invalid_response(self):
        result = parse_response("garbage")
        assert result["rc"] == -1

    def test_empty(self):
        result = parse_response("")
        assert result["rc"] == -1
