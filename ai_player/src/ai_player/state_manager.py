import redis, json

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def get_current_game_for_ai_player(player_name):
    game_id = r.get("current_game_id")
    if not game_id:
        return None
    all_data = r.hgetall(f"game:{game_id}")
    # Safely decode JSON-encoded fields and handle missing keys
    revealed = json.loads(all_data.get("revealed", "[]"))
    guessed_letters = json.loads(all_data.get("guessed_letters", "[]"))
    scores = json.loads(all_data.get("scores", "{}"))
    score = scores.get(player_name, 0)

    data = {
        "puzzle": all_data.get("puzzle"),
        "theme": all_data.get("theme"),
        "guessed_letters": guessed_letters,
        "score": score,
        "revealed": revealed,
    }
    return data
