import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig
import json


logger = logging.getLogger(__name__)

class PatFunctionConfig(FunctionBaseConfig, name="pat"):
    """
    Host setup function (Pat Sajak). Starts a new Wheel of Fortune game in Redis
    with a masked puzzle, answer, theme, and initializes turn/scores/guesses.
    """
    # Optional: allow forcing a new game even if one is active
    force_new: bool = Field(default=False, description="If true, start a new game even if one is active")


@register_function(config_type=PatFunctionConfig)
async def pat_function(
    config: PatFunctionConfig, builder: Builder
):
    # Implement your function logic here
    async def _response_fn(input_message: str) -> str:
        # Create or resume a game in Redis
        from pat.puzzle_helper import get_puzzle, mask_puzzle
        from pat.state_manager import start_new_game, get_current_game, get_field
        # Use shared helpers from AI player to ensure consistent fields
        try:
            from ai_player.state_manager import clear_turn_completed, set_turn
        except Exception:
            clear_turn_completed = None
            set_turn = None

        current_game_id = get_field("current_game_id")
        current_game_status = get_field("status")

        if (not config.force_new) and current_game_status == "active":
            current_player_turn = get_field("turn")
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
            start_new_game(masked, puzzle, theme)
            # Initialize turn to AI1 and clear the per-run guard
            if set_turn:
                try:
                    set_turn("AI1")
                except Exception:
                    pass
            if clear_turn_completed:
                try:
                    clear_turn_completed()
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
                "Initializes puzzle/answer/theme, sets turn to AI1, and clears the per-run turn guard."
            ),
        )
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up pat workflow.")
