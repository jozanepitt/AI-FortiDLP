"""Canned query registry tests."""
from __future__ import annotations

from app.agent.canned_queries import CANNED, get_canned, list_canned
from app.agent.tools import DISPATCH


def test_list_canned_returns_id_and_label():
    items = list_canned()
    assert len(items) == len(CANNED)
    for item in items:
        assert set(item.keys()) == {"id", "label"}


def test_every_canned_references_existing_tool():
    for q in CANNED:
        assert q.tool in DISPATCH, f"canned {q.id} -> unknown tool {q.tool}"


def test_get_canned_by_id():
    assert get_canned("top_user_today") is not None
    assert get_canned("nonexistent") is None
