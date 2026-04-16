"""Tests für die TotalstationConnection (TCP + Seriell)."""
import pytest
from tachylog.connection import ConnectionConfig, TotalstationConnection


def test_tcp_config_default():
    config = ConnectionConfig()
    assert config.port == "tcp://localhost:4444"
    assert config.reflectorless is True


def test_tcp_flag():
    config = ConnectionConfig(port="tcp://localhost:4444")
    conn = TotalstationConnection(config)
    assert conn._use_tcp is True


def test_serial_flag():
    config = ConnectionConfig(port="/dev/rfcomm0")
    conn = TotalstationConnection(config)
    assert conn._use_tcp is False


def test_tcp_host_port_parsing():
    config = ConnectionConfig(port="tcp://localhost:4444")
    conn = TotalstationConnection(config)
    host, port = conn._tcp_host_port()
    assert host == "localhost"
    assert port == 4444


def test_tcp_host_port_ip():
    config = ConnectionConfig(port="tcp://192.168.1.5:9999")
    conn = TotalstationConnection(config)
    host, port = conn._tcp_host_port()
    assert host == "192.168.1.5"
    assert port == 9999


def test_not_connected_initially():
    config = ConnectionConfig()
    conn = TotalstationConnection(config)
    assert conn.is_connected() is False


def test_send_command_not_connected():
    config = ConnectionConfig()
    conn = TotalstationConnection(config)
    result = conn.send_command(5003)
    assert result["rc"] == -1
    assert "error" in result
