"""Валидация конфига и разворот count."""

import copy

import pytest
import yaml

from config import ConfigError, parse_devices
from generator import expand_template

BASE = {
    "dev": {
        "port_type": "modbus_tcp",
        "ip": "127.0.0.1",
        "port": 15020,
        "slave_id": 1,
        "registers": [
            {"id": "temp", "reg_type": "holding", "address": 0, "format": "uint", "test_value": 5},
        ],
    }
}


def config_with(*registers, **device_fields):
    raw = copy.deepcopy(BASE)
    raw["dev"].update(device_fields)
    raw["dev"]["registers"] = list(registers)
    return raw


def test_valid_config_parses():
    devices = parse_devices(copy.deepcopy(BASE))
    assert [d.name for d in devices] == ["dev"]
    assert devices[0].registers[0].id == "temp"


def test_bit_register_normalized_to_whole_word():
    """format: bool + bit — в datastore кладём слово, поэтому uint/1 слово."""
    raw = config_with(
        {"id": "status", "reg_type": "holding", "address": 0, "format": "bool", "test_value": 42, "bit": 5}
    )
    reg = parse_devices(raw)[0].registers[0]
    assert (reg.format, reg.reg_size, reg.bit) == ("uint", 1, 5)


def test_bit_requires_format_bool():
    raw = config_with(
        {"id": "status", "reg_type": "holding", "address": 0, "format": "int", "test_value": 42, "bit": 5}
    )
    with pytest.raises(ConfigError, match="format: bool"):
        parse_devices(raw)


def test_bit_rejected_on_coil():
    raw = config_with({"id": "flag", "reg_type": "coil", "address": 0, "format": "bool", "test_value": 1, "bit": 3})
    with pytest.raises(ConfigError, match="holding/input"):
        parse_devices(raw)


def test_bit_out_of_range():
    raw = config_with(
        {"id": "status", "reg_type": "holding", "address": 0, "format": "bool", "test_value": 1, "bit": 16}
    )
    with pytest.raises(ConfigError, match="0..15"):
        parse_devices(raw)


def test_overlapping_addresses_rejected():
    """float на адресе 0 занимает 0 и 1, поэтому сосед на 1 — ошибка."""
    raw = config_with(
        {"id": "a", "reg_type": "holding", "address": 0, "reg_size": 2, "format": "float", "test_value": 1.0},
        {"id": "b", "reg_type": "holding", "address": 1, "format": "uint", "test_value": 2},
    )
    with pytest.raises(ConfigError, match="address 1 claimed"):
        parse_devices(raw)


def test_same_address_in_different_blocks_allowed():
    raw = config_with(
        {"id": "a", "reg_type": "holding", "address": 0, "format": "uint", "test_value": 1},
        {"id": "b", "reg_type": "input", "address": 0, "format": "uint", "test_value": 2},
    )
    assert len(parse_devices(raw)[0].registers) == 2


def test_duplicate_register_id_rejected():
    raw = config_with(
        {"id": "a", "reg_type": "holding", "address": 0, "format": "uint", "test_value": 1},
        {"id": "a", "reg_type": "holding", "address": 1, "format": "uint", "test_value": 2},
    )
    with pytest.raises(ConfigError, match="duplicate register id"):
        parse_devices(raw)


def test_unknown_reg_type_rejected():
    raw = config_with({"id": "a", "reg_type": "register", "address": 0, "format": "uint", "test_value": 1})
    with pytest.raises(ConfigError, match="unknown reg_type"):
        parse_devices(raw)


def test_unknown_port_type_rejected():
    raw = copy.deepcopy(BASE)
    raw["dev"]["port_type"] = "rs485"
    with pytest.raises(ConfigError, match="unknown port_type"):
        parse_devices(raw)


def test_tcp_requires_port():
    raw = copy.deepcopy(BASE)
    del raw["dev"]["port"]
    with pytest.raises(ConfigError, match="port is required"):
        parse_devices(raw)


def test_duplicate_endpoint_rejected():
    raw = copy.deepcopy(BASE)
    raw["twin"] = copy.deepcopy(raw["dev"])
    with pytest.raises(ConfigError, match="already used"):
        parse_devices(raw)


def test_unsupported_format_size_rejected():
    raw = config_with({"id": "a", "reg_type": "holding", "address": 0, "reg_size": 1, "format": "float", "test_value": 1.0})
    with pytest.raises(ConfigError, match="unsupported format"):
        parse_devices(raw)


def test_expand_count_increments_port_and_slave(tmp_path):
    template = tmp_path / "t.yaml"
    raw = copy.deepcopy(BASE)
    raw["dev"]["count"] = 3
    template.write_text(yaml.dump(raw))

    expanded = expand_template(str(template))

    assert list(expanded) == ["dev_01", "dev_02", "dev_03"]
    assert [d["port"] for d in expanded.values()] == [15020, 15021, 15022]
    assert [d["slave_id"] for d in expanded.values()] == [1, 2, 3]
    assert "count" not in expanded["dev_01"]


def test_expand_count_one_keeps_name(tmp_path):
    template = tmp_path / "t.yaml"
    template.write_text(yaml.dump(copy.deepcopy(BASE)))
    assert list(expand_template(str(template))) == ["dev"]


def test_expand_serial_without_port_increments_only_slave(tmp_path):
    """У serial-прототипа нет поля port — инкрементируется только slave_id."""
    template = tmp_path / "t.yaml"
    template.write_text(yaml.dump({
        "meter": {"port_type": "serial", "slave_id": 20, "count": 2, "registers": []},
    }))

    expanded = expand_template(str(template))

    assert set(expanded) == {"meter_01", "meter_02"}
    assert "port" not in expanded["meter_02"]
    assert expanded["meter_02"]["slave_id"] == 21


def test_expand_rejects_non_positive_count(tmp_path):
    """count: 0 молча выбрасывал устройство из конфига."""
    template = tmp_path / "t.yaml"
    raw = copy.deepcopy(BASE)
    raw["dev"]["count"] = 0
    template.write_text(yaml.dump(raw))
    with pytest.raises(ValueError, match="count must be"):
        expand_template(str(template))


def test_expand_rejects_empty_device_block(tmp_path):
    template = tmp_path / "t.yaml"
    template.write_text("dev:\n")
    with pytest.raises(ValueError, match="device block is empty"):
        expand_template(str(template))
