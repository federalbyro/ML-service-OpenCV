import sqlite3
from typing import Any, Iterable

DB = "database.db"

def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(clear_events: bool = True, clear_attendance: bool = False, clear_participants: bool = True):
    conn = get_conn()
    c = conn.cursor()

    # админ только для входа в /admin
    c.execute("""
    CREATE TABLE IF NOT EXISTS admin(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # участники = одна сущность
    c.execute("""
CREATE TABLE IF NOT EXISTS participants(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT UNIQUE NOT NULL,
    name TEXT,
    photo_blob BLOB NOT NULL,
    photo_ext TEXT NOT NULL,
    photo_mime TEXT NOT NULL
)
""")


    # мероприятия
    c.execute("""
    CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL
    )
    """)

    # журнал
    c.execute("""
    CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participant_id INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        match_score REAL,
        FOREIGN KEY(participant_id) REFERENCES participants(id),
        FOREIGN KEY(event_id) REFERENCES events(id),
        UNIQUE(participant_id, event_id)
    )
    """)

    # seed admin
    c.execute("SELECT 1 FROM admin WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO admin(username,password) VALUES (?,?)", ("admin", "admin"))

    if clear_events:
        c.execute("DELETE FROM events")    
    if clear_participants:
        c.execute("DELETE FROM participants")
    if clear_attendance:
        c.execute("DELETE FROM attendance")

    conn.commit()
    conn.close()

def query(sql: str, params: Iterable[Any] = (), fetch: bool = False):
    conn = get_conn()
    c = conn.cursor()
    c.execute(sql, tuple(params))
    data = c.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return data
