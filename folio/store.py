"""SQLite persistence with explicit, caller-owned transactions."""
import json
import sqlite3
from contextlib import contextmanager

from .models import Document

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    collection TEXT NOT NULL,
    key TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tags TEXT NOT NULL,
    PRIMARY KEY (collection, key)
)
"""


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute(SCHEMA)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        if self.db.in_transaction:
            raise RuntimeError("nested transactions are unsupported")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def put(self, document):
        self.db.execute(
            """INSERT INTO documents VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(collection, key) DO UPDATE SET
               title=excluded.title, body=excluded.body, tags=excluded.tags""",
            (document.collection, document.key, document.title,
             document.body, json.dumps(document.tags)),
        )

    @staticmethod
    def decode(row):
        collection, key, title, body, tags = row
        return Document(collection, key, title, body, tuple(json.loads(tags)))

    def get(self, collection, key):
        row = self.db.execute(
            "SELECT collection, key, title, body, tags FROM documents "
            "WHERE collection = ? AND key = ?", (collection, key),
        ).fetchone()
        return self.decode(row) if row is not None else None

    def documents(self, collection):
        rows = self.db.execute(
            "SELECT collection, key, title, body, tags FROM documents "
            "WHERE collection = ? ORDER BY key", (collection,),
        )
        return [self.decode(row) for row in rows]

    def remove(self, collection, key):
        cursor = self.db.execute(
            "DELETE FROM documents WHERE collection = ? AND key = ?",
            (collection, key),
        )
        return cursor.rowcount == 1
