"""Tests for harness/faq_cache.py (Story 6.11 Tier 0 stub)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import faq_cache


def test_match_hits_on_seeded_trigger():
    entry = faq_cache.match("how many spaces are open now in Berlin and which one?")
    assert entry is not None
    assert entry["trigger"] == "open now in berlin"


def test_match_is_case_insensitive():
    entry = faq_cache.match("OPEN NOW IN BERLIN please")
    assert entry is not None


def test_match_returns_none_on_miss():
    assert faq_cache.match("what's the weather in Ghent?") is None
