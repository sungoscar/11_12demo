"""僅新增缺少的 Demo 帳號；不覆寫既有密碼或角色。"""
import os
import warnings
from getpass import GetPassWarning, getpass

import psycopg

from auth_utils import hash_password
from db import get_connection

ACCOUNTS = (("author1", "author", "SEED_AUTHOR_PASSWORD"),
            ("editor1", "editor", "SEED_EDITOR_PASSWORD"))


def read_password(username: str, env_name: str) -> str:
    password = os.getenv(env_name)
    if password is None:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", GetPassWarning)
                password = getpass(f"請輸入 {username} 的測試密碼（至少 12 字元）：")
                confirmation = getpass("請再次輸入密碼：")
        except GetPassWarning:
            raise ValueError("此終端機無法隱藏輸入，請改用安全的環境變數提供測試密碼。") from None
        if password != confirmation:
            raise ValueError("兩次密碼不一致，未建立帳號。")
    if len(password) < 12 or len(password) > 1024:
        raise ValueError(f"{username} 的密碼必須為 12 至 1024 字元。")
    return password


def seed_users():
    messages = []
    # 同一交易：任一帳號輸入失敗時，不留下部分新增結果。
    with get_connection() as connection:
        for username, role, env_name in ACCOUNTS:
            existing = connection.execute(
                "SELECT id FROM users WHERE username = %s", (username,)
            ).fetchone()
            if existing:
                messages.append(f"{username} 已存在，保留原密碼與角色。")
                continue
            password_hash = hash_password(read_password(username, env_name))
            created = connection.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s) "
                "ON CONFLICT (username) DO NOTHING RETURNING id",
                (username, password_hash, role),
            ).fetchone()
            messages.append(f"{username} 已建立。" if created else f"{username} 已存在，未變更。")
    for message in messages:
        print(message)


if __name__ == "__main__":
    try:
        seed_users()
    except (ValueError, EOFError) as exc:
        raise SystemExit(str(exc)) from None
    except psycopg.Error:
        raise SystemExit("資料庫操作失敗，請檢查 .env 與 PostgreSQL 狀態；本次交易已回復。") from None
