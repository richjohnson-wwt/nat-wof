from importlib import resources as _resources
import random


def spin_wheel() -> str:
    """Return a random wedge value from packaged assets/wheel.txt.

    Values can be numeric strings (e.g., "500"), or special values like
    "BANKRUPT" or "LOSE A TURN". Caller is responsible for interpreting
    the outcome (e.g., bankruptcy or losing a turn).
    """
    lines = _resources.files("wof_shared.assets").joinpath("wheel.txt").read_text().splitlines()
    lines = [ln.strip() for ln in lines if ln.strip()]
    return random.choice(lines)
