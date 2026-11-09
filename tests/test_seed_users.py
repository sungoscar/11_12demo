from copy import deepcopy
from unittest.mock import MagicMock
import secrets
import warnings
from getpass import GetPassWarning

import pytest

from auth_utils import verify_password
import seed_users


@pytest.fixture
def seed_database(monkeypatch):
    records = {}
    connection = MagicMock()
    connection.__enter__.return_value = connection
    snapshot = {}

    def enter():
        snapshot.update(deepcopy(records))
        return connection

    def exit_transaction(exc_type, exc, traceback):
        if exc_type:
            records.clear()
            records.update(snapshot)
        return False

    def execute(query, params):
        result = MagicMock()
        if query.startswith("SELECT"):
            result.fetchone.return_value = records.get(params[0])
        else:
            assert "ON CONFLICT (username) DO NOTHING" in query
            username, password_hash, role = params
            if username in records:
                result.fetchone.return_value = None
            else:
                records[username] = {"id": len(records) + 1, "username": username,
                                     "password_hash": password_hash, "role": role}
                result.fetchone.return_value = {"id": records[username]["id"]}
        return result

    connection.__enter__.side_effect = enter
    connection.__exit__.side_effect = exit_transaction
    connection.execute.side_effect = execute
    monkeypatch.setattr(seed_users, "get_connection", lambda: connection)
    return records, connection


def test_seed_creates_hashes_and_is_idempotent(seed_database, monkeypatch, capsys):
    records, connection = seed_database
    author_password, editor_password = secrets.token_urlsafe(18), secrets.token_urlsafe(18)
    monkeypatch.setenv("SEED_AUTHOR_PASSWORD", author_password)
    monkeypatch.setenv("SEED_EDITOR_PASSWORD", editor_password)
    seed_users.seed_users()
    original = deepcopy(records)
    assert records["author1"]["role"] == "author"
    assert records["editor1"]["role"] == "editor"
    assert verify_password(author_password, records["author1"]["password_hash"])
    assert verify_password(editor_password, records["editor1"]["password_hash"])
    monkeypatch.setenv("SEED_AUTHOR_PASSWORD", "")
    monkeypatch.setenv("SEED_EDITOR_PASSWORD", "")
    seed_users.seed_users()
    assert records == original
    output = capsys.readouterr().out
    assert author_password not in output and editor_password not in output
    assert records["author1"]["password_hash"] not in output
    assert len([call for call in connection.execute.call_args_list
                if call.args[0].startswith("INSERT")]) == 2


def test_existing_account_role_is_preserved(seed_database, monkeypatch):
    records, _ = seed_database
    records["author1"] = {"id": 9, "role": "editor", "password_hash": "existing"}
    original = deepcopy(records["author1"])
    monkeypatch.setenv("SEED_EDITOR_PASSWORD", secrets.token_urlsafe(18))
    seed_users.seed_users()
    assert records["author1"] == original


def test_second_password_failure_rolls_back(seed_database, monkeypatch):
    records, _ = seed_database
    monkeypatch.setenv("SEED_AUTHOR_PASSWORD", secrets.token_urlsafe(18))
    monkeypatch.setenv("SEED_EDITOR_PASSWORD", "short")
    with pytest.raises(ValueError, match="12"):
        seed_users.seed_users()
    assert records == {}


def test_interactive_password_confirmation(monkeypatch):
    password = secrets.token_urlsafe(18)
    monkeypatch.delenv("SEED_AUTHOR_PASSWORD", raising=False)
    answers = iter([password, password])
    monkeypatch.setattr(seed_users, "getpass", lambda _: next(answers))
    assert seed_users.read_password("author1", "SEED_AUTHOR_PASSWORD") == password


def test_interactive_password_mismatch(monkeypatch):
    monkeypatch.delenv("SEED_AUTHOR_PASSWORD", raising=False)
    answers = iter([secrets.token_urlsafe(18), secrets.token_urlsafe(18)])
    monkeypatch.setattr(seed_users, "getpass", lambda _: next(answers))
    with pytest.raises(ValueError, match="不一致"):
        seed_users.read_password("author1", "SEED_AUTHOR_PASSWORD")


def test_no_echo_unavailable_refuses_input(monkeypatch):
    monkeypatch.delenv("SEED_AUTHOR_PASSWORD", raising=False)
    def unsafe_input(_):
        warnings.warn("no echo unavailable", GetPassWarning)
        raise AssertionError("不可執行回顯輸入")
    monkeypatch.setattr(seed_users, "getpass", unsafe_input)
    with pytest.raises(ValueError, match="無法隱藏"):
        seed_users.read_password("author1", "SEED_AUTHOR_PASSWORD")
