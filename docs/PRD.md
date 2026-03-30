# PRD: modbus-emulator

## Цель

Эмулятор Modbus-устройств для ручного функционального тестирования шлюза go-modbus2mqtt.
Запускает набор Modbus-серверов на основе YAML-конфига, который одновременно используется
тестируемым шлюзом. Регистры инициализируются тестовыми значениями из поля `test_value`.

## Транспорты

| port_type в config | Реализация |
|---|---|
| `modbus tcp` | pymodbus `ModbusTcpServer`, framer TCP (MBAP) |
| `tcp` | pymodbus `ModbusTcpServer`, framer RTU (RTU-over-TCP) |
| `serial` | pymodbus `ModbusSerialServer` + socat PTY |

Все серверы работают в одном процессе через asyncio.

## Конфиг

Файл `devices.yaml` — копия `testdata/devices_local.yaml` из go-modbus2mqtt.

Поля, которые читает эмулятор:
- `port_type`, `ip`, `port`, `slave_id` — транспорт и адресация
- `path`, `baud_rate`, `parity`, `data_bits`, `stop_bits` — параметры serial
- `registers[].reg_type`, `registers[].address`, `registers[].reg_size` — что инициализировать
- `registers[].format`, `registers[].bit` — как кодировать `test_value`
- `registers[].test_value` — начальное значение (игнорируется шлюзом)

Поле `test_value` трактуется так:
- `format: uint` / `int` — целое число, кодируется в N uint16-слов (big-endian)
- `format: float` — число с плавающей точкой, кодируется через `struct.pack`
- `reg_type: coil` / `discrete` — 0 или 1
- регистры с полем `bit` — `test_value` не нужен, значение берётся из raw_word того же адреса

## Поведение

- При запуске читает config, для каждого устройства создаёт `ModbusSimulatorContext`
  с инициализированными регистрами из `test_value`.
- Serial-устройства: перед стартом эмулятор запускает `socat` и создаёт PTY-пары,
  записывает пути обратно в config (runtime-patch, не перезаписывает файл).
- Запись (FC5/FC6/FC16): принимается и сохраняется в памяти (поведение pymodbus по умолчанию).
  Следующий poll шлюза вернёт записанное значение — полезно для тестирования write-команд.
- Graceful shutdown: Ctrl+C → остановка всех серверов, освобождение PTY.

## Вне scope (v1)

- Динамические значения (инкремент, формулы)
- TLS
- Веб-интерфейс или REST API
- Docker

## Устройства в devices.yaml

16 устройств, полное покрытие port_type x reg_type:

| Группа | Устройства | Порты | slave_id |
|---|---|---|---|
| modbus tcp | tcp_uint, tcp_int, tcp_float, tcp_scale | 15020–15023 | 1–4 |
| modbus tcp | tcp_coil, tcp_discrete, tcp_input | 15024–15026 | 5–7 |
| modbus tcp | tcp_bitmap, tcp_write, tcp_realistic | 15027–15029 | 8–10 |
| serial | serial_holding, serial_coil_discrete, serial_bitmap_write | socat PTY | 11–13 |
| RTU-over-TCP | rtu_holding, rtu_coil_discrete, rtu_bitmap | 15030–15032 | 14–16 |

## Стек

- Python 3.10+
- pymodbus 3.x (asyncio)
- socat (системная зависимость, `apt install socat`)
