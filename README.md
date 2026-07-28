# modbus-emulator

Эмулятор Modbus-устройств для интеграционного тестирования шлюзов и драйверов без железа. Поднимает парк устройств из одного YAML-шаблона: Modbus TCP, RTU-over-TCP и serial RTU через PTY.

Читает `template.yaml`, разворачивает прототипы устройств по полю `count` и запускает Modbus-серверы. Регистры инициализируются из `test_value`, динамические меняются по закону из `sim:`. Написан как тестовый стенд для промышленного шлюза go-modbus2mqtt, но пригоден для любого Modbus-клиента.

## Быстрый старт

```bash
git clone https://github.com/daniil4545/modbus-emulator.git
cd modbus-emulator
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Устройства описываются в `template.yaml`; файл содержит все доступные поля с комментариями. При запуске эмулятор печатает список серверов и готовую команду для драйвера:

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

Драйвер запускается в отдельном терминале командой из вывода.

## Инженерные решения

- **PTY-эмуляция serial.** Для `port_type: serial` создаётся псевдотерминальная пара через `os.openpty()`; драйвер получает путь настоящего терминального устройства и работает с RTU-портом как с железным, без USB-адаптеров и проводов.
- **Генератор парка из шаблона.** Поле `count: N` разворачивает прототип в N устройств с инкрементом порта и `slave_id`; сто однотипных датчиков описываются пятью строками.
- **Потокобезопасный datastore.** Записи Modbus-клиента и обновления симулятора идут из разных потоков; `ObservableDataBlock` сериализует их через `threading.Lock`, обновления симулятора не триггерят write-колбэк.
- **Serial-серверы в отдельных потоках.** `pymodbus` блокирует event loop в `serve_forever()` для serial; каждый serial-сервер живёт в своём потоке со своим event loop, TCP-серверы остаются в основном asyncio-цикле.
- **Симуляция динамики регистров.** Законы `sine`, `ramp`, `step`, `random_walk` на регистр; клиент видит живые, меняющиеся значения, а не константы.
- **Патченный конфиг для драйвера.** Пути созданных PTY подставляются в `devices_patched.yaml`; конфиг эмулятора и конфиг драйвера гарантированно согласованы.

## Транспорты

| `port_type` | Framing | Класс |
|---|---|---|
| `modbus_tcp` | MBAP | `ModbusTcpServer` + `FramerType.SOCKET` |
| `tcp` | RTU-over-TCP | `ModbusTcpServer` + `FramerType.RTU` |
| `serial` | RTU | `ModbusSerialServer` + PTY |

## Структура проекта

```
modbus-emulator/
├── template.yaml   конфиг устройств, редактировать здесь
├── main.py         точка входа
├── generator.py    разворачивает template.yaml в devices.yaml
├── config.py       парсинг YAML, кодирование значений в uint16 words
├── servers.py      создание серверов, PTY для serial
├── simulator.py    динамическое обновление регистров (sim:)
└── requirements.txt
```

`devices.yaml` и `devices_patched.yaml` генерируются при каждом запуске, в git не хранятся.

## Стек

Python 3.11+, pymodbus, PyYAML, asyncio.

## Лицензия

MIT, см. [LICENSE](LICENSE).
