"""Random helpers used across the bot."""

import random


def random_delay(min_seconds: int, max_seconds: int) -> int:
    """Returns a random integer delay within [min, max]."""
    return random.randint(
        min(min_seconds, max_seconds),
        max(min_seconds, max_seconds),
    )


def should_act(percent: int) -> bool:
    """Returns True with probability `percent`/100."""
    return random.random() < (max(0, min(100, percent)) / 100)
