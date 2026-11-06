"""Tiny DuckDB store used by every version of the server.

Every note has an owner. In v1/v2 the owner is always "local".
In v3 the owner is the user id that Descope puts in the token (the `sub` claim),
which is what gives every user their own private notes.
"""

from pathlib import Path

import duckdb

DB_PATH = Path(__file__).parent / "notes.duckdb"

# Write the file in DuckDB's v1.0 storage format (version 64) instead of the
# DuckDB 2.0 default (version 999), so older readers such as the VS Code
# "DuckDB Viewer" extension can still open notes.duckdb.
DUCKDB_CONFIG = {"storage_compatibility_version": "v1.0.0"}


def _conn() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(str(DB_PATH), config=DUCKDB_CONFIG)
    conn.execute("CREATE SEQUENCE IF NOT EXISTS notes_id_seq START 1")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS notes ("
        "id INTEGER PRIMARY KEY DEFAULT nextval('notes_id_seq'), "
        "owner TEXT NOT NULL, text TEXT NOT NULL, "
        "created_at TIMESTAMP DEFAULT current_timestamp)"
    )
    return conn


def _rows_to_dicts(cur: duckdb.DuckDBPyConnection) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def list_notes(owner: str) -> list[dict]:
    with _conn() as conn:
        cur = conn.execute(
            "SELECT id, text, CAST(created_at AS VARCHAR) AS created_at "
            "FROM notes WHERE owner = ? ORDER BY id",
            [owner],
        )
        return _rows_to_dicts(cur)


def add_note(owner: str, text: str) -> dict:
    with _conn() as conn:
        (note_id,) = conn.execute(
            "INSERT INTO notes (owner, text) VALUES (?, ?) RETURNING id", [owner, text]
        ).fetchone()
    return {"id": note_id, "text": text}


def delete_note(owner: str, note_id: int) -> bool:
    with _conn() as conn:
        deleted = conn.execute(
            "DELETE FROM notes WHERE owner = ? AND id = ? RETURNING id", [owner, note_id]
        ).fetchall()
    return len(deleted) > 0
