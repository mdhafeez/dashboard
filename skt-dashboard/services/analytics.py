from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import pandas as pd


SECTION_ORDER = ["SLPPI", "SLAD", "SLKD", "SLPD", "SLID", "SLPS"]
STATUS_ORDER = ["Completed", "Upcoming", "In Progress", "Delayed", "No Update", "Dropped", "Mode Changed"]


def rows_to_df(rows) -> pd.DataFrame:
    df = pd.DataFrame([dict(row) for row in rows])
    if df.empty:
        return pd.DataFrame()
    for col in ["target_participants", "actual_participants", "budget"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in ["planned_start_date", "planned_end_date", "actual_start_date", "actual_end_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["effective_status"] = df["status_override"].fillna(df["status"])
    df["month_label"] = df["planned_start_date"].dt.strftime("%b %Y").fillna("No Date")
    df["month_num"] = df["planned_start_date"].dt.month.fillna(99).astype(int)
    return df


def kpis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "total_courses": 0, "completed": 0, "upcoming": 0, "delayed": 0, "dropped": 0,
            "target_participants": 0, "actual_participants": 0, "achievement_pct": 0, "budget": 0
        }
    target = float(df["target_participants"].sum())
    actual = float(df["actual_participants"].sum())
    statuses = df["effective_status"].value_counts()
    return {
        "total_courses": int(len(df)),
        "completed": int(statuses.get("Completed", 0)),
        "upcoming": int(statuses.get("Upcoming", 0)),
        "delayed": int(statuses.get("Delayed", 0)),
        "dropped": int(statuses.get("Dropped", 0)),
        "target_participants": int(target),
        "actual_participants": int(actual),
        "achievement_pct": round((actual / target * 100), 1) if target else 0,
        "budget": float(df["budget"].sum()),
    }


def section_performance(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    grouped = df.groupby("section", dropna=False).agg(
        courses=("id", "count"),
        target_participants=("target_participants", "sum"),
        actual_participants=("actual_participants", "sum"),
        budget=("budget", "sum"),
        completed=("effective_status", lambda s: (s == "Completed").sum()),
    ).reset_index()
    grouped["section"] = grouped["section"].fillna("Unassigned")
    grouped["completion_pct"] = (grouped["completed"] / grouped["courses"] * 100).round(1)
    return grouped.sort_values("section").to_dict("records")


def monthly_performance(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    grouped = df.groupby(["month_num", "month_label"], dropna=False).agg(
        courses=("id", "count"),
        completed=("effective_status", lambda s: (s == "Completed").sum()),
        upcoming=("effective_status", lambda s: (s == "Upcoming").sum()),
        target_participants=("target_participants", "sum"),
        actual_participants=("actual_participants", "sum"),
    ).reset_index().sort_values(["month_num", "month_label"])
    grouped["achievement_pct"] = grouped.apply(
        lambda r: round(r.actual_participants / r.target_participants * 100, 1) if r.target_participants else 0,
        axis=1,
    )
    return grouped.to_dict("records")


def chart_payload(df: pd.DataFrame) -> dict:
    sections = SECTION_ORDER + sorted(set(df.get("section", pd.Series(dtype=str)).dropna()) - set(SECTION_ORDER))
    section_rows = section_performance(df)
    by_section = {r["section"]: r for r in section_rows}
    months = monthly_performance(df)
    status_counts = df["effective_status"].value_counts().to_dict() if not df.empty else {}
    type_section = _type_by_section(df)
    top_budget = df.sort_values("budget", ascending=False).head(10) if not df.empty else pd.DataFrame()
    return {
        "sections": sections,
        "coursesBySection": [int(by_section.get(s, {}).get("courses", 0)) for s in sections],
        "targetBySection": [float(by_section.get(s, {}).get("target_participants", 0)) for s in sections],
        "actualBySection": [float(by_section.get(s, {}).get("actual_participants", 0)) for s in sections],
        "budgetBySection": [float(by_section.get(s, {}).get("budget", 0)) for s in sections],
        "months": [m["month_label"] for m in months],
        "coursesByMonth": [int(m["courses"]) for m in months],
        "completedByMonth": [int(m["completed"]) for m in months],
        "upcomingByMonth": [int(m["upcoming"]) for m in months],
        "achievementByMonth": [float(m["achievement_pct"]) for m in months],
        "statusLabels": STATUS_ORDER,
        "statusCounts": [int(status_counts.get(s, 0)) for s in STATUS_ORDER],
        "topBudgetLabels": top_budget["course_title"].tolist() if not top_budget.empty else [],
        "topBudgetValues": top_budget["budget"].fillna(0).tolist() if not top_budget.empty else [],
        "typeSectionLabels": type_section["labels"],
        "typeSectionDatasets": type_section["datasets"],
    }


def build_alerts(df: pd.DataFrame) -> list[dict]:
    alerts = []
    if df.empty:
        return alerts
    today = pd.Timestamp(date.today())
    for _, row in df.iterrows():
        title = row.get("course_title") or "Untitled course"
        if pd.notna(row.get("planned_end_date")) and row["planned_end_date"] < today and not row.get("actual_participants"):
            alerts.append(_alert("Date Passed", title, "Course date already passed but actual participant is empty.", row))
        if not row.get("budget"):
            alerts.append(_alert("Missing Budget", title, "Course has no budget value.", row))
        if not str(row.get("coordinator") or "").strip():
            alerts.append(_alert("Missing Coordinator", title, "Course has no coordinator.", row))
        if not str(row.get("section") or "").strip():
            alerts.append(_alert("Missing Section", title, "Course has no section.", row))
        if pd.notna(row.get("actual_start_date")) and pd.notna(row.get("planned_start_date")) and row["actual_start_date"] != row["planned_start_date"]:
            alerts.append(_alert("Date Difference", title, "Actual date differs from planned date.", row))
        if row.get("target_participants", 0) and row.get("actual_participants", 0) and row["actual_participants"] < row["target_participants"]:
            alerts.append(_alert("Below Target", title, "Participant achievement below target.", row))

    duplicates = df[df.duplicated(subset=["section", "planned_start_date", "planned_end_date"], keep=False)]
    for _, row in duplicates.iterrows():
        if pd.notna(row.get("planned_start_date")):
            alerts.append(_alert("Overlap", row.get("course_title"), "Duplicate or overlapping course dates in the same section.", row))
    return alerts[:300]


def _alert(kind: str, title: str, message: str, row) -> dict:
    return {
        "type": kind,
        "course": title,
        "section": row.get("section") or "Unassigned",
        "date": row.get("planned_start_date").strftime("%Y-%m-%d") if pd.notna(row.get("planned_start_date")) else "",
        "message": message,
        "severity": "danger" if kind in {"Date Passed", "Missing Section", "Overlap"} else "warning",
    }


def _type_by_section(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"labels": [], "datasets": []}
    labels = [s for s in SECTION_ORDER if s in set(df["section"].dropna())]
    types = [t for t in df["course_type"].fillna("Unspecified").value_counts().head(6).index]
    datasets = []
    colors = ["#0b3d91", "#198754", "#ffc107", "#6c757d", "#0dcaf0", "#dc3545"]
    for idx, course_type in enumerate(types):
        counts = []
        for section in labels:
            counts.append(int(((df["section"] == section) & (df["course_type"].fillna("Unspecified") == course_type)).sum()))
        datasets.append({"label": course_type, "data": counts, "backgroundColor": colors[idx % len(colors)]})
    return {"labels": labels, "datasets": datasets}
