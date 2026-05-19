from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, Sequence
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - optional in local SQLite-only setups
    psycopg = None
    dict_row = None

DB_PATH = Path(__file__).with_name("interview.db")
IST = ZoneInfo("Asia/Kolkata")
DISPLAY_TIME_FORMAT = "%d %b %Y, %I:%M %p"


def _read_secret(name: str) -> str:
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name]).strip()

        database_section = st.secrets.get("database")
        if database_section is not None and hasattr(database_section, "get"):
            nested_value = database_section.get(name.lower())
            if nested_value:
                return str(nested_value).strip()
    except Exception:
        pass
    return ""


def get_database_url() -> str:
    return (
        os.getenv("DATABASE_URL", "").strip()
        or os.getenv("SUPABASE_DB_URL", "").strip()
        or _read_secret("DATABASE_URL")
        or _read_secret("SUPABASE_DB_URL")
        or _read_secret("url")
    )


def using_postgres() -> bool:
    return bool(get_database_url())


def get_database_runtime_warning() -> str:
    if using_postgres():
        if psycopg is None:
            return "Postgres is configured, but the psycopg dependency is unavailable. Reinstall requirements before deploying."
        return ""

    return (
        "DATABASE_URL is not configured. The app is using local SQLite storage. "
        "This is fine for local development, but Streamlit Cloud data may not persist between rebuilds."
    )


def _sqlite_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _postgres_connection():
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    if psycopg is None:
        raise RuntimeError("Postgres support requires psycopg. Install requirements.txt first.")
    return psycopg.connect(database_url, row_factory=dict_row)


@contextmanager
def get_connection() -> Iterator[object]:
    connection = _postgres_connection() if using_postgres() else _sqlite_connection()
    try:
        yield connection
    finally:
        connection.close()


def current_ist_time() -> datetime:
    return datetime.now(IST)


def format_timestamp(value: object) -> str:
    if value in (None, ""):
        return ""

    if isinstance(value, datetime):
        timestamp = value
    else:
        text = str(value).strip()
        if not text:
            return ""
        for pattern in (DISPLAY_TIME_FORMAT, "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S%z"):
            try:
                timestamp = datetime.strptime(text, pattern)
                break
            except ValueError:
                timestamp = None
        else:
            try:
                timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return text

    if timestamp is None:
        return ""

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))

    return timestamp.astimezone(IST).strftime(DISPLAY_TIME_FORMAT)


