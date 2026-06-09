"""HTML + JSON report builder for alignment pipeline results."""

import json
from datetime import datetime
from pathlib import Path

from jinja2 import Template

from src.dataset_alignment.config import get_alignment_config
from src.dataset_alignment.database import connect

_REPORT_TEMPLATE = Template(r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Dataset Alignment Report — {{ novel }}</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 1100px; margin: 2rem auto; padding: 0 1rem;
         color: #1a1a1a; background: #fafafa; }
  h1 { border-bottom: 2px solid #333; padding-bottom: .4rem; }
  h2 { margin-top: 2rem; }
  .meta { color: #666; font-size: .9rem; }
  table { border-collapse: collapse; width: 100%; margin: .5rem 0 2rem; }
  th, td { padding: .4rem .6rem; border-bottom: 1px solid #ddd;
           text-align: left; vertical-align: top; }
  th { background: #eee; }
  tr.error td  { background: #fdecea; }
  tr.warn td   { background: #fff8e1; }
  tr.info td   { background: #e8f4fd; }
  code { background: #f0f0f0; padding: 0 .25rem; border-radius: 3px; }
  .summary-grid { display: grid; grid-template-columns: repeat(3, 1fr);
                  gap: 1rem; margin: 1rem 0; }
  .card { background: white; padding: 1rem; border-radius: 6px;
          box-shadow: 0 1px 3px rgba(0,0,0,.1); }
  .card .n { font-size: 2rem; font-weight: 700; }
  .card.error  .n { color: #c62828; }
  .card.warn   .n { color: #ef6c00; }
  .card.info   .n { color: #1565c0; }
  details { background: white; border: 1px solid #ddd; border-radius: 6px;
            padding: .5rem 1rem; margin: .5rem 0; }
  details[open] { background: #fcfcfc; }
  summary { cursor: pointer; font-weight: 600; }
</style></head><body>

<h1>Dataset Alignment Report</h1>
<p class="meta">Novel: <b>{{ novel }}</b> · Generated: {{ generated_at }}</p>

<h2>Summary</h2>
<div class="summary-grid">
  <div class="card error"><div class="n">{{ summary.error }}</div>errors</div>
  <div class="card warn"><div class="n">{{ summary.warn }}</div>warnings</div>
  <div class="card info"><div class="n">{{ summary.info }}</div>info</div>
</div>

<h2>Coverage</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Chapters with source</td><td>{{ coverage.with_src }}</td></tr>
<tr><td>Chapters with target</td><td>{{ coverage.with_tgt }}</td></tr>
<tr><td>Chapters fully paired</td><td>{{ coverage.paired }}</td></tr>
<tr><td>Total alignments</td><td>{{ coverage.alignments }}</td></tr>
<tr><td>1:1 alignments</td><td>{{ coverage.one_to_one }}</td></tr>
<tr><td>NULL alignments (omissions)</td><td>{{ coverage.nulls }}</td></tr>
</table>

<h2>Issues by category</h2>
{% for cat, rows in by_category.items() %}
<details>
  <summary>{{ cat }} ({{ rows|length }})</summary>
  <table>
    <tr><th>Sev</th><th>Chapter</th><th>Message</th><th>Evidence</th></tr>
    {% for r in rows[:50] %}
    <tr class="{{ r.severity }}">
      <td>{{ r.severity }}</td>
      <td>{{ r.chapter_no or "—" }}</td>
      <td>{{ r.message }}</td>
      <td><code>{{ (r.evidence or "")[:160] }}</code></td>
    </tr>
    {% endfor %}
    {% if rows|length > 50 %}
    <tr><td colspan="4"><i>... {{ rows|length - 50 }} more rows truncated.</i></td></tr>
    {% endif %}
  </table>
</details>
{% endfor %}

</body></html>
""")


def build_report(novel: str) -> Path:
    """Generate HTML + JSON reports for a novel's alignment results."""
    cfg = get_alignment_config()

    with connect() as conn:
        summary = {"error": 0, "warn": 0, "info": 0}
        for r in conn.execute(
            """SELECT severity, COUNT(*) AS c
               FROM issues i LEFT JOIN chapters c ON i.chapter_id = c.id
               WHERE c.novel = ? OR c.novel IS NULL
               GROUP BY severity""",
            (novel,),
        ):
            if r["severity"] in summary:
                summary[r["severity"]] = r["c"]

        cov_row = conn.execute(
            """SELECT
                 SUM(CASE WHEN src_file_id IS NOT NULL THEN 1 ELSE 0 END) AS s,
                 SUM(CASE WHEN tgt_file_id IS NOT NULL THEN 1 ELSE 0 END) AS t,
                 SUM(CASE WHEN src_file_id IS NOT NULL
                          AND tgt_file_id IS NOT NULL THEN 1 ELSE 0 END) AS p
               FROM chapters WHERE novel=?""",
            (novel,),
        ).fetchone()
        align_row = conn.execute(
            """SELECT
                 COUNT(*) AS total,
                 SUM(CASE WHEN kind='1:1' THEN 1 ELSE 0 END) AS one,
                 SUM(CASE WHEN kind LIKE '%NULL%' THEN 1 ELSE 0 END) AS nulls
               FROM alignments a JOIN chapters c ON a.chapter_id = c.id
               WHERE c.novel=?""",
            (novel,),
        ).fetchone()
        coverage = {
            "with_src": cov_row["s"] or 0,
            "with_tgt": cov_row["t"] or 0,
            "paired": cov_row["p"] or 0,
            "alignments": align_row["total"] or 0,
            "one_to_one": align_row["one"] or 0,
            "nulls": align_row["nulls"] or 0,
        }

        rows = conn.execute(
            """SELECT i.category, i.severity, i.message, i.evidence, c.chapter_no
               FROM issues i LEFT JOIN chapters c ON i.chapter_id = c.id
               WHERE c.novel = ? OR c.novel IS NULL
               ORDER BY i.category, c.chapter_no""",
            (novel,),
        ).fetchall()
        by_cat: dict[str, list[dict]] = {}
        for r in rows:
            by_cat.setdefault(r["category"], []).append(dict(r))

    html = _REPORT_TEMPLATE.render(
        novel=novel,
        generated_at=datetime.now().isoformat(timespec="seconds"),
        summary=summary,
        coverage=coverage,
        by_category=by_cat,
    )

    out = cfg.path("reports_dir") / f"{novel}_alignment_report.html"
    out.write_text(html, encoding="utf-8")
    (cfg.path("reports_dir") / f"{novel}_alignment_report.json").write_text(
        json.dumps({"summary": summary, "coverage": coverage, "by_category": {
            k: [dict(r) for r in v] for k, v in by_cat.items()
        }}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out
