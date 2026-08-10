# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.0] - 2026-08-11

Наведение порядка перед консервацией: исправление дефектов, снос обходных решений,
тесты и документация. Формат конфига не менялся — он остаётся общим с go-modbus2mqtt.

### Fixed

- `config.py`: регистр с `bit` теперь кладётся в datastore целым словом и требует
  `format: bool`. В 0.4.0 такой регистр перестал пропускаться, но кодировался по своему
  `format`, а при корректном для драйвера `format: bool` падал в `encode_value`; драйвер
  же сбрасывает `bit` при любом другом формате (`config_yaml.go:160`)
- `servers.py`: устройство отвечает только на свой `slave_id`
  (`ModbusServerContext(slaves={slave_id: ...}, single=False)`); запрос к чужому остаётся
  без ответа, как на реальной шине, и отмечается в логе. `ignore_missing_slaves=True`
  выбран потому, что при `False` pymodbus 3.9.2 отвечает `ExceptionResponse(0x00, ...)`
  с function code `0x80`, который клиент не может декодировать
- `servers.py`: `BoundedDataBlock` возвращает `ILLEGAL_DATA_ADDRESS` за границами блока —
  у `ModbusSequentialDataBlock` в pymodbus 3.9.2 проверки границ нет, `getValues` молча
  возвращает пустой срез
- `servers.py`: `SlaveContext` пробрасывает наверх код исключения от датаблока. Штатный
  `ModbusSlaveContext.setValues` (`datastore/context.py:124-133`) не возвращает результат
  вызова блока, из-за чего FC15 / FC16 за границей блока отвечали клиенту успехом, хотя
  запись не происходила; одиночная запись FC5 / FC6 маскировала дефект, потому что
  формирует ответ через `getValues`
- `servers.py`: `_listen` вызывает `listen()` явно и проверяет результат — `serve_forever()`
  (`server/base.py:78-87`) результат игнорирует, поэтому при занятом порте процесс висел
  без диагностики; теперь эмулятор выходит с кодом 1 и сообщением
- `servers.py`: PTY-дескрипторы закрываются, если сборка серверов прервалась на одном из
  следующих устройств
- `main.py`: сообщение об остановке печаталось из недостижимой ветки `except KeyboardInterrupt`
- `main.py`: пустой или неразбираемый `template.yaml` давал traceback вместо сообщения
- `generator.py`: `count: 0` молча выбрасывал устройство из конфига; пустой блок устройства
  падал с `AttributeError`
- `template.example.yaml`: у `status_word` было `bit: 5` с `format: int`, при котором
  драйвер сбрасывает `bit` — исправлено на `format: bool`

### Changed

- `config.py`: валидация переведена на правила, которые реально ломают работу — согласие
  `bit` с `format: bool`, допустимые пары `format`/`reg_size`, пересечение адресов
  многословных регистров, дубли `id`, конфликт `ip:port`. Проверки полей, которые читает
  только драйвер (`scale`, `truncate`, `timeout`, `poll_time`), убраны вместе с полями
  из `RegisterConfig` и `DeviceConfig`: эмулятор их не интерпретирует, а у драйвера есть
  своя валидация
- `servers.py`: serial-серверы работают в общем event loop вместе с TCP — транспорт
  pymodbus для serial асинхронный, отдельные потоки не требовались. Убраны потоки,
  `asyncio.run` внутри них, `time.sleep(0.1)`, `join(timeout=2.0)` и общий на весь
  процесс `threading.Lock` в датаблоке
- `servers.py`: размер каждого блока считается по фактически объявленным адресам вместо
  фиксированных 65536 ячеек на блок
- `servers.py`: лог трафика переведён на штатный хук `trace_pdu` — видны и чтения, и
  записи, с именем устройства, `id` регистра и декодированным значением вместо сырых слов.
  `ObservableDataBlock` удалён
- `main.py`: `argparse` с флагом `--check` (развернуть, проверить, показать карту конфига)
  и уровнями лога `-q` / `-v`; стартовая таблица печатается здесь, а не внутри `build_all`
- `main.py`, `generator.py`: пишется один `devices.yaml` с подставленными путями PTY;
  промежуточный round-trip через диск и `devices_patched.yaml` убраны
- `config.py`: `load_config` разделён на чтение файла и `parse_devices(dict)`
- `tests/`: набор из 0.4.0 заменён на покрытие нового поведения — кодирование и обратное
  декодирование, правила валидации, разворот `count`, законы симуляции и сквозные сценарии
  с настоящим Modbus-клиентом

### Added

- `config.py`: `decode_words` — обратное преобразование слов в значение для лога
- `AGENTS.md`: стек, команды, структура и ловушки pymodbus
- `docs/backlog.md`, `docs/state.md` — состояние проекта на момент консервации

### Removed

- Отладочные точки входа `__main__` в `servers.py`, `config.py`, `generator.py` —
  их заменяет `main.py --check`
- `docs/TASKS.md` — заменён на `docs/backlog.md`

## [0.4.0] - 2026-07-28

### Added

- `tests/`: pytest-тесты `encode_value`, `load_config`, `expand_template`, `compute_next`
- `.github/workflows/ci.yml`: сборка (`compileall`) и тесты на push и pull request
- `requirements-dev.txt`: зависимости для тестов
- README: раздел «Тесты», CI-бейдж, актуализированная структура проекта

### Fixed

- `config.py`: `load_config` пропускал регистр с полем `bit` целиком, включая `test_value`
  (комментарий предполагал отдельный `raw_word`-регистр, которого в шаблонах нет) — теперь
  такой регистр инициализируется как обычный, `bit` остаётся полем для драйвера

### Changed

- `docs/PRD.md`: версия Python приведена в соответствие с README (3.11+)
- `docs/TASKS.md`: убрана ссылка на несуществующий файл спеки, M5 закрыт по факту ручного
  тестирования всех транспортов
- `.gitignore`: убрано игнорирование `docs/` — `PRD.md` и `TASKS.md` в нём трекаются
- `port_type` values updated to match driver format: `modbus tcp` → `modbus_tcp`
  (backward-compatible — old `modbus tcp` still works via normalization map)
- `config.py`: `DeviceConfig` gains `timeout` (int, default 1) and `poll_time` (int, default 5)
  fields — passed through to `devices.yaml` for driver consumption
- `config.py`: `RegisterConfig` gains `scale` (float, default 1.0), `truncate` (int|None),
  `writeable` (int 0/1, default 0), `event` (int 0/1, default 0) fields — mirror driver template
- `template.yaml`: rewritten as focused `test_device` covering all reg_types, formats, byte_order,
  sim, writeable, event; replaced three-prototype reference with a single minimal driver test config
- `servers.py`: `ObservableDataBlock` acquires `threading.Lock` in both `setValues` and
  `sim_setValues` — prevents data races between serial threads and main asyncio loop
- `servers.py`: serial servers now run in background threads with `asyncio.run` each; previously
  blocked the main event loop via blocking I/O inside `ModbusSerialServer`
- `servers.py`: `ServerSetup` gains `serial_threads: list[threading.Thread]` — joined with
  `timeout=2.0` on shutdown in both `main.py` and `servers.py` standalone entry point
- `simulator.py`: `asyncio.get_running_loop()` replaces deprecated `asyncio.get_event_loop()`
- README.md: transport table updated with `modbus_tcp` naming

## [0.3.0] - 2026-04-03

### Added

- `generator.py`: template-based config generator — `expand_template(template_path) -> dict`
  expands `count: N` into N devices with incremented `port` and `slave_id`; `save_devices`
  serializes result to YAML; standalone: `python generator.py template.yaml [out.yaml]`
- `main.py`: new entry point — `python main.py [template.yaml]` runs the full pipeline:
  expand template → save devices.yaml → load config → build servers → asyncio.gather
- `template.yaml`: user-facing config template with three prototypes (`modbus tcp`, `tcp`, `serial`);
  first register of `tcp_sensor` shows every available field with comments and defaults;
  all sim sub-fields (`phase`, `step`, `values`) documented inline
- `byte_order` field in `RegisterConfig` — `"big-endian"` (default, high word first) or
  `"little-endian"` (word-swap: reversed uint16 word list); ignored for single-register and coil/discrete

### Changed

- `config.py`: `encode_value` extended with `byte_order` parameter; validates and reverses word list
  for little-endian multi-register values; `load_config` parses `byte_order` from YAML
- `servers.py`, `simulator.py`: pass `reg.byte_order` through to `encode_value`
- `README.md`: updated workflow to `python main.py [template.yaml]`; template.yaml noted as full field reference
- `docs/PRD.md`: condensed to essential reference; added `byte_order` to encoding table

### Removed

- `gen_stress.py`: replaced by `template.yaml` + `count` field in generator
- `devices.yaml`: removed from git tracking — generated by `generator.py` on each run

## [0.2.1] - 2026-03-31

### Added

- `gen_stress.py`: stress-test config generator — 50 TCP devices across 5 profiles
  (pump, tank, motor, conveyor, sensor_hub), ports 16000–16049

### Changed

- `servers.py`: `devices_patched.yaml` is now written on every startup regardless of whether
  serial devices are present — driver can always use this fixed path
- `servers.py`: `ObservableDataBlock._on_write` promoted to a class-level annotated field

## [0.2.0] - 2026-03-31

### Added

- `simulator.py`: dynamic register simulation with `compute_next` (sine, ramp, step, random_walk)
  and `run_device_sim` async coroutine that updates registers every `sim_tick` seconds
- `config.py`: `SimConfig` dataclass; `RegisterConfig.sim` field; `DeviceConfig.sim_tick` field
- `servers.py`: `ObservableDataBlock` — logs FC5/FC6/FC16 writes; `sim_setValues` bypasses log;
  `ServerSetup.sim_coroutines` field

## [0.1.1] - 2026-03-30

### Fixed

- `servers.py`: register init used wrong address offset — fixed to `block.setValues(address + 1, words)`
  to compensate for the hardcoded `+1` inside `ModbusSlaveContext`
- `config.py`: `encode_value` reversed word order for multi-register values — removed reversal;
  go-modbus-client reads big-endian (high word first), no reversal needed

## [0.1.0] - 2026-03-29

### Added

- `config.py`: YAML config parsing (`load_config`) and value encoding (`encode_value`)
- `servers.py`: TCP / RTU-over-TCP / serial servers; PTY pairs via `os.openpty()`; `devices_patched.yaml`
- `devices.yaml`: 16 test devices covering all transport × register type combinations
