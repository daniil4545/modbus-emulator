"""Разворачивает template.yaml в dict, совместимый с devices.yaml.

Публичный интерфейс:
    expand_template(template_path) -> dict
    save_devices(expanded, output_path) -> None
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import yaml


def expand_template(template_path: str) -> dict:
    """Читает template.yaml и разворачивает count в отдельные устройства.

    Правила разворачивания:
    - count=1 (или поле отсутствует): устройство остаётся под исходным именем
    - count=N: создаёт N копий с именами name_01..name_N;
      port инкрементируется на i (только если поле port есть в прототипе),
      slave_id инкрементируется на i

    Args:
        template_path: путь к template.yaml

    Returns:
        dict вида {device_name: device_dict, ...} без поля count —
        готов к передаче в save_devices или load_config
    """
    with open(template_path) as f:
        raw = yaml.safe_load(f)

    result: dict = {}

    for name, proto in raw.items():
        count = proto.pop("count", 1)

        if count == 1:
            result[name] = copy.deepcopy(proto)
        else:
            for i in range(count):
                copy_name = f"{name}_{i+1:02d}"
                device = copy.deepcopy(proto)
                if "port" in proto:
                    device["port"] = proto["port"] + i
                device["slave_id"] = proto["slave_id"] + i
                result[copy_name] = device

    return result


def save_devices(expanded: dict, output_path: str) -> None:
    """Сериализует развёрнутый dict в YAML-файл и печатает подтверждение.

    Args:
        expanded:    результат expand_template()
        output_path: путь для записи (создаёт файл или перезаписывает существующий)
    """
    with open(output_path, "w") as f:
        yaml.dump(expanded, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"[generator] Expanded {len(expanded)} devices → {output_path}")


if __name__ == "__main__":
    template_path = sys.argv[1] if len(sys.argv) > 1 else "template.yaml"
    output_path = sys.argv[2] if len(sys.argv) > 2 else str(Path(template_path).parent / "devices.yaml")

    expanded = expand_template(template_path)
    print(yaml.dump(expanded, allow_unicode=True, default_flow_style=False, sort_keys=False))
    save_devices(expanded, output_path)
