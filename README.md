# modbus-emulator

Эмулятор Modbus-устройств для функционального тестирования шлюза [go-modbus2mqtt](https://github.com/daniil/go-modbus2mqtt).

Запускает набор Modbus-серверов на основе `devices.yaml`. Регистры инициализируются тестовыми значениями из поля `test_value`.

## Транспорты

| `port_type` | Framing | Реализация |
|---|---|---|
| `modbus tcp` | MBAP | `ModbusTcpServer` + `FramerType.SOCKET` |
| `tcp` | RTU-over-TCP | `ModbusTcpServer` + `FramerType.RTU` |
| `serial` | RTU | `ModbusSerialServer` + `os.openpty()` |

## Требования

- Python 3.10+
- `pip install -r requirements.txt` (pymodbus 3.9.2, pyserial 3.5)

## Запуск

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Запуск эмулятора
python servers.py devices.yaml
```

Для serial-устройств эмулятор создаёт PTY-пары и записывает `devices_patched.yaml`
с актуальными путями. Передать этот файл драйверу:

```bash
go run . --config ../modbus-emulator/devices_patched.yaml
```

## Структура

```
modbus-emulator/
├── config.py         # парсинг YAML, кодирование test_value → uint16 words
├── servers.py        # создание серверов по DeviceConfig
├── devices.yaml      # 16 устройств: TCP, RTU-over-TCP, serial
├── requirements.txt
└── docs/
    └── PRD.md
```

## devices.yaml

16 тестовых устройств, охватывающих все комбинации транспортов и типов регистров:

| Группа | Устройства | Порты |
|---|---|---|
| modbus tcp | tcp_uint, tcp_int, tcp_float, tcp_scale, tcp_coil, tcp_discrete, tcp_input, tcp_bitmap, tcp_write, tcp_realistic | 15020–15029 |
| RTU-over-TCP | rtu_holding, rtu_coil_discrete, rtu_bitmap | 15030–15032 |
| serial | serial_holding, serial_coil_discrete, serial_bitmap_write | PTY |
