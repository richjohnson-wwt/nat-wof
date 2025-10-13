
Redis commands

     HGET game:1 puzzle
    "_ _ _ _ _ _ _ _ * _ _ _ _ _ _ _ _ _ _"
    127.0.0.1:6379> HGET game:1 answer
    "PITCHING HORSESHOES"
    127.0.0.1:6379> HGET game:2 answer
    "QUIRKY QUIZ QUESTIONS"


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
  "scores": { "AI1": 0, "AI2": 0, "Rich": 0 },
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
  "scores": { "AI1": 0, "AI2": 0, "Rich": 0 },
  "player": "AI1"
}
JSON
)"
```

```bash
nat run --config_file wof/ai_player/src/ai_player/configs/config.yml --input "$(cat << 'JSON'
     You are AI1 in Wheel of Fortune. Decide your next action based on the game state. Make only one action and Your Final Answer must exactly summarize the last tool you executed and its result. Do not propose a different action. Do not introduce new actions in the Final Answer. Use the available tools. You should always try to solve the puzzle unless you want to spin for money.
{
     "puzzle": "_ _ L _ H _ M A * C _ T _",
     "theme": "On the Map",
     "turn": "AI1",
     "status": "active",
     "guessed_letters": ["R", "S", "T", "L", "N", "D", "H", "M", "C", "B"],
     "guessed_vowels": ["A"],
     "scores": { "AI1": 2750, "AI2": 0, "Rich": 0 },
     "player": "AI1"
}
JSON
)"
```

```bash
    nat run --config_file wof/pat/configs/config.yml --input "Hello world"
```


# Pat (Host) Usage

Use Pat to start or resume a Wheel of Fortune game in Redis. Pat initializes a new puzzle, answer, and theme, sets the turn to AI1, and clears the single-turn guard.

Start or resume a game (structured JSON output):

```bash
nat run --config_file wof/pat/configs/config.yml --input "Start a new game"
```

Force a new game even if one is active (example via environment-driven override):

```bash
# If you want a guaranteed fresh start, you can first finish any existing game
python -m pat.redis_admin finished

# Clear the per-run guard just in case
python -m pat.redis_admin clear_turn

# Start a fresh game with Pat
nat run --config_file wof/pat/configs/config.yml --input "Start a new game"
```

Between AI turns, clear the single-turn guard and (optionally) set whose turn it is:

```bash
# Clear per-run guard so the next NAT run may take exactly one action
python -m pat.redis_admin clear_turn

# Optionally set whose turn it is
python -m pat.redis_admin set_turn AI1   # or AI2 or Rich
```

Then run the AI player with instruction + JSON state (see examples above). The AI tools will mutate Redis and return a structured JSON snapshot. The agent will output the tool's final_answer verbatim and stop.
