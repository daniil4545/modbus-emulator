"""Создание Modbus-серверов, инициализация регистров и лог трафика."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime

from pymodbus import FramerType
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server import ModbusSerialServer, ModbusTcpServer

from config import REG_TYPE_LABELS, DeviceConfig, decode_words, encode_value
from simulator import run_device_sim

QUIET, NORMAL, VERBOSE = -1, 0, 1

# function code -> (операция, блок, атрибут PDU со значениями)
_FUNCTION_CODES = {
    1: ("read", "co", "bits"),
    2: ("read", "di", "bits"),
    3: ("read", "hr", "registers"),
    4: ("read", "ir", "registers"),
    5: ("write", "co", "bits"),
    6: ("write", "hr", "registers"),
    15: ("write", "co", "bits"),
    16: ("write", "hr", "registers"),
}

_EXCEPTION_TEXTS = {
    1: "illegal function",
    2: "illegal data address",
    3: "illegal data value",
    4: "device failure",
    0x0A: "gateway path unavailable",
    0x0B: "gateway target failed to respond",
}


class SlaveContext(ModbusSlaveContext):
    """ModbusSlaveContext, пробрасывающий наверх код исключения от датаблока.

    Штатный setValues (datastore/context.py:124-133) не возвращает результат вызова
    блока, поэтому код исключения теряется и FC15/FC16 за границей блока выглядят
    успешными, хотя запись не произошла. У getValues возврат есть, отсюда и разное
    поведение чтения и записи.
    """

    def setValues(self, fc_as_hex, address, values):
        return self.store[self.decode(fc_as_hex)].setValues(address + 1, values)


class BoundedDataBlock(ModbusSequentialDataBlock):
    """Блок фиксированного размера, отвечающий ILLEGAL_DATA_ADDRESS за своими границами.

    В pymodbus 3.9.2 у ModbusSequentialDataBlock проверки границ нет: getValues делает
    срез списка и за пределами блока молча возвращает пустой ответ. Возврат int из
    getValues/setValues вызывающий код трактует как код исключения
    (pdu/register_message.py:38, :197).
    """

    ILLEGAL_ADDRESS = 2

    def _fits(self, address: int, count: int) -> bool:
        start = address - self.address
        return start >= 0 and start + count <= len(self.values)

    def getValues(self, address, count=1):
        if not self._fits(address, count):
            return self.ILLEGAL_ADDRESS
        return super().getValues(address, count)

    def setValues(self, address, values):
        if not isinstance(values, list):
            values = [values]
        if not self._fits(address, len(values)):
            return self.ILLEGAL_ADDRESS
        super().setValues(address, values)
        return None


@dataclass
class ServerSetup:
    servers: dict = field(default_factory=dict)          # имя устройства -> сервер
    endpoints: dict[str, str] = field(default_factory=dict)
    master_fds: list[int] = field(default_factory=list)
    sim_coroutines: list = field(default_factory=list)
    serial_paths: dict[str, str] = field(default_factory=dict)


def block_sizes(device: DeviceConfig) -> dict[str, int]:
    """Размер каждого блока по фактически занятым адресам.

    +1 компенсирует инкремент адреса внутри ModbusSlaveContext (datastore/context.py:120),
    из-за которого ячейка 0 недостижима.
    """
    sizes = {"di": 1, "co": 1, "hr": 1, "ir": 1}
    for reg in device.registers:
        sizes[reg.reg_type] = max(sizes[reg.reg_type], reg.address + reg.span + 1)
    return sizes


def build_context(device: DeviceConfig) -> tuple[ModbusServerContext, dict[str, BoundedDataBlock]]:
    """Создаёт datastore устройства и заполняет его значениями test_value."""
    sizes = block_sizes(device)
    blocks = {k: BoundedDataBlock(0, [0] * sizes[k]) for k in ("di", "co", "hr", "ir")}

    for reg in device.registers:
        words = encode_value(reg.test_value, reg.format, reg.reg_size, reg.byte_order)
        blocks[reg.reg_type].setValues(reg.address + 1, words)

    # Все четыре блока передаём всегда: в pymodbus 3.9.2 ModbusSlaveContext.__init__
    # проверяет наличие co/ir/hr через `if di is not None` (datastore/context.py:96-99).
    store = SlaveContext(di=blocks["di"], co=blocks["co"], hr=blocks["hr"], ir=blocks["ir"])
    context = ModbusServerContext(slaves={device.slave_id: store}, single=False)
    return context, blocks


def _make_tracer(device: DeviceConfig, blocks: dict, verbosity: int):
    """Колбэк trace_pdu: печатает каждый запрос с именем регистра и значением.

    Запрос печатается на входящем PDU, ошибка — на исходящем: в ответе уже известен
    exception_code, а в запросе ещё нет.
    """
    index = {(reg.reg_type, reg.address): reg for reg in device.registers}

    def describe(reg_type: str, address: int, words: list) -> str:
        label = REG_TYPE_LABELS[reg_type]
        span = f"{address}..{address + len(words) - 1}" if len(words) > 1 else str(address)
        reg = index.get((reg_type, address))
        if reg is not None and len(words) == reg.span:
            value = decode_words(list(words), reg.format, reg.byte_order)
            return f"{label} {span} = {value} ({reg.id})"
        return f"{label} {span} = {list(words)}"

    def log(kind: str, text: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"{stamp}  {device.name}  {kind:<5}  {text}", flush=True)

    def trace(sending: bool, pdu):
        if sending:
            if pdu.isError():
                reason = _EXCEPTION_TEXTS.get(pdu.exception_code, f"exception {pdu.exception_code}")
                log("error", reason)
            return pdu

        # Чужой slave_id остаётся без ответа (ignore_missing_slaves), поэтому
        # исходящего PDU не будет — единственный шанс сообщить о нём здесь.
        if pdu.dev_id != device.slave_id:
            log("error", f"request for slave_id={pdu.dev_id}, this device is {device.slave_id}")
            return pdu

        entry = _FUNCTION_CODES.get(pdu.function_code)
        if entry is None:
            if verbosity >= NORMAL:
                log("req", f"function code {pdu.function_code}")
            return pdu

        operation, reg_type, attr = entry
        if operation == "read":
            if verbosity < VERBOSE:
                return pdu
            words = blocks[reg_type].getValues(pdu.address + 1, pdu.count)
            if isinstance(words, int):
                return pdu  # адрес вне блока — причину напечатает ответ с exception_code
        else:
            if verbosity < NORMAL:
                return pdu
            words = getattr(pdu, attr, [])

        log(operation, describe(reg_type, pdu.address, list(words)))
        return pdu

    return trace


def _open_pty() -> tuple[int, str]:
    """PTY-пара: сервер слушает master, драйверу отдаётся путь slave."""
    master_fd, slave_fd = os.openpty()
    slave_path = os.ttyname(slave_fd)
    os.close(slave_fd)
    return master_fd, slave_path


async def build_all(devices: list[DeviceConfig], verbosity: int = NORMAL) -> ServerSetup:
    """Создаёт серверы и sim-корутины. Вызывать из работающего event loop.

    Serial-серверы живут в общем event loop наравне с TCP: транспорт pymodbus для
    serial асинхронный (transport/transport.py:197), отдельные потоки не нужны.
    ModbusSerialServer.__init__ обращается к asyncio.get_running_loop(), поэтому
    функция асинхронная.
    """
    setup = ServerSetup()

    try:
        for device in devices:
            context, blocks = build_context(device)
            tracer = _make_tracer(device, blocks, verbosity)

            if device.port_type == "serial":
                master_fd, slave_path = _open_pty()
                setup.master_fds.append(master_fd)
                setup.serial_paths[device.name] = slave_path
                server = ModbusSerialServer(
                    context,
                    port=f"/dev/fd/{master_fd}",
                    framer=FramerType.RTU,
                    baudrate=device.baud_rate or 9600,
                    bytesize=device.data_bits or 8,
                    parity=device.parity or "N",
                    stopbits=device.stop_bits or 1,
                    ignore_missing_slaves=True,
                    trace_pdu=tracer,
                )
                endpoint = slave_path
            else:
                framer = FramerType.SOCKET if device.port_type == "modbus tcp" else FramerType.RTU
                server = ModbusTcpServer(
                    context,
                    address=(device.ip or "0.0.0.0", device.port),
                    framer=framer,
                    ignore_missing_slaves=True,
                    trace_pdu=tracer,
                )
                endpoint = device.endpoint

            setup.servers[device.name] = server
            setup.endpoints[device.name] = endpoint

            if any(reg.sim is not None for reg in device.registers):
                setup.sim_coroutines.append(
                    run_device_sim(device.name, device.registers, blocks, device.sim_tick)
                )
    except BaseException:
        # PTY уже открыты, а serve() с их закрытием вызвана не будет
        _release(setup)
        raise

    return setup


def _release(setup: ServerSetup) -> None:
    for coroutine in setup.sim_coroutines:
        coroutine.close()
    for fd in setup.master_fds:
        os.close(fd)
    setup.sim_coroutines.clear()
    setup.master_fds.clear()


async def _listen(name: str, endpoint: str, server) -> None:
    """Слушает до остановки сервера.

    serve_forever() игнорирует результат listen() (server/base.py:82) и уходит в ожидание
    future, который при неудачном открытии порта уже некому разрешить — процесс висит
    молча. Поэтому listen() вызывается здесь, с проверкой результата.
    """
    if not await server.listen():
        raise OSError(f"{name}: cannot open {endpoint}")
    await server.serving


async def serve(setup: ServerSetup) -> None:
    """Запускает все серверы и симуляции до отмены; на выходе освобождает ресурсы."""
    tasks = [
        asyncio.create_task(_listen(name, setup.endpoints[name], server), name=name)
        for name, server in setup.servers.items()
    ]
    tasks += [asyncio.create_task(coroutine) for coroutine in setup.sim_coroutines]
    setup.sim_coroutines.clear()  # обёрнуты в задачи, повторно закрывать нечего

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for server in setup.servers.values():
            await server.shutdown()
        _release(setup)
