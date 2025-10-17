import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig
from typing import Optional, Dict
import json


logger = logging.getLogger(__name__)

class PatFunctionConfig(FunctionBaseConfig, name="pat"):
    """
    Host setup function (Pat Sajak). Starts a new Wheel of Fortune game in Redis
    with a masked puzzle, answer, theme, and initializes player/scores/guesses.
    """
    # Optional: allow forcing a new game even if one is active
    force_new: bool = Field(default=False, description="If true, start a new game even if one is active")
    players: Optional[Dict[str, str]] = Field(
        default={"ai1": "AI1", "ai2": "AI2", "human": "Rich"}, description="Optional mapping of player names to AI and Human player names"
    )

@register_function(config_type=PatFunctionConfig)
async def pat_function(
    config: PatFunctionConfig, builder: Builder
):
    # Implement your function logic here
    async def _response_fn(input_message: str) -> str:
        # Create or resume a game in Redis
        from pat.puzzle_helper import get_puzzle, mask_puzzle
        from wof_shared.state import start_new_game, get_current_game, get_field
        # Use shared helpers from AI player to ensure consistent fields
        try:
            from wof_shared.state import set_turn
        except Exception:
            set_turn = None

        if config.players:
            print("Players: ", config.players)


        current_game_id = get_field("current_game_id")
        current_game_status = get_field("status")

        if (not config.force_new) and current_game_status == "active":
            current_player_turn = get_field("player")
            output = {
                "action": "start_or_resume",
                "success": True,
                "details": f"Game is already active. Current player turn: {current_player_turn}",
                "updates": {
                    "game_id": current_game_id,
                    "status": current_game_status,
                    "player": current_player_turn,
                },
            }
            return json.dumps(output)
        else:
            # Start a fresh game
            puzzle, theme = get_puzzle()
            masked = mask_puzzle(puzzle)
            # Build display-name mapping from config for UI only; keep stable IDs in state
            try:
                cfg_players = config.players or {}
            except Exception:
                cfg_players = {}
            players = {
                "AI1": cfg_players.get("ai1") or "AI1",
                "AI2": cfg_players.get("ai2") or "AI2",
                "Human": cfg_players.get("human") or "Human",
            }
            start_new_game(masked, puzzle, theme, players)
            # Initialize player to AI1 and clear the per-run guard
            if set_turn:
                try:
                    set_turn("AI1")
                except Exception:
                    pass

            state = get_current_game()
            output = {
                "action": "start_new_game",
                "success": True,
                "details": "New game started by host (Pat)",
                "updates": state,
            }
            return json.dumps(output)

    try:
        yield FunctionInfo.from_fn(
            _response_fn,
            description=(
                "Host function to start a new Wheel of Fortune game in Redis. "
                "Initializes puzzle/answer/theme, sets player to AI1, and clears the per-run turn guard."
            ),
        )
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up pat workflow.")
