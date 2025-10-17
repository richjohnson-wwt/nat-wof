import random
from wof_shared.wheel import spin_wheel


def test_spin_wheel_returns_known_value(monkeypatch):
    # Force deterministic choice by patching random.choice
    def _choose(seq):
        # Always pick the first entry
        return seq[0]

    monkeypatch.setattr(random, "choice", _choose)
    val = spin_wheel()
    # With our sample wheel.txt, first line is "500"
    assert val == "650"


def test_spin_wheel_multiple_calls():
    # Call a few times; should always return a non-empty string and one of the known types
    vals = [spin_wheel() for _ in range(5)]
    for v in vals:
        assert isinstance(v, str) and len(v) > 0
        # Either a number or a special wedge
        if v.isdigit():
            assert int(v) > 0
        else:
            assert v in {"BANKRUPT", "LOSE A TURN"}
