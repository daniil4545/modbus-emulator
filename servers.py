"""Создание Modbus-серверов и инициализация регистров из DeviceConfig."""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass

import yaml
from pymodbus import FramerType
from pymodbus.datastore import ModbusSlaveContext, ModbusSequentialDataBlock, ModbusServerContext
from pymodbus.server import ModbusSerialServer, ModbusTcpServer

from config import DeviceConfig, encode_value, load_config
from simulator import run_device_sim


class ObservableDataBlock(ModbusSequentialDataBlock):
    """DataBlock, логирующий входящие записи через _on_write.

    _on_write=None во время инициализации — init-записи молчат.
    Устанавливается после того, как все стартовые значения записаны.
    """

    def __init__(self, address, values):
        super().__init__(address, values)
        self._on_write = None

    def setValues(self, address, values):
        super().setValues(address, values)
        if self._on_write is not None:
            # ModbusSlaveContext добавляет +1 перед вызовом; вычитаем, чтобы
            # получить 0-indexed адрес как в devices.yaml.
            self._on_write(address - 1, values)

    def sim_setValues(self, address, values):
        """Запись без вызова _on_write. Используется симулятором."""
        super().setValues(address, values)


@dataclass
class ServerSetup:
    servers: list
    master_fds: list[int]
    sim_coroutines: list


_BLOCK_LABELS = {"di": "discrete", "co": "coil", "hr": "holding", "ir": "input"}


def _build_context(
    device: DeviceConfig,
) -> tuple[ModbusServerContext, dict[str, ObservableDataBlock]]:
    blocks: dict[str, ObservableDataBlock] = {
        k: ObservableDataBlock(0, [0] * 65536) for k in ("di", "co", "hr", "ir")
    }

    for reg in device.registers:
        words = encode_value(reg.test_value, reg.format, reg.reg_size)
        blocks[reg.reg_type].setValues(reg.address + 1, words)

    # Включаем колбэки после init — выше они были None и не срабатывали
    for block_type, block in blocks.items():
        label = _BLOCK_LABELS[block_type]
        block._on_write = lambda addr, vals, n=device.name, t=label: print(
            f"[write] {n} [{t}] addr={addr}  values={vals}"
        )

    store = ModbusSlaveContext(di=blocks["di"], co=blocks["co"], hr=blocks["hr"], ir=blocks["ir"])
    return ModbusServerContext(slaves=store, single=True), blocks


def _make_serial_server(device: DeviceConfig) -> tuple[ModbusSerialServer, int, str, dict]:
    master_fd, slave_fd = os.openpty()
    slave_path = os.ttyname(slave_fd)
    os.close(slave_fd)  # slave alive as long as master_fd is open; driver opens slave_path

    context, blocks = _build_context(device)
    server = ModbusSerialServer(
        context,
        port=f"/dev/fd/{master_fd}",   # emulator opens master via fd path (same process)
        framer=FramerType.RTU,
        baudrate=device.baud_rate or 9600,
        bytesize=device.data_bits or 8,
        parity=device.parity or "N",
        stopbits=device.stop_bits or 1,
    )
    return server, master_fd, slave_path, blocks


def _write_patched_config(serial_paths: dict[str, str], source_path: str) -> str:
    with open(source_path) as f:
        raw = yaml.safe_load(f)

    for name, master_path in serial_paths.items():
        raw[name]["path"] = master_path

    source_dir = os.path.dirname(os.path.abspath(source_path))
    patched_path = os.path.join(source_dir, "devices_patched.yaml")
    with open(patched_path, "w") as f:
        yaml.dump(raw, f, allow_unicode=True, default_flow_style=False)

    return patched_path


def build_all(devices: list[DeviceConfig], config_path: str) -> ServerSetup:
    """Создает все серверы. Для serial-устройств создает PTY-пары и пишет devices_patched.yaml."""
    servers = []
    master_fds = []
    sim_coroutines = []
    serial_paths = {}

    for device in devices:
        if device.port_type == "serial":
            server, master_fd, slave_path, blocks = _make_serial_server(device)
            master_fds.append(master_fd)
            serial_paths[device.name] = slave_path
            print(f"[serial]     {device.name}  driver_path={slave_path}  slave_id={device.slave_id}")
            servers.append(server)

        elif device.port_type in ("modbus tcp", "tcp"):
            if device.port is None:
                raise ValueError(f"{device.name}: port is required for {device.port_type}")
            framer = FramerType.SOCKET if device.port_type == "modbus tcp" else FramerType.RTU
            context, blocks = _build_context(device)
            server = ModbusTcpServer(
                context,
                address=(device.ip or "0.0.0.0", device.port),
                framer=framer,
            )
            print(f"[{device.port_type}]  {device.name}  {device.ip}:{device.port}  slave_id={device.slave_id}")
            servers.append(server)

        else:
            raise ValueError(f"{device.name}: unknown port_type '{device.port_type}'")

        if any(r.sim is not None for r in device.registers):
            sim_coroutines.append(
                run_device_sim(device.name, device.registers, blocks, device.sim_tick)
            )

    if serial_paths:
        patched_path = _write_patched_config(serial_paths, config_path)
        print(f"\n[emulator] devices_patched.yaml written. Run driver with:")
        print(f"  go run . --config {os.path.abspath(patched_path)}")

    return ServerSetup(servers=servers, master_fds=master_fds, sim_coroutines=sim_coroutines)


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "devices.yaml"
    devices = load_config(config_path)

    async def run():
        print(f"Building {len(devices)} servers...\n")
        setup = build_all(devices, config_path)
        print("\nAll servers ready. Press Ctrl+C to stop.\n")
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

    asyncio.run(run())