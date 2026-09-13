"""Small SQLite store. Every write is transactional; quantities come from batches."""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import uuid

ROOT = Path(__file__).parent

def now():
    return datetime.now(timezone.utc).isoformat()

def uid():
    return str(uuid.uuid4())

def connect(path):
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=15000')
    return db

def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript((ROOT / 'schema.sql').read_text())

def rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]

def one(db, sql, args=()):
    r = db.execute(sql, args).fetchone()
    return dict(r) if r else None

def balance(db, item):
    return round(db.execute('SELECT COALESCE(SUM(qty),0) FROM batches WHERE item=?', (item,)).fetchone()[0], 6)

def backup(path):
    folder = Path(path).parent / 'backups'
    folder.mkdir(exist_ok=True)
    target = folder / (now()[:10] + '.sqlite')
    with connect(path) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
