from pathlib import Path
import random

def load_wheel():
    wheel_path = Path(__file__).resolve().parents[2] / "data" / "wheel.txt"
    with open(wheel_path, "r") as f:
        wheel = f.read().splitlines()
    return wheel


def spin_wheel():
    wheel = load_wheel()
    return random.choice(wheel)
