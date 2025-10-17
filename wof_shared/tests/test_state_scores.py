import json
from wof_shared.redis_client import get_redis
from wof_shared.state import update_score, get_field


def seed_scores():
    r = get_redis()
    r.set("current_game_id", "1")
    key = "game:1"
    r.hset(key, mapping={
        "scores": json.dumps({"AI1": 100, "AI2": 0, "Human": 0}),
    })


def test_update_score_increments_player_score():
    seed_scores()
    update_score("AI1", 250)
    scores_raw = get_field("scores")
    assert scores_raw is not None
    scores = json.loads(scores_raw)
    assert scores["AI1"] == 350


def test_update_score_initializes_missing_player():
    seed_scores()
    update_score("Human", 400)
    scores_raw = get_field("scores")
    scores = json.loads(scores_raw)
    assert scores["Human"] == 400
