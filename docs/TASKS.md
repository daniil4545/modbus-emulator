# TASKS — modbus-emulator

## v1 + v2: Выполнено

- [x] `config.py`: парсинг YAML, `encode_value`, `SimConfig`, `DeviceConfig.sim_tick`
- [x] `servers.py`: TCP / RTU-over-TCP / serial, PTY-пары, `devices_patched.yaml`, `ObservableDataBlock`
- [x] `simulator.py`: `compute_next` (sine/ramp/step/random_walk), `run_device_sim`
- [x] `devices.yaml`: 16 устройств, полное покрытие транспортов × типов регистров
- [x] `tcp_realistic`: sim-регистры (temperature, rpm, load_pct, fault)
- [x] Исправлен offset +1 и big-endian word order в `encode_value`

## M5: Ручное тестирование (pending)

- [ ] Запустить связку эмулятор + драйвер
- [ ] Убедиться что `tcp_realistic` меняет значения, статические устройства стабильны

---

## v3: Template Generator

Спек: `docs/superpowers/specs/2026-03-31-template-generator-design.md`

### M6: `generator.py` — Выполнено

- [x] `expand_template(template_path) -> dict`: читает template.yaml, разворачивает `count`
      - count=1: имя без суффикса, поля без изменений
      - count>1: `name_01..name_N`, port+i, slave_id+i (serial: только slave_id+i)
      - поле `count` удаляется из output
- [x] `save_devices(expanded, output_path)`: сохраняет dict в YAML
- [x] `if __name__ == "__main__"`: standalone запуск `python generator.py template.yaml [out.yaml]`

### M7: `template.yaml` — Выполнено

- [x] Три прототипа: `modbus tcp`, `tcp`, `serial`
- [x] `tcp_sensor`: holding (writable), input (sim:sine), coil (writable), discrete
- [x] Подробные комментарии по полям

### M8: `main.py` — Выполнено

- [x] Точка входа: `sys.argv[1]` или дефолт `template.yaml`
- [x] Вызов `expand_template` → `save_devices` → `load_config` → `build_all` → `asyncio.gather`
- [x] Печать `[generator] Expanded N devices → path/to/devices.yaml`

### M9: Обновление `.gitignore` и `README.md` — Выполнено

- [x] Добавить `devices.yaml` в `.gitignore`
- [x] Обновить README: новый workflow (template → main.py)
- [x] Удалить `gen_stress.py`
