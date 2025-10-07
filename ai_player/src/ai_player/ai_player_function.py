import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


class AiPlayerFunctionConfig(FunctionBaseConfig, name="ai_player"):
    """
    NAT function template. Please update the description.
    """
    # Add your custom configuration parameters here
    parameter: str = Field(default="default_value", description="Notional description for this parameter")


@register_function(config_type=AiPlayerFunctionConfig)
async def ai_player_function(
    config: AiPlayerFunctionConfig, builder: Builder
):
    # Implement your function logic here
    async def _response_fn(player_name: str) -> str:
        # Process the input_message and generate output
        from ai_player.wheel import spin_wheel
        from ai_player.state_manager import get_current_game_for_ai_player
        result = spin_wheel()
        game_data = get_current_game_for_ai_player(player_name)
        print(f"Data from Current game id: {game_data}")
        output_message = f"{player_name} is spinning the wheel! Result: {result}"
        return output_message

    try:
        yield FunctionInfo.create(single_fn=_response_fn)
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up ai_player workflow.")
