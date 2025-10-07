import logging
import random
from pathlib import Path
import csv


def get_puzzle() -> tuple[str, str]:
    """Return a random (puzzle, theme) pair from data/puzzles.csv.

    The CSV is expected to have rows of the form:
    puzzle, theme, date, episode, round
    with no header row.
    """
    # Resolve CSV path relative to this file: examples/wof/data/puzzles.csv
    csv_path = Path(__file__).resolve().parents[2] / "data" / "puzzles.csv"

    puzzles: list[tuple[str, str]] = []
    try:
        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or len(row) < 2:
                    continue
                puzzle, theme = row[0].strip(), row[1].strip()
                if puzzle and theme:
                    puzzles.append((puzzle, theme))
    except FileNotFoundError:
        logger.error("puzzles.csv not found at %s", csv_path)
        raise

    if not puzzles:
        raise ValueError("No puzzles loaded from puzzles.csv")

    return random.choice(puzzles)

def mask_puzzle(puzzle: str) -> str:
    """Mask a puzzle by replacing letters with '_' and spaces with '*',
    separating each symbol with a single space.

    Example: "STEAK KNIFE" -> "_ _ _ _ _ * _ _ _ _ _"
    Punctuation and digits are left as-is but still spaced out.
    """
    masked_chars = []
    for ch in puzzle:
        if ch.isalpha():
            masked_chars.append("_")
        elif ch == " ":
            masked_chars.append("*")
        else:
            masked_chars.append(ch)
    return " ".join(masked_chars)
