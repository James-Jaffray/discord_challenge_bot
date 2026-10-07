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

def load_projects(csv_path="projects.csv"):
    with get_connection() as conn, open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            conn.execute(
                "INSERT OR IGNORE INTO projects (name, description, skills) VALUES (?, ?, ?)",
                (row["name"], row["description"], row["skills"]),
            )