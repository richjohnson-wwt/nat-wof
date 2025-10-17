import os
import sys
import pytest

# Ensure we can import the ai_player src module
CURRENT_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from ai_player.buy_vowel import choose_vowel_heuristic  # noqa: E402


def test_over_pattern_prefers_o():
    masked = "___*_VER*____"
    remaining = list("AEIOU")
    chosen = choose_vowel_heuristic(masked, remaining)
    assert chosen == "O"


def test_q_requires_u_when_available():
    masked = "Q*_XXXX"
    remaining = list("AEIOU")
    chosen = choose_vowel_heuristic(masked, remaining)
    assert chosen == "U"


def test_th_suggests_e():
    masked = "TH_"
    remaining = list("AEIOU")
    chosen = choose_vowel_heuristic(masked, remaining)
    assert chosen == "E"


def test_ing_nudges_i_when_e_not_available():
    masked = "_ING"
    remaining = list("AIOU")  # Exclude E so the I nudge can take effect
    chosen = choose_vowel_heuristic(masked, remaining)
    assert chosen == "I"


def test_handles_no_remaining():
    masked = "ANY"
    remaining = []
    chosen = choose_vowel_heuristic(masked, remaining)
    assert chosen is None
