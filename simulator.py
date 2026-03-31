"""Фоновые корутины обновления динамических регистров по закону из SimConfig."""

from __future__ import annotations

import asyncio
import math
import random

from config import RegisterConfig, SimConfig, encode_value


def compute_next(sim: SimConfig, elapsed: float, state: list[float]) -> float:
    """Вычисляет значение регистра на момент времени elapsed (сек от старта).

    state — список из одного элемента; используется только для random_walk,
    остальные типы игнорируют его.
    """
    if sim.type == "sine":
        mid = (sim.max + sim.min) / 2
        amp = (sim.max - sim.min) / 2
        return mid + amp * math.sin(2 * math.pi * (elapsed + sim.phase) / sim.period)

    if sim.type == "ramp":
        t = math.fmod(elapsed, sim.period) / sim.period
        return sim.min + (sim.max - sim.min) * t

    if sim.type == "step":
        idx = int(elapsed / sim.period) % len(sim.values)
        return float(sim.values[idx])

    if sim.type == "random_walk":
        delta = random.uniform(-sim.step, sim.step)
        state[0] = max(sim.min, min(sim.max, state[0] + delta))
        return state[0]

    raise ValueError(f"unknown sim type: {sim.type!r}")


async def run_device_sim(
    device_name: str,
    registers: list[RegisterConfig],
    blocks: dict,
    tick_sec: float,
) -> None:
    """Фоновая корутина: обновляет регистры с sim: каждые tick_sec секунд.

    blocks — словарь {"hr": ObservableDataBlock, ...}; используется метод
    sim_setValues, который записывает значение без активации колбэка записи.
    """
    sim_regs = [r for r in registers if r.sim is not None]
    if not sim_regs:
        return

    # Начальное состояние для random_walk — берётся из test_value каждого регистра
    states: dict[int, list[float]] = {
        id(r): [float(r.test_value)] for r in sim_regs
    }

    start = asyncio.get_event_loop().time()

    while True:
        await asyncio.sleep(tick_sec)
        elapsed = asyncio.get_event_loop().time() - start

        for reg in sim_regs:
            state = states[id(reg)]
            raw = compute_next(reg.sim, elapsed, state)

            # Привести тип к ожидаемому encode_value:
            # float-формат остаётся float, int/uint — int, coil/discrete — bool
            if reg.format in ("uint", "int"):
                value = int(round(raw))
            elif reg.format is None:
                value = bool(round(raw))
            else:
                value = raw

            words = encode_value(value, reg.format, reg.reg_size)
            blocks[reg.reg_type].sim_setValues(reg.address + 1, words)
