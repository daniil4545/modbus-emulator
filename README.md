# modbus-emulator

Эмулятор Modbus-устройств для тестирования шлюза [go-modbus2mqtt](https://github.com/daniil/go-modbus2mqtt).

Читает `template.yaml`, разворачивает прототипы устройств по полю `count` и запускает Modbus-серверы. Регистры инициализируются из `test_value`, динамические меняются по закону из `sim:`.

## Быстрый старт

**1. Установить зависимости**

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

**2. Настроить устройства**

Отредактировать `template.yaml` — описать нужные устройства. Файл содержит все доступные поля с комментариями; неиспользуемые можно удалить. Поле `count: N` создаёт N копий прототипа с инкрементом порта и slave_id.

**3. Запустить эмулятор**

```bash
python main.py
```

При запуске выведет список серверов и команду для драйвера:

```
[generator] Expanded 4 devices → /path/to/devices.yaml
[modbus tcp]  tcp_sensor_01  127.0.0.1:15020  slave_id=1
[modbus tcp]  tcp_sensor_02  127.0.0.1:15021  slave_id=2
[tcp]         rtu_controller  127.0.0.1:15030  slave_id=10
[serial]      serial_meter  driver_path=/dev/pts/3  slave_id=20

[emulator] Run driver with:
  go run . --config /path/to/devices_patched.yaml

All servers ready. Press Ctrl+C to stop.
```

**4. Запустить драйвер** (в отдельном терминале)

Скопировать путь из вывода эмулятора:

```bash
go run . --config /path/to/devices_patched.yaml
```

## Транспорты

| `port_type` | Framing | Класс |
|---|---|---|
| `modbus tcp` | MBAP | `ModbusTcpServer` + `FramerType.SOCKET` |
| `tcp` | RTU-over-TCP | `ModbusTcpServer` + `FramerType.RTU` |
| `serial` | RTU | `ModbusSerialServer` + PTY |

## Структура проекта

```
modbus-emulator/
├── template.yaml   # конфиг устройств — редактировать здесь
├── main.py         # точка входа
├── generator.py    # разворачивает template.yaml → devices.yaml
├── config.py       # парсинг YAML, кодирование значений в uint16 words
├── servers.py      # создание серверов; PTY для serial
├── simulator.py    # динамическое обновление регистров (sim:)
└── requirements.txt
```

`devices.yaml` и `devices_patched.yaml` генерируются при каждом запуске — в git не хранятся.
