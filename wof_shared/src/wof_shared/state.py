import json
from typing import Any, Dict, List, Optional

from .redis_client import get_redis
from .constants import VOWELS, VOWEL_COST, PLAYER_ID_ORDER, STATUS_ACTIVE, STATUS_FINISHED


def start_new_game(puzzle, answer, theme, players):
    r = get_redis()
    game_id = r.incr("game_id_counter")
    key = f"game:{game_id}"
    # Initialize scores dynamically from provided players (support dict of ids->names or iterable of ids)
    try:
        if isinstance(players, dict) and players:
            score_keys = list(players.keys())
        elif isinstance(players, (list, tuple)) and players:
            score_keys = list(players)
        else:
            # Fallback to known player IDs
            score_keys = ["AI1", "AI2", "Human"]
    except Exception:
        score_keys = ["AI1", "AI2", "Human"]
    initial_scores = {pid: 0 for pid in score_keys}
    r.hset(key, mapping={
        "puzzle": puzzle,
        "theme": theme,
        "player": "AI1",
        "status": "active",
        "winner": "",
        "guessed_consonants": json.dumps([]),
        "guessed_vowels": json.dumps([]),
        "revealed": json.dumps([]),
        "scores": json.dumps(initial_scores),
        "players": json.dumps(players)
    })
    # Store answer in a separate secret key so HGETALL game:<id> does not expose it
    r.set(f"game:{game_id}:answer", answer)
    r.set("current_game_id", game_id)
    # Save display names mapping globally for UI/console rendering only
    try:
        if isinstance(players, dict):
            # Expecting mapping of stable IDs -> display names, e.g. {"AI1": "AI1_guy", "AI2": "AI2_guy", "Human": "Richard"}
            r.hset("player_names", mapping=players)
    except Exception:
        # Non-fatal if we fail to store names
        pass
    return game_id

def get_current_game():
    r = get_redis()
    game_id = r.get("current_game_id")
    if not game_id:
        return None
    data = r.hgetall(f"game:{game_id}")
    # decode any JSON fields
    data["revealed"] = json.loads(data["revealed"])
    data["scores"] = json.loads(data["scores"])
    data["guessed_consonants"] = json.loads(data["guessed_consonants"])
    data["guessed_vowels"] = json.loads(data["guessed_vowels"])
    data["players"] = json.loads(data["players"])
    return data

def get_player_score(player_name: str):
    # Load scores from Redis (handle both JSON string and dict)
    try:
        import json as _json
        scores_raw = hget("scores")
        if isinstance(scores_raw, str):
            scores = _json.loads(scores_raw) if scores_raw else {}
        elif isinstance(scores_raw, dict):
            scores = scores_raw
        else:
            scores = {}
    except Exception as e:
        logger.warning("Failed to load scores: %s", e)
        scores = {}
    return int(scores.get(player_name, 0) or 0)

# --- Helpers to get/set JSON fields ---

def _get_game_id() -> Optional[str]:
    r = get_redis()
    return r.get("current_game_id")


def get_answer() -> Optional[str]:
    """Return the secret answer for the current game from the protected key."""
    r = get_redis()
    game_id = _get_game_id()
    if not game_id:
        return None
    return r.get(f"game:{game_id}:answer")


def set_answer(answer: str) -> None:
    r = get_redis()
    game_id = _get_game_id()
    if not game_id:
        return
    r.set(f"game:{game_id}:answer", answer)


def hget(field: str) -> Optional[str]:
    r = get_redis()
    game_id = _get_game_id()
    if not game_id:
        return None
    return r.hget(f"game:{game_id}", field)


def hset(field: str, value: str) -> None:
    r = get_redis()
    game_id = _get_game_id()
    if not game_id:
        return
    r.hset(f"game:{game_id}", field, value)


def hget_json(field: str, default: Any) -> Any:
    raw = hget(field)
    if raw is None:
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


def hset_json(field: str, value: Any) -> None:
    hset(field, json.dumps(value))


# --- Public API used by apps ---

# Basic field access

def get_field(field: str) -> Optional[str]:
    return hget(field)


def update_game_field(field: str, value: str) -> None:
    hset(field, value)


# Status helpers

def set_status(status: str) -> None:
    hset("status", status)


def set_current_game_status_finished() -> None:
    set_status(STATUS_FINISHED)


# Player/turn helpers (we use 'player' as the current turn)

def get_turn() -> Optional[str]:
    return hget("player")


def set_turn(player: str) -> None:
    hset("player", player)


def next_turn() -> Optional[str]:
    cur = get_turn()
    if not cur:
        nxt = PLAYER_ID_ORDER[0]
    else:
        try:
            idx = PLAYER_ID_ORDER.index(cur)
            nxt = PLAYER_ID_ORDER[(idx + 1) % len(PLAYER_ID_ORDER)]
        except ValueError:
            nxt = PLAYER_ID_ORDER[0]
    set_turn(nxt)
    return nxt


# --- Player display names (UI only) ---

def set_player_names(names: Dict[str, str]) -> None:
    """Store display names for players in a global hash 'player_names'.
    Keys should be stable player IDs (e.g., 'AI1','AI2','Human').
    """
    r = get_redis()
    if names:
        r.hset("player_names", mapping=names)


def get_player_names() -> Dict[str, str]:
    """Return the display names mapping or an empty dict if unset."""
    r = get_redis()
    try:
        data = r.hgetall("player_names") or {}
        # hgetall returns str->str already
        return dict(data)
    except Exception:
        return {}


def resolve_display_name(player_id: str) -> str:
    names = get_player_names()
    return names.get(player_id, player_id)


# Vowel helpers

def get_unguessed_vowels() -> List[str]:
    guessed_vowels: List[str] = hget_json("guessed_vowels", [])
    return [v for v in VOWELS if v not in guessed_vowels]


# Scores

def update_score(player: str, delta: int) -> None:
    scores: Dict[str, int] = hget_json("scores", {})
    old = int(scores.get(player, 0) or 0)
    scores[player] = old + int(delta)
    hset_json("scores", scores)


# Guesses

def add_guessed_letter(letter: str, is_vowel: bool) -> None:
    letter = (letter or "").upper()
    if not letter:
        return
    if is_vowel:
        lst: List[str] = hget_json("guessed_vowels", [])
        if letter not in lst:
            lst.append(letter)
        hset_json("guessed_vowels", lst)
    else:
        lst: List[str] = hget_json("guessed_consonants", [])
        if letter not in lst:
            lst.append(letter)
        hset_json("guessed_consonants", lst)


# Reveal/masking

def _mask_from_answer_and_revealed(answer: str, revealed_positions: List[int]) -> str:
    out: List[str] = []
    for idx, ch in enumerate(answer or ""):
        if ch == " ":
            out.append("*")
        elif ch.isalpha():
            out.append(ch.upper() if idx in revealed_positions else "_")
        else:
            out.append(ch)
    return " ".join(out)


def reveal_letter(letter: str) -> int:
    r = get_redis()
    game_id = _get_game_id()
    if not game_id:
        return 0
    answer = get_answer() or ""
    letter = (letter or "").upper()
    if not letter or not answer:
        return 0

    revealed: List[int] = hget_json("revealed", [])
    newly = 0
    for idx, ch in enumerate((answer or "").upper()):
        if ch == letter and idx not in revealed:
            revealed.append(idx)
            newly += 1
    if newly:
        revealed.sort()
        hset_json("revealed", revealed)
        masked = _mask_from_answer_and_revealed(answer, revealed)
        hset("puzzle", masked)
    return newly


def reveal_all() -> None:
    answer = get_answer() or ""
    revealed = [i for i, _ in enumerate(answer)]
    hset_json("revealed", revealed)
    masked = _mask_from_answer_and_revealed(answer, revealed)
    hset("puzzle", masked)


# Aggregate current game snapshot tailored for AI player

def get_current_game_for_ai_player(player_name: str) -> Optional[Dict[str, Any]]:
    r = get_redis()
    game_id = _get_game_id()
    if not game_id:
        return None
    all_data = r.hgetall(f"game:{game_id}")
    # Decode JSON fields safely
    revealed = json.loads(all_data.get("revealed", "[]"))
    guessed_consonants = json.loads(all_data.get("guessed_consonants", "[]"))
    guessed_vowels = json.loads(all_data.get("guessed_vowels", "[]"))
    guessed_letters = json.loads(all_data.get("guessed_letters", "[]"))
    scores = json.loads(all_data.get("scores", "{}"))

    data = {
        "puzzle": all_data.get("puzzle"),
        "theme": all_data.get("theme"),
        "guessed_consonants": guessed_consonants or [c for c in guessed_letters if c.upper() not in VOWELS],
        "guessed_vowels": guessed_vowels or [v for v in guessed_letters if v.upper() in VOWELS],
        "revealed": revealed,
    }
    return data
