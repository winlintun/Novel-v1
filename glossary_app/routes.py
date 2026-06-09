"""
REST endpoints for glossary review.

Endpoints:
    GET  /                          → index.html (single-page app)
    GET  /api/novels                → list all novels
    GET  /api/terms                 → list terms (with filters)
    GET  /api/terms/<term_id>       → term detail + variants + usage
    POST /api/terms/<term_id>/approve   → set status='approved'
    POST /api/terms/<term_id>/reject    → set status='rejected'
    POST /api/terms/<term_id>/edit      → update target/category
    POST /api/terms/<term_id>/variants  → add a variant
    DELETE /api/variants/<variant_id>   → remove a variant
    GET  /api/stats/<novel_id>          → counts by status
    GET  /api/audit/<term_id>           → audit log for a term
    POST /api/bulk/approve              → approve multiple terms
"""

import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request

from glossary_app.db import get_conn, row_to_dict

bp = Blueprint("glossary", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/novels")
def list_novels():
    with get_conn() as c:
        rows = c.execute("""
            SELECT n.id, n.name, n.source_language,
                   COUNT(t.id) AS term_count,
                   SUM(CASE WHEN t.status='pending' THEN 1 ELSE 0 END) AS pending_count
            FROM novels n
            LEFT JOIN glossary_terms t ON t.novel_id = n.id
            GROUP BY n.id
            ORDER BY n.name
        """).fetchall()
        return jsonify([row_to_dict(r) for r in rows])


@bp.route("/api/terms")
def list_terms():
    novel_id = request.args.get("novel_id", "")
    status = request.args.get("status", "")
    category = request.args.get("category", "")
    min_conf = float(request.args.get("min_confidence", "0"))
    max_conf = float(request.args.get("max_confidence", "1"))
    search = request.args.get("q", "").strip()
    sort = request.args.get("sort", "confidence_desc")
    limit = int(request.args.get("limit", "100"))
    offset = int(request.args.get("offset", "0"))

    where = ["1=1"]
    params: list = []
    if novel_id:
        where.append("novel_id = ?")
        params.append(novel_id)
    if status and status != "all":
        where.append("status = ?")
        params.append(status)
    if category:
        where.append("category = ?")
        params.append(category)
    where.append("confidence >= ? AND confidence <= ?")
    params.extend([min_conf, max_conf])
    if search:
        where.append("(source_term LIKE ? OR target_term LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    order_map = {
        "confidence_desc": "confidence DESC",
        "confidence_asc": "confidence ASC",
        "usage_desc": "usage_count DESC",
        "created_desc": "created_at DESC",
        "source_asc": "source_term ASC",
    }
    order = order_map.get(sort, "confidence DESC")

    sql = f"""
        SELECT id, novel_id, source_term, target_term, category, status,
               confidence, usage_count, created_at, reviewed_at
        FROM glossary_terms
        WHERE {' AND '.join(where)}
        ORDER BY {order}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with get_conn() as c:
        rows = c.execute(sql, params).fetchall()

        count_where = " AND ".join(where)
        count_params = params[:len(params) - 2]
        total = c.execute(
            f"SELECT COUNT(*) AS total FROM glossary_terms WHERE {count_where}",
            count_params,
        ).fetchone()["total"]

        return jsonify({
            "total": total,
            "limit": limit,
            "offset": offset,
            "terms": [row_to_dict(r) for r in rows],
        })


@bp.route("/api/terms/<term_id>")
def term_detail(term_id: str):
    with get_conn() as c:
        term = c.execute(
            "SELECT * FROM glossary_terms WHERE id = ?", (term_id,)
        ).fetchone()
        if not term:
            return jsonify({"error": "not_found"}), 404

        variants = c.execute(
            "SELECT id, variant_text, match_type FROM term_variants WHERE term_id = ?",
            (term_id,),
        ).fetchall()

        usage = c.execute("""
            SELECT u.chapter_id, u.paragraph_idx, u.variant_used,
                   u.confidence, u.context_snippet
            FROM term_usage u
            WHERE u.term_id = ?
            ORDER BY u.chapter_id, u.paragraph_idx
            LIMIT 20
        """, (term_id,)).fetchall()

        return jsonify({
            "term": row_to_dict(term),
            "variants": [row_to_dict(v) for v in variants],
            "usage": [row_to_dict(u) for u in usage],
        })


@bp.route("/api/terms/<term_id>/approve", methods=["POST"])
def approve(term_id: str):
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as c:
        cur = c.execute(
            "SELECT status FROM glossary_terms WHERE id = ?",
            (term_id,),
        ).fetchone()
        if not cur:
            return jsonify({"error": "not_found"}), 404

        c.execute(
            "UPDATE glossary_terms SET status='approved', reviewed_at=? WHERE id=?",
            (now, term_id),
        )
        c.execute("""
            INSERT INTO audit_log (table_name, record_id, action, old_data,
                                   new_data, source)
            VALUES ('glossary_terms', ?, 'approve', ?, ?, 'review_ui')
        """, (term_id,
              json.dumps({"status": cur["status"]}),
              json.dumps({"status": "approved", "reviewed_at": now})))
    return jsonify({"ok": True, "status": "approved"})


@bp.route("/api/terms/<term_id>/reject", methods=["POST"])
def reject(term_id: str):
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as c:
        cur = c.execute(
            "SELECT status FROM glossary_terms WHERE id = ?", (term_id,)
        ).fetchone()
        if not cur:
            return jsonify({"error": "not_found"}), 404

        c.execute(
            "UPDATE glossary_terms SET status='rejected', reviewed_at=? WHERE id=?",
            (now, term_id),
        )
        c.execute("""
            INSERT INTO audit_log (table_name, record_id, action, old_data,
                                   new_data, source)
            VALUES ('glossary_terms', ?, 'reject', ?, ?, 'review_ui')
        """, (term_id, json.dumps({"status": cur["status"]}),
              json.dumps({"status": "rejected"})))
    return jsonify({"ok": True, "status": "rejected"})


@bp.route("/api/terms/<term_id>/edit", methods=["POST"])
def edit(term_id: str):
    data = request.get_json(force=True)
    fields = {}
    if "target_term" in data:
        fields["target_term"] = data["target_term"].strip()
        fields["canonical_form"] = fields["target_term"]
    if "category" in data:
        fields["category"] = data["category"].strip()
    if "confidence" in data:
        try:
            fields["confidence"] = float(data["confidence"])
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_confidence"}), 400
    if not fields:
        return jsonify({"error": "no_fields"}), 400

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values()) + [term_id]

    with get_conn() as c:
        old = c.execute(
            "SELECT target_term, category, confidence FROM glossary_terms WHERE id=?",
            (term_id,),
        ).fetchone()
        if not old:
            return jsonify({"error": "not_found"}), 404

        c.execute(f"UPDATE glossary_terms SET {set_clause} WHERE id = ?", params)
        c.execute("""
            INSERT INTO audit_log (table_name, record_id, action, old_data,
                                   new_data, source)
            VALUES ('glossary_terms', ?, 'edit', ?, ?, 'review_ui')
        """, (term_id, json.dumps(dict(old)), json.dumps(fields)))
    return jsonify({"ok": True})


@bp.route("/api/terms/<term_id>/variants", methods=["POST"])
def add_variant(term_id: str):
    data = request.get_json(force=True)
    text = (data.get("variant_text") or "").strip()
    if not text:
        return jsonify({"error": "empty"}), 400
    with get_conn() as c:
        if not c.execute(
            "SELECT 1 FROM glossary_terms WHERE id = ?", (term_id,)
        ).fetchone():
            return jsonify({"error": "not_found"}), 404
        if c.execute(
            "SELECT 1 FROM term_variants WHERE term_id=? AND variant_text=?",
            (term_id, text),
        ).fetchone():
            return jsonify({"error": "duplicate"}), 409
        cur = c.execute("""
            INSERT INTO term_variants (term_id, variant_text, match_type,
                                       case_sensitive)
            VALUES (?, ?, 'exact', 0)
        """, (term_id, text))
        return jsonify({"ok": True, "id": cur.lastrowid})


@bp.route("/api/variants/<int:variant_id>", methods=["DELETE"])
def delete_variant(variant_id: int):
    with get_conn() as c:
        cur = c.execute(
            "DELETE FROM term_variants WHERE id = ?", (variant_id,)
        )
        if cur.rowcount == 0:
            return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True})


@bp.route("/api/stats/<novel_id>")
def stats(novel_id: str):
    with get_conn() as c:
        overall = c.execute("""
            SELECT
                SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved,
                SUM(CASE WHEN status='pending'  THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) AS rejected,
                COUNT(*) AS total,
                AVG(confidence) AS avg_confidence
            FROM glossary_terms WHERE novel_id = ?
        """, (novel_id,)).fetchone()

        by_cat = c.execute("""
            SELECT category, COUNT(*) AS count
            FROM glossary_terms WHERE novel_id = ?
            GROUP BY category ORDER BY count DESC
        """, (novel_id,)).fetchall()

        return jsonify({
            "overall": row_to_dict(overall),
            "by_category": [row_to_dict(r) for r in by_cat],
        })


@bp.route("/api/audit/<term_id>")
def audit(term_id: str):
    with get_conn() as c:
        rows = c.execute("""
            SELECT action, old_data, new_data, timestamp, source
            FROM audit_log
            WHERE table_name='glossary_terms' AND record_id=?
            ORDER BY timestamp DESC LIMIT 50
        """, (term_id,)).fetchall()
        return jsonify([row_to_dict(r) for r in rows])


@bp.route("/api/bulk/approve", methods=["POST"])
def bulk_approve():
    data = request.get_json(force=True)
    ids = data.get("term_ids", [])
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "no_ids"}), 400

    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as c:
        placeholders = ",".join(["?"] * len(ids))
        c.execute(
            f"UPDATE glossary_terms SET status='approved', reviewed_at=? "
            f"WHERE id IN ({placeholders}) AND status='pending'",
            [now] + ids,
        )
        for tid in ids:
            c.execute("""
                INSERT INTO audit_log (table_name, record_id, action,
                                       new_data, source)
                VALUES ('glossary_terms', ?, 'bulk_approve', ?, 'review_ui')
            """, (tid, json.dumps({"reviewed_at": now})))
    return jsonify({"ok": True, "count": len(ids)})
