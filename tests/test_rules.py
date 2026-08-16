"""Rules engine tests (RULES.md enforcement: auto vs verify)."""

from __future__ import annotations

from src.pipeline.rules import RulesEngine

RULE_CONFIG = {
    "auto_fix_enabled": True,
    "max_auto_fix_per_chunk": 2,
    "priorities": ["R-AUTO-01", "R-RE-01"],
    "rules": [
        {"id": "R-AUTO-01", "enabled": True, "severity": "error", "scope": "global",
         "enforcement": "auto", "regex": "\\u200b", "replacement": "", "description": "strip ZWSP"},
        {"id": "R-RE-01", "enabled": True, "severity": "error", "scope": "global",
         "enforcement": "verify", "regex": "[A-Za-z]{2,}", "replacement": "", "description": "no latin words"},
    ],
}


def test_load_missing_file_returns_empty():
    eng = RulesEngine.load("nope.json")
    assert eng.rules == []


def test_auto_rule_fixes_and_counts():
    eng = RulesEngine(RULE_CONFIG)
    text = "a\u200bb \u200bc"
    fixed, issues, auto_fixed = eng.evaluate(text)
    assert "\u200b" not in fixed
    assert auto_fixed == 2
    assert any(i.auto_fixed for i in issues)


def test_verify_rule_reports_issue():
    eng = RulesEngine(RULE_CONFIG)
    _, issues, _ = eng.evaluate("Hello world မြန်မာ")
    assert any(i.rule_id == "R-RE-01" for i in issues)


def test_auto_fix_cap_leftover_becomes_issue():
    eng = RulesEngine(RULE_CONFIG)  # cap = 2
    text = "\u200b" * 5
    fixed, issues, auto_fixed = eng.evaluate(text)
    assert auto_fixed == 2
    assert any(i.rule_id == "R-AUTO-01" and not i.auto_fixed for i in issues)


def test_sort_issues_by_priority_and_severity():
    from src.pipeline.models import Issue

    eng = RulesEngine(RULE_CONFIG)
    issues = [
        Issue(severity="warning", category="format", rule_id="R-RE-01"),
        Issue(severity="error", category="format", rule_id="R-AUTO-01"),
        Issue(severity="info", category="format", rule_id="R-AUTO-01"),
    ]
    ordered = eng.sort_issues(issues)
    assert ordered[0].rule_id == "R-AUTO-01"


def test_disabled_rule_not_enforced():
    cfg = {
        "rules": [
            {"id": "R-OFF", "enabled": False, "severity": "fatal", "enforcement": "verify",
             "regex": "x", "description": "off"},
        ]
    }
    eng = RulesEngine(cfg)
    assert eng.rules == []