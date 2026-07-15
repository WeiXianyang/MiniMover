"""小车本地人脸用户库（SQLite + 图片文件）；人脸特征在百度云。"""
import hashlib
import os
import sqlite3
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FACE_DIR = BASE_DIR / '人脸识别' / 'media' / 'face_images'
DB_PATH = BASE_DIR / 'face' / 'face_users.db'

_lock = threading.Lock()


def _hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    FACE_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        conn = _conn()
        try:
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    face_token TEXT,
                    created_at REAL NOT NULL
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS face_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    path TEXT NOT NULL,
                    face_token TEXT,
                    created_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                '''
            )
            conn.commit()
        finally:
            conn.close()


def get_user_by_username(username):
    conn = _conn()
    try:
        row = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = _conn()
    try:
        row = conn.execute('SELECT * FROM users WHERE id=?', (int(user_id),)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def verify_password(user, password):
    return user and user['password'] == _hash_password(password)


def create_user(username, password, email, phone):
    with _lock:
        conn = _conn()
        try:
            cur = conn.execute(
                'INSERT INTO users (username, password, email, phone, created_at) VALUES (?,?,?,?,?)',
                (username, _hash_password(password), email, phone, time.time()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


def delete_user(user_id):
    with _lock:
        conn = _conn()
        try:
            rows = conn.execute(
                'SELECT path FROM face_images WHERE user_id=?', (user_id,)
            ).fetchall()
            for row in rows:
                try:
                    os.remove(row['path'])
                except OSError:
                    pass
            conn.execute('DELETE FROM face_images WHERE user_id=?', (user_id,))
            conn.execute('DELETE FROM users WHERE id=?', (user_id,))
            conn.commit()
        finally:
            conn.close()


def save_face_image(user_id, username, image_bytes, face_token=None):
    user_dir = FACE_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    filename = f'{int(time.time() * 1000)}_{os.getpid()}.jpg'
    path = user_dir / filename
    path.write_bytes(image_bytes)
    with _lock:
        conn = _conn()
        try:
            conn.execute(
                'INSERT INTO face_images (user_id, path, face_token, created_at) VALUES (?,?,?,?)',
                (user_id, str(path), face_token, time.time()),
            )
            if face_token:
                conn.execute(
                    'UPDATE users SET face_token=? WHERE id=? AND (face_token IS NULL OR face_token="")',
                    (face_token, user_id),
                )
            conn.commit()
        finally:
            conn.close()
    return str(path)


def set_user_face_token(user_id, face_token):
    with _lock:
        conn = _conn()
        try:
            conn.execute('UPDATE users SET face_token=? WHERE id=?', (face_token, user_id))
            conn.commit()
        finally:
            conn.close()
