# PRD: modbus-emulator

## Цель

Эмулятор Modbus-устройств для ручного функционального тестирования шлюза go-modbus2mqtt.
Запускает набор Modbus-серверов на основе YAML-конфига. Регистры инициализируются
тестовыми значениями из поля `test_value`.

## Транспорты

| `port_type` в config | pymodbus класс | Framer |
|---|---|---|
| `modbus tcp` | `ModbusTcpServer` | `FramerType.SOCKET` |
| `tcp` | `ModbusTcpServer` | `FramerType.RTU` (RTU-over-TCP) |
| `serial` | `ModbusSerialServer` | `FramerType.RTU` + os.openpty() |

Один asyncio-процесс, все серверы запускаются через `asyncio.gather`.

## Конфиг

Файл `devices.yaml`. Поля, которые читает эмулятор:

```
port_type, ip, port, slave_id
path, baud_rate, parity, data_bits, stop_bits     # только для serial
registers[].reg_type, address, reg_size, format, bit, test_value
```

Поле `test_value` игнорируется драйвером (неизвестные поля yaml.v3 отбрасывает).

## Кодирование test_value в регистры Modbus

Регистры Modbus хранят uint16. Все многобайтовые значения — big-endian.

| format | reg_size | Python | Результат |
|---|---|---|---|
| uint | 1 | `struct.pack('>H', v)` | 1 слово |
| uint | 2 | `struct.pack('>I', v)` | 2 слова |
| uint | 4 | `struct.pack('>Q', v)` | 4 слова |
| int | 1 | `struct.pack('>h', v)` | 1 слово (two's complement) |
| int | 2 | `struct.pack('>i', v)` | 2 слова |
| int | 4 | `struct.pack('>q', v)` | 4 слова |
| float | 2 | `struct.pack('>f', v)` | 2 слова |
| float | 4 | `struct.pack('>d', v)` | 4 слова |
| coil / discrete | — | bool(v) | один бит |
| любой, поле `bit` | — | пропустить | raw_word того же address уже задаёт слово |

Конверсия packed bytes → список uint16:
```python
raw = struct.pack('>I', value)                    # пример для uint32
words = list(struct.unpack(f'>{len(raw)//2}H', raw))
```

Регистровый блок: `ModbusSequentialDataBlock(0, [0] * 65536)` — потом записать words по адресу.

**Важно: offset +1 в `ModbusSlaveContext`.**
`ModbusSlaveContext.getValues` и `setValues` жёстко прибавляют `+1` к адресу внутри.
При прямой записи в `ModbusSequentialDataBlock` (минуя контекст) нужно компенсировать:
```python
block.setValues(address + 1, words)  # +1 компенсирует внутренний offset ModbusSlaveContext
```

## pymodbus API (v3.x)

```python
from pymodbus import FramerType
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.server import ModbusTcpServer, ModbusSerialServer

# Контекст для одного устройства
store = ModbusSlaveContext(  # в pymodbus 3.9.2 класс называется ModbusSlaveContext; ModbusDeviceContext не существует
    di=ModbusSequentialDataBlock(0, [0] * 65536),
    co=ModbusSequentialDataBlock(0, [0] * 65536),
    hr=ModbusSequentialDataBlock(0, [0] * 65536),
    ir=ModbusSequentialDataBlock(0, [0] * 65536),
)
context = ModbusServerContext(slaves=store, single=True)

# Modbus TCP (MBAP)
server = ModbusTcpServer(context, address=("0.0.0.0", port), framer=FramerType.SOCKET)

# RTU-over-TCP
server = ModbusTcpServer(context, address=("0.0.0.0", port), framer=FramerType.RTU)

# Serial RTU
server = ModbusSerialServer(context, port="/dev/pts/3", framer=FramerType.RTU,
                             baudrate=9600, bytesize=8, parity="N", stopbits=1)

await asyncio.gather(server1.serve_forever(), server2.serve_forever(), ...)
```

## Serial: os.openpty() и передача путей драйверу

Для каждого `port_type: serial` устройства используется `os.openpty()` из стандартной
библиотеки Python — без внешних зависимостей.

1. Вызвать `os.openpty()` — возвращает `(master_fd, slave_fd)`.
2. Получить путь slave: `os.ttyname(slave_fd)` → строка вида `/dev/pts/X`.
3. Эмулятор слушает на slave (`ModbusSerialServer(port=slave_path, ...)`).
4. `master_fd` держать открытым — это "другой конец кабеля", к которому подключается драйвер.
5. Получить путь master: `os.ttyname(master_fd)` → передать в `devices_patched.yaml`.
6. После создания всех PTY-пар эмулятор записывает файл `devices_patched.yaml` —
   копию `devices.yaml` с заменёнными `path` для serial-устройств (master_fd каждого).
7. Вывести в консоль путь к файлу:
   ```
   [emulator] Serial PTY ready. Run driver with:
     go run . --config /abs/path/to/devices_patched.yaml
   ```

Файл `devices_patched.yaml` не коммитится (добавить в `.gitignore`).

## Запись регистров

pymodbus по умолчанию сохраняет FC5/FC6/FC16 в datastore. Следующий poll вернёт
записанное значение — дополнительного кода не требуется.

## Graceful shutdown

Ctrl+C → отмена asyncio tasks → закрытие PTY файловых дескрипторов → выход.

## Структура файлов

```
modbus-emulator/
├── main.py           # точка входа, asyncio.gather
├── config.py         # парсинг YAML, кодирование test_value → uint16 words
├── servers.py        # создание ModbusTcpServer / ModbusSerialServer по device
├── pty_manager.py    # создание PTY-пар через os.openpty(), запись devices_patched.yaml
├── devices.yaml      # 16 устройств, полное покрытие транспортов × типов регистров
├── requirements.txt  # pymodbus==3.9.2, pyserial==3.5
├── .gitignore
└── docs/
    └── PRD.md
```

## Как запустить систему целиком

```bash
# Терминал 1 — эмулятор
cd modbus-emulator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
# выведет путь к devices_patched.yaml

# Терминал 2 — MQTT брокер
docker run -p 1883:1883 eclipse-mosquitto

# Терминал 3 — драйвер
cd go-modbus2mqtt
go run . --config ../modbus-emulator/devices_patched.yaml --mqtt-broker tcp://localhost:1883
```

## Вне scope (v1)

- Динамические значения (инкремент, формулы)
- TLS
- Docker
- Автозапуск драйвера из эмулятора

## Устройства в devices.yaml

16 устройств, полное покрытие `port_type` × `reg_type`:

| Группа | Устройства | Порты | slave_id |
|---|---|---|---|
| modbus tcp | tcp_uint, tcp_int, tcp_float, tcp_scale | 15020–15023 | 1–4 |
| modbus tcp | tcp_coil, tcp_discrete, tcp_input | 15024–15026 | 5–7 |
| modbus tcp | tcp_bitmap, tcp_write, tcp_realistic | 15027–15029 | 8–10 |
| serial | serial_holding, serial_coil_discrete, serial_bitmap_write | os.openpty() PTY | 11–13 |
| RTU-over-TCP | rtu_holding, rtu_coil_discrete, rtu_bitmap | 15030–15032 | 14–16 |

## Стек

- Python 3.10+
- pymodbus 3.9.2 (asyncio, закреплена версия во избежание breaking changes)
- pyserial 3.5
- os (стандартная библиотека Python, внешних зависимостей не требует)
