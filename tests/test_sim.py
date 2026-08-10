"""Законы динамического изменения регистров: simulator.compute_next."""

import pytest

from config import SimConfig
from simulator import compute_next


def test_sine_spans_min_max_over_period():
    sim = SimConfig(type="sine", min=20.0, max=30.0, period=8.0)
    values = [compute_next(sim, t, [0.0]) for t in range(9)]
    assert min(values) == pytest.approx(20.0)
    assert max(values) == pytest.approx(30.0)


def test_ramp_restarts_at_period():
    sim = SimConfig(type="ramp", min=0.0, max=100.0, period=10.0)
    assert compute_next(sim, 0.0, [0.0]) == pytest.approx(0.0)
    assert compute_next(sim, 5.0, [0.0]) == pytest.approx(50.0)
    assert compute_next(sim, 10.0, [0.0]) == pytest.approx(0.0)


def test_step_cycles_through_values():
    sim = SimConfig(type="step", period=1.0, values=[10, 20, 30])
    assert [compute_next(sim, t, [0.0]) for t in range(4)] == [10, 20, 30, 10]


def test_random_walk_stays_within_bounds():
    sim = SimConfig(type="random_walk", min=0.0, max=10.0, step=100.0)
    state = [5.0]
    values = [compute_next(sim, t, state) for t in range(50)]
    assert all(0.0 <= v <= 10.0 for v in values)


def test_unknown_type_rejected():
    with pytest.raises(ValueError, match="unknown sim type"):
        compute_next(SimConfig(type="chaos"), 0.0, [0.0])
