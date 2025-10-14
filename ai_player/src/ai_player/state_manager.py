import redis, json

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def get_current_game_for_ai_player(player_name):
    game_id = r.get("current_game_id")
    if not game_id:
        return None
    all_data = r.hgetall(f"game:{game_id}")
    # Safely decode JSON-encoded fields and handle missing keys
    revealed = json.loads(all_data.get("revealed", "[]"))
    guessed_consonants = json.loads(all_data.get("guessed_consonants", "[]"))
    guessed_vowels = json.loads(all_data.get("guessed_vowels", "[]"))
    # Some game flows may store a single list under 'guessed_letters'
    guessed_letters = json.loads(all_data.get("guessed_letters", "[]"))
    scores = json.loads(all_data.get("scores", "{}"))
    score = scores.get(player_name, 0)

    data = {
        "puzzle": all_data.get("puzzle"),
        "theme": all_data.get("theme"),
        "guessed_consonants": guessed_consonants or [c for c in guessed_letters if c.upper() not in ["A","E","I","O","U"]],
        "guessed_vowels": guessed_vowels or [v for v in guessed_letters if v.upper() in ["A","E","I","O","U"]],
        "revealed": revealed,
    }
    return data

def get_field(field):
    game_id = r.get("current_game_id")
    return r.hget(f"game:{game_id}", field)

def get_unguessed_vowels():
    game_id = r.get("current_game_id")
    guessed_vowels = json.loads(r.hget(f"game:{game_id}", "guessed_vowels"))
    vowels = ["A", "E", "I", "O", "U"]
    remaining_vowels = [v for v in vowels if v not in guessed_vowels]
    return remaining_vowels


# --- Mutation helpers (non-destructive wrappers) ---
def update_game_field(field: str, value: str) -> None:
    """Update a raw field on the current game."""
    game_id = r.get("current_game_id")
    if game_id:
        r.hset(f"game:{game_id}", field, value)


def _load_json_field(field: str, default):
    game_id = r.get("current_game_id")
    if not game_id:
        return default
    raw = r.hget(f"game:{game_id}", field)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def add_guessed_letter(letter: str, is_vowel: bool) -> None:
    """Add a guessed letter to the appropriate JSON list in Redis.

    If 'guessed_consonants' is missing but 'guessed_letters' exists, update that instead.
    """
    letter = (letter or "").upper()
    if not letter:
        return
    game_id = r.get("current_game_id")
    if not game_id:
        return

    # Prefer split storage; fallback to unified 'guessed_letters'
    if is_vowel:
        lst = _load_json_field("guessed_vowels", [])
        if letter not in lst:
            lst.append(letter)
        r.hset(f"game:{game_id}", "guessed_vowels", json.dumps(lst))
    else:
        if r.hexists(f"game:{game_id}", "guessed_consonants"):
            lst = _load_json_field("guessed_consonants", [])
            if letter not in lst:
                lst.append(letter)
            r.hset(f"game:{game_id}", "guessed_consonants", json.dumps(lst))
        else:
            # Fallback
            lst = _load_json_field("guessed_letters", [])
            if letter not in lst:
                lst.append(letter)
            r.hset(f"game:{game_id}", "guessed_letters", json.dumps(lst))


def update_score(player: str, delta: int) -> None:
    """Add delta to the player's score in the 'scores' JSON field."""
    game_id = r.get("current_game_id")
    if not game_id:
        return
    scores = _load_json_field("scores", {})
    old = int(scores.get(player, 0) or 0)
    scores[player] = old + int(delta)
    r.hset(f"game:{game_id}", "scores", json.dumps(scores))


def _mask_from_answer_and_revealed(answer: str, revealed_positions: list[int]) -> str:
    """Produce the masked puzzle string using underscores and '*' for spaces.

    Example: "STEAK KNIFE" -> "_ _ _ _ _ * _ _ _ _ _"
    """
    out = []
    for idx, ch in enumerate(answer or ""):
        if ch == " ":
            out.append("*")
        elif ch.isalpha():
            out.append(ch.upper() if idx in revealed_positions else "_")
        else:
            out.append(ch)
    return " ".join(out)


def reveal_letter(letter: str) -> int:
    """Reveal all occurrences of 'letter' in the answer; update 'revealed' and masked 'puzzle'.

    Returns the number of newly revealed occurrences.
    """
    game_id = r.get("current_game_id")
    if not game_id:
        return 0
    answer = r.hget(f"game:{game_id}", "answer") or ""
    letter = (letter or "").upper()
    if not letter or not answer:
        return 0

    revealed = _load_json_field("revealed", [])
    newly = 0
    for idx, ch in enumerate(answer.upper()):
        if ch == letter and idx not in revealed:
            revealed.append(idx)
            newly += 1
    if newly:
        revealed.sort()
        r.hset(f"game:{game_id}", "revealed", json.dumps(revealed))
        masked = _mask_from_answer_and_revealed(answer, revealed)
        r.hset(f"game:{game_id}", "puzzle", masked)
    return newly


# --- Additional helpers for game control ---
def set_status(status: str) -> None:
    """Set the current game's status (e.g., 'active', 'finished')."""
    game_id = r.get("current_game_id")
    if not game_id:
        return
    r.hset(f"game:{game_id}", "status", status)


def set_current_game_status_finished() -> None:
    set_status("finished")


def get_turn() -> str | None:
    game_id = r.get("current_game_id")
    if not game_id:
        return None
    return r.hget(f"game:{game_id}", "turn")


def set_turn(player: str) -> None:
    game_id = r.get("current_game_id")
    if not game_id:
        return
    r.hset(f"game:{game_id}", "turn", player)


def next_turn() -> str | None:
    order = ["AI1", "AI2", "Rich"]
    cur = get_turn()
    if not cur:
        nxt = order[0]
    else:
        try:
            idx = order.index(cur)
            nxt = order[(idx + 1) % len(order)]
        except ValueError:
            nxt = order[0]
    set_turn(nxt)
    return nxt


def reveal_all() -> None:
    """Reveal the entire answer in the masked puzzle and update 'revealed'."""
    game_id = r.get("current_game_id")
    if not game_id:
        return
    answer = r.hget(f"game:{game_id}", "answer") or ""
    # Reveal all alpha characters (keep '*' for spaces, leave punctuation as-is in mask function)
    revealed = [i for i, ch in enumerate(answer)]
    r.hset(f"game:{game_id}", "revealed", json.dumps(revealed))
    masked = _mask_from_answer_and_revealed(answer, revealed)
    r.hset(f"game:{game_id}", "puzzle", masked)


