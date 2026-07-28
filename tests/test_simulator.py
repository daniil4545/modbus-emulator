"""Тесты compute_next из simulator.py."""

import pytest

from config import SimConfig
from simulator import compute_next


def test_compute_next_sine_at_start_equals_midpoint():
    sim = SimConfig(type="sine", min=0.0, max=10.0, period=10.0, phase=0.0)
    assert compute_next(sim, 0.0, []) == pytest.approx(5.0)


def test_compute_next_ramp_at_half_period():
    sim = SimConfig(type="ramp", min=0.0, max=10.0, period=10.0)
    assert compute_next(sim, 5.0, []) == pytest.approx(5.0)


def test_compute_next_step_cycles_through_values():
    sim = SimConfig(type="step", period=5.0, values=[10, 20, 30])
    assert compute_next(sim, 7.0, []) == 20
    assert compute_next(sim, 12.0, []) == 30
    assert compute_next(sim, 17.0, []) == 10


def test_compute_next_random_walk_stays_within_bounds():
    sim = SimConfig(type="random_walk", min=0.0, max=10.0, step=1.0)
    state = [5.0]
    for _ in range(100):
        value = compute_next(sim, 0.0, state)
        assert sim.min <= value <= sim.max
        assert state[0] == value
