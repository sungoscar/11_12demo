from unittest.mock import MagicMock

import db


def test_queries_bind_parameters(monkeypatch):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr(db, "get_connection", lambda: connection)
    username = "' OR 1=1 --"
    db.find_user_by_username(username)
    query, params = connection.execute.call_args.args
    assert username not in query and "username = %s" in query
    assert params == (username,)
    db.find_user_by_id(42)
    query, params = connection.execute.call_args.args
    assert "id = %s" in query and params == (42,)
    assert "password_hash" not in query
