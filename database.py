import os
import sqlite3
from datetime import date

if os.name == 'nt':
    DB_PATH = 'attendance.db'
else:
    DB_PATH = os.environ.get('ATTENDANCE_DB_PATH', '/tmp/attendance.db')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT    NOT NULL,
            embedding  BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS face_samples (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            embedding  BLOB    NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id        INTEGER NOT NULL,
            date           TEXT    NOT NULL,
            timestamp      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status         TEXT    DEFAULT 'on_time',
            check_in_time  TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    # Default schedule settings
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('check_in_time', '09:00')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('check_out_time', '17:00')")
    # Migrate: add status/check_in_time cols to existing attendance table
    c.execute("PRAGMA table_info(attendance)")
    existing_cols = [row[1] for row in c.fetchall()]
    if 'status' not in existing_cols:
        c.execute("ALTER TABLE attendance ADD COLUMN status TEXT DEFAULT 'on_time'")
    if 'check_in_time' not in existing_cols:
        c.execute("ALTER TABLE attendance ADD COLUMN check_in_time TEXT")
    # Migrate legacy single embeddings into face_samples
    c.execute('SELECT id, embedding FROM users WHERE embedding IS NOT NULL')
    for uid, emb in c.fetchall():
        c.execute('SELECT COUNT(*) FROM face_samples WHERE user_id = ?', (uid,))
        if c.fetchone()[0] == 0:
            c.execute('INSERT INTO face_samples (user_id, embedding) VALUES (?, ?)', (uid, emb))

    # Migrate: make users.embedding nullable if it was created as NOT NULL
    c.execute("PRAGMA table_info(users)")
    users_cols = {row[1]: row for row in c.fetchall()}
    embedding_col = users_cols.get('embedding')
    # notnull flag is index 3; if it's 1 the column is NOT NULL — recreate table
    if embedding_col and embedding_col[3] == 1:
        c.execute('''
            CREATE TABLE users_new (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT    NOT NULL,
                embedding  BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('INSERT INTO users_new SELECT id, name, embedding, created_at FROM users')
        c.execute('DROP TABLE users')
        c.execute('ALTER TABLE users_new RENAME TO users')
    conn.commit()
    conn.close()


def add_user(name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO users (name) VALUES (?)', (name,))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return user_id


def add_face_sample(user_id, embedding):
    # Store a record in face_samples so sample counts are reflected in the UI.
    # Embedding may be None in lightweight mode.
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO face_samples (user_id, embedding) VALUES (?, ?)', (user_id, embedding if embedding is not None else b''))
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT u.id, u.name, fs.embedding
        FROM face_samples fs
        JOIN users u ON fs.user_id = u.id
    ''')
    rows = c.fetchall()
    conn.close()
    # Keep behavior of user matching by first user; embeddings are not used in lightweight mode.
    return [{'id': uid, 'name': name} for uid, name, emb in rows]


def mark_attendance(user_id, status='on_time', check_in_time=None):
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(
            'INSERT INTO attendance (user_id, date, status, check_in_time) VALUES (?, ?, ?, ?)',
            (user_id, today, status, check_in_time)
        )
        conn.commit()
        marked = True
    except sqlite3.IntegrityError:
        marked = False  # Already marked for today
    conn.close()
    return marked


def get_attendance_records():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT u.name, a.date, a.timestamp, a.status, a.check_in_time
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.timestamp DESC
    ''')
    records = c.fetchall()
    conn.close()
    return records


def get_settings():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT key, value FROM settings")
    rows = c.fetchall()
    conn.close()
    return {k: v for k, v in rows}


def save_settings(check_in_time, check_out_time):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('check_in_time', ?)", (check_in_time,))
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('check_out_time', ?)", (check_out_time,))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM attendance WHERE user_id = ?', (user_id,))
    c.execute('DELETE FROM face_samples WHERE user_id = ?', (user_id,))
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()


def list_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT u.id, u.name, u.created_at, COUNT(fs.id) as sample_count
        FROM users u
        LEFT JOIN face_samples fs ON fs.user_id = u.id
        GROUP BY u.id
        ORDER BY u.name
    ''')
    rows = c.fetchall()
    conn.close()
    return rows

