import sqlite3
import csv

DB_PATH = "challenge.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                skills TEXT,
                used INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                message_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

def load_projects(csv_path="projects.csv"):
    with get_connection() as conn, open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            conn.execute(
                "INSERT OR IGNORE INTO projects (name, description, skills) VALUES (?, ?, ?)",
                (row["name"], row["description"], row["skills"]),
            )

def draw_project():
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE used = 0 ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        conn.execute("UPDATE projects SET used = 1 WHERE id = ?", (row["id"],))
        return row

def create_round(project_id, message_id):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO rounds (project_id, message_id) VALUES (?, ?)",
            (project_id, message_id),
        )