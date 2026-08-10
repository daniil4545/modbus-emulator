"""Парсинг конфига устройств и кодирование test_value в uint16 words для Modbus datastore.

Схема конфига совпадает со схемой go-modbus2mqtt (config_yaml.go) плюс четыре поля
эмулятора: test_value, sim, sim_tick, count. Поля, которые читает только драйвер
(scale, truncate, writeable, event, timeout, poll_time), здесь не разбираются —
они уезжают в сгенерированный devices.yaml как есть.
"""

from __future__ import annotations

import struct
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
    id: str
    reg_type: str                    # "hr", "co", "di", "ir"
    address: int
    test_value: int | float | bool
    reg_size: int = 1
    format: Optional[str] = None     # "uint", "int", "float"; None для coil/discrete
    bit: Optional[int] = None
    sim: Optional[SimConfig] = None
    byte_order: str = "big-endian"   # "big-endian" | "little-endian"

    @property
    def span(self) -> int:
        """Сколько ячеек блока занимает регистр: слов для hr/ir, один бит для co/di."""
        return 1 if self.format is None else self.reg_size


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
    sim_tick: float = 1.0

    @property
    def endpoint(self) -> str:
        """Человекочитаемый адрес для стартовой таблицы и сообщений об ошибках."""
        if self.port_type == "serial":
            return self.path or "(pty)"
        return f"{self.ip or '0.0.0.0'}:{self.port}"


_REG_TYPE_MAP = {
    "holding": "hr",
    "input": "ir",
    "coil": "co",
    "discrete": "di",
}

REG_TYPE_LABELS = {v: k for k, v in _REG_TYPE_MAP.items()}

_WORD_REG_TYPES = ("hr", "ir")

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


class ConfigError(ValueError):
    """Конфиг не пройдёт ни на эмуляторе, ни на драйвере."""


def load_config(path: str) -> list[DeviceConfig]:
    """Читает YAML-файл устройств и возвращает список DeviceConfig."""
    with open(path) as f:
        return parse_devices(yaml.safe_load(f))


def parse_devices(raw: dict) -> list[DeviceConfig]:
    """Разбирает развёрнутый словарь устройств. Валидирует до запуска серверов."""
    if not raw:
        raise ConfigError("config is empty")

    devices = [_parse_device(name, dev) for name, dev in raw.items()]
    _check_endpoints(devices)
    return devices


def _parse_device(name: str, dev: dict) -> DeviceConfig:
    port_type = _PORT_TYPE_MAP.get(dev.get("port_type"))
    if port_type is None:
        raise ConfigError(f"{name}: unknown port_type {dev.get('port_type')!r}")

    slave_id = int(dev.get("slave_id", 1))
    if not 0 <= slave_id <= 0xF7:
        raise ConfigError(f"{name}: slave_id must be 0..247, got {slave_id}")

    if port_type in ("modbus tcp", "tcp") and dev.get("port") is None:
        raise ConfigError(f"{name}: port is required for port_type {port_type!r}")

    device = DeviceConfig(
        name=name,
        port_type=port_type,
        slave_id=slave_id,
        ip=dev.get("ip"),
        port=dev.get("port"),
        path=dev.get("path"),
        baud_rate=dev.get("baud_rate"),
        parity=dev.get("parity"),
        data_bits=dev.get("data_bits"),
        stop_bits=dev.get("stop_bits"),
        sim_tick=float(dev.get("sim_tick", 1.0)),
    )

    raw_regs = dev.get("registers") or []
    if not raw_regs:
        raise ConfigError(f"{name}: no registers")

    seen_ids: set[str] = set()
    for raw_reg in raw_regs:
        reg = _parse_register(name, raw_reg)
        if reg.id in seen_ids:
            raise ConfigError(f"{name}: duplicate register id {reg.id!r}")
        seen_ids.add(reg.id)
        device.registers.append(reg)

    _check_overlaps(device)
    return device


