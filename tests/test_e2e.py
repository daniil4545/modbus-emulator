"""Сквозная проверка: поднять сервер и прочитать его настоящим Modbus-клиентом."""

import asyncio
import logging

import pytest
from pymodbus.client import AsyncModbusTcpClient

from config import parse_devices
from servers import QUIET, block_sizes, build_all, serve

PORT = 15599

CONFIG = {
    "dev": {
        "port_type": "modbus_tcp",
        "ip": "127.0.0.1",
        "port": PORT,
        "slave_id": 7,
        "registers": [
            {"id": "status", "reg_type": "holding", "address": 0, "format": "int", "test_value": 42},
            {"id": "flags", "reg_type": "holding", "address": 1, "format": "bool", "test_value": 42, "bit": 5},
            {"id": "energy", "reg_type": "holding", "address": 2, "reg_size": 2, "format": "uint", "test_value": 999999},
            {"id": "enable", "reg_type": "coil", "address": 0, "test_value": 1},
        ],
    }
}


async def _with_server(scenario):
    logging.getLogger("pymodbus").setLevel(logging.CRITICAL)
    devices = parse_devices(CONFIG)
    setup = await build_all(devices, QUIET)
    server_task = asyncio.create_task(serve(setup))
    await asyncio.sleep(0.2)

    client = AsyncModbusTcpClient("127.0.0.1", port=PORT, retries=1, timeout=1)
    await client.connect()
    try:
        return await scenario(client)
    finally:
        client.close()
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)


def test_registers_readable_with_initial_values():
    async def scenario(client):
        return (
            (await client.read_holding_registers(0, count=1, slave=7)).registers,
            (await client.read_holding_registers(1, count=1, slave=7)).registers,
            (await client.read_holding_registers(2, count=2, slave=7)).registers,
            (await client.read_coils(0, count=1, slave=7)).bits[0],
        )

    status, flags, energy, enable = asyncio.run(_with_server(scenario))
    assert status == [42]
    assert (flags[0] >> 5) & 1 == 1  # bit-регистр лежит в datastore целым словом
    assert energy == [15, 16959]  # 999999 = 0x000F423F, high word first
    assert enable is True


def test_write_is_visible_on_next_read():
    async def scenario(client):
        await client.write_register(0, 777, slave=7)
        return (await client.read_holding_registers(0, count=1, slave=7)).registers

    assert asyncio.run(_with_server(scenario)) == [777]


def test_foreign_slave_id_gets_no_answer():
    async def scenario(client):
        try:
            await client.read_holding_registers(0, count=1, slave=99)
            return "answered"
        except Exception:
            return "silent"

    assert asyncio.run(_with_server(scenario)) == "silent"


def test_address_outside_block_is_illegal():
    async def scenario(client):
        return await client.read_holding_registers(900, count=1, slave=7)

    response = asyncio.run(_with_server(scenario))
    assert response.isError()
    assert response.exception_code == 2  # ILLEGAL_DATA_ADDRESS


def test_multi_write_outside_block_is_illegal():
    """FC15/FC16 теряли код исключения: ModbusSlaveContext.setValues не возвращает результат."""

    async def scenario(client):
        return (
            await client.write_registers(900, [5, 6], slave=7),
            await client.write_coils(900, [True, False], slave=7),
        )

    registers, coils = asyncio.run(_with_server(scenario))
    assert registers.isError() and registers.exception_code == 2
    assert coils.isError() and coils.exception_code == 2


def test_multi_write_crossing_block_end_does_not_silently_drop():
    """Запись, начинающаяся внутри блока и уходящая за его конец, не должна выглядеть успешной."""

    async def scenario(client):
        before = (await client.read_holding_registers(3, count=1, slave=7)).registers
        response = await client.write_registers(3, [11, 22], slave=7)
        after = (await client.read_holding_registers(3, count=1, slave=7)).registers
        return response, before, after

    response, before, after = asyncio.run(_with_server(scenario))
    assert response.isError()
    assert after == before  # ничего не записалось, и клиент об этом знает


def test_failed_build_closes_opened_pty(monkeypatch):
    """PTY открывается до создания сервера — при сбое на следующем устройстве fd не должен утечь."""
    import os

    import servers as servers_module

    opened = []
    real_open_pty = servers_module._open_pty

    def spy():
        fd, path = real_open_pty()
        opened.append(fd)
        return fd, path

    def boom(*args, **kwargs):
        raise RuntimeError("server construction failed")

    monkeypatch.setattr(servers_module, "_open_pty", spy)
    monkeypatch.setattr(servers_module, "ModbusTcpServer", boom)

    config = {
        "meter": {"port_type": "serial", "slave_id": 1,
                  "registers": [{"id": "a", "reg_type": "holding", "address": 0, "format": "uint", "test_value": 1}]},
        "sensor": {"port_type": "modbus_tcp", "ip": "127.0.0.1", "port": 15598, "slave_id": 2,
                   "registers": [{"id": "b", "reg_type": "holding", "address": 0, "format": "uint", "test_value": 1}]},
    }

    with pytest.raises(RuntimeError):
        asyncio.run(build_all(parse_devices(config), QUIET))

    assert opened, "PTY должен был открыться до сбоя"
    for fd in opened:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_block_sized_by_used_addresses():
    """Раньше каждый блок занимал 65536 ячеек независимо от конфига."""
    device = parse_devices(CONFIG)[0]
    sizes = block_sizes(device)
    assert sizes["hr"] == 5  # адреса 0..3 + компенсация смещения ModbusSlaveContext
    assert sizes["ir"] == 1
