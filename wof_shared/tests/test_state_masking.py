import json
from wof_shared.redis_client import get_redis
from wof_shared.state import update_game_field, reveal_letter, reveal_all, get_field


def seed_game(answer: str = "STEAK KNIFE"):
    r = get_redis()
    r.set("current_game_id", "1")
    key = "game:1"
    r.hset(key, mapping={
        "puzzle": "",  # will be overwritten by reveal helpers
        "theme": "Thing",
        "player": "AI1",
        "status": "active",
        "guessed_consonants": json.dumps([]),
        "guessed_vowels": json.dumps([]),
        "revealed": json.dumps([]),
        "scores": json.dumps({"AI1": 0, "AI2": 0, "Human": 0}),
    })
    # Store answer in secret key to match production behavior
    r.set("game:1:answer", answer)


def test_reveal_letter_updates_puzzle_and_count():
    seed_game("STEAK KNIFE")
    # Reveal E (appears twice in STEAK KNIFE)
    count = reveal_letter("E")
    assert count == 2
    puzzle = get_field("puzzle")
    assert puzzle is not None
    # Should contain two 'E' and a '*' for the space
    assert puzzle.count("E") == 2
    assert "*" in puzzle
    # Underscores should still be present (not fully revealed yet)
    assert "_" in puzzle


def test_reveal_all_removes_underscores():
    seed_game("STEAK KNIFE")
    reveal_all()
    puzzle = get_field("puzzle")
    assert puzzle is not None
    # After reveal_all, there should be no underscores; spaces become '*'
    assert "_" not in puzzle
    assert "*" in puzzle
