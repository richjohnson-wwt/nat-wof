import redis
import sys
from pathlib import Path
import random

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

def set_current_game_status_finished():
    game_id = r.get("current_game_id")
    r.hset(f"game:{game_id}", "status", "finished")

def set_turn(player: str):
    """Set the current player's turn (e.g., AI1, AI2, Human)."""
    game_id = r.get("current_game_id")
    if not game_id:
        print("No current_game_id set")
        return
    r.hset(f"game:{game_id}", "player", player)
    print(f"Set player to {player} on game:{game_id}")

def hello_redis():
    r.set("msg:hello", "Hello Redis!!!")
    msg = r.get("msg:hello")
    print(msg)

def generate_ai_player_prompt():
    game_id = r.get("current_game_id")
    if not game_id:
        print("No current_game_id set")
        return
    import json as _json
    # Fetch fields from Redis
    puzzle = r.hget(f"game:{game_id}", "puzzle")
    theme = r.hget(f"game:{game_id}", "theme")
    status = r.hget(f"game:{game_id}", "status")
    # Prefer consonants-specific list if available
    guessed_consonants_raw = r.hget(f"game:{game_id}", "guessed_consonants")
    # Backward-compatibility: some games may store all letters in 'guessed_letters'
    guessed_letters_raw = r.hget(f"game:{game_id}", "guessed_letters")
    guessed_vowels_raw = r.hget(f"game:{game_id}", "guessed_vowels")
    scores_raw = r.hget(f"game:{game_id}", "scores")
    player = r.hget(f"game:{game_id}", "player")

    # Coerce JSON-like fields safely
    def _coerce_json(s, default):
        try:
            return _json.loads(s) if s not in (None, "", "null") else default
        except Exception:
            return default

    # guessed_letters should represent consonants used in examples and AI inputs
    guessed_consonants = _coerce_json(guessed_consonants_raw, None)
    if guessed_consonants is None:
        # Fallback to 'guessed_letters' if consonants-specific key isn't present
        guessed_consonants = _coerce_json(guessed_letters_raw, [])
    guessed_letters = guessed_consonants
    guessed_vowels = _coerce_json(guessed_vowels_raw, [])
    scores = _coerce_json(scores_raw, {"AI1": 0, "AI2": 0, "Human": 0})

    payload = {
        "puzzle": puzzle,
        "theme": theme,
        "status": status,
        "guessed_letters": guessed_letters,
        "guessed_vowels": guessed_vowels,
        "scores": scores,
        "player": player,
    }
    payload_json = _json.dumps(payload)

    # Write payload to file under ai_player data folder
    import os as _os
    out_dir = _os.path.join("ai_player", "data")
    _os.makedirs(out_dir, exist_ok=True)
    out_path = _os.path.join(out_dir, "prompt.json")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(payload_json)

    # Return a command that reads the file
    cmd = (
        f"nat run --config_file ai_player/configs/config.yml --input \"$(cat {out_path})\""
    )
    return cmd

def human_turn():
    game_id = r.get("current_game_id")
    if not game_id:
        print("No current_game_id set")
        return
    # prompt for action
    action = input("Enter action (1 spin, 2 buy_vowel, 3 solve): ")
    if action == "1":
        wheel_path = Path(__file__).resolve().parents[2] / "data" / "wheel.txt"
        with open(wheel_path, "r") as f:
            wheel = f.read().splitlines()
        spin = random.choice(wheel)
        print(f"Spin: {spin}")
        #prompt for consonant
        consonant = input("Enter consonant: ")

    elif action == "2":
        buy_vowel()
    elif action == "3":
        solve_puzzle()
    else:
        print("Invalid action")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == "finished":
            set_current_game_status_finished()
        elif sys.argv[1] == "set_turn" and len(sys.argv) > 2:
            set_turn(sys.argv[2])
        elif sys.argv[1] == "hello":
            hello_redis()
        elif sys.argv[1] == "generate_ai_player_prompt":
            print(generate_ai_player_prompt())
        elif sys.argv[1] == "human_turn":
            human_turn()
        else:
            print("Invalid command")
