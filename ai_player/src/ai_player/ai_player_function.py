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
        from ai_player.state_manager import get_field, set_current_game_status_finished, reveal_all

        llm_guess = None
        # Parse any provided input for optional context (player, puzzle, theme)
        try:
            data = json.loads(input_text) if input_text else {}
            player_name = data.get("player")
        except Exception:
            data = {}

        # Load the true answer from Redis if available
        true_answer = None
        try:
            true_answer = get_field("answer")
        except Exception as e:
            logger.warning("Failed to load true answer from Redis: %s", e)

        success = False
        details = "No solution available yet"

        # Attempt LLM guess using masked puzzle + theme context
        try:
            # Gather masked puzzle/theme from input or Redis
            masked_puzzle = None
            theme = None
            try:
                masked_puzzle = data.get("puzzle")
                theme = data.get("theme")
            except Exception:
                pass
            if not masked_puzzle:
                try:
                    masked_puzzle = get_field("puzzle")
                except Exception:
                    masked_puzzle = None
            if not theme:
                try:
                    theme = get_field("theme")
                except Exception:
                    theme = None

            llm = await builder.get_llm("openai_llm", wrapper_type="langchain")
            system_preamble = (
                "You are playing Wheel of Fortune. Decide exactly ONE of the following and reply accordingly:\n"
                "1) If you are confident you can solve the puzzle, reply: 'Solution: <ANSWER>' (UPPERCASE letters and spaces only).\n"
                "2) If you want to buy a vowel, reply exactly: 'I would like to buy a vowel'.\n"
                "3) If you want to spin, reply exactly: 'I would like to spin'.\n"
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
                if true_answer is None:
                    details = f"LLM proposed '{llm_guess}', but true answer unavailable"
                else:
                    norm_true = "".join(true_answer.upper().split())
                    norm_prop = "".join(str(llm_guess).upper().split())
                    # Debug: log normalization comparison
                    try:
                        logger.info(
                            "Solve step: compare guess(norm)='%s' vs answer(norm)='%s'; answer='%s'",
                            norm_prop,
                            norm_true,
                            true_answer,
                        )
                    except Exception:
                        pass
                    success = norm_true == norm_prop
                    details = (
                        f"Correct! LLM guessed '{llm_guess}'"
                        if success
                        else f"LLM guessed '{llm_guess}', but answer is '{true_answer}'"
                    )
                    # If an incorrect solve was attempted, end the turn (skip downstream)
                    if not success:
                        logger.info("Solve step: incorrect solve attempted; ending turn and skipping downstream steps.")
            elif next_action == "buy_vowel":
                details = "Chose to buy a vowel."
                success = False
            elif next_action == "spin":
                details = "Chose to spin."
                success = False
            else:
                details = "LLM did not produce a usable guess"
        except Exception as e:
            logger.warning("LLM guess failed in solve tool: %s", e)
            # Keep default details if still unset

        if success:
            # Mark game finished and reveal the full puzzle for clarity
            try:
                set_current_game_status_finished()
                reveal_all()
            except Exception as e:
                logger.warning("Failed to finalize game on correct solve: %s", e)

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
        # Initialize history with this step
        try:
            solve_output["history"] = [{k: v for k, v in solve_output.items() if k != "history"}]
        except Exception:
            pass
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



class BuyVowelIfEnoughMoneyConfig(FunctionBaseConfig, name="buy_vowel_if_enough_money"):
    pass

@register_function(config_type=BuyVowelIfEnoughMoneyConfig)
async def buy_vowel_if_enough_money(
    config: BuyVowelIfEnoughMoneyConfig, builder: Builder
):
    # Implement your function logic here
    async def _buy_vowel_if_enough_money(solve_output: str) -> str:
        # Accept a single text input, parse JSON if present, and check funds from Redis
        from ai_player.state_manager import (
            get_unguessed_vowels,
            get_field,
            add_guessed_letter,
            reveal_letter,
            update_score
        )

        player_name = "AI1"
        try:
            data = json.loads(solve_output) if solve_output else {}
            player_name = data.get("player") or data.get("turn") or player_name
        except Exception:
            data = {}

        # Respect next_action from solve step
        next_action = (data.get("next_action") or "").strip().lower() if isinstance(data, dict) else None

        # Sequential skip: if the solve step already succeeded (or asked to skip next), no-op
        try:
            if bool(data.get("skip_next")) or (data.get("action") == "solve" and bool(data.get("success"))):
                skipped_output = {
                    "action": "buy_vowel",
                    "success": True,
                    "skipped": True,
                    "details": "Skipped because puzzle was already solved.",
                    "player": player_name,
                    "next_action": next_action or "",
                    "updates": {
                        "player": player_name,
                        "puzzle": get_field("puzzle"),
                        "scores": get_field("scores"),
                    },
                    # Propagate skip so spin is also skipped
                    "skip_next": True,
                }
                # History aggregation
                try:
                    hist = data.get("history") or []
                    hist.append({k: v for k, v in skipped_output.items() if k != "history"})
                    skipped_output["history"] = hist
                except Exception:
                    pass
                return json.dumps(skipped_output)
            # If the agent chose to spin, skip buying a vowel but let spin proceed (skip_next False)
            if next_action == "spin":
                skipped_output = {
                    "action": "buy_vowel",
                    "success": True,
                    "skipped": True,
                    "details": "Skipped because agent chose to spin.",
                    "player": player_name,
                    "next_action": next_action,
                    "updates": {
                        "player": player_name,
                        "puzzle": get_field("puzzle"),
                        "scores": get_field("scores"),
                    },
                    # Do not skip next so spin can run
                    "skip_next": False,
                }
                return json.dumps(skipped_output)
        except Exception:
            pass

        # Load scores from Redis (handle both JSON string and dict)
        try:
            import json as _json
            scores_raw = get_field("scores")
            if isinstance(scores_raw, str):
                scores = _json.loads(scores_raw) if scores_raw else {}
            elif isinstance(scores_raw, dict):
                scores = scores_raw
            else:
                scores = {}
        except Exception as e:
            logger.warning("Failed to load scores: %s", e)
            scores = {}

        current_money = int(scores.get(player_name, 0) or 0)
        cost = 250
        remaining_vowels = []
        try:
            remaining_vowels = get_unguessed_vowels()
        except Exception as e:
            logger.warning("Failed to load remaining vowels: %s", e)

        if current_money < cost:
            output = {
                "action": "buy_vowel",
                "success": False,
                "skipped": False,
                "details": f"Insufficient funds: {player_name} has {current_money}, needs {cost}",
                "player": player_name,
                "next_action": next_action or "buy_vowel",
                "updates": {
                    "player": player_name,
                    "puzzle": get_field("puzzle"),
                    "remaining_vowels": remaining_vowels,
                },
            }
            # History aggregation
            try:
                hist = data.get("history") or []
                hist.append({k: v for k, v in output.items() if k != "history"})
                output["history"] = hist
            except Exception:
                pass
            # History aggregation
            try:
                hist = data.get("history") or []
                hist.append({k: v for k, v in output.items() if k != "history"})
                output["history"] = hist
            except Exception:
                pass
            return json.dumps(output)

        # Choose a vowel to buy (simple heuristic: first available)
        chosen_vowel = remaining_vowels[0] if remaining_vowels else None
        details = (
            f"{player_name} will buy vowel '{chosen_vowel}' for {cost}"
            if chosen_vowel is not None
            else "No vowels remaining to buy"
        )

        occurrences = 0
        if chosen_vowel is not None:
            try:
                # Deduct cost (Wheel rules: vowels cost money and typically do not add winnings)
                update_score(player_name, -cost)
                # Reveal vowel occurrences and record guess
                occurrences = reveal_letter(chosen_vowel)
                add_guessed_letter(chosen_vowel, is_vowel=True)
            except Exception as e:
                logger.warning("Failed to apply vowel purchase updates: %s", e)

        # Attempt to provide updated snapshots for puzzle and scores
        try:
            import json as _json
            scores_snapshot = get_field("scores")
            try:
                scores_snapshot = _json.loads(scores_snapshot) if scores_snapshot else {}
            except Exception:
                pass
        except Exception:
            scores_snapshot = None

        # Compose final answer to copy verbatim
        if chosen_vowel is not None:
            fa = f"Final Answer: {player_name} bought vowel '{chosen_vowel}' for {cost}; occurrences={occurrences}."
        else:
            fa = f"Final Answer: No vowels remaining to buy."
        buy_vowel_output = {
            "action": "buy_vowel",
            "success": chosen_vowel is not None,
            "skipped": False,
            "details": details + (f"; occurrences={occurrences}" if chosen_vowel else ""),
            "player": player_name,
            "next_action": "buy_vowel",
            "updates": {
                "player": player_name,
                "chosen_vowel": chosen_vowel,
                "cost": cost,
                "occurrences": occurrences,
                "remaining_vowels": remaining_vowels,
                "money": current_money - cost if chosen_vowel is not None else current_money,
                "puzzle": get_field("puzzle"),
                "scores": scores_snapshot,
            },
            # If the purchase succeeded, skip spinning
            "skip_next": bool(chosen_vowel is not None),
            "final_answer": fa,
        }
        # History aggregation
        try:
            hist = data.get("history") or []
            hist.append({k: v for k, v in buy_vowel_output.items() if k != "history"})
            buy_vowel_output["history"] = hist
        except Exception:
            pass
        return json.dumps(buy_vowel_output)

    try:
        yield FunctionInfo.from_fn(
            _buy_vowel_if_enough_money,
            description=(
                "If the player has enough money, propose and buy a vowel; returns structured JSON with choice, occurrences, and updated state. "
                "Outputs include 'success', 'skipped', and 'skip_next' to support sequential execution."
            )
        )
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up buy_vowel workflow.")



class SpinWheelAndGuessConsonantConfig(FunctionBaseConfig, name="spin_wheel_and_guess_consonant"):
    pass

@register_function(config_type=SpinWheelAndGuessConsonantConfig)
async def spin_wheel_and_guess_consonant(
    config: SpinWheelAndGuessConsonantConfig, builder: Builder
):
    # Implement your function logic here
    async def _spin_wheel_and_guess_consonant(buy_vowel_output: str) -> str:
        # Accept a single text input, parse JSON if present, and mutate Redis state accordingly
        from ai_player.state_manager import (
            get_current_game_for_ai_player,
            get_field,
            add_guessed_letter,
            reveal_letter,
            update_score,
        )

        player_name = "AI1"
        try:
            data = json.loads(buy_vowel_output) if buy_vowel_output else {}
            player_name = data.get("player") or data.get("turn") or player_name
        except Exception:
            data = {}

        next_action = (data.get("next_action") or "").strip().lower() if isinstance(data, dict) else None

        # Sequential skip: if previous step signaled skip or buy_vowel succeeded, no-op
        try:
            if bool(data.get("skip_next")):
                skipped_output = {
                    "action": "spin",
                    "success": True,
                    "skipped": True,
                    "details": "Skipped because a previous step requested skip (turn ended).",
                    "player": player_name,
                    "next_action": next_action or "",
                    "updates": {
                        "player": player_name,
                        "puzzle": get_field("puzzle"),
                        "scores": get_field("scores"),
                    },
                }
                return json.dumps(skipped_output)
            if (data.get("action") == "buy_vowel" and bool(data.get("success"))):
                skipped_output = {
                    "action": "spin",
                    "success": True,
                    "skipped": True,
                    "details": "Skipped because a vowel was just bought.",
                    "player": player_name,
                    "next_action": next_action or "buy_vowel",
                    "updates": {
                        "player": player_name,
                        "puzzle": get_field("puzzle"),
                        "scores": get_field("scores"),
                    },
                }
                try:
                    hist = data.get("history") or []
                    hist.append({k: v for k, v in skipped_output.items() if k != "history"})
                    skipped_output["history"] = hist
                except Exception:
                    pass
                return json.dumps(skipped_output)
        except Exception:
            pass

        # 1) Spin the wheel
        wedge = None
        try:
            from ai_player.wheel import spin_wheel
            wedge = spin_wheel()
        except Exception as e:
            logger.warning("spin_wheel not available or failed: %s", e)

        if wedge is None:
            output = {
                "action": "spin",
                "success": False,
                "skipped": False,
                "details": "Spin failed (no wheel)",
                "player": player_name,
                "next_action": "spin",
                "updates": {"player": player_name},
                "final_answer": "Final Answer: Spin failed (no wheel).",
            }
            return json.dumps(output)

        # Normalize wedge
        wedge_str = str(wedge).strip().upper()
        amount = None
        try:
            amount = int(wedge_str)
        except ValueError:
            amount = None

        # Load current state and letters
        state = get_current_game_for_ai_player(player_name) or {}
        guessed_cons = set((state.get("guessed_consonants") or []))
        guessed_vowels = set((state.get("guessed_vowels") or []))

        vowels = set(list("AEIOU"))
        alphabet = set(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        remaining_cons = [
            c for c in (
                [
                    "R","S","T","L","N","D","H","M","C","B","P",
                    "G","Y","K","F","W","V","X","Z","J","Q",
                ]
            )
            if c not in vowels and c not in guessed_cons
        ]

        # Handle special wedges
        details = f"{player_name} spun the wheel: {wedge_str}"
        occurrences = 0
        chosen_letter = None

        if "BANKRUPT" in wedge_str:
            # Set player's score to 0 by applying negative delta of current score
            try:
                import json as _json
                scores_raw = get_field("scores")
                scores = _json.loads(scores_raw) if scores_raw else {}
                current_money = int(scores.get(player_name, 0) or 0)
                if current_money:
                    update_score(player_name, -current_money)
            except Exception as e:
                logger.warning("Failed to apply BANKRUPT: %s", e)
            output = {
                "action": "spin",
                "success": True,
                "skipped": False,
                "details": details + "; BANKRUPT -> score set to 0",
                "player": player_name,
                "next_action": "spin",
                "updates": {
                    "player": player_name,
                    "wheel_wedge": wedge,
                    "chosen_letter": None,
                    "occurrences": 0,
                    "puzzle": get_field("puzzle"),
                    "scores": get_field("scores"),
                },
                "final_answer": "Final Answer: BANKRUPT – score set to 0.",
            }
            return json.dumps(output)

        if "LOSE" in wedge_str and "TURN" in wedge_str:
            output = {
                "action": "spin",
                "success": True,
                "skipped": False,
                "details": details + "; Lose a Turn",
                "player": player_name,
                "next_action": "spin",
                "updates": {
                    "player": player_name,
                    "wheel_wedge": wedge,
                    "chosen_letter": None,
                    "occurrences": 0,
                    "puzzle": get_field("puzzle"),
                    "scores": get_field("scores"),
                },
                "final_answer": "Final Answer: Lose a Turn.",
            }
            return json.dumps(output)

        # Monetary wedge or free play: attempt a consonant
        if not remaining_cons:
            details += "; no consonants remaining"
        else:
            chosen_letter = remaining_cons[0]
            # Reveal and update
            try:
                occurrences = reveal_letter(chosen_letter)
                add_guessed_letter(chosen_letter, is_vowel=False)
                if amount is not None and occurrences > 0:
                    update_score(player_name, amount * occurrences)
            except Exception as e:
                logger.warning("Failed to apply letter updates: %s", e)

        # Build output snapshot
        try:
            import json as _json
            scores_snapshot = get_field("scores")
            try:
                # Normalize to JSON object for convenience
                scores_snapshot = _json.loads(scores_snapshot) if scores_snapshot else {}
            except Exception:
                pass
        except Exception:
            scores_snapshot = None

        # Compose a deterministic final answer line to copy verbatim
        if chosen_letter:
            if occurrences > 0:
                final_ans = f"Final Answer: {player_name} spun {wedge_str} and guessed '{chosen_letter}', occurrences={occurrences}, amount={amount}."
            else:
                final_ans = f"Final Answer: {player_name} spun {wedge_str} and guessed '{chosen_letter}', but it is not in the puzzle."
        else:
            final_ans = f"Final Answer: {player_name} spun {wedge_str}."

        output = {
            "action": "spin",
            "success": True,
            "skipped": False,
            "details": details + (
                f"; guessed '{chosen_letter}', occurrences={occurrences}, amount={amount}"
                if chosen_letter else ""
            ),
            "player": player_name,
            "next_action": "spin",
            "updates": {
                "player": player_name,
                "wheel_wedge": wedge,
                "chosen_letter": chosen_letter,
                "occurrences": occurrences,
                "amount": amount,
                "puzzle": get_field("puzzle"),
                "scores": scores_snapshot,
            },
            "final_answer": final_ans,
        }
        return json.dumps(output)

    try:
        yield FunctionInfo.from_fn(
            _spin_wheel_and_guess_consonant,
            description=(
                "Spin the wheel and propose an unguessed consonant; returns structured JSON with spin result and a state snapshot. "
            )
        )
    except GeneratorExit:
        logger.warning("Function exited early!")
    finally:
        logger.info("Cleaning up spin_wheel workflow.")
