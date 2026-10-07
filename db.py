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

        # One row per person per round: which team they were put on.
        # This is the history of who worked with who.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS round_teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_id INTEGER NOT NULL REFERENCES rounds(id),
                team_number INTEGER NOT NULL,
                user_id INTEGER NOT NULL
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
    """Pick a random project that hasn't been used yet (None if all are used).

    This only PICKS a project. Call mark_project_used() after the announcement
    has actually been posted, so a failed post doesn't waste a project.
    """
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM projects WHERE used = 0 ORDER BY RANDOM() LIMIT 1"
        ).fetchone()


def mark_project_used(project_id):
    """Mark a project as used so it won't be drawn again."""
    with get_connection() as conn:
        conn.execute("UPDATE projects SET used = 1 WHERE id = ?", (project_id,))

def create_round(project_id, message_id):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO rounds (project_id, message_id) VALUES (?, ?)",
            (project_id, message_id),
        )


def get_open_round_by_message(message_id):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM rounds WHERE message_id = ? AND status = 'open'",
            (message_id,),
        ).fetchone()


def get_latest_open_round():
    """Return the most recent round still open for sign-ups, or None."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM rounds WHERE status = 'open' ORDER BY id DESC LIMIT 1"
        ).fetchone()


def get_project(project_id):
    """Return one project row by its id."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()


def close_round(round_id):
    """Mark a round closed so late reactions on its announcement are ignored."""
    with get_connection() as conn:
        conn.execute("UPDATE rounds SET status = 'closed' WHERE id = ?", (round_id,))


def close_all_open_rounds():
    """Close every open round (used by /reset-round)."""
    with get_connection() as conn:
        conn.execute("UPDATE rounds SET status = 'closed' WHERE status = 'open'")


def save_teams(round_id, teams):
    """Save the teams for a round. `teams` is a list of lists of Discord user ids."""
    with get_connection() as conn:
        for team_number, user_ids in enumerate(teams, start=1):
            for user_id in user_ids:
                conn.execute(
                    "INSERT INTO round_teams (round_id, team_number, user_id) VALUES (?, ?, ?)",
                    (round_id, team_number, user_id),
                )
