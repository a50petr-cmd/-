from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from egrocery.geocode import geocode_address_yandex


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
