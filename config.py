"""Парсинг YAML-конфига и кодирование test_value в uint16 words для Modbus datastore."""

from __future__ import annotations

import struct
import sys
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class SimConfig:
    type: str                        # "sine" | "ramp" | "step" | "random_walk"
    min: float = 0.0
    max: float = 1.0
    period: float = 10.0
    phase: float = 0.0               # сдвиг фазы в секундах, только для sine
    step: float = 1.0                # шаг случайного блуждания, только для random_walk
    values: list = field(default_factory=list)  # список значений, только для step


@dataclass
class RegisterConfig:
    reg_type: str                    # "hr", "co", "di", "ir"
    address: int
    test_value: int | float | bool
    reg_size: int = 1
    format: Optional[str] = None    # "uint", "int", "float"; None для coil/discrete
    bit: Optional[int] = None
    sim: Optional[SimConfig] = None
    byte_order: str = "big-endian"  # "big-endian" | "little-endian"
    scale: float = 1.0              # множитель значения (для драйвера)
    truncate: Optional[int] = None  # знаков после запятой (для драйвера)
    writeable: int = 0              # 0/1: признак записываемого регистра (для драйвера)
    event: int = 0                  # 0/1: публиковать только при изменении (для драйвера)


@dataclass
class DeviceConfig:
    name: str
    port_type: str                   # "modbus_tcp", "tcp", "serial"
    slave_id: int
    registers: list[RegisterConfig] = field(default_factory=list)
    ip: Optional[str] = None
    port: Optional[int] = None
    path: Optional[str] = None
    baud_rate: Optional[int] = None
    parity: Optional[str] = None
    data_bits: Optional[int] = None
    stop_bits: Optional[int] = None
    sim_tick: float = 1.0
    timeout: int = 1                 # таймаут соединения, сек (для драйвера)
    poll_time: int = 5               # интервал опроса, сек (для драйвера)


_REG_TYPE_MAP = {
    "holding": "hr",
    "input": "ir",
    "coil": "co",
    "discrete": "di",
}

_PORT_TYPE_MAP = {
    "modbus_tcp": "modbus tcp",  # normalize to internal name
    "modbus tcp": "modbus tcp",
    "tcp": "tcp",
    "serial": "serial",
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
        raw_port_type = dev["port_type"]
        port_type = _PORT_TYPE_MAP.get(raw_port_type)
        if port_type is None:
            raise ValueError(f"{name}: unknown port_type '{raw_port_type}'")

        timeout = int(dev.get("timeout", 1))
        if timeout <= 0:
            raise ValueError(f"{name}: timeout must be positive, got {timeout}")

        poll_time = int(dev.get("poll_time", 5))
        if poll_time <= 0:
            raise ValueError(f"{name}: poll_time must be positive, got {poll_time}")

        device = DeviceConfig(
            name=name,
            port_type=port_type,
            slave_id=dev["slave_id"],
            ip=dev.get("ip"),
            port=dev.get("port"),
            path=dev.get("path"),
            baud_rate=dev.get("baud_rate"),
            parity=dev.get("parity"),
            data_bits=dev.get("data_bits"),
            stop_bits=dev.get("stop_bits"),
            sim_tick=float(dev.get("sim_tick", 1.0)),
            timeout=timeout,
            poll_time=poll_time,
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

            sim = None
            sim_raw = reg.get("sim")
            if sim_raw is not None:
                sim = SimConfig(
                    type=sim_raw["type"],
                    min=float(sim_raw.get("min", 0.0)),
                    max=float(sim_raw.get("max", 1.0)),
                    period=float(sim_raw.get("period", 10.0)),
                    phase=float(sim_raw.get("phase", 0.0)),
                    step=float(sim_raw.get("step", 1.0)),
                    values=list(sim_raw.get("values", [])),
                )

            _trunc = reg.get("truncate")
            if _trunc is not None and _trunc != "~":
                truncate_val = int(_trunc)
                if truncate_val < 0:
                    raise ValueError(f"{name}: truncate must be non-negative, got {truncate_val}")
            else:
                truncate_val = None

            scale = float(reg.get("scale", 1.0))
            if scale == 0.0:
                raise ValueError(f"{name}: scale must not be zero")

            device.registers.append(RegisterConfig(
                reg_type=reg_type,
                address=reg["address"],
                test_value=reg["test_value"],
                reg_size=reg.get("reg_size", 1),
                format=reg.get("format"),  # None для coil/discrete
                sim=sim,
                byte_order=reg.get("byte_order", "big-endian"),
                scale=scale,
                truncate=truncate_val,
                writeable=int(reg.get("writeable", 0)),
                event=int(reg.get("event", 0)),
            ))

        devices.append(device)

    return devices


def encode_value(
    value: int | float | bool,
    fmt: Optional[str],
    reg_size: int,
    byte_order: str = "big-endian",
) -> list[int]:
    """Кодирует test_value в список uint16 words для записи в Modbus datastore.

    fmt=None означает coil или discrete — кодируется как один бит (0 или 1).

    byte_order="big-endian": high word first (дефолт).
    byte_order="little-endian": word-swap — те же bytes, слова в обратном порядке.
    Для reg_size=1 и coil/discrete byte_order игнорируется.
    """
    if fmt is None:
        return [int(bool(value))]

    if byte_order not in ("big-endian", "little-endian"):
        raise ValueError(f"unknown byte_order: {byte_order!r}; expected 'big-endian' or 'little-endian'")

    struct_fmt = _STRUCT_FORMATS.get((fmt, reg_size))
    if struct_fmt is None:
        raise ValueError(f"unsupported: format='{fmt}', reg_size={reg_size}")

    raw = struct.pack(struct_fmt, value)
    words = list(struct.unpack(f">{len(raw) // 2}H", raw))

    if byte_order == "little-endian" and len(words) > 1:
        words = list(reversed(words))

    return words


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "devices.yaml"
    devices = load_config(config_path)

    print(f"Loaded {len(devices)} devices\n")
    for dev in devices:
        addr_info = f"{dev.ip}:{dev.port}" if dev.ip else dev.path
        print(f"  [{dev.port_type}] {dev.name}  {addr_info}  slave_id={dev.slave_id}")
        for reg in dev.registers:
            words = encode_value(reg.test_value, reg.format, reg.reg_size, reg.byte_order)
            print(
                f"    [{reg.reg_type}] addr={reg.address}  "
                f"fmt={reg.format or 'bool'}  val={reg.test_value}  words={words}"
            )
        print()
