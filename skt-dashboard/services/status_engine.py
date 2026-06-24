from __future__ import annotations

from datetime import date
import pandas as pd


MODE_TERMS = ("tukar mod", "dalam talian", "hibrid")


def classify_status(row: dict, today: date | None = None) -> str:
    today = today or date.today()
    title = str(row.get("course_title") or "").lower()
    remarks = " ".join(
        str(row.get(key) or "")
        for key in ("remarks", "mode", "source_status", "user_remarks")
    ).lower()
    combined = f"{title} {remarks}"

    if "gugur" in combined or "digugur" in combined or "batal" in combined:
        return "Dropped"
    if any(term in combined for term in MODE_TERMS):
        return "Mode Changed"

    planned_start = _as_date(row.get("planned_start_date"))
    planned_end = _as_date(row.get("planned_end_date")) or planned_start
    actual_start = _as_date(row.get("actual_start_date"))
    actual_participants = _as_number(row.get("actual_participants"))
    source_status = str(row.get("source_status") or "").lower()

    if planned_start and actual_start and actual_start > planned_start:
        return "Delayed"
    if actual_participants and actual_participants > 0:
        return "Completed"
    if "selesai" in source_status:
        return "Completed"
    if planned_start and planned_end and planned_start <= today <= planned_end:
        return "In Progress"
    if planned_start and planned_start > today:
        return "Upcoming"
    if planned_end and planned_end < today:
        return "No Update"
    return "No Update"


def _as_date(value):
    if value in ("", None):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.date()


def _as_number(value):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
