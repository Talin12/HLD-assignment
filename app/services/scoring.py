"""
Recency + Popularity Scoring
-----------------------------
score(q) = frequency * W_freq + recency_score * W_recency

  recency_score is a running sum of e^(-λ * Δt) contributions, where Δt is the
  time in seconds since each individual search event. We approximate this by
  storing a single decayed accumulator and updating it on each new search:

    new_recency_score = old_recency_score * e^(-λ * Δt) + 1

  This gives a smooth exponential moving average without storing every event.

  λ (decay_lambda) controls how fast old searches lose influence:
    - λ = 0.0001  → half-life ≈ 6931 seconds (~1.9 hours)
    - λ = 0.001   → half-life ≈ 693  seconds (~12 minutes)

  Final combined score weights frequency (long-term popularity) and recency
  together so both viral/trending queries and evergreen popular ones surface.
"""

import math
import time


W_FREQ = 1.0       # weight for historical frequency
W_RECENCY = 50.0   # recency carries extra punch to surface trending queries


def compute_score(frequency: int, recency_score: float) -> float:
    return frequency * W_FREQ + recency_score * W_RECENCY


def decay_recency(old_recency: float, last_searched_at: float, decay_lambda: float) -> float:
    """Decay existing recency accumulator to 'now' and add 1 for the new event."""
    now = time.time()
    delta = max(0.0, now - last_searched_at)
    decayed = old_recency * math.exp(-decay_lambda * delta)
    return decayed + 1.0
