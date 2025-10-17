#!/usr/bin/env python3
import json
import subprocess
import sys
import time
from pathlib import Path

from wof_shared.state import get_field

# .../nemo-agent-toolkit
REPO_ROOT = Path(__file__).resolve().parents[2]
AI_CONFIG = "nat_wof_game/ai_player/configs/config.yml"
PAT_CONFIG = "nat_wof_game/pat/configs/config.yml"
PROMPT_PATH = REPO_ROOT / "nat_wof_game/ai_player/data" / "prompt.json"

def create_new_game():
    return subprocess.run(
        ["nat", "run", "--config_file", PAT_CONFIG, "--input", "create_new_game"],
        cwd=REPO_ROOT,
        check=False,
    ).returncode

def run_human():
    subprocess.run(
        [sys.executable, "nat_wof_game/pat/src/pat/redis_admin.py", "set_turn", "Human"],
        cwd=REPO_ROOT,
        check=False,
    )
    return subprocess.run(
        [sys.executable, "nat_wof_game/human/human_cli.py"],
        cwd=REPO_ROOT,
        check=False,
    ).returncode

def run_ai(player: str):
    # Regenerate the AI prompt so it reflects the latest Redis state
    subprocess.run(
        [sys.executable, "nat_wof_game/pat/src/pat/redis_admin.py", "set_turn", player],
        cwd=REPO_ROOT,
        check=False,
    )

    gen = subprocess.run(
        [sys.executable, "nat_wof_game/pat/src/pat/redis_admin.py", "generate_ai_player_prompt"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if gen.returncode != 0:
        print("Failed to generate AI prompt:", gen.stderr or gen.stdout)
        return gen.returncode

    try:
        prompt_text = PROMPT_PATH.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Failed to read prompt.json: {e}")
        return 1

    # Run the AI workflow with the prompt as input
    return subprocess.run(
        ["nat", "run", "--config_file", AI_CONFIG, "--input", prompt_text],
        cwd=REPO_ROOT,
        check=False,
    ).returncode

def is_game_over():
    return get_field("status") == "finished"

def main():
    if is_game_over():
        print("Game over. Starting a new game.")
        create_new_game()
    else:
        print("Game is already in progress.")

    while True:
        print("\nChoose action: [1] AI1  [2] AI2  [3] Human  [q] Quit")
        choice = input("> ").strip().lower()
        if choice == "q":
            return 0
        if choice not in {"1", "2", "3"}:
            print("Invalid choice. Try again.")
            continue

        if choice == "1":
            rc = run_ai("AI1")
        elif choice == "2":
            rc = run_ai("AI2")
        elif choice == "3":
            rc = run_human()
        if rc != 0:
            print(f"Last turn runner exited with code {rc}.")
        if is_game_over():
            print("Game over.")
            return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(0)
