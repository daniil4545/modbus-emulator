"""Тесты expand_template из generator.py."""

import yaml

from generator import expand_template


def _write_template(tmp_path, template):
    path = tmp_path / "template.yaml"
    with open(path, "w") as f:
        yaml.dump(template, f)
    return str(path)


def test_expand_template_count_one_no_suffix(tmp_path):
    path = _write_template(tmp_path, {
        "dev1": {"port_type": "modbus_tcp", "ip": "127.0.0.1", "port": 15020, "slave_id": 1, "count": 1, "registers": []},
    })
    result = expand_template(path)
    assert "dev1" in result
    assert "dev1_01" not in result


def test_expand_template_count_n_increments_port_and_slave_id(tmp_path):
    path = _write_template(tmp_path, {
        "dev1": {"port_type": "modbus_tcp", "ip": "127.0.0.1", "port": 15020, "slave_id": 1, "count": 3, "registers": []},
    })
    result = expand_template(path)
    assert set(result) == {"dev1_01", "dev1_02", "dev1_03"}
    assert result["dev1_02"]["port"] == 15021
    assert result["dev1_02"]["slave_id"] == 2
    assert result["dev1_03"]["port"] == 15022
    assert result["dev1_03"]["slave_id"] == 3


def test_expand_template_serial_without_port_does_not_fail(tmp_path):
    path = _write_template(tmp_path, {
        "dev1": {"port_type": "serial", "slave_id": 20, "count": 2, "registers": []},
    })
    result = expand_template(path)
    assert set(result) == {"dev1_01", "dev1_02"}
    assert "port" not in result["dev1_02"]
    assert result["dev1_02"]["slave_id"] == 21
