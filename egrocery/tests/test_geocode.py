from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from egrocery.geocode import geocode_address, geocode_address_nominatim, geocode_address_yandex


def test_geocode_address_yandex_parses_response() -> None:
    payload = {
        "response": {
            "GeoObjectCollection": {
                "featureMember": [
                    {
                        "GeoObject": {
                            "Point": {"pos": "38.444 55.789"},
                            "metaDataProperty": {
                                "GeocoderMetaData": {
                                    "text": "Россия, Электросталь, …",
                                    "Address": {
                                        "Components": [
                                            {"kind": "locality", "name": "Электросталь"}
                                        ]
                                    },
                                }
                            },
                        }
                    }
                ]
            }
        }
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    with patch("egrocery.geocode.urllib.request.urlopen", return_value=mock_resp):
        result = geocode_address_yandex("Электросталь", api_key="test-key")
    assert result is not None
    assert result.lat == 55.789
    assert result.lon == 38.444
    assert result.city == "Электросталь"
    assert result.source == "yandex"


def test_geocode_address_nominatim_parses_response() -> None:
    payload = [
        {
            "lat": "55.78412",
            "lon": "38.44567",
            "display_name": "улица Ялагина, Электросталь, …",
            "address": {"city": "Электросталь", "road": "улица Ялагина"},
        }
    ]
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    with patch("egrocery.geocode.urllib.request.urlopen", return_value=mock_resp):
        result = geocode_address_nominatim(
            "Ялагина 13",
            city="Электросталь",
            region="Московская область",
            country="RU",
        )
    assert result is not None
    assert result.lat == 55.78412
    assert result.lon == 38.44567
    assert result.city == "Электросталь"
    assert result.source == "nominatim"


def test_geocode_address_uses_nominatim_without_yandex_key(monkeypatch) -> None:
    monkeypatch.delenv("YANDEX_GEOCODER_API_KEY", raising=False)
    payload = [{"lat": "55.78", "lon": "38.44", "display_name": "test", "address": {}}]
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    with patch("egrocery.geocode.urllib.request.urlopen", return_value=mock_resp) as urlopen:
        result = geocode_address("Электросталь, Ялагина 13", city="Электросталь")
    assert result is not None
    assert result.source == "nominatim"
    called_url = urlopen.call_args[0][0].full_url
    assert "nominatim.openstreetmap.org" in called_url
