import logging
import json

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


class SolvesPuzzleIfKnowsTheAnswerConfig(FunctionBaseConfig, name="solve_puzzle_if_knows_answer"):
    pass

@register_function(config_type=SolvesPuzzleIfKnowsTheAnswerConfig)
async def solve_puzzle_if_knows_answer(
    config: SolvesPuzzleIfKnowsTheAnswerConfig, builder: Builder
):
    # Implement your function logic here
    async def _solve_puzzle_if_knows_answer(input_text: str) -> str:
        # Accept a single text input, parse JSON if present, and evaluate against Redis answer
        from wof_shared.state import (
            get_field,
            set_current_game_status_finished,
            reveal_all,
            get_answer,
            get_player_score,
            resolve_display_name,
            update_game_field,
        )

        llm_guess = None
        # Parse any provided input for optional context (player, puzzle, theme)
        try:
            data = json.loads(input_text) if input_text else {}
            player_name = data.get("player")
            masked_puzzle = data.get("puzzle")
            theme = data.get("theme")
        except Exception:
            data = {}

        success = False
        details = "No solution available yet"

        # Attempt LLM guess using masked puzzle + theme context
        try:

            llm = await builder.get_llm("openai_llm", wrapper_type="langchain")
            current_money = get_player_score(player_name)
            if current_money >= 250:
                system_preamble = (
                    "You are playing Wheel of Fortune and have enough money to buy a vowel IF it makes sense to do so. Decide exactly ONE of the following and reply accordingly:\n"
                    "1) Highest priority is to solve the puzzle but only if you are confident that you can solve the puzzle, reply: 'Solution: <ANSWER>' (UPPERCASE letters and spaces only).\n"
                    "2) If you want to buy a vowel and it makes sense to do so, reply exactly: 'I would like to buy a vowel'.\n"
                    "3) If you want to spin, reply exactly: 'I would like to spin'.\n"
                    "Do not add any extra commentary."
                )
            else:
                system_preamble = (
                    "You are playing Wheel of Fortune and do not have enough money to buy a vowel. Decide exactly ONE of the following and reply accordingly:\n"
                    "1) Highest priority is to solve the puzzle but only if you are confident that you can solve the puzzle, reply: 'Solution: <ANSWER>' (UPPERCASE letters and spaces only).\n"
                    "2) If you want to spin, reply exactly: 'I would like to spin'.\n"
                    "Do not add any extra commentary."
                )
            # Replace '*' with spaces to reduce ambiguity for the model
            masked_for_prompt = (masked_puzzle or "").replace("*", " ")
            prompt = (
                f"{system_preamble}\n"
                f"Masked Puzzle: {masked_for_prompt}\n"
                f"Theme: {theme}\n"
                f"Constraints: If choosing Solution, return 'Solution: ' followed by only UPPERCASE letters and spaces."
            )
            llm_output = await llm.ainvoke(prompt)
            # Debug: log raw LLM output for troubleshooting
            try:
                logger.info("Solve step: LLM raw output: %r", llm_output)
            except Exception:
                pass
            try:
                raw_reply = getattr(llm_output, "content", None) or (
                    llm_output if isinstance(llm_output, str) else str(llm_output)
                )
            except Exception:
                raw_reply = str(llm_output)

            # Cleanup proposed solution: keep letters and spaces only, uppercase
            import re as _re
            next_action = None
            llm_guess = None
            raw_lower = (raw_reply or "").strip().lower()
            # Parse intent
            if raw_lower.startswith("solution:"):
                next_action = "solve"
                # Extract after 'Solution:' and clean
                _ans = (raw_reply.split(":", 1)[1] if ":" in (raw_reply or "") else raw_reply)
                llm_guess = _re.sub(r"[^A-Za-z ]+", "", _ans or "").upper().strip()
            elif "buy a vowel" in raw_lower:
                next_action = "buy_vowel"
            elif "spin" in raw_lower:
                next_action = "spin"
            else:
                # Fallback: treat as a direct guess answer
                next_action = "solve"
                llm_guess = _re.sub(r"[^A-Za-z ]+", "", raw_reply or "").upper().strip()
            # Debug: log cleaned guess and context
            try:
                logger.info(
                    "Solve step: parsed next_action='%s', cleaned guess='%s', masked_puzzle='%s', theme='%s'",
                    next_action,
                    llm_guess,
                    masked_puzzle,
                    theme,
                )
            except Exception:
                pass

            if next_action == "solve" and llm_guess:
                true_answer = get_answer()
                # Normalize both strings by removing all non-letters so symbols like '&' don't cause mismatches.
                import re as _re
                norm_true = "".join(_re.sub(r"[^A-Za-z ]+", "", (true_answer or "")).upper().split())
                norm_prop = "".join(_re.sub(r"[^A-Za-z ]+", "", str(llm_guess or "")).upper().split())
                # Debug: log normalization comparison
                success = norm_true == norm_prop
                details = (
                    f"Correct! LLM guessed '{llm_guess}'"
                    if success
                    else f"LLM guessed '{llm_guess}', but answer is '{true_answer}'"
                )
                # If an incorrect solve was attempted, end the turn (skip downstream)
                if not success:
                    logger.info("Solve step: incorrect solve attempted; ending turn and skipping downstream steps.")
                    details = "LLM did not produce a usable guess"

            if success:
                # Mark game finished, record the winner display name, and reveal the puzzle
                try:
                    # Determine the winning player's display name, preferring provided player_name
                    try:
                        current_player_id = player_name or (get_field("player") or "")
                    except Exception:
                        current_player_id = player_name or ""
                    winner_name = resolve_display_name(current_player_id)
                    update_game_field("winner", winner_name)
                except Exception as e:
                    logger.warning("Failed to set winner on correct solve: %s", e)
                try:
                    set_current_game_status_finished()
                    reveal_all()
                except Exception as e:
                    logger.warning("Failed to finalize game on correct solve: %s", e)
        except Exception as e:
            logger.warning("Failed to solve puzzle: %s", e)
            success = False

        try:
            import json as _json
            scores_snapshot = get_field("scores")
            try:
                scores_snapshot = _json.loads(scores_snapshot) if scores_snapshot else {}
            except Exception:
                pass
        except Exception:
            scores_snapshot = None

        # Compose final answer for solve attempt
        if success and llm_guess:
            fa = f"Final Answer: Solved '{llm_guess}'."
        elif next_action == "solve" and llm_guess:
            fa = f"Final Answer: LLM proposed '{llm_guess}' but it was incorrect."
        elif next_action == "buy_vowel":
            fa = "Final Answer: I would like to buy a vowel."
        elif next_action == "spin":
            fa = "Final Answer: I would like to spin."
        else:
            fa = "Final Answer: No LLM solution produced."
        solve_output = {
            "action": "solve",
            "success": success,
            "details": details,
            # Top-level fields to make downstream steps simpler
            "player": player_name,
            "llm_guess": llm_guess,
            "next_action": next_action,
            "updates": {
                "player": player_name,
                "llm_guess": llm_guess,
                "answer": true_answer if success else None,
                "status": get_field("status"),
                "puzzle": get_field("puzzle"),
                "scores": scores_snapshot,
            },
            # Hint for sequential_executor: when True, downstream steps should no-op/skip
            # End-turn if solved correctly OR if an incorrect solve was attempted
            "skip_next": bool(success) or (next_action == "solve" and not success and llm_guess is not None),
            "final_answer": fa,
        }
        return json.dumps(solve_output)

    try:
        yield FunctionInfo.from_fn(
            _solve_puzzle_if_knows_answer,
            description=(
                "Attempt to solve the puzzle by inferring a solution with the LLM using the masked puzzle and theme; compares with Redis answer, updates status/puzzle on success, and returns structured JSON. "
                "Outputs include 'success' and 'skip_next' to support sequential execution."
            )
        )
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up solve_puzzle workflow.")
