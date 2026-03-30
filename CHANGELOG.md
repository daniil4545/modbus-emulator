# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

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
