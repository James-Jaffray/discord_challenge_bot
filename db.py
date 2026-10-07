import os
import sqlite3
import csv

# Where the database file lives. Locally this is just "challenge.db" next to the code.
# In Docker we set DB_PATH=/data/challenge.db so the file is kept on a volume
# and survives rebuilding or replacing the container.
DB_PATH = os.getenv("DB_PATH", "challenge.db")


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
    """Fill the projects table from the CSV, but ONLY if the table is empty.

    The CSV is just the starting list. After the first run the database is the
    source of truth, so projects you remove with /remove-project can't come
    back when the bot restarts. Manage the list with /add-project and /remove-project.
    """
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        if count > 0:
            return  # already seeded, leave the list alone

        with open(csv_path, newline="", encoding="utf-8") as f:
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


def list_projects():
    """Return every project (oldest first), including whether it's been used."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, name, description, skills, used FROM projects ORDER BY id"
        ).fetchall()


def add_project(name, description, skills):
    """Add a project. Returns False if one with that name already exists."""
    with get_connection() as conn:
        # Compare in lowercase so "Digital Pet" and "digital pet" count as duplicates
        existing = conn.execute(
            "SELECT 1 FROM projects WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if existing is not None:
            return False
        conn.execute(
            "INSERT INTO projects (name, description, skills) VALUES (?, ?, ?)",
            (name, description, skills),
        )
        return True


def remove_project(name):
    """Remove an UNUSED project by name.

    Returns "removed", "not_found", or "used". Used projects can't be removed
    because past rounds point to them (they're part of the history).
    """
    with get_connection() as conn:
        project = conn.execute(
            "SELECT id, used FROM projects WHERE LOWER(name) = LOWER(?)", (name,)
        ).fetchone()
        if project is None:
            return "not_found"

        # Refuse if it's been used, or if any round references it
        in_a_round = conn.execute(
            "SELECT 1 FROM rounds WHERE project_id = ?", (project["id"],)
        ).fetchone()
        if project["used"] == 1 or in_a_round is not None:
            return "used"

        conn.execute("DELETE FROM projects WHERE id = ?", (project["id"],))
        return "removed"
