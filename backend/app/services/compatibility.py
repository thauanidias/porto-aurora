"""Explain the recorded vacancy score without inventing missing evidence."""

import math


def rank_compatibility(items):
    """Rank comparable, visible professional scores; unknown scores remain unranked."""
    def percentage(item):
        summary = item.get("compatibility") or {}
        report = summary.get("curriculum") or summary
        value = report.get("percentage")
        if report.get("status") not in {"CALCULATED", "PENDING"}:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
            return None
        return value

    ordered = sorted(items, key=lambda item: (percentage(item) is None, -(percentage(item) or 0), item["id"]))
    last, rank = None, None
    for index, item in enumerate(ordered, 1):
        value = percentage(item)
        if value is not None and value != last:
            rank = index
        item["compatibility_rank"] = rank if value is not None else None
        last = value
    return ordered


def compatibility_summary(score, model, sealed=False):
    if sealed:
        return {"percentage": None, "status": "SEALED", "items": []}
    if not model or not any(not c.get("not_applicable") for c in model.criteria):
        return {"percentage": None, "status": "NOT_CONFIGURED", "items": []}
    if not score or score.model_id != model.id:
        return {"percentage": None, "status": "OUTDATED", "items": []}
    detail = score.breakdown
    items = [item for item in detail.get("items", []) if item.get("applicable")]
    missing = [item["name"] for item in items if item.get("value") is None]
    pending = detail.get("pending_components", [])
    known = [item for item in items if item.get("value") is not None]
    return {
        "percentage": float(score.total) if score.total is not None and (known or any(v is not None for k, v in detail.get("components", {}).items() if k != "OBJECTIVE")) else None,
        "status": "PENDING" if missing or pending else "CALCULATED",
        "knockout": score.knockout,
        "items": items,
        "missing_criteria": missing,
        "unmet_required_criteria": detail.get("unmet_required_criteria", []),
        "evidence_coverage": detail.get("evidence_coverage"),
        "basis": detail.get("basis"),
        "pending_components": pending,
        "model_version": model.number,
        "calculated_at": score.created_at,
        "curriculum": detail.get("curriculum_analysis"),
        "bands": getattr(model, "bands", []),
    }
