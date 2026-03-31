# TASKS — modbus-emulator

## v2: Динамические значения

Цель: регистры с полем `sim:` обновляются в фоне по заданному закону.
Детали архитектуры и YAML-синтаксис — в PRD.md (секция "Динамические значения").

---

### M1: Расширение config.py

- [x] Добавить `@dataclass SimConfig` с полями:
      `type: str`, `min`, `max`, `period`, `phase`, `step`, `values`
- [x] Добавить `sim: Optional[SimConfig] = None` в `RegisterConfig`
- [x] Добавить `sim_tick: float = 1.0` в `DeviceConfig`
- [x] Обновить `load_config`: парсить `sim:` блок если присутствует;
      поле `values` — список, остальные — числа

### M2: Модуль simulator.py

- [x] Реализовать `compute_next(sim: SimConfig, elapsed: float) -> int | float | bool`
      для типов `sine`, `ramp`, `step`
- [x] Реализовать `random_walk`: хранит текущее значение в изменяемом контейнере
      (например, `list[float]` с одним элементом), передаётся в `compute_next`
- [x] Реализовать `run_device_sim(device_name, registers, blocks, tick_sec) -> coroutine`

### M3: Интеграция в servers.py

- [x] Изменить `_build_context` — возвращать `(context, blocks)`
      где `blocks: dict[str, ObservableDataBlock]`
- [x] Добавить `sim_setValues` в `ObservableDataBlock` — запись без колбэка
- [x] Добавить `sim_coroutines: list` в `ServerSetup`
- [x] В `build_all`: для каждого устройства с sim-регистрами создавать корутину
      `run_device_sim` и добавлять в `ServerSetup.sim_coroutines`
- [x] Обновить `__main__`: `asyncio.gather(*servers, *sim_coroutines)`

### M4: Обновление devices.yaml

- [x] Добавить `sim_tick: 1` и `sim:` блоки к `tcp_realistic` (temperature, rpm, load_pct, fault)
- [x] Убедиться что статические устройства (tcp_uint и др.) не затронуты

### M5: Проверка

- [ ] Запустить эмулятор, проверить в логах драйвера что значения `tcp_realistic`
      меняются каждые несколько секунд
- [ ] Убедиться что статические устройства продолжают отдавать фиксированные значения

---

## v1: Выполнено

- [x] `config.py`: парсинг YAML, `encode_value` (все форматы, big-endian word order)
- [x] `servers.py`: TCP, RTU-over-TCP, serial; PTY-пары; `devices_patched.yaml`
- [x] `devices.yaml`: 16 устройств, полное покрытие
- [x] Исправлен offset +1 при записи в `ModbusSequentialDataBlock`
- [x] Исправлен порядок слов в `encode_value` (big-endian, не reversed)
