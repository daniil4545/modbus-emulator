"""Тесты encode_value и load_config из config.py."""

import pytest
import yaml

from config import encode_value, load_config


def test_encode_value_big_endian_int_word_order():
    assert encode_value(1, "int", 2) == [0, 1]


def test_encode_value_little_endian_word_swap():
    big = encode_value(1.5, "float", 2, byte_order="big-endian")
    little = encode_value(1.5, "float", 2, byte_order="little-endian")
    assert little == list(reversed(big))


def test_encode_value_invalid_byte_order():
    with pytest.raises(ValueError):
        encode_value(1, "uint", 1, byte_order="middle-endian")


def test_encode_value_unsupported_format():
    with pytest.raises(ValueError):
        encode_value(1, "uint", 3)


def _write_devices(tmp_path, devices):
    path = tmp_path / "devices.yaml"
    with open(path, "w") as f:
        yaml.dump(devices, f)
    return str(path)


def test_load_config_mapping_and_defaults(tmp_path):
    path = _write_devices(tmp_path, {
        "dev1": {
            "port_type": "modbus_tcp",
            "slave_id": 1,
            "registers": [
                {"reg_type": "holding", "address": 0, "format": "uint", "test_value": 10},
            ],
        },
    })
    devices = load_config(path)
    assert len(devices) == 1
    device = devices[0]
    assert device.port_type == "modbus tcp"
    assert device.timeout == 1
    assert device.poll_time == 5
    assert device.registers[0].reg_type == "hr"
    assert device.registers[0].scale == 1.0


def test_load_config_invalid_port_type(tmp_path):
    path = _write_devices(tmp_path, {
        "dev1": {"port_type": "bogus", "slave_id": 1, "registers": []},
    })
    with pytest.raises(ValueError):
        load_config(path)


def test_load_config_invalid_timeout(tmp_path):
    path = _write_devices(tmp_path, {
        "dev1": {"port_type": "tcp", "slave_id": 1, "timeout": 0, "registers": []},
    })
    with pytest.raises(ValueError):
        load_config(path)


def test_load_config_bit_register_keeps_test_value(tmp_path):
    """Регрессия: регистр с полем bit не должен пропускаться при инициализации."""
    path = _write_devices(tmp_path, {
        "dev1": {
            "port_type": "tcp",
            "slave_id": 1,
            "registers": [
                {"reg_type": "holding", "address": 4, "format": "int", "test_value": 42, "bit": 5},
            ],
        },
    })
    devices = load_config(path)
    assert len(devices[0].registers) == 1
    assert devices[0].registers[0].test_value == 42
