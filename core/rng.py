"""Seeded random numbers. One numpy Generator is created from the seed and passed explicitly to whoever needs it."""
from __future__ import annotations

import numpy as np


def make_rng(seed: int, stream: str = "") -> np.random.Generator:
    """Return a Generator for (seed, stream). Different stream names give independent but reproducible streams."""
    key = [seed] + [ord(c) for c in stream]
    return np.random.default_rng(key)