def format_timestamp_column(dataframe: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    if column not in dataframe.columns:
        return dataframe
    formatted = dataframe.copy()
    formatted[column] = formatted[column].apply(format_timestamp)
    return formatted


def _run_statement(sqlite_query: str, postgres_query: str, params: Sequence[object] = ()) -> None:
    with get_connection() as connection:
        cursor = connection.cursor()
        if using_postgres():
            cursor.execute(postgres_query, params)
        else:
            cursor.execute(sqlite_query, params)
        connection.commit()


def _query_dataframe(
    sqlite_query: str,
    postgres_query: str,
    params: Sequence[object] = (),
) -> pd.DataFrame:
    with get_connection() as connection:
        cursor = connection.cursor()
        if using_postgres():
            cursor.execute(postgres_query, params)
        else:
            cursor.execute(sqlite_query, params)

        rows = cursor.fetchall()
        if not rows:
            columns = [
                column.name if hasattr(column, "name") else column[0]
                for column in cursor.description
            ] if cursor.description else []
            return pd.DataFrame(columns=columns)

        if using_postgres():
            return pd.DataFrame(rows)

        return pd.DataFrame([dict(row) for row in rows])


def init_db() -> None:
    sqlite_schema = [
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            usn TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usn TEXT NOT NULL,
            score INTEGER NOT NULL,
            mode TEXT NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (usn) REFERENCES students(usn) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_scores_usn ON scores(usn)",
    ]

    postgres_schema = [
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name TEXT NOT NULL,
            usn TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            usn TEXT NOT NULL REFERENCES students(usn) ON DELETE CASCADE,
            score INTEGER NOT NULL,
            mode TEXT NOT NULL,
            date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_scores_usn ON scores(usn)",
    ]

    schema = postgres_schema if using_postgres() else sqlite_schema
    with get_connection() as connection:
        cursor = connection.cursor()
        for statement in schema:
            cursor.execute(statement)
        connection.commit()


def ensure_student(name: str, usn: str, email: str) -> None:
    normalized_usn = usn.strip().lower()
    normalized_name = name.strip()
    normalized_email = email.strip().lower()

    if using_postgres():
        _run_statement(
            "",
            """
            INSERT INTO students (name, usn, email)
            VALUES (%s, %s, %s)
            ON CONFLICT (usn)
            DO UPDATE SET
                name = EXCLUDED.name,
                email = EXCLUDED.email
            """,
            (normalized_name, normalized_usn, normalized_email),
        )
        return

    _run_statement(
        """
        INSERT INTO students (name, usn, email)
        VALUES (?, ?, ?)
        ON CONFLICT(usn)
        DO UPDATE SET
            name = excluded.name,
            email = excluded.email
        """,
        "",
        (normalized_name, normalized_usn, normalized_email),
    )


def insert_score(usn: str, score: int, mode: str, date: Optional[str] = None) -> None:
    normalized_usn = usn.strip().lower()
    attempt_date = date or current_ist_time().isoformat()

    if using_postgres():
        timestamp = current_ist_time() if date is None else datetime.fromisoformat(str(date).replace("Z", "+00:00"))
        _run_statement(
            "",
            "INSERT INTO scores (usn, score, mode, date) VALUES (%s, %s, %s, %s)",
            (normalized_usn, int(score), mode, timestamp),
        )
        return

    _run_statement(
        "INSERT INTO scores (usn, score, mode, date) VALUES (?, ?, ?, ?)",
        "",
        (normalized_usn, int(score), mode, attempt_date),
    )


def load_student_records(usn: str) -> pd.DataFrame:
    normalized_usn = usn.strip().lower()
    dataframe = _query_dataframe(
        """
        SELECT students.name, students.usn, students.email, scores.score, scores.mode, scores.date
        FROM students
        LEFT JOIN scores ON students.usn = scores.usn
        WHERE students.usn = ?
        ORDER BY scores.id DESC
        """,
        """
        SELECT students.name, students.usn, students.email, scores.score, scores.mode, scores.date
        FROM students
        LEFT JOIN scores ON students.usn = scores.usn
        WHERE students.usn = %s
        ORDER BY scores.id DESC NULLS LAST
        """,
        (normalized_usn,),
    )
    return format_timestamp_column(dataframe)


def fetch_student_summary() -> pd.DataFrame:
    return _query_dataframe(
        """
        SELECT
            students.name,
            students.usn,
            students.email,
            COUNT(scores.id) AS total_attempts,
            ROUND(COALESCE(AVG(scores.score), 0), 2) AS average_score
        FROM students
        LEFT JOIN scores ON students.usn = scores.usn
        GROUP BY students.usn, students.name, students.email
        ORDER BY LOWER(students.name) ASC
        """,
        """
        SELECT
            students.name,
            students.usn,
            students.email,
            COUNT(scores.id) AS total_attempts,
            ROUND(COALESCE(AVG(scores.score), 0)::numeric, 2) AS average_score
        FROM students
        LEFT JOIN scores ON students.usn = scores.usn
        GROUP BY students.usn, students.name, students.email
        ORDER BY LOWER(students.name) ASC
        """,
    )


def fetch_joined_records() -> pd.DataFrame:
    dataframe = _query_dataframe(
        """
        SELECT
            students.name,
            students.usn,
            students.email,
            scores.score,
            scores.mode,
            scores.date
        FROM students
        LEFT JOIN scores ON students.usn = scores.usn
        ORDER BY scores.id DESC, LOWER(students.name) ASC
        """,
        """
        SELECT
            students.name,
            students.usn,
            students.email,
            scores.score,
            scores.mode,
            scores.date
        FROM students
        LEFT JOIN scores ON students.usn = scores.usn
        ORDER BY scores.id DESC NULLS LAST, LOWER(students.name) ASC
        """,
    )
    return format_timestamp_column(dataframe)


def fetch_leaderboard(limit: int = 10) -> pd.DataFrame:
    safe_limit = max(1, int(limit))
    dataframe = _query_dataframe(
        f"""
        SELECT
            students.name,
            students.usn,
            MAX(scores.score) AS best_score,
            ROUND(COALESCE(AVG(scores.score), 0), 2) AS average_score,
            COUNT(scores.id) AS total_attempts,
            COALESCE(
                (
                    SELECT latest_scores.date
                    FROM scores AS latest_scores
                    WHERE latest_scores.usn = students.usn
                    ORDER BY latest_scores.id DESC
                    LIMIT 1
                ),
                ''
            ) AS last_attempt
        FROM students
        LEFT JOIN scores ON students.usn = scores.usn
        GROUP BY students.usn, students.name
        ORDER BY best_score DESC, average_score DESC, LOWER(students.name) ASC
        LIMIT {safe_limit}
        """,
        """
        SELECT
            students.name,
            students.usn,
            MAX(scores.score) AS best_score,
            ROUND(COALESCE(AVG(scores.score), 0)::numeric, 2) AS average_score,
            COUNT(scores.id) AS total_attempts,
            COALESCE(
                (
                    SELECT latest_scores.date
                    FROM scores AS latest_scores
                    WHERE latest_scores.usn = students.usn
                    ORDER BY latest_scores.id DESC
                    LIMIT 1
                ),
                NULL
            ) AS last_attempt
        FROM students
        LEFT JOIN scores ON students.usn = scores.usn
        GROUP BY students.usn, students.name
        ORDER BY best_score DESC NULLS LAST, average_score DESC, LOWER(students.name) ASC
        LIMIT %s
        """,
        (safe_limit,) if using_postgres() else (),
    )
    return format_timestamp_column(dataframe, column="last_attempt")


def delete_student_by_usn(usn: str) -> bool:
    normalized_usn = usn.strip().lower()
    if not normalized_usn:
        return False

    with get_connection() as connection:
        cursor = connection.cursor()
        if using_postgres():
            cursor.execute("SELECT usn FROM students WHERE usn = %s", (normalized_usn,))
        else:
            cursor.execute("SELECT usn FROM students WHERE usn = ?", (normalized_usn,))
        existing = cursor.fetchone()
        if existing is None:
            return False

        if using_postgres():
            cursor.execute("DELETE FROM students WHERE usn = %s", (normalized_usn,))
        else:
            cursor.execute("DELETE FROM students WHERE usn = ?", (normalized_usn,))
        connection.commit()
        return True


def reset_database() -> None:
    with get_connection() as connection:
        cursor = connection.cursor()
        if using_postgres():
            cursor.execute("TRUNCATE TABLE scores, students RESTART IDENTITY CASCADE")
        else:
            cursor.execute("DELETE FROM scores")
            cursor.execute("DELETE FROM students")
        connection.commit()
