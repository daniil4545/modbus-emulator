# PRD: modbus-emulator

## Цель

Эмулятор Modbus-устройств для тестирования шлюза go-modbus2mqtt.
Запускает серверы из YAML-конфига, инициализирует регистры из `test_value`.

## Транспорты

| `port_type` | pymodbus класс | Framer |
|---|---|---|
| `modbus tcp` | `ModbusTcpServer` | `FramerType.SOCKET` |
| `tcp` | `ModbusTcpServer` | `FramerType.RTU` (RTU-over-TCP) |
| `serial` | `ModbusSerialServer` | `FramerType.RTU` + `os.openpty()` |

## Конфиг (`devices.yaml`)

Поля, которые читает эмулятор:
```
port_type, ip, port, slave_id
path, baud_rate, parity, data_bits, stop_bits   # только serial
registers[].reg_type, address, reg_size, format, bit, test_value, sim
```
Остальные поля (id, writeable и др.) передаются в файл без изменений и читаются драйвером.

## Кодирование test_value → uint16 words

При записи в datablock: `block.setValues(address + 1, words)` (+1 компенсирует внутренний offset `ModbusSlaveContext`).

| format | reg_size | struct |
|---|---|---|
| uint | 1 / 2 / 4 | `>H` / `>I` / `>Q` |
| int | 1 / 2 / 4 | `>h` / `>i` / `>q` |
| float | 2 / 4 | `>f` / `>d` |
| coil / discrete | — | `bool(v)` |

`byte_order` (на уровне регистра): `"big-endian"` (дефолт, high word first) | `"little-endian"` (word-swap — reversed uint16 list). Для `reg_size=1` и coil/discrete игнорируется.

## Симуляция (поле `sim:`)

`sim_tick: float` на уровне устройства (дефолт 1.0 сек).

| type | Параметры | Поведение |
|---|---|---|
| `sine` | `min`, `max`, `period`, `phase` (опц.) | синусоида |
| `ramp` | `min`, `max`, `period` | линейный рост, сброс |
| `step` | `values` (список), `period` | циклический перебор |
| `random_walk` | `min`, `max`, `step` | случайное блуждание |

## Структура файлов (v3)

```
modbus-emulator/
├── main.py          # точка входа: generator → config → servers
├── generator.py     # template.yaml → devices.yaml (expand count)
├── config.py        # парсинг devices.yaml → [DeviceConfig]
├── servers.py       # ModbusTcpServer / ModbusSerialServer + PTY + devices_patched.yaml
├── simulator.py     # фоновые корутины sim-регистров
├── template.yaml    # пользовательский конфиг (редактируется)
├── requirements.txt # pymodbus==3.9.2, pyserial==3.5
└── docs/
```

Генерируемые (gitignore): `devices.yaml`, `devices_patched.yaml`.

## Стек

Python 3.10+, pymodbus 3.9.2, pyserial 3.5
