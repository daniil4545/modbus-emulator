"""Парсинг YAML-конфига и кодирование test_value в uint16 words для Modbus datastore."""

from __future__ import annotations

import struct
import sys
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class RegisterConfig:
    reg_type: str                    # "hr", "co", "di", "ir"
    address: int
    test_value: int | float | bool
    reg_size: int = 1
    format: Optional[str] = None    # "uint", "int", "float"; None для coil/discrete
    bit: Optional[int] = None


@dataclass
class DeviceConfig:
    name: str
    port_type: str                   # "modbus tcp", "tcp", "serial"
    slave_id: int
    registers: list[RegisterConfig] = field(default_factory=list)
    ip: Optional[str] = None
    port: Optional[int] = None
    path: Optional[str] = None
    baud_rate: Optional[int] = None
    parity: Optional[str] = None
    data_bits: Optional[int] = None
    stop_bits: Optional[int] = None


_REG_TYPE_MAP = {
    "holding": "hr",
    "input": "ir",
    "coil": "co",
    "discrete": "di",
}

_STRUCT_FORMATS = {
    ("uint", 1): ">H",
    ("uint", 2): ">I",
    ("uint", 4): ">Q",
    ("int", 1): ">h",
    ("int", 2): ">i",
    ("int", 4): ">q",
    ("float", 2): ">f",
    ("float", 4): ">d",
}


def load_config(path: str) -> list[DeviceConfig]:
    """Читает devices.yaml и возвращает список DeviceConfig."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    devices = []
    for name, dev in raw.items():
        device = DeviceConfig(
            name=name,
            port_type=dev["port_type"],
            slave_id=dev["slave_id"],
            ip=dev.get("ip"),
            port=dev.get("port"),
            path=dev.get("path"),
            baud_rate=dev.get("baud_rate"),
            parity=dev.get("parity"),
            data_bits=dev.get("data_bits"),
            stop_bits=dev.get("stop_bits"),
        )

        for reg in dev.get("registers", []):
            # Bit-регистры разделяют адрес с raw_word и не имеют своего test_value.
            # raw_word несёт полное значение слова — его мы и запишем в datastore.
            if reg.get("bit") is not None:
                continue

            yaml_reg_type = reg["reg_type"]
            reg_type = _REG_TYPE_MAP.get(yaml_reg_type)
            if reg_type is None:
                raise ValueError(f"{name}: unknown reg_type '{yaml_reg_type}'")

            device.registers.append(RegisterConfig(
                reg_type=reg_type,
                address=reg["address"],
                test_value=reg["test_value"],
                reg_size=reg.get("reg_size", 1),
                format=reg.get("format"),  # None для coil/discrete
            ))

        devices.append(device)

    return devices


def encode_value(value: int | float | bool, fmt: Optional[str], reg_size: int) -> list[int]:
    """Кодирует test_value в список uint16 words для записи в Modbus datastore.

    fmt=None означает coil или discrete — кодируется как один бит (0 или 1).

    Multi-register значения кодируются в big-endian word order (high word first),
    так как go-modbus-client читает регистры в стандартном big-endian порядке.
    """
    if fmt is None:
        return [int(bool(value))]

    struct_fmt = _STRUCT_FORMATS.get((fmt, reg_size))
    if struct_fmt is None:
        raise ValueError(f"unsupported: format='{fmt}', reg_size={reg_size}")

    raw = struct.pack(struct_fmt, value)
    return list(struct.unpack(f">{len(raw) // 2}H", raw))


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "devices.yaml"
    devices = load_config(config_path)

    print(f"Loaded {len(devices)} devices\n")
    for dev in devices:
        addr_info = f"{dev.ip}:{dev.port}" if dev.ip else dev.path
        print(f"  [{dev.port_type}] {dev.name}  {addr_info}  slave_id={dev.slave_id}")
        for reg in dev.registers:
            words = encode_value(reg.test_value, reg.format, reg.reg_size)
            print(
                f"    [{reg.reg_type}] addr={reg.address}  "
                f"fmt={reg.format or 'bool'}  val={reg.test_value}  words={words}"
            )
        print()
