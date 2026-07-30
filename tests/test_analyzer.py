from __future__ import annotations

from inventory import Item
from analyzer import health_score


def test_health_score_range():
    score, _ = health_score([Item("Applications", "Test", risk="Safe")])
    assert 0 <= score <= 100
