"""Tolerant JSON recovery tests (AGENTS.md invariant)."""

from __future__ import annotations

from src.pipeline import jsonparse


def test_load_json_clean():
    assert jsonparse.load_json('{"translations": ["a"]}') == {"translations": ["a"]}


def test_load_json_truncated_trailing_brace():
    assert jsonparse.load_json('{"translations": ["a"]') == {"translations": ["a"]}


def test_load_json_fenced():
    assert jsonparse.load_json('```json\n{"translations": ["a"]}\n```') == {"translations": ["a"]}


def test_load_json_wrapped_object():
    text = 'note ({"translations": ["a"]}) end'
    parsed = jsonparse.load_json(text)
    assert parsed == {"translations": ["a"]}


def test_load_json_none():
    assert jsonparse.load_json("no json here") is None


def test_parse_translations_dict():
    assert jsonparse.parse_translations('{"translations": ["ဟုတ်", "မဟုတ်"]}') == ["ဟုတ်", "မဟုတ်"]


def test_parse_translations_plain_list():
    assert jsonparse.parse_translations("ရှေ့တန်း\nနောက်တန်း") == ["ရှေ့တန်း", "နောက်တန်း"]


def test_parse_translations_empty():
    assert jsonparse.parse_translations("") == []


def test_parse_results_dict():
    assert jsonparse.parse_results('{"results": [{"a": 1}]}') == [{"a": 1}]


def test_parse_results_scalar():
    assert jsonparse.parse_results('{"results": ["ok"]}') == [{"value": "ok"}]