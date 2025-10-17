import logging
import json

from pydantic import Field

from nat.builder.builder import Builder
from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

logger = logging.getLogger(__name__)


def choose_vowel_heuristic(masked: str, remaining):
    """
    Pattern-aware vowel chooser used when buying a vowel.
    - Uses English frequency priors.
    - Adds bonuses for simple masked-puzzle patterns.
    - Restricts to remaining (unguessed) vowels.
    Returns best uppercase vowel or None.
    """
    import re as _re

    if not remaining:
        return None

    masked = (masked or "")
    norm = masked.upper()

    # Frequency priors (rough English/puzzle heuristic)
    priors = {"E": 12.0, "A": 9.0, "O": 8.0, "I": 7.0, "U": 3.0}

    # Initialize scores from priors, but only for remaining vowels
    scores = {v.upper(): priors.get(v.upper(), 0.0) for v in remaining}

    # Small reinforcement: if vowel already visible in puzzle, it might have more instances
    for v in list(scores.keys()):
        try:
            scores[v] += norm.count(v) * 0.75
        except Exception:
            pass

    # Pattern bonuses
    # 1) Unknown before 'VER' strongly suggests 'OVER'
    try:
        if _re.search(r"(?:\*|_)VER", norm):
            if "O" in scores:
                scores["O"] += 6.0
    except Exception:
        pass

    # 2) 'Q' before unknown strongly suggests 'U'
    try:
        if _re.search(r"Q(?:\*|_)", norm):
            if "U" in scores:
                scores["U"] += 10.0
    except Exception:
        pass

    # 3) 'TH' before unknown often forms 'THE'
    try:
        if _re.search(r"TH(?:\*|_)", norm):
            if "E" in scores:
                scores["E"] += 4.0
    except Exception:
        pass

    # 4) Unknown followed by 'ING' often indicates existing I; if I not revealed, give it a nudge
    try:
        if _re.search(r"(?:\*|_)ING", norm):
            if "I" in scores:
                scores["I"] += 2.0
    except Exception:
        pass

    # Deterministic tie-breaker using common preference order
    pref = ["E", "A", "O", "I", "U"]
    pref = [v for v in pref if v in scores]

    best_vowel = None
    best_score = float("-inf")
    for v in pref:
        sc = scores.get(v, float("-inf"))
        if sc > best_score:
            best_score = sc
            best_vowel = v
    if best_vowel is None and scores:
        best_vowel = max(scores.items(), key=lambda kv: kv[1])[0]
    return best_vowel


class BuyVowelIfEnoughMoneyConfig(FunctionBaseConfig, name="buy_vowel_if_enough_money"):
    vowel_strategy: str = Field(
        default="heuristic",
        description="Strategy to choose vowel: 'heuristic' (default) or 'random'",
    )
    randomize_vowel_ties: bool = Field(
        default=False,
        description="If true, when multiple vowels tie at top score, pick randomly among them.",
    )

@register_function(config_type=BuyVowelIfEnoughMoneyConfig)
async def buy_vowel_if_enough_money(
    config: BuyVowelIfEnoughMoneyConfig, builder: Builder
):
    # Implement your function logic here
    async def _buy_vowel_if_enough_money(solve_output: str) -> str:
        # Accept a single text input, parse JSON if present, and check funds from Redis
        from wof_shared.state import (
            get_unguessed_vowels,
            get_field,
            add_guessed_letter,
            reveal_letter,
            update_score,
            get_player_score,
        )

        try:
            data = json.loads(solve_output) if solve_output else {}
            player_name = data.get("player")
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
                    "details": "Skipped because puzzle solution was attempted.",
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

        current_money = get_player_score(player_name)
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

        # Load current masked puzzle
        try:
            masked_puzzle = data.get("puzzle") if isinstance(data, dict) else None
        except Exception:
            masked_puzzle = None
        if not masked_puzzle:
            try:
                masked_puzzle = get_field("puzzle")
            except Exception:
                masked_puzzle = None

        # Choose a vowel to buy according to configured strategy
        remaining_upper = [v.upper() for v in (remaining_vowels or [])]
        if config.vowel_strategy == "random":
            import random as _random
            chosen_vowel = _random.choice(remaining_upper) if remaining_upper else None
        else:
            # Heuristic strategy (default)
            chosen_vowel = choose_vowel_heuristic(masked_puzzle or "", remaining_upper)

        # Compose details
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
