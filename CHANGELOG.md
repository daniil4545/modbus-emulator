# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.2.1] - 2026-03-31

### Added

- `gen_stress.py`: stress-test config generator — 50 TCP devices across 5 profiles
  (pump, tank, motor, conveyor, sensor_hub), ports 16000–16049, run with `stress_devices.yaml`

### Changed

- `servers.py`: `devices_patched.yaml` is now written on every startup regardless of whether
  serial devices are present — driver can always use this fixed path
- `servers.py`: `ObservableDataBlock._on_write` promoted to a class-level annotated field
  (`Callable | None`) to satisfy Pyright type checker

## [0.2.0] - 2026-03-31

### Added

- `simulator.py`: dynamic register simulation with `compute_next` (sine, ramp, step, random_walk)
  and `run_device_sim` async coroutine that updates registers every `sim_tick` seconds
- `config.py`: `SimConfig` dataclass; `RegisterConfig.sim` field; `DeviceConfig.sim_tick` field;
  `load_config` now parses `sim:` blocks from YAML
- `servers.py`: `ObservableDataBlock` subclass — logs incoming FC5/FC6/FC16 writes to stdout;
  `sim_setValues` method for simulator writes (bypasses the write log);
  `ServerSetup.sim_coroutines` field; simulation coroutines launched via `asyncio.gather`
- `devices.yaml`: `tcp_realistic` now has `sim_tick: 1` and `sim:` on four registers —
  temperature (sine 200–320, 60s), rpm (ramp 800–2200, 30s),
  fault (step, 10% duty), load_pct (sine 30–95, 45s)
- `docs/TASKS.md`: task tracking file

## [0.1.1] - 2026-03-30

### Fixed

- **servers.py**: register init used wrong address offset — `block.setValues(address, words)`
  stored values one slot below where `ModbusSlaveContext.getValues` reads them.
  Fixed to `block.setValues(address + 1, words)` to compensate for the hardcoded
  `+1` offset inside `ModbusSlaveContext`. Affected all 16 devices.

- **config.py**: `encode_value` reversed word order for multi-register values,
  producing wrong results for uint32/int32/float32/int64/uint64/float64 registers.
  go-modbus-client reads big-endian word order (high word first), so reversal was incorrect.
  Removed the `if reg_size > 1: words = list(reversed(words))` block.

## [0.1.0] - 2026-03-29

### Added

- `config.py`: YAML config parsing (`load_config`) and value encoding (`encode_value`)
- `servers.py`: server creation for TCP, RTU-over-TCP, and serial transports;
  PTY pair setup via `os.openpty()`; `devices_patched.yaml` generation for serial paths
- `devices.yaml`: 16 test devices covering all transport × register type combinations
- `docs/PRD.md`: architecture, encoding rules, pymodbus API reference
