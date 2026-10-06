from unittest.mock import MagicMock, patch

from egrocery.clients.lavka_session import bootstrap_guest_session, resolve_lavka_session


def test_resolve_uses_override(monkeypatch) -> None:
    monkeypatch.setenv("YANDEX_LAVKA_COOKIE", "test=1")
    s = resolve_lavka_session()
    assert s.cookie_header == "test=1"


def test_bootstrap_saves_cookie(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("JOB_AGENT_STORE", str(tmp_path))
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '"csrfToken":"abc123"'
    mock_resp.raise_for_status = MagicMock()
    mock_session = MagicMock()
    mock_session.cookies.get_dict.return_value = {"yandexuid": "999"}
    mock_session.get.return_value = mock_resp
    with patch("egrocery.clients.lavka_session.requests.Session", return_value=mock_session):
        s = bootstrap_guest_session()
    assert "yandexuid=999" in s.cookie_header
    assert s.csrf_token == "abc123"
    cache = tmp_path / "internal" / "egrocery" / "lavka-cookies.txt"
    assert cache.is_file()
