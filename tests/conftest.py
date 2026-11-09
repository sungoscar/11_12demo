import os
import secrets

import pytest
from fastapi.testclient import TestClient

# 在匯入 main 前隔離測試金鑰，完全不依賴本機 .env 的 Session 設定。
os.environ["SESSION_SECRET"] = secrets.token_urlsafe(48)
os.environ["APP_ENV"] = "development"
os.environ["SESSION_HTTPS_ONLY"] = "false"

import db
import seed_users
from auth_utils import hash_password
from main import create_app


@pytest.fixture(autouse=True)
def block_real_database(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("測試禁止連線正式資料庫")
    monkeypatch.setattr(db, "get_connection", blocked)
    monkeypatch.setattr(seed_users, "get_connection", blocked)


@pytest.fixture(scope="session")
def credentials():
    password = secrets.token_urlsafe(24)
    return password, hash_password(password)


@pytest.fixture
def users(monkeypatch, credentials):
    _, hashed = credentials
    records = {
        1: {"id": 1, "username": "author1", "role": "author", "password_hash": hashed},
        2: {"id": 2, "username": "editor1", "role": "editor", "password_hash": hashed},
    }
    monkeypatch.setattr(db, "find_user_by_username", lambda name: next(
        (u.copy() for u in records.values() if u["username"] == name), None))
    monkeypatch.setattr(db, "find_user_by_id", lambda uid: (
        {k: v for k, v in records[uid].items() if k != "password_hash"}
        if uid in records else None))
    return records


@pytest.fixture
def client(users):
    with TestClient(create_app(), follow_redirects=False) as test_client:
        yield test_client
