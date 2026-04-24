"""Создание Modbus-серверов и инициализация регистров из DeviceConfig."""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

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

    Thread-safe: both setValues (Modbus write) and sim_setValues (simulator
    update) acquire a threading.Lock before mutating the underlying values list,
    preventing data races when serial server threads and the main asyncio loop
    write concurrently.
    """
    _on_write: Callable[[int, list], None] | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, address, values):
        super().__init__(address, values)

    def setValues(self, address, values):
        with self._lock:
            super().setValues(address, values)
        if self._on_write is not None:
            # ModbusSlaveContext добавляет +1 перед вызовом; вычитаем, чтобы
            # получить 0-indexed адрес как в devices.yaml.
            self._on_write(address - 1, values)

    def sim_setValues(self, address, values):
        """Запись без вызова _on_write. Используется симулятором."""
        with self._lock:
            super().setValues(address, values)


@dataclass
class ServerSetup:
    servers: list
    master_fds: list[int]
    sim_coroutines: list
    serial_threads: list[threading.Thread] = field(default_factory=list)


_BLOCK_LABELS = {"di": "discrete", "co": "coil", "hr": "holding", "ir": "input"}


def _build_context(
    device: DeviceConfig,
) -> tuple[ModbusServerContext, dict[str, ObservableDataBlock]]:
    blocks: dict[str, ObservableDataBlock] = {
        k: ObservableDataBlock(0, [0] * 65536) for k in ("di", "co", "hr", "ir")
    }

    for reg in device.registers:
        words = encode_value(reg.test_value, reg.format, reg.reg_size, reg.byte_order)
        blocks[reg.reg_type].setValues(reg.address + 1, words)

    # Включаем колбэки после init — выше они были None и не срабатывали
    for block_type, block in blocks.items():
        label = _BLOCK_LABELS[block_type]
        block._on_write = lambda addr, vals, n=device.name, t=label: print(
            f"[write] {n} [{t}] addr={addr}  values={vals}"
        )

    store = ModbusSlaveContext(di=blocks["di"], co=blocks["co"], hr=blocks["hr"], ir=blocks["ir"])
    return ModbusServerContext(slaves=store, single=True), blocks


def _make_serial_server(device: DeviceConfig) -> tuple[int, str]:
    """Creates PTY pair and returns (master_fd, slave_path).

    The actual ModbusSerialServer is created inside the thread's event loop.
    """
    master_fd, slave_fd = os.openpty()
    slave_path = os.ttyname(slave_fd)
    os.close(slave_fd)
    return master_fd, slave_path


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
    """Создает все серверы. Для serial-устройств создает PTY-пары и пишет devices_patched.yaml.

    Serial-серверы запускаются в отдельных потоках, т.к. pymodbus использует
    блокирующий I/O внутри serve_forever(), что блокирует asyncio event loop.
    """
    tcp_servers = []
    master_fds = []
    sim_coroutines = []
    serial_paths = {}
    serial_threads = []

    for device in devices:
        if device.port_type == "serial":
            master_fd, slave_path = _make_serial_server(device)
            master_fds.append(master_fd)
            serial_paths[device.name] = slave_path
            print(f"[serial]     {device.name}  driver_path={slave_path}  slave_id={device.slave_id}")

            # Build context and blocks in main thread
            context, blocks = _build_context(device)

            # Serial server runs in a background thread with its own event loop
            # to avoid blocking the main asyncio event loop.
            # Server must be created inside the coroutine (after event loop starts)
            # because pymodbus calls asyncio.get_running_loop() in __init__.
            def _run_serial(
                ctx=context,
                mfd=master_fd,
                dev=device,
                blks=blocks,
            ):
                async def start():
                    srv = ModbusSerialServer(
                        ctx,
                        port=f"/dev/fd/{mfd}",
                        framer=FramerType.RTU,
                        baudrate=dev.baud_rate or 9600,
                        bytesize=dev.data_bits or 8,
                        parity=dev.parity or "N",
                        stopbits=dev.stop_bits or 1,
                    )
                    await srv.serve_forever()
                asyncio.run(start())

            t = threading.Thread(target=_run_serial, daemon=True, name=device.name)
            t.start()
            serial_threads.append(t)
            time.sleep(0.1)  # let serial server thread open the port

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
            tcp_servers.append(server)

        else:
            raise ValueError(f"{device.name}: unknown port_type '{device.port_type}'")

        if any(r.sim is not None for r in device.registers):
            sim_coroutines.append(
                run_device_sim(device.name, device.registers, blocks, device.sim_tick)
            )

    patched_path = _write_patched_config(serial_paths, config_path)
    print("\n[emulator] Run driver with:")
    print(f"  go run . --config {os.path.abspath(patched_path)}")

    return ServerSetup(
        servers=tcp_servers,
        master_fds=master_fds,
        sim_coroutines=sim_coroutines,
        serial_threads=serial_threads,
    )


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
            for t in setup.serial_threads:
                t.join(timeout=2.0)

    asyncio.run(run())