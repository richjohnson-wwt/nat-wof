
Redis commands

```bash
127.0.0.1:6379> GET current_game_id
"1"
127.0.0.1:6379> HGET game:1 puzzle
"_ _ _ _ _ _ _ _ * _ _ _ _ _ _ _ _ _ _"
127.0.0.1:6379> HGET game:1 answer
"PITCHING HORSESHOES"
127.0.0.1:6379> HGET game:2 answer
"QUIRKY QUIZ QUESTIONS"
```

# Install dependencies

    uv pip install -e wof_shared
    uv pip install redis fakeredis pytest


# Smoke Test Commands

```bash
nat run --config_file pat/configs/config.yml --input "Start a new game"

uv run pat/src/pat/redis_admin.py finished
uv run pat/src/pat/redis_admin.py set_turn AI1
uv run pat/src/pat/redis_admin.py generate_ai_player_prompt
redis-cli
    GET game:18:answer
    HGETALL game:37
uv run human/human_cli.py
```

# Running the game:

```bash
uv run human/game_runner.py
```

# Tests

```bash
pytest wof_shared/tests -q
pytest -q ai_player/tests/test_vowel_heuristic.py
```

### The remainder of Readme is notes on running the game manually

# Human Player

```bash
uv run human/human_cli.py
```

# Run the AI Player with correct here-doc syntax

Option A: Write input to a file, then pass it

```bash
cat > /tmp/wof_input.txt << 'JSON'
You are AI1 in Wheel of Fortune. Decide your next action based on the game state. Use the available tools.
{
  "puzzle": "_ _ _ _ * _ _ _ _ _ _ _",
  "theme": "Food & Drink",
  "turn": "AI1",
  "status": "active",
  "guessed_letters": [],
  "guessed_vowels": [],
  "scores": { "AI1": 0, "AI2": 0, "Human": 0 },
  "player": "AI1"
}
JSON

nat run --config_file wof/ai_player/src/ai_player/configs/config.yml --input "$(cat /tmp/wof_input.txt)"
```

Option B: Inline command substitution (no file)

```bash
nat run --config_file wof/ai_player/src/ai_player/configs/config.yml --input "$(cat << 'JSON'
You are AI1 in Wheel of Fortune. Decide your next action based on the game state. Make only one action and Your Final Answer must exactly summarize the last tool you executed and its result. Do not propose a different action. Do not introduce new actions in the Final Answer. Use the available tools.
{
  "puzzle": "_ _ _ _ * _ _ _ _ _ _ _",
  "theme": "Food & Drink",
  "turn": "AI1",
  "status": "active",
  "guessed_letters": [],
  "guessed_vowels": [],
  "scores": { "AI1": 0, "AI2": 0, "Human": 0 },
  "player": "AI1"
}
JSON
)"
```

```bash
nat run --config_file ai_player/configs/config.yml --input "$(cat << 'JSON'
{
     "puzzle": "_ E _ E T A R I A _ * _ I _ _ A",
     "theme": "Food & Drink",
     "status": "active",
     "guessed_letters": ["R", "S", "T"],
     "guessed_vowels": ["A", "E", "I"],
     "scores": { "AI1": 850, "AI2": 0, "Human": 0 },
     "player": "AI1"
}
JSON
)"
```


# Pat (Host) Usage

Use Pat to start or resume a Wheel of Fortune game in Redis. Pat initializes a new puzzle, answer, and theme, sets the turn to AI1, and clears the single-turn guard.

Start or resume a game (structured JSON output):

```bash
nat run --config_file pat/configs/config.yml --input "Start a new game"
```

### Helper script for game management if needed

```bash
# If you want a guaranteed fresh start, you can first finish any existing game
uv run wof/pat/src/pat/redis_admin.py finished

# Clear the per-run guard just in case
uv run wof/pat/src/pat/redis_admin clear_turn

# Start a fresh game with Pat
nat run --config_file wof/pat/configs/config.yml --input "Start a new game"
```

Between AI turns, clear the single-turn guard and (optionally) set whose turn it is:

```bash
# Create the ai player input file
uv run wof/pat/src/pat/redis_admin.py generate_ai_player_prompt

# Optionally set whose turn it is
uv run wof/pat/src/pat/redis_admin.py set_turn AI1   # or AI2 or Human
```

Then run the AI player with instruction + JSON state (see examples above). The AI tools will mutate Redis and return a structured JSON snapshot. The agent will output the tool's final_answer verbatim and stop.
