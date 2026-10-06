from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_NOMINATIM_USER_AGENT = "egrocery-bot/0.1 contact@example.com"


@dataclass(frozen=True)
class GeocodeResult:
    lat: float
    lon: float
    formatted_address: str | None = None
    city: str | None = None
    source: str | None = None


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
        source="yandex",
    )


def get_nominatim_user_agent() -> str:
    raw = os.environ.get("NOMINATIM_USER_AGENT", "").strip()
    return raw or DEFAULT_NOMINATIM_USER_AGENT


def _nominatim_search_query(
    address: str,
    *,
    city: str | None = None,
    region: str | None = None,
    country: str | None = None,
) -> str:
    parts = [address.strip()]
    for extra in (city, region, country):
        if extra and str(extra).strip():
            parts.append(str(extra).strip())
    return ", ".join(parts)


def geocode_address_nominatim(
    address: str,
    *,
    city: str | None = None,
    region: str | None = None,
    country: str = "RU",
) -> GeocodeResult | None:
    query = urllib.parse.urlencode(
        {
            "q": _nominatim_search_query(
                address, city=city, region=region, country=country
            ),
            "format": "json",
            "limit": "1",
            "accept-language": "ru",
        }
    )
    url = f"{NOMINATIM_SEARCH_URL}?{query}"
    req = urllib.request.Request(
        url, headers={"User-Agent": get_nominatim_user_agent()}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not isinstance(payload, list) or not payload:
        return None
    hit = payload[0]
    lat_s = hit.get("lat")
    lon_s = hit.get("lon")
    if lat_s is None or lon_s is None:
        return None
    addr = hit.get("address") if isinstance(hit.get("address"), dict) else {}
    resolved_city = None
    for key in ("city", "town", "village", "municipality", "hamlet"):
        name = addr.get(key)
        if name:
            resolved_city = str(name)
            break
    display = hit.get("display_name")
    return GeocodeResult(
        lat=float(lat_s),
        lon=float(lon_s),
        formatted_address=str(display) if display else None,
        city=resolved_city,
        source="nominatim",
    )


def geocode_address(
    address: str,
    *,
    city: str | None = None,
    region: str | None = None,
    country: str = "RU",
) -> GeocodeResult | None:
    """Yandex when API key is set; otherwise OpenStreetMap Nominatim."""
    if get_yandex_geocoder_api_key():
        return geocode_address_yandex(address)
    return geocode_address_nominatim(
        address, city=city, region=region, country=country
    )


def geocode_address_with_warning(
    address: str,
    *,
    city: str | None = None,
    region: str | None = None,
    country: str = "RU",
) -> tuple[GeocodeResult | None, str | None]:
    """Returns (result, user-facing warning when coordinates could not be resolved)."""
    try:
        result = geocode_address(
            address, city=city, region=region, country=country
        )
    except urllib.error.URLError as exc:
        logger.warning("geocode failed for %r: %s", address, exc)
        return None, (
            "Геокодер недоступен — сохранён только текст адреса. "
            "Можно отправить геопозицию."
        )
    if result:
        logger.info(
            "geocode ok source=%s lat=%s lon=%s city=%s",
            result.source,
            result.lat,
            result.lon,
            result.city,
        )
        return result, None
    return None, (
        "Адрес не распознан геокодером — сохранён текст. "
        "Пришлите геопозицию для точных цен."
    )