def _parse_register(device_name: str, raw: dict) -> RegisterConfig:
    reg_id = raw.get("id")
    if not reg_id:
        raise ConfigError(f"{device_name}: register without id")

    where = f"{device_name}.{reg_id}"

    reg_type = _REG_TYPE_MAP.get(raw.get("reg_type"))
    if reg_type is None:
        raise ConfigError(f"{where}: unknown reg_type {raw.get('reg_type')!r}")

    address = raw.get("address")
    if not isinstance(address, int) or address < 0:
        raise ConfigError(f"{where}: address must be a non-negative int, got {address!r}")

    if "test_value" not in raw:
        raise ConfigError(f"{where}: test_value is required")

    byte_order = raw.get("byte_order", "big-endian")
    if byte_order not in ("big-endian", "little-endian"):
        raise ConfigError(f"{where}: unknown byte_order {byte_order!r}")

    fmt = raw.get("format")
    reg_size = int(raw.get("reg_size", 1))
    bit = raw.get("bit")
    if bit == "~":  # YAML '~' уже даёт None, но конфиги встречаются и со строкой
        bit = None

    if bit is not None:
        # Драйвер сбрасывает bit при любом формате кроме bool (config_yaml.go:160),
        # поэтому несогласованный конфиг молча терял бы бит-регистр.
        if reg_type not in _WORD_REG_TYPES:
            raise ConfigError(f"{where}: bit is only valid for holding/input")
        if fmt != "bool":
            raise ConfigError(f"{where}: bit requires format: bool, got {fmt!r}")
        if not isinstance(bit, int) or not 0 <= bit <= 15:
            raise ConfigError(f"{where}: bit must be 0..15, got {bit!r}")
        # В datastore ложится всё слово целиком — бит из него извлекает драйвер.
        fmt, reg_size = "uint", 1
    elif reg_type in _WORD_REG_TYPES:
        if (fmt, reg_size) not in _STRUCT_FORMATS:
            raise ConfigError(f"{where}: unsupported format={fmt!r} with reg_size={reg_size}")
    else:
        fmt, reg_size = None, 1  # coil/discrete — один бит, format не участвует

    sim_raw = raw.get("sim")
    sim = None
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
        if sim.type == "step" and not sim.values:
            raise ConfigError(f"{where}: sim type 'step' requires non-empty values")
        if sim.period <= 0:
            raise ConfigError(f"{where}: sim period must be positive, got {sim.period}")

    return RegisterConfig(
        id=reg_id,
        reg_type=reg_type,
        address=address,
        test_value=raw["test_value"],
        reg_size=reg_size,
        format=fmt,
        bit=bit,
        sim=sim,
        byte_order=byte_order,
    )


def _check_overlaps(device: DeviceConfig) -> None:
    """Многословный регистр занимает address..address+reg_size-1 — соседи не должны туда попадать."""
    for reg_type in ("hr", "ir", "co", "di"):
        occupied: dict[int, str] = {}
        for reg in device.registers:
            if reg.reg_type != reg_type:
                continue
            for addr in range(reg.address, reg.address + reg.span):
                owner = occupied.get(addr)
                if owner is not None:
                    label = REG_TYPE_LABELS[reg_type]
                    raise ConfigError(
                        f"{device.name}: {label} address {addr} claimed by both "
                        f"{owner!r} and {reg.id!r}"
                    )
                occupied[addr] = reg.id


def _check_endpoints(devices: list[DeviceConfig]) -> None:
    """Один сервер на устройство, поэтому два устройства не могут делить ip:port."""
    seen: dict[str, str] = {}
    for device in devices:
        if device.port_type == "serial":
            continue
        key = device.endpoint
        owner = seen.get(key)
        if owner is not None:
            raise ConfigError(f"{device.name}: endpoint {key} already used by {owner}")
        seen[key] = device.name


def encode_value(
    value: int | float | bool,
    fmt: Optional[str],
    reg_size: int,
    byte_order: str = "big-endian",
) -> list[int]:
    """Кодирует значение в список uint16 words для записи в Modbus datastore.

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


def decode_words(words: list[int], fmt: Optional[str], byte_order: str = "big-endian") -> int | float | bool:
    """Обратная encode_value: слова из datastore → значение для лога."""
    if fmt is None:
        return bool(words[0]) if words else False

    if byte_order == "little-endian" and len(words) > 1:
        words = list(reversed(words))

    struct_fmt = _STRUCT_FORMATS.get((fmt, len(words)))
    if struct_fmt is None:
        return words[0] if len(words) == 1 else words

    raw = struct.pack(f">{len(words)}H", *words)
    return struct.unpack(struct_fmt, raw)[0]
