"""Точка входа эмулятора: template.yaml → devices.yaml → запуск всех Modbus-серверов.

Usage:
    python main.py                  # использует template.yaml в текущей директории
    python main.py template.yaml
    python main.py custom.yaml
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from config import load_config
from generator import expand_template, save_devices
from servers import build_all


async def run(template_path: str) -> None:
    """Запускает полный pipeline: expand → save → load → build → serve.

    Шаги:
    1. Разворачивает template.yaml → expanded dict
    2. Сохраняет expanded dict → devices.yaml рядом с template
    3. Загружает devices.yaml → список DeviceConfig
    4. Создаёт серверы, PTY-пары, sim-корутины → ServerSetup
       (build_all сам печатает список серверов и driver-команду)
    5. Запускает все серверы и симуляции, ждёт Ctrl+C
    6. При выходе закрывает PTY file descriptors
    """
    devices_path = str(Path(template_path).parent / "devices.yaml")

    expanded = expand_template(template_path)
    save_devices(expanded, devices_path)

    devices = load_config(devices_path)
    setup = build_all(devices, devices_path)

    print("\nAll servers ready. Press Ctrl+C to stop.")

    try:
        await asyncio.gather(
            *(s.serve_forever() for s in setup.servers),
            *setup.sim_coroutines,
        )
    except asyncio.CancelledError:
        pass
    finally:
        for fd in setup.master_fds:
            os.close(fd)


if __name__ == "__main__":
    template_path = sys.argv[1] if len(sys.argv) > 1 else "template.yaml"
    asyncio.run(run(template_path))
