# modbus-emulator

[![CI](https://github.com/daniil4545/modbus-emulator/actions/workflows/ci.yml/badge.svg)](https://github.com/daniil4545/modbus-emulator/actions/workflows/ci.yml)

Эмулятор Modbus-устройств для интеграционного тестирования шлюзов и драйверов без железа. Поднимает парк устройств из одного YAML-шаблона: Modbus TCP, RTU-over-TCP и serial RTU через PTY.

Читает `template.yaml`, разворачивает прототипы по полю `count` и запускает серверы. Регистры инициализируются из `test_value`, динамические меняются по закону из `sim:`. Рядом кладётся `devices.yaml` — тот же конфиг с подставленными путями PTY, его и получает драйвер. Написан как стенд для шлюза go-modbus2mqtt, но пригоден для любого Modbus-клиента.

## Быстрый старт

```bash
git clone https://github.com/daniil4545/modbus-emulator.git
cd modbus-emulator
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Устройства описываются в `template.yaml`. Справочник всех полей с примерами — `template.example.yaml`. Поле `count: N` создаёт N копий прототипа с инкрементом `port` и `slave_id`.

## Проверка конфига

```bash
python main.py --check
```

Разворачивает `count`, проверяет конфиг и печатает карту: что и по каким адресам окажется в datastore, в какие слова закодировано каждое `test_value`. Серверы не поднимаются.

## Запуск

```
[emulator] 2 devices from template.yaml

  modbus tcp  tcp_sensor           127.0.0.1:15620        slave_id=1    5 registers
  serial      serial_meter         /dev/ttys000           slave_id=20   1 registers

[emulator] driver config written to /path/to/devices.yaml
  go run . --config /path/to/devices.yaml

All servers ready. Press Ctrl+C to stop.
```

## Лог трафика

Каждый запрос печатается с именем регистра из поля `id` и декодированным значением:

```
23:03:24  tcp_sensor  read   holding 0 = 42 (status_word)
23:03:24  tcp_sensor  write  holding 4 = 500 (counter)
23:03:24  tcp_sensor  error  illegal data address
23:03:24  tcp_sensor  error  request for slave_id=99, this device is 1
```

| Флаг | Что в логе |
|---|---|
| `-q` | только ошибки |
| (без флага) | записи и ошибки |
| `-v` | плюс чтения |

## Транспорты

| `port_type` | Framing | Класс |
|---|---|---|
| `modbus_tcp` | MBAP | `ModbusTcpServer` + `FramerType.SOCKET` |
| `tcp` | RTU-over-TCP | `ModbusTcpServer` + `FramerType.RTU` |
| `serial` | RTU | `ModbusSerialServer` + PTY-пара |

Для `serial` эмулятор создаёт PTY-пару: сервер слушает master, драйверу отдаётся путь slave. Путь подставляется в `devices.yaml` автоматически.

## Поведение устройства

- Отвечает только на свой `slave_id`; запрос к чужому остаётся без ответа, как на реальной шине, и отмечается в логе
- Datastore выделяется по объявленным адресам; чтение или любая запись за их пределами возвращает `ILLEGAL_DATA_ADDRESS`, включая множественную запись, частично выходящую за границу блока
- Регистр с `bit` кладёт в datastore слово целиком — бит из него извлекает драйвер; такой регистр требует `format: bool`
- Если порт занят или конфиг некорректен, эмулятор выходит с кодом 1 и сообщением, а не зависает

## Структура проекта

```
main.py                 CLI, стартовая таблица, --check
generator.py            разворот count
config.py               разбор и валидация конфига, кодирование значений
servers.py              серверы, datastore, PTY, лог трафика
simulator.py            динамическое обновление регистров (sim:)
template.yaml           конфиг устройств
template.example.yaml   справочник полей и примеры
tests/                  pytest-тесты
docs/                   PRD, backlog, состояние проекта
```

`devices.yaml` генерируется при каждом запуске, в git не хранится.

## Тесты

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Стек

Python 3.11+, pymodbus 3.9.2, pyserial, PyYAML, asyncio.

## Лицензия

MIT, см. [LICENSE](LICENSE).
