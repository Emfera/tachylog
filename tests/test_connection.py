"""Tests für ConnectionConfig."""
from tachylog.connection import ConnectionConfig


def test_default_port():
    config = ConnectionConfig()
    assert config.port == "tcp://localhost:4444"


def test_default_baudrate():
    # 115200 ist der korrekte Standardwert für Leica Flexline
    config = ConnectionConfig()
    assert config.baudrate == 115200


def test_tcp_port():
    config = ConnectionConfig(port="tcp://192.168.1.5:9999")
    assert config.port.startswith("tcp://")


def test_serial_port():
    config = ConnectionConfig(port="/dev/rfcomm0", baudrate=9600)
    assert config.baudrate == 9600
