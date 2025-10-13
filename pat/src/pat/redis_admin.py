import redis
import sys

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

def set_current_game_status_finished():
    game_id = r.get("current_game_id")
    r.hset(f"game:{game_id}", "status", "finished")

def clear_turn_completed():
    """Clear the per-run guard that prevents multiple actions in one turn."""
    game_id = r.get("current_game_id")
    if not game_id:
        print("No current_game_id set")
        return
    r.hdel(f"game:{game_id}", "turn_completed")
    print(f"Cleared turn_completed on game:{game_id}")

def set_turn(player: str):
    """Set the current player's turn (e.g., AI1, AI2, Rich)."""
    game_id = r.get("current_game_id")
    if not game_id:
        print("No current_game_id set")
        return
    r.hset(f"game:{game_id}", "turn", player)
    print(f"Set turn to {player} on game:{game_id}")

def hello_redis():
    r.set("msg:hello", "Hello Redis!!!")
    msg = r.get("msg:hello")
    print(msg)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == "finished":
            set_current_game_status_finished()
        elif sys.argv[1] == "clear_turn":
            clear_turn_completed()
        elif sys.argv[1] == "set_turn" and len(sys.argv) > 2:
            set_turn(sys.argv[2])
        elif sys.argv[1] == "hello":
            hello_redis()
