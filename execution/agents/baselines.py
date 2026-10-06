"""Baselines that use ONLY the lineage graph and commit history. They never re-run anything.

B1 lineage_recency : among the shortlisted suspects, blame the one whose change commit is the most recent.
                     This is the "most recently changed upstream table is the likely cause" pattern of lineage tools.
B2 lineage_distance: blame the suspect closest to the anomalous table in the lineage graph; ties go to the more recent change.
Both get exactly the same shortlist as replay (same suspects, same window), so the comparison is like for like.
"""
from __future__ import annotations

from agents.shortlist import Suspect


def rank_recency(suspects: list[Suspect]) -> list[Suspect]:
    """Most recent change first (ties: table name)."""
    return sorted(suspects, key=lambda s: (-s.last_change.committed_at, s.table))


def rank_distance(suspects: list[Suspect]) -> list[Suspect]:
    """Closest to the anomalous table first, then most recent change, then table name."""
    return sorted(suspects, key=lambda s: (s.distance, -s.last_change.committed_at, s.table))


def blame_recency(suspects: list[Suspect]) -> str | None:
    ranked = rank_recency(suspects)
    return ranked[0].table if ranked else None


def blame_distance(suspects: list[Suspect]) -> str | None:
    ranked = rank_distance(suspects)
    return ranked[0].table if ranked else None
