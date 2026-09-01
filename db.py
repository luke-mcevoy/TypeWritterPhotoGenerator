import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "carriage.db")
POSTS_DIR = os.path.join(DATA_DIR, "posts")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(POSTS_DIR, exist_ok=True)


def connect() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                caption TEXT NOT NULL DEFAULT '',
                image_name TEXT NOT NULL,
                source_name TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS likes (
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (post_id, user_id),
                FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        cols = {row["name"] for row in db.execute("PRAGMA table_info(posts)").fetchall()}
        if "source_name" not in cols:
            db.execute("ALTER TABLE posts ADD COLUMN source_name TEXT")


def create_user(username: str, display_name: str, password: str) -> sqlite3.Row:
    with get_db() as db:
        cur = db.execute(
            """
            INSERT INTO users (username, display_name, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (username, display_name, generate_password_hash(password), utcnow()),
        )
        return db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()


def get_user_by_id(user_id: int):
    with get_db() as db:
        return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_username(username: str):
    with get_db() as db:
        return db.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone()


def verify_login(username: str, password: str):
    user = get_user_by_username(username)
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


def _post_query(where: str = "", extra: str = "") -> str:
    return f"""
        SELECT
            posts.id,
            posts.caption,
            posts.image_name,
            posts.source_name,
            posts.created_at,
            users.username,
            users.display_name,
            (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count
            {extra}
        FROM posts
        JOIN users ON users.id = posts.user_id
        {where}
        ORDER BY posts.id DESC
    """


def list_posts(viewer_id=None, username=None, limit=60):
    extra = ""
    params: list = []
    if viewer_id:
        extra = """,
            EXISTS(
                SELECT 1 FROM likes
                WHERE likes.post_id = posts.id AND likes.user_id = ?
            ) AS liked
        """
        params.append(viewer_id)
    where = ""
    if username:
        where = "WHERE users.username = ? COLLATE NOCASE"
        params.append(username)
    params.append(limit)
    with get_db() as db:
        return db.execute(_post_query(where, extra) + " LIMIT ?", params).fetchall()


def get_post(post_id: int, viewer_id=None):
    extra = ""
    params: list = []
    if viewer_id:
        extra = """,
            EXISTS(
                SELECT 1 FROM likes
                WHERE likes.post_id = posts.id AND likes.user_id = ?
            ) AS liked
        """
        params.append(viewer_id)
    params.append(post_id)
    with get_db() as db:
        return db.execute(
            _post_query("WHERE posts.id = ?", extra), params
        ).fetchone()


def create_post(user_id: int, caption: str, image_name: str, source_name: str | None) -> int:
    with get_db() as db:
        cur = db.execute(
            """
            INSERT INTO posts (user_id, caption, image_name, source_name, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, caption, image_name, source_name, utcnow()),
        )
        return int(cur.lastrowid)


def delete_post(post_id: int, user_id: int):
    with get_db() as db:
        row = db.execute(
            "SELECT image_name, source_name FROM posts WHERE id = ? AND user_id = ?",
            (post_id, user_id),
        ).fetchone()
        if not row:
            return None
        db.execute("DELETE FROM posts WHERE id = ? AND user_id = ?", (post_id, user_id))
        return row


def toggle_like(post_id: int, user_id: int) -> dict:
    with get_db() as db:
        exists = db.execute(
            "SELECT 1 FROM likes WHERE post_id = ? AND user_id = ?",
            (post_id, user_id),
        ).fetchone()
        if exists:
            db.execute(
                "DELETE FROM likes WHERE post_id = ? AND user_id = ?",
                (post_id, user_id),
            )
            liked = False
        else:
            db.execute(
                "INSERT INTO likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
                (post_id, user_id, utcnow()),
            )
            liked = True
        count = db.execute(
            "SELECT COUNT(*) AS n FROM likes WHERE post_id = ?", (post_id,)
        ).fetchone()["n"]
        return {"liked": liked, "like_count": count}


def post_count(user_id: int) -> int:
    with get_db() as db:
        return db.execute(
            "SELECT COUNT(*) AS n FROM posts WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]
