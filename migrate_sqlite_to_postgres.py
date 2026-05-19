from __future__ import annotations

import sqlite3
from pathlib import Path

import psycopg

from db import DB_PATH, get_database_url, init_db


def main() -> None:
    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("Set DATABASE_URL before running this migration.")

    if not Path(DB_PATH).exists():
        raise RuntimeError(f"Local SQLite database not found at {DB_PATH}.")

    sqlite_connection = sqlite3.connect(DB_PATH)
    sqlite_connection.row_factory = sqlite3.Row

    postgres_connection = psycopg.connect(database_url)
    try:
        init_db()

        sqlite_students = sqlite_connection.execute(
            "SELECT name, usn, email FROM students ORDER BY id ASC"
        ).fetchall()
        sqlite_scores = sqlite_connection.execute(
            "SELECT usn, score, mode, date FROM scores ORDER BY id ASC"
        ).fetchall()

        with postgres_connection.cursor() as cursor:
            for row in sqlite_students:
                cursor.execute(
                    """
                    INSERT INTO students (name, usn, email)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (usn)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email
                    """,
                    (row["name"], row["usn"], row["email"]),
                )

            for row in sqlite_scores:
                cursor.execute(
                    """
                    INSERT INTO scores (usn, score, mode, date)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (row["usn"], int(row["score"]), row["mode"], row["date"]),
                )

        postgres_connection.commit()
        print(
            f"Migrated {len(sqlite_students)} students and {len(sqlite_scores)} scores to Postgres successfully."
        )
    finally:
        sqlite_connection.close()
        postgres_connection.close()


if __name__ == "__main__":
    main()
