"""Разворачивает template.yaml в словарь устройств формата go-modbus2mqtt.

Публичный интерфейс:
    expand_template(template_path) -> dict
    save_devices(expanded, output_path) -> None
"""

from __future__ import annotations

import copy

import yaml


def expand_template(template_path: str) -> dict:
    """Читает template.yaml и разворачивает count в отдельные устройства.

    Правила разворачивания:
    - count=1 (или поле отсутствует): устройство остаётся под исходным именем
    - count=N: создаёт N копий с именами name_01..name_N;
      port инкрементируется на i (только если поле port есть в прототипе),
      slave_id инкрементируется на i

    Returns:
        dict вида {device_name: device_dict, ...} без поля count —
        готов к передаче в save_devices или parse_devices
    """
    with open(template_path) as f:
        raw = yaml.safe_load(f)

    if not raw:
        raise ValueError(f"{template_path}: template is empty")

    result: dict = {}

    for name, proto in raw.items():
        if not isinstance(proto, dict):
            raise ValueError(f"{name}: device block is empty")

        count = proto.get("count", 1)
        if not isinstance(count, int) or count < 1:
            raise ValueError(f"{name}: count must be a positive int, got {count!r}")

        for i in range(count):
            device = copy.deepcopy(proto)
            device.pop("count", None)

            if count == 1:
                result[name] = device
                continue

            if "port" in proto:
                device["port"] = proto["port"] + i
            device["slave_id"] = proto.get("slave_id", 1) + i
            result[f"{name}_{i + 1:02d}"] = device

    return result


def save_devices(expanded: dict, output_path: str) -> None:
    """Сериализует развёрнутый словарь в YAML-файл для драйвера."""
    with open(output_path, "w") as f:
        yaml.dump(expanded, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
