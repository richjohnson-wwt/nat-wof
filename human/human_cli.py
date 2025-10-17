#!/usr/bin/env python3
import json
import sys
from typing import Optional

from wof_shared.wheel import spin_wheel
from wof_shared.constants import VOWELS, VOWEL_COST
from wof_shared.state import (
    get_field,
    set_turn,
    next_turn,
    reveal_letter,
    update_score,
    add_guessed_letter,
    set_current_game_status_finished,
    get_answer,
    resolve_display_name,
)


def _load_json_field(name: str, default):
    raw = get_field(name)
    if raw in (None, ""):
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def show_state():
    puzzle = get_field("puzzle") or ""
    theme = get_field("theme") or ""
    player = get_field("player") or ""
    scores = _load_json_field("scores", {})
    guessed_consonants = _load_json_field("guessed_consonants", [])
    guessed_vowels = _load_json_field("guessed_vowels", [])

    print("\n=== Wheel of Fortune (Human Turn) ===")
    print(f"Player: {resolve_display_name(player)}")
    print(f"Theme:  {theme}")
    print(f"Puzzle: {puzzle}")
    # Map score keys to display names for presentation only
    pretty_scores = {resolve_display_name(pid): val for pid, val in (scores or {}).items()}
    print(f"Scores: {pretty_scores}")
    print(f"Guessed consonants: {', '.join(guessed_consonants) if guessed_consonants else '-'}")
    print(f"Guessed vowels:     {', '.join(guessed_vowels) if guessed_vowels else '-'}")


def _is_consonant(ch: str) -> bool:
    ch = (ch or "").upper()
    return len(ch) == 1 and ch.isalpha() and ch not in VOWELS


def _is_vowel(ch: str) -> bool:
    ch = (ch or "").upper()
    return len(ch) == 1 and ch in VOWELS


def handle_spin(current_player: str) -> bool:
    wedge = spin_wheel()
    print(f"You spun: {wedge}")

    if wedge.upper() == "BANKRUPT":
        # Set player's score to 0
        scores = _load_json_field("scores", {})
        scores[current_player] = 0
        # write scores
        from wof_shared.state import hset_json  # local import to avoid exporting in public API
        hset_json("scores", scores)
        print("BANKRUPT! Your score is now 0. Turn ends.")
        return True  # end turn

    if wedge.upper() == "LOSE A TURN":
        print("Lose a Turn! Turn ends.")
        return True  # end turn

    # Ask for consonant
    while True:
        guess = input("Enter a consonant: ").strip().upper()
        if not _is_consonant(guess):
            print("Please enter a single consonant (A/E/I/O/U are vowels).")
            continue
        guessed_consonants = _load_json_field("guessed_consonants", [])
        if guess in guessed_consonants:
            print("That consonant was already guessed. Try another.")
            continue
        break

    occurrences = reveal_letter(guess)
    add_guessed_letter(guess, is_vowel=False)
    if occurrences > 0:
        amount = int(wedge) if wedge.isdigit() else 0
        update_score(current_player, amount * occurrences)
        print(f"'{guess}' appears {occurrences} time(s). You earn {amount * occurrences}.")
        return False
    else:
        print(f"'{guess}' is not in the puzzle.")
        return True


def handle_buy_vowel(current_player: str) -> bool:
    scores = _load_json_field("scores", {})
    balance = int(scores.get(current_player, 0) or 0)
    if balance < VOWEL_COST:
        print(f"Insufficient funds. You have {balance}, need {VOWEL_COST}.")
        return False  # allow trying another action in this simple CLI

    # Deduct cost
    scores[current_player] = balance - VOWEL_COST
    from wof_shared.state import hset_json
    hset_json("scores", scores)

    while True:
        guess = input("Enter a vowel (A/E/I/O/U): ").strip().upper()
        if not _is_vowel(guess):
            print("Please enter a single vowel (A/E/I/O/U).")
            continue
        guessed_vowels = _load_json_field("guessed_vowels", [])
        if guess in guessed_vowels:
            print("That vowel was already bought. Try another or choose a different action.")
            continue
        break

    occurrences = reveal_letter(guess)
    add_guessed_letter(guess, is_vowel=True)
    print(f"Revealed '{guess}' {occurrences} time(s).")
    # After buying a vowel, keep the turn in classic rules, but for simplicity end turn here
    return occurrences == 0


def handle_solve(current_player: str) -> bool:
    attempt = input("Enter your solution (UPPERCASE letters and spaces): ").strip().upper()
    # Normalize both by removing non-letters
    import re
    norm_attempt = re.sub(r"[^A-Z]", "", attempt)
    answer = (get_answer() or "").upper()
    norm_answer = re.sub(r"[^A-Z]", "", answer)

    if norm_attempt == norm_answer and answer:
        print("Correct! You solved the puzzle!")
        # Reveal the full puzzle in Redis so other clients don't see masked letters
        from wof_shared.state import update_game_field, resolve_display_name  # local import to avoid exporting in public API
        update_game_field("puzzle", answer)
        # Record winner display name (from config/player_names mapping)
        winner_name = resolve_display_name(current_player)
        update_game_field("winner", winner_name)
        set_current_game_status_finished()
        return True
    else:
        print(f"Incorrect. The attempt '{attempt}' does not match.")
        return True  # end turn on incorrect solve


def main() -> int:
    current_player = get_field("player") or ""
    if not current_player:
        print("No active game or current player set. Start a game via Pat first.")
        return 1

    show_state()

    while True:
        print("\nChoose action: [1] Spin  [2] Buy vowel  [3] Solve  [q] Quit")
        choice = input("> ").strip().lower()
        if choice == "q":
            return 0
        if choice not in {"1", "2", "3"}:
            print("Invalid choice. Try again.")
            continue

        end_turn = False
        if choice == "1":
            end_turn = handle_spin(current_player)
        elif choice == "2":
            end_turn = handle_buy_vowel(current_player)
        elif choice == "3":
            end_turn = handle_solve(current_player)

        show_state()
        if end_turn:
            nxt = next_turn()
            print(f"Turn ended. Next player: {nxt}")
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
