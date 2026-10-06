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
PHOTON_SEARCH_URL = "https://photon.komoot.io/api/"
DEFAULT_NOMINATIM_USER_AGENT = "egrocery-bot/0.1 contact@example.com"

# Dev-only fallback for Petro test address (Электросталь, Ялагина 13).
_DEV_ADDRESS_COORDS = (55.78412, 38.44567)


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
    req = urllib.request.Request(
        url, headers={"User-Agent": get_nominatim_user_agent()}
    )
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
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            logger.warning("Nominatim HTTP 403 — проверьте NOMINATIM_USER_AGENT с email")
        else:
            logger.warning("Nominatim HTTP %s", exc.code)
        return None
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


def _dev_geo_fallback_enabled() -> bool:
    raw = os.environ.get("EGROCERY_DEV_GEO_FALLBACK", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _dev_known_coords(address: str) -> GeocodeResult | None:
    if not _dev_geo_fallback_enabled():
        return None
    norm = address.lower().replace("ё", "е")
    if "электросталь" in norm and "ялагина" in norm and "13" in norm:
        lat, lon = _DEV_ADDRESS_COORDS
        return GeocodeResult(
            lat=lat,
            lon=lon,
            formatted_address="Электросталь, ул. Ялагина, 13 (dev fallback)",
            city="Электросталь",
            source="dev_fallback",
        )
    return None


def geocode_address_photon(
    address: str,
    *,
    city: str | None = None,
    region: str | None = None,
    country: str = "RU",
) -> GeocodeResult | None:
    q = _nominatim_search_query(address, city=city, region=region, country=country)
    query = urllib.parse.urlencode({"q": q, "limit": "1", "lang": "default"})
    url = f"{PHOTON_SEARCH_URL}?{query}"
    req = urllib.request.Request(
        url, headers={"User-Agent": get_nominatim_user_agent()}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        logger.warning("Photon geocode failed: %s", exc)
        return None
    features = payload.get("features") if isinstance(payload, dict) else None
    if not features:
        return None
    hit = features[0]
    if not isinstance(hit, dict):
        return None
    geom = hit.get("geometry") or {}
    coords = geom.get("coordinates")
    if not isinstance(coords, list) or len(coords) < 2:
        return None
    lon_s, lat_s = coords[0], coords[1]
    props = hit.get("properties") if isinstance(hit.get("properties"), dict) else {}
    resolved_city = props.get("city") or props.get("locality") or props.get("town")
    street = props.get("street") or props.get("name")
    housenumber = props.get("housenumber")
    parts = [p for p in (street, housenumber, resolved_city) if p]
    display = ", ".join(str(p) for p in parts) if parts else q
    return GeocodeResult(
        lat=float(lat_s),
        lon=float(lon_s),
        formatted_address=display,
        city=str(resolved_city) if resolved_city else None,
        source="photon",
    )


def geocode_address(
    address: str,
    *,
    city: str | None = None,
    region: str | None = None,
    country: str = "RU",
) -> GeocodeResult | None:
    """Yandex (if key) → Nominatim → Photon → optional dev fallback."""
    key = get_yandex_geocoder_api_key()
    if key:
        try:
            result = geocode_address_yandex(address, api_key=key)
        except urllib.error.URLError as exc:
            logger.warning("Yandex geocoder failed: %s", exc)
            result = None
        if result:
            return result
    result = geocode_address_nominatim(
        address, city=city, region=region, country=country
    )
    if result:
        return result
    result = geocode_address_photon(
        address, city=city, region=region, country=country
    )
    if result:
        return result
    return _dev_known_coords(address)


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
        dev = _dev_known_coords(address)
        if dev:
            return dev, None
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
        "Адрес не распознан (Nominatim/Photon). "
        "Задайте YANDEX_GEOCODER_API_KEY или пришлите геопозицию 📍."
    )
