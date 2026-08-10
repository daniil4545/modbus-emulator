"""Точка входа эмулятора: template.yaml -> devices.yaml -> запуск Modbus-серверов.

Usage:
    python main.py                    # template.yaml в текущей директории
    python main.py custom.yaml
    python main.py --check            # только развернуть и проверить конфиг
    python main.py -v                 # логировать и чтения тоже
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from config import REG_TYPE_LABELS, ConfigError, DeviceConfig, encode_value, parse_devices
from generator import expand_template, save_devices
from servers import NORMAL, QUIET, VERBOSE, build_all, serve


def print_map(devices: list[DeviceConfig]) -> None:
    """Карта конфига: что и по каким адресам окажется в datastore."""
    for device in devices:
        print(f"\n{device.name}  [{device.port_type}]  {device.endpoint}  slave_id={device.slave_id}")
        for reg in device.registers:
            span = f"{reg.address}..{reg.address + reg.span - 1}" if reg.span > 1 else str(reg.address)
            words = encode_value(reg.test_value, reg.format, reg.reg_size, reg.byte_order)
            notes = []
            if reg.bit is not None:
                notes.append(f"bit {reg.bit}")
            if reg.byte_order != "big-endian":
                notes.append(reg.byte_order)
            if reg.sim is not None:
                notes.append(f"sim {reg.sim.type}")
            suffix = f"  [{', '.join(notes)}]" if notes else ""
            print(
                f"  {REG_TYPE_LABELS[reg.reg_type]:<8} {span:<7} "
                f"{reg.format or 'bool':<6} {str(reg.test_value):<8} -> {words}"
                f"  {reg.id}{suffix}"
            )


def print_devices(devices: list[DeviceConfig], setup) -> None:
    """Стартовая таблица: где какой сервер слушает."""
    for device in devices:
        endpoint = setup.serial_paths.get(device.name, device.endpoint)
        print(
            f"  {device.port_type:<11} {device.name:<20} {endpoint:<22} "
            f"slave_id={device.slave_id:<4} {len(device.registers)} registers"
        )


async def run(template_path: str, verbosity: int) -> None:
    """expand -> parse -> build -> записать devices.yaml -> serve."""
    expanded = expand_template(template_path)
    devices = parse_devices(expanded)

    setup = await build_all(devices, verbosity)

    for name, pty_path in setup.serial_paths.items():
        expanded[name]["path"] = pty_path

    devices_path = Path(template_path).parent / "devices.yaml"
    save_devices(expanded, str(devices_path))

    print(f"[emulator] {len(devices)} devices from {template_path}\n")
    print_devices(devices, setup)
    print(f"\n[emulator] driver config written to {devices_path.resolve()}")
    print(f"  go run . --config {devices_path.resolve()}")
    print("\nAll servers ready. Press Ctrl+C to stop.\n")

    await serve(setup)
    print("[emulator] stopped")


def main() -> int:
    # Внутренние сообщения pymodbus дублируют наш лог (например про чужой slave_id).
    logging.getLogger("pymodbus").setLevel(logging.CRITICAL)

    parser = argparse.ArgumentParser(description="Modbus device emulator")
    parser.add_argument("template", nargs="?", default="template.yaml", help="путь к template.yaml")
    parser.add_argument("--check", action="store_true", help="проверить конфиг и показать карту, не запуская серверы")
    parser.add_argument("-q", "--quiet", action="store_true", help="логировать только ошибки")
    parser.add_argument("-v", "--verbose", action="store_true", help="логировать и чтения тоже")
    args = parser.parse_args()

    try:
        if args.check:
            devices = parse_devices(expand_template(args.template))
            print(f"[emulator] {args.template}: {len(devices)} devices, config is valid")
            print_map(devices)
            return 0

        verbosity = QUIET if args.quiet else VERBOSE if args.verbose else NORMAL
        asyncio.run(run(args.template, verbosity))
    except ConfigError as exc:
        print(f"[config error] {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:  # пустой или неразбираемый template
        print(f"[config error] {exc}", file=sys.stderr)
        return 1
    except OSError as exc:  # порт занят, нет файла конфига, недоступен путь
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
