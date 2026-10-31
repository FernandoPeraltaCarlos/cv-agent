import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from .errors import APIError


class ResponseStore:
    def __init__(self, path: Path, ttl: int, maximum: int = 2000):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.ttl, self.maximum = path, ttl, maximum
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS responses (id TEXT PRIMARY KEY, owner TEXT NOT NULL, expires INTEGER NOT NULL, history TEXT NOT NULL, response TEXT NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS responses_expiry ON responses(expires)")
            db.execute("DELETE FROM responses WHERE expires <= ?", (int(time.time()),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=3)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA secure_delete=ON")
            with db:
                yield db
        finally:
            db.close()

    def save(self, owner: str, response: dict, history: list[dict]):
        now = int(time.time())
        with self.connect() as db:
            db.execute("DELETE FROM responses WHERE expires <= ?", (now,))
            db.execute(
                "INSERT INTO responses VALUES (?, ?, ?, ?, ?)",
                (response["id"], owner, now + self.ttl, json.dumps(history), json.dumps(response)),
            )
            db.execute(
                "DELETE FROM responses WHERE id IN (SELECT id FROM responses ORDER BY expires DESC, rowid DESC LIMIT -1 OFFSET ?)",
                (self.maximum,),
            )

    def get(self, owner: str, response_id: str) -> tuple[list[dict], dict]:
        with self.connect() as db:
            db.execute("DELETE FROM responses WHERE expires <= ?", (int(time.time()),))
            row = db.execute(
                "SELECT history, response FROM responses WHERE id=? AND owner=?",
                (response_id, owner),
            ).fetchone()
        if row is None:
            raise APIError(
                404,
                "previous_response_not_found",
                "Response not found, expired, or unavailable for this credential.",
                "previous_response_id",
            )
        return json.loads(row[0]), json.loads(row[1])

    def delete(self, owner: str, response_id: str):
        self.get(owner, response_id)
        with self.connect() as db:
            db.execute("DELETE FROM responses WHERE id=? AND owner=?", (response_id, owner))
