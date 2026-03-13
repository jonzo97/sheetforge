"""Dice rolling service wrapping the d20 library."""

import d20


def roll(expression: str) -> d20.RollResult:
    """Roll dice using standard notation.

    Args:
        expression: Dice expression like "4d6kh3", "1d20+5", "2d6+3".

    Returns:
        A d20.RollResult with .total and string representation.
    """
    return d20.roll(expression)


def roll_ability_scores() -> list[tuple[int, str]]:
    """Roll a full set of 6 ability scores using 4d6-drop-lowest.

    Returns:
        List of 6 (total, detail_string) tuples.
    """
    results = []
    for _ in range(6):
        result = d20.roll("4d6kh3")
        results.append((result.total, str(result)))
    return results


STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]
