
import os

import psycopg
from psycopg.rows import dict_row

import config  # 載入專案根目錄的 .env


def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        connect_timeout=5,
        sslmode=os.getenv("DB_SSLMODE", "prefer"),
        row_factory=dict_row,
    )


def find_user_by_username(username: str):
    with get_connection() as connection:
        return connection.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = %s",
            (username,),
        ).fetchone()


def find_user_by_id(user_id: int):
    with get_connection() as connection:
        return connection.execute(
            "SELECT id, username, role FROM users WHERE id = %s", (user_id,)
        ).fetchone()
