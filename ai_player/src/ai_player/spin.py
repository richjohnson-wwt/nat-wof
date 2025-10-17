import logging
import json

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)



async def choose_consonant(builder: Builder, masked: str, remaining):
    print(f"=================Remaining consonants: {remaining}")
    llm = await builder.get_llm("openai_llm", wrapper_type="langchain")
    # Normalize masked puzzle for readability
    masked_for_prompt = (masked or "").replace("*", " ")
    # Provide valid choices in a simple, copyable form
    remaining_upper = [str(c).upper() for c in (remaining or [])]
    valid_choices_str = " | ".join(remaining_upper)

    system_preamble = (
        "You are playing Wheel of Fortune and have just completed your spin. You did not bankrupt or lose turn so it is time to guess a consonant.\n"
        "Given the masked puzzle and the remaining consonants, choose the best consonant.\n"
        "YOU MUST follow these rules strictly:\n"
        "- Choose EXACTLY ONE letter from the list of valid choices.\n"
        "- Do NOT choose any letter that is not in the list of valid choices.\n"
        "- Respond in this exact format: 'Letter: <LETTER>' where <LETTER> is one of the valid choices.\n"
        "- No extra words or punctuation."
    )
    prompt = (
        f"{system_preamble}\n\n"
        f"Masked Puzzle: {masked_for_prompt}\n"
        f"Remaining Consonants (valid choices only): {valid_choices_str}\n\n"
        f"Examples:\n"
        f"- If you choose S, respond: 'Letter: S'\n"
        f"- If you choose M, respond: 'Letter: M'\n\n"
        f"Return only one line with the exact format."
    )
    llm_output = await llm.ainvoke(prompt)
    raw = None
    try:
        raw = getattr(llm_output, "content", None) or (
            llm_output if isinstance(llm_output, str) else str(llm_output)
        )
    except Exception:
        raw = str(llm_output)

    # Parse "Letter: X" robustly
    chosen = None
    try:
        part = (raw or "").strip().split(":", 1)
        if len(part) == 2:
            chosen = part[1].strip().upper()
            # Keep only the first A-Z char in case the model adds junk
            import re as _re
            m = _re.search(r"[A-Z]", chosen)
            if m:
                chosen = m.group(0)
    except Exception:
        chosen = None

    # Validate against remaining; fallback if invalid
    if not chosen or chosen not in set(remaining_upper):
        # Deterministic fallback by consonant preference order
        pref = [
            "R","S","T","L","N","D","H","M","C","B","P",
            "G","Y","K","F","W","V","X","Z","J","Q",
        ]
        for c in pref:
            if c in remaining_upper:
                return c
        return remaining_upper[0] if remaining_upper else None

    return chosen

class SpinWheelAndGuessConsonantConfig(FunctionBaseConfig, name="spin_wheel_and_guess_consonant"):
    pass

@register_function(config_type=SpinWheelAndGuessConsonantConfig)
async def spin_wheel_and_guess_consonant(
    config: SpinWheelAndGuessConsonantConfig, builder: Builder
):
    # Implement your function logic here
    async def _spin_wheel_and_guess_consonant(buy_vowel_output: str) -> str:
        # Accept a single text input, parse JSON if present, and mutate Redis state accordingly
        from wof_shared.state import (
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
                if data.get("chosen_vowel") is not None:
                    skipped_output = {
                        "action": "spin",
                        "success": True,
                        "skipped": True,
                        "details": data.get("details", ""),
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
                else:
                    skipped_output = {
                        "action": "spin",
                        "success": True,
                        "skipped": True,
                        "details": data.get("details", ""),
                        "player": player_name,
                        "next_action": next_action or "",
                        "updates": {
                            "player": player_name,
                            "puzzle": get_field("puzzle"),
                            "scores": get_field("scores"),
                        },
                    }
                    return json.dumps(skipped_output)
        except Exception:
            pass

        # 1) Spin the wheel
        wedge = None
        try:
            from wof_shared.wheel import spin_wheel
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
        remaining_cons = [
            c for c in (
                [
                    "R","S","T","L","N","D","H","M","C","B","P",
                    "G","Y","K","F","W","V","X","Z","J","Q",
                ]
            )
            if c not in guessed_cons
        ]

        # Handle special wedges
        details = f"{player_name} spun the wheel: {wedge_str}"
        occurrences = 0
        chosen_letter = None

        # Load current masked puzzle for consonant choice
        try:
            masked_puzzle = get_field("puzzle")
        except Exception:
            masked_puzzle = ""

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
            # chosen_letter = remaining_cons[0]
            chosen_letter = await choose_consonant(builder, masked_puzzle, remaining_cons)
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
