from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import urllib.error

from egrocery.geocode import geocode_address, geocode_address_photon


def test_geocode_address_photon_parses_feature() -> None:
    payload = {
        "features": [
            {
                "geometry": {"coordinates": [38.44, 55.78]},
                "properties": {
                    "city": "Электросталь",
                    "street": "улица Ялагина",
                    "housenumber": "13",
                },
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    with patch("egrocery.geocode.urllib.request.urlopen", return_value=mock_resp):
        result = geocode_address_photon("Ялагина 13", city="Электросталь")
    assert result is not None
    assert result.source == "photon"
    assert result.lat == 55.78


def test_geocode_chain_uses_photon_when_nominatim_403(monkeypatch) -> None:
    monkeypatch.delenv("YANDEX_GEOCODER_API_KEY", raising=False)

    def fake_urlopen(req, timeout=20):
        url = req.full_url
        if "nominatim" in url:
            raise urllib.error.HTTPError(url, 403, "Forbidden", hdrs=None, fp=None)
        payload = {
            "features": [
                {
                    "geometry": {"coordinates": [38.44, 55.78]},
                    "properties": {"city": "Электросталь"},
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("egrocery.geocode.urllib.request.urlopen", side_effect=fake_urlopen):
        result = geocode_address("Электросталь", city="Электросталь")
    assert result is not None
    assert result.source == "photon"


def test_dev_fallback_for_yalagina(monkeypatch) -> None:
    monkeypatch.setenv("EGROCERY_DEV_GEO_FALLBACK", "1")
    monkeypatch.delenv("YANDEX_GEOCODER_API_KEY", raising=False)

    def fail_all(*_a, **_k):
        raise urllib.error.HTTPError("http://x", 403, "x", hdrs=None, fp=None)

    with patch("egrocery.geocode.urllib.request.urlopen", side_effect=fail_all):
        with patch("egrocery.geocode.geocode_address_photon", return_value=None):
            with patch("egrocery.geocode.geocode_address_nominatim", return_value=None):
                result = geocode_address("Электросталь, Ялагина 13")
    assert result is not None
    assert result.source == "dev_fallback"
