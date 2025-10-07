import logging

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig


logger = logging.getLogger(__name__)

class PatFunctionConfig(FunctionBaseConfig, name="pat"):
    """
    NAT function template. Please update the description.
    """
    # Add your custom configuration parameters here
    parameter: str = Field(default="default_value", description="Notional description for this parameter")


@register_function(config_type=PatFunctionConfig)
async def pat_function(
    config: PatFunctionConfig, builder: Builder
):
    # Implement your function logic here
    async def _response_fn(input_message: str) -> str:
        # Process the input_message and generate output
        from pat.puzzle_helper import get_puzzle, mask_puzzle
        from pat.state_manager import start_new_game, get_current_game

        puzzle, theme = get_puzzle()
        start_new_game(mask_puzzle(puzzle), puzzle, theme)
        print(f"Data from Current game id: {get_current_game()}")
        return f"Hello from pat workflow! You said: {input_message}."

    try:
        yield FunctionInfo.create(single_fn=_response_fn)
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up pat workflow.")
