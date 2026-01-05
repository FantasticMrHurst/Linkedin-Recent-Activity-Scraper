import atexit
import os
import sqlite3
from datetime import datetime
from typing import List, Tuple

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, flash, redirect, render_template, request, url_for

from scraper import scrape_profile_posts

DATABASE_PATH = os.environ.get("SCRAPER_DB_PATH", "app.db")
PLAYWRIGHT_STATE = os.environ.get("PLAYWRIGHT_STORAGE", "playwright_state.json")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                name TEXT,
                last_checked TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                post_url TEXT NOT NULL,
                posted_at TEXT,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                reposts INTEGER DEFAULT 0,
                scraped_at TEXT NOT NULL,
                UNIQUE(profile_id, post_url),
                FOREIGN KEY(profile_id) REFERENCES profiles(id)
            )
            """
        )


def add_profile(url: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO profiles (url, last_checked) VALUES (?, ?)",
            (url, None),
        )


def update_profile(profile_id: int, name: str) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE profiles SET name = ?, last_checked = ? WHERE id = ?",
            (name, datetime.utcnow().isoformat(), profile_id),
        )


def store_posts(profile_id: int, posts: List[dict]) -> None:
    with get_db() as conn:
        for post in posts:
            conn.execute(
                """
                INSERT OR REPLACE INTO posts
                    (profile_id, post_url, posted_at, likes, comments, reposts, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_id,
                    post["post_url"],
                    post.get("posted_at"),
                    post.get("likes", 0),
                    post.get("comments", 0),
                    post.get("reposts", 0),
                    post.get("scraped_at", datetime.utcnow().isoformat()),
                ),
            )


def get_profiles() -> List[sqlite3.Row]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, url, name, last_checked FROM profiles ORDER BY id DESC"
        ).fetchall()
    return rows


def get_recent_posts(limit: int = 25) -> List[sqlite3.Row]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT posts.*, profiles.name as profile_name, profiles.url as profile_url
            FROM posts
            JOIN profiles ON posts.profile_id = profiles.id
            ORDER BY posts.scraped_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return rows


def run_profile_scrape(profile_row: sqlite3.Row) -> Tuple[str, List[dict]]:
    name, posts = scrape_profile_posts(
        profile_row["url"], storage_state_path=PLAYWRIGHT_STATE
    )
    update_profile(profile_row["id"], name)
    store_posts(profile_row["id"], posts)
    return name, posts


def check_all_profiles() -> None:
    for profile in get_profiles():
        try:
            run_profile_scrape(profile)
        except Exception as exc:  # pragma: no cover - log friendly output
            print(f"Failed to scrape {profile['url']}: {exc}")


@app.route("/", methods=["GET"])
def index():
    profiles = get_profiles()
    posts = get_recent_posts()
    return render_template("index.html", profiles=profiles, posts=posts)


@app.post("/profiles")
def create_profile():
    url = request.form.get("url", "").strip()
    if not url:
        flash("Please provide a LinkedIn profile URL.")
        return redirect(url_for("index"))
    add_profile(url)
    flash("Profile added. Click Check Now to fetch posts.")
    return redirect(url_for("index"))


@app.post("/check")
def check_now():
    try:
        check_all_profiles()
        flash("Scrape completed.")
    except Exception as exc:
        flash(f"Scrape failed: {exc}")
    return redirect(url_for("index"))


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(check_all_profiles, "interval", days=1, id="daily-scrape")
    scheduler.start()
    return scheduler


init_db()
scheduler = start_scheduler()
atexit.register(lambda: scheduler.shutdown(wait=False))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
