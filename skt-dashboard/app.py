from __future__ import annotations

from pathlib import Path
from uuid import uuid4
from io import BytesIO

import pandas as pd
from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, url_for

from models.database import execute, fetch_all, fetch_one, init_db, replace_courses
from services.analytics import build_alerts, chart_payload, kpis, monthly_performance, rows_to_df, section_performance
from services.excel_loader import load_excel_to_rows


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_EXCEL = DATA_DIR / "PerancanganSKT2026.xlsx"

app = Flask(__name__)
app.secret_key = "skt-dashboard-dev-key"


def bootstrap_data() -> None:
    init_db()
    count = fetch_one("SELECT COUNT(*) AS total FROM courses")
    if DEFAULT_EXCEL.exists() and (not count or count["total"] == 0):
        rows = load_excel_to_rows(DEFAULT_EXCEL)
        replace_courses(rows, DEFAULT_EXCEL.name, str(DEFAULT_EXCEL))


def filtered_courses():
    clauses = []
    params = []
    mapping = {
        "year": "strftime('%Y', planned_start_date)",
        "month": "strftime('%m', planned_start_date)",
        "section": "section",
        "course_type": "course_type",
        "status": "COALESCE(status_override, status)",
        "coordinator": "coordinator",
        "psp_category": "psp_category",
    }
    for key, column in mapping.items():
        value = request.args.get(key, "").strip()
        if value:
            clauses.append(f"{column} = ?")
            params.append(value)
    sql = "SELECT * FROM courses"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY planned_start_date IS NULL, planned_start_date, section, course_title"
    return fetch_all(sql, tuple(params))


def filter_options() -> dict:
    def values(expr):
        return [
            r["value"]
            for r in fetch_all(
                f"SELECT DISTINCT {expr} AS value FROM courses "
                f"WHERE {expr} IS NOT NULL AND TRIM({expr}) <> '' ORDER BY value"
            )
        ]

    return {
        "years": values("strftime('%Y', planned_start_date)"),
        "months": [{"value": f"{i:02d}", "label": name} for i, name in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)],
        "sections": values("section"),
        "course_types": values("course_type"),
        "statuses": values("COALESCE(status_override, status)"),
        "coordinators": values("coordinator"),
        "psp_categories": values("psp_category"),
    }


@app.context_processor
def inject_globals():
    def filtered_url(endpoint: str, **extra):
        params = request.args.to_dict()
        params.update(extra)
        return url_for(endpoint, **params)

    return {
        "filter_options": filter_options(),
        "active_filters": request.args.to_dict(),
        "filtered_url": filtered_url,
    }


@app.route("/")
def dashboard():
    rows = filtered_courses()
    df = rows_to_df(rows)
    return render_template("dashboard.html", kpis=kpis(df), alerts=build_alerts(df)[:8])


@app.route("/section")
def section():
    rows = filtered_courses()
    return render_template("section.html", section_rows=section_performance(rows_to_df(rows)))


@app.route("/monthly")
def monthly():
    rows = filtered_courses()
    return render_template("monthly.html", monthly_rows=monthly_performance(rows_to_df(rows)))


@app.route("/courses")
def courses():
    return render_template("courses.html", courses=filtered_courses())


@app.route("/alerts")
def alerts():
    rows = filtered_courses()
    return render_template("alerts.html", alerts=build_alerts(rows_to_df(rows)))


@app.route("/api/charts")
def charts():
    return jsonify(chart_payload(rows_to_df(filtered_courses())))


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("excel_file")
    if not file or not file.filename:
        flash("Please choose an Excel file to upload.", "warning")
        return redirect(url_for("dashboard"))
    if not file.filename.lower().endswith((".xlsx", ".xlsm", ".xls")):
        flash("Only Excel files are supported.", "danger")
        return redirect(url_for("dashboard"))
    DATA_DIR.mkdir(exist_ok=True)
    stored = DATA_DIR / f"{uuid4().hex}_{file.filename}"
    file.save(stored)
    rows = load_excel_to_rows(stored)
    replace_courses(rows, file.filename, str(stored))
    flash(f"Imported {len(rows)} courses from {file.filename}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/refresh", methods=["POST"])
def refresh():
    latest = fetch_one("SELECT stored_path, filename FROM upload_history ORDER BY uploaded_at DESC, id DESC LIMIT 1")
    source = Path(latest["stored_path"]) if latest else DEFAULT_EXCEL
    rows = load_excel_to_rows(source)
    replace_courses(rows, latest["filename"] if latest else source.name, str(source))
    flash(f"Dashboard refreshed from {source.name}.", "success")
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/courses/<int:course_id>/update", methods=["POST"])
def update_course(course_id: int):
    execute(
        "UPDATE courses SET status_override = ?, user_remarks = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (request.form.get("status_override") or None, request.form.get("user_remarks") or None, course_id),
    )
    flash("Course status updated.", "success")
    return redirect(request.referrer or url_for("courses"))


@app.route("/export")
def export():
    rows = [dict(r) for r in filtered_courses()]
    df = pd.DataFrame(rows)
    export_type = request.args.get("type", "csv")
    if export_type == "xlsx":
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Courses")
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name="skt_courses_filtered.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    buffer = BytesIO(df.to_csv(index=False).encode("utf-8-sig"))
    return send_file(buffer, as_attachment=True, download_name="skt_courses_filtered.csv", mimetype="text/csv")


if __name__ == "__main__":
    bootstrap_data()
    app.run(debug=True, host="127.0.0.1", port=5000)
else:
    bootstrap_data()
