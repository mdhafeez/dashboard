from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "database" / "skt_dashboard.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_sheet TEXT,
                source_row INTEGER,
                course_title TEXT NOT NULL,
                course_type TEXT,
                collaboration_type TEXT,
                planned_start_date TEXT,
                planned_end_date TEXT,
                actual_start_date TEXT,
                actual_end_date TEXT,
                days INTEGER,
                month TEXT,
                month_year TEXT,
                target_participants REAL DEFAULT 0,
                actual_participants REAL,
                target_group TEXT,
                budget REAL DEFAULT 0,
                section TEXT,
                coordinator TEXT,
                paid_status TEXT,
                source_status TEXT,
                status TEXT,
                remarks TEXT,
                mode TEXT,
                secretary TEXT,
                level TEXT,
                bitara_program TEXT,
                cluster_training TEXT,
                focus_area TEXT,
                psp_category TEXT,
                status_override TEXT,
                user_remarks TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS coordinators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS psp_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS course_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS upload_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                rows_imported INTEGER NOT NULL,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def replace_courses(rows: list[dict], filename: str, stored_path: str) -> int:
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM courses")
        if rows:
            cols = list(rows[0].keys())
            placeholders = ", ".join(["?"] * len(cols))
            sql = f"INSERT INTO courses ({', '.join(cols)}) VALUES ({placeholders})"
            conn.executemany(sql, [[row.get(col) for col in cols] for row in rows])
        _refresh_lookup_tables(conn)
        conn.execute(
            "INSERT INTO upload_history (filename, stored_path, rows_imported) VALUES (?, ?, ?)",
            (filename, stored_path, len(rows)),
        )
        return len(rows)


def _refresh_lookup_tables(conn: sqlite3.Connection) -> None:
    for status in ["Completed", "Upcoming", "In Progress", "Delayed", "No Update", "Dropped", "Mode Changed"]:
        conn.execute("INSERT OR IGNORE INTO course_status (name) VALUES (?)", (status,))

    lookup_map = {
        "sections": "section",
        "coordinators": "coordinator",
        "psp_categories": "psp_category",
    }
    for table, column in lookup_map.items():
        conn.execute(f"DELETE FROM {table}")
        rows = conn.execute(
            f"SELECT DISTINCT TRIM({column}) AS value FROM courses "
            f"WHERE {column} IS NOT NULL AND TRIM({column}) <> '' ORDER BY value"
        ).fetchall()
        conn.executemany(f"INSERT OR IGNORE INTO {table} (name) VALUES (?)", [(r["value"],) for r in rows])


def fetch_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: tuple = ()) -> None:
    with get_connection() as conn:
        conn.execute(sql, params)
