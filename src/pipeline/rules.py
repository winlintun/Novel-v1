"""Rule engine (RULES.md) backed by config/rules.json.

Rules carry ``enforcement`` in ``{auto | verify | audit}``:

- **auto**: a deterministic regex + replacement applied to the text, counted
  against ``max_auto_fix_per_chunk`` (TEST-RULE-002)
- **verify**: a regex presence/pattern check that emits an issue (TEST-RULE-001)

Priorities resolve conflicts when several rules fire on the same location.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .models import Issue


class Rule:
    def __init__(self, cfg: Dict[str, Any]):
        self.id = str(cfg.get("id", ""))
        self.enabled = bool(cfg.get("enabled", True))
        self.severity = str(cfg.get("severity", "warning"))
        self.scope = str(cfg.get("scope", "global"))
        self.enforcement = str(cfg.get("enforcement", "verify"))
        self.regex = str(cfg.get("regex", ""))
        self.replacement = str(cfg.get("replacement", ""))
        self.description = str(cfg.get("description", ""))
        self._pattern: Optional[re.Pattern] = None
        if self.regex:
            try:
                self._pattern = re.compile(self.regex, re.MULTILINE)
            except re.error:
                self._pattern = None


class RulesEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config if config is not None else {}
        self.priorities: List[str] = [
            str(p) for p in self.config.get("priorities", [])
        ]
        self.auto_fix_enabled = bool(self.config.get("auto_fix_enabled", True))
        self.max_auto_fix = int(self.config.get("max_auto_fix_per_chunk", 10))
        self.rules: List[Rule] = []
        for r in (self.config.get("rules") or []):
            rule = Rule(r)
            if rule.enabled:
                self.rules.append(rule)

    @classmethod
    def load(cls, path: Optional[Path | str] = None) -> "RulesEngine":
        if not path:
            return cls()
        p = Path(path)
        if not p.is_file():
            return cls()
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def rank(self, rule_id: str) -> int:
        try:
            return self.priorities.index(rule_id)
        except ValueError:
            return len(self.priorities)

    def sort_issues(self, issues: List[Issue]) -> List[Issue]:
        sev_rank = {"critical": 0, "fatal": 0, "error": 1, "warning": 2, "info": 3}
        return sorted(
            issues,
            key=lambda i: (sev_rank.get(i.severity, 9), self.rank(i.rule_id)),
        )

    def evaluate(
        self,
        text: str,
        *,
        max_auto_fix: Optional[int] = None,
    ) -> Tuple[str, List[Issue], int]:
        """Apply auto rules, collect verify issues.

        Returns ``(fixed_text, issues, auto_fixed_count)``.  Auto fixes stop
        once the per-chunk cap is reached; the leftovers become error issues.
        """
        cap = self.max_auto_fix if max_auto_fix is None else max_auto_fix
        fixed = text
        issues: List[Issue] = []
        auto_fixed = 0

        for rule in self.rules:
            if rule.enforcement == "auto" and rule._pattern is not None:
                remaining = cap - auto_fixed
                if remaining <= 0:
                    issues.append(
                        Issue(
                            severity=rule.severity if rule.severity != "auto" else "error",
                            category=self._category_for(rule),
                            rule_id=rule.id,
                            message=f"auto-fix cap reached for {rule.id}",
                        )
                    )
                    continue
                matches = [m for m in rule._pattern.finditer(fixed)]
                fixes = matches[:remaining]
                leftover = matches[remaining:]
                # Apply from the last match backwards so positions stay valid
                # while ``fixed`` shrinks/grows during the loop.
                for m in reversed(fixes):
                    fixed = fixed[:m.start()] + rule.replacement + fixed[m.end():]
                    auto_fixed += 1
                    issues.append(
                        Issue(
                            severity="info",
                            category=self._category_for(rule),
                            rule_id=rule.id,
                            location={"snippet": m.group(0)},
                            message=f"auto-fixed by {rule.id}",
                            auto_fixed=True,
                        )
                    )
                for m in leftover:
                    issues.append(
                        Issue(
                            severity=rule.severity if rule.severity != "auto" else "error",
                            category=self._category_for(rule),
                            rule_id=rule.id,
                            location={"snippet": m.group(0)},
                            message=f"auto-fix cap reached for {rule.id}",
                            suggestion="Raise max_auto_fix_per_chunk or split the chunk",
                        )
                    )
            elif rule.enforcement == "verify":
                if rule._pattern is None:
                    continue
                seen_snippets: set = set()
                for m in rule._pattern.finditer(fixed):
                    snippet = m.group(0)
                    if snippet in seen_snippets:
                        continue
                    seen_snippets.add(snippet)
                    issues.append(
                        Issue(
                            severity=rule.severity,
                            category=self._category_for(rule),
                            rule_id=rule.id,
                            location={"snippet": snippet},
                            message=rule.description or f"violated {rule.id}",
                            suggestion=self._suggestion(rule),
                        )
                    )
        return fixed, self.sort_issues(issues), auto_fixed

    @staticmethod
    def _category_for(rule: Rule) -> str:
        rid = rule.id
        if rid.startswith(("R-GLOSS",)):
            return "glossary"
        if rid.startswith(("R-STYLE",)):
            return "register"
        if rid.startswith(("R-STRUCT",)):
            return "coherence"
        if rid.startswith(("R-FORMAT",)):
            return "format"
        if rid.startswith(("R-FORBID", "R-CTX")):
            return "voice"
        return "coherence"

    @staticmethod
    def _suggestion(rule: Rule) -> str:
        if rule.replacement:
            return f"replace matched text with {rule.replacement!r}"
        return "review and fix the matched text"