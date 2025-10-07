import redis, json

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

def start_new_game(puzzle, answer, theme):
    game_id = r.incr("game_id_counter")
    key = f"game:{game_id}"
    r.hset(key, mapping={
        "puzzle": puzzle,
        "answer": answer,
        "theme": theme,
        "turn": "AI1",
        "status": "active",
        "guessed_letters": json.dumps([]),
        "revealed": json.dumps([]),
        "scores": json.dumps({"AI1": 0, "AI2": 0, "Rich": 0})
    })
    r.set("current_game_id", game_id)
    return game_id

def get_current_game():
    game_id = r.get("current_game_id")
    if not game_id:
        return None
    data = r.hgetall(f"game:{game_id}")
    # decode any JSON fields
    data["revealed"] = json.loads(data["revealed"])
    data["scores"] = json.loads(data["scores"])
    return data

def update_game_field(field, value):
    game_id = r.get("current_game_id")
    r.hset(f"game:{game_id}", field, value)

def end_current_game():
    game_id = r.get("current_game_id")
    r.hset(f"game:{game_id}", "status", "finished")
