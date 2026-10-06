from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class GeocodeResult:
    lat: float
    lon: float
    formatted_address: str | None = None
    city: str | None = None


def get_yandex_geocoder_api_key() -> str | None:
    raw = os.environ.get("YANDEX_GEOCODER_API_KEY", "").strip()
    return raw or None


def geocode_address_yandex(address: str, *, api_key: str | None = None) -> GeocodeResult | None:
    key = api_key or get_yandex_geocoder_api_key()
    if not key:
        return None
    query = urllib.parse.urlencode(
        {
            "apikey": key,
            "geocode": address,
            "format": "json",
            "results": "1",
        }
    )
    url = f"https://geocode-maps.yandex.ru/1.x/?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "egrocery/0.1"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    members = (
        payload.get("response", {})
        .get("GeoObjectCollection", {})
        .get("featureMember", [])
    )
    if not members:
        return None
    geo = members[0].get("GeoObject", {})
    pos = geo.get("Point", {}).get("pos", "")
    parts = pos.split()
    if len(parts) != 2:
        return None
    lon_s, lat_s = parts
    meta = geo.get("metaDataProperty", {}).get("GeocoderMetaData", {})
    city = None
    for comp in meta.get("Address", {}).get("Components", []) or []:
        if comp.get("kind") == "locality":
            city = comp.get("name")
            break
    return GeocodeResult(
        lat=float(lat_s),
        lon=float(lon_s),
        formatted_address=meta.get("text"),
        city=city,
    )
