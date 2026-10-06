from __future__ import annotations

import os
from pathlib import Path

_CLOUD_STORE_ROOT = Path("/cursor/stores/self")
_DEFAULT_LOCAL_STORE = Path.home() / "job-agent-store"

LOCATION_REL = Path("docs/e-grocery-location.yaml")
BASKET_REL = Path("docs/e-grocery-basket-starter.yaml")

# Before live price fetch: confirm Samokat / Yandex Lavka deliver to this point.
COVERAGE_NOTE = (
    "Elektrostal (MO): verify Samokat and Yandex Lavka delivery zones for your "
    "address before trusting live prices."
)


def get_store_root() -> Path:
    for key in ("EGROCERY_STORE", "JOB_AGENT_STORE"):
        raw = os.environ.get(key)
        if raw:
            return Path(raw).expanduser()
    cloud_secrets = _CLOUD_STORE_ROOT / "internal" / "secrets.env"
    if cloud_secrets.is_file():
        return _CLOUD_STORE_ROOT
    return _DEFAULT_LOCAL_STORE


def get_location_path() -> Path:
    override = os.environ.get("EGROCERY_LOCATION_YAML")
    if override:
        return Path(override).expanduser()
    return get_store_root() / LOCATION_REL


def get_basket_path() -> Path:
    override = os.environ.get("EGROCERY_BASKET_YAML")
    if override:
        return Path(override).expanduser()
    return get_store_root() / BASKET_REL


def get_vkusvill_mcp_url() -> str | None:
    raw = os.environ.get("VKUSVILL_MCP_URL", "").strip()
    return raw or None


def _read_secrets_env(store_root: Path) -> dict[str, str]:
    path = store_root / "internal" / "secrets.env"
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def get_bot_token() -> str | None:
    raw = os.environ.get("EGROCERY_BOT_TOKEN", "").strip()
    if raw:
        return raw
    secrets = _read_secrets_env(get_store_root())
    return secrets.get("EGROCERY_BOT_TOKEN") or None
