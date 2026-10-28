import sqlite3
from pathlib import Path


class InvestigationStore:
    def __init__(self, path="payguard.db"):
        self.path = str(path)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS investigations (transaction_id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'Open', note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")

    def _connect(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path)

    def list_all(self):
        with self._connect() as db:
            return {row[0]: {"status": row[1], "note": row[2], "updated_at": row[3]} for row in db.execute("SELECT transaction_id,status,note,updated_at FROM investigations")}

    def save(self, transaction_id, status, note):
        with self._connect() as db:
            db.execute("INSERT INTO investigations(transaction_id,status,note,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(transaction_id) DO UPDATE SET status=excluded.status,note=excluded.note,updated_at=CURRENT_TIMESTAMP", (str(transaction_id), status, note[:2000]))

