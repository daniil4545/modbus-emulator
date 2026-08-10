# PRD: modbus-emulator

## Цель

Эмулятор Modbus-устройств для тестирования шлюза go-modbus2mqtt.
Запускает серверы из YAML-конфига, инициализирует регистры из `test_value`.

## Конфиг

Схема совпадает со схемой `Device` / `Register` из `go-modbus2mqtt/config_yaml.go` плюс
четыре поля эмулятора: `test_value`, `sim`, `sim_tick`, `count`. Драйвер парсит YAML без
`KnownFields`, поэтому лишние поля игнорирует — один файл обслуживает обе стороны.

Эмулятор читает:
```
port_type, ip, port, slave_id, sim_tick, count
path, baud_rate, parity, data_bits, stop_bits    # только serial
registers[].id, reg_type, address, reg_size, format, bit, byte_order, test_value, sim
```
Поля `scale`, `truncate`, `writeable`, `event`, `timeout`, `poll_time` эмулятор не
использует — они уезжают в сгенерированный `devices.yaml` как есть.

`template.yaml` разворачивается по `count` в `devices.yaml`; для serial-устройств туда
подставляется путь PTY. `devices.yaml` генерируется при каждом запуске.

## Транспорты

| `port_type` | pymodbus класс | Framer |
|---|---|---|
| `modbus_tcp` | `ModbusTcpServer` | `FramerType.SOCKET` |
| `tcp` | `ModbusTcpServer` | `FramerType.RTU` (RTU-over-TCP) |
| `serial` | `ModbusSerialServer` | `FramerType.RTU` + `os.openpty()` |

Все серверы, включая serial, работают в одном event loop.

## Кодирование test_value

Правило выбирается по `reg_type`:

| условие | что попадает в datastore |
|---|---|
| `coil` / `discrete` | один бит, `int(bool(v))` |
| `holding` / `input`, задан `bit` | всё слово как uint16 (бит извлекает драйвер) |
| `holding` / `input`, без `bit` | по `format` + `reg_size` |

| format | reg_size | struct |
|---|---|---|
| uint | 1 / 2 / 4 | `>H` / `>I` / `>Q` |
| int | 1 / 2 / 4 | `>h` / `>i` / `>q` |
| float | 2 / 4 | `>f` / `>d` |

`byte_order`: `big-endian` (дефолт, high word first) или `little-endian` (word-swap).
Для `reg_size=1` и coil/discrete игнорируется.

Запись в блок идёт по адресу `address + 1` — компенсация инкремента внутри
`ModbusSlaveContext` (`datastore/context.py:120`).

## Симуляция (поле `sim:`)

`sim_tick: float` на уровне устройства (дефолт 1.0 сек).

| type | Параметры | Поведение |
|---|---|---|
| `sine` | `min`, `max`, `period`, `phase` (опц.) | синусоида |
| `ramp` | `min`, `max`, `period` | линейный рост, сброс |
| `step` | `values` (список), `period` | циклический перебор |
| `random_walk` | `min`, `max`, `step` | случайное блуждание |

## Поведение устройства

- Отвечает только на свой `slave_id`; запрос к чужому остаётся без ответа
- Блок datastore выделяется по объявленным адресам; выход за границы возвращает
  `ILLEGAL_DATA_ADDRESS`
- Регистр с `bit` требует `format: bool` — иначе драйвер сбрасывает `bit`

## Стек

Python 3.11+, pymodbus 3.9.2, pyserial 3.5, PyYAML 6.0.3
