from __future__ import annotations

import re

import requests

TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]+$")

INVALID_TOKEN_API_MSG = (
    "Неверный PRICE_BOT_TOKEN: Telegram API отклонил токен (401/404). "
    "Проверьте PRICE_BOT_TOKEN в secrets.env, при необходимости Revoke в BotFather "
    "и создайте новый токен; не путайте с TELEGRAM_BOT_TOKEN job-бота."
)

INVALID_TOKEN_FORMAT_MSG = (
    "PRICE_BOT_TOKEN имеет неверный формат (ожидается «123456789:ABC…» от BotFather). "
    "Проверьте secrets.env на лишние пробелы и символы перевода строки (CRLF)."
)


def normalize_bot_token(token: str) -> str:
    return token.strip().rstrip("\r")


def validate_bot_token_format(token: str) -> bool:
    return bool(TOKEN_RE.match(token))


def verify_bot_token_getme(token: str) -> None:
    if not validate_bot_token_format(token):
        raise SystemExit(INVALID_TOKEN_FORMAT_MSG)
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        resp = requests.get(url, timeout=30)
    except requests.RequestException as exc:
        raise SystemExit(f"Не удалось проверить токен через getMe: {exc}") from exc
    if resp.status_code in (401, 404):
        raise SystemExit(INVALID_TOKEN_API_MSG)
    if resp.status_code != 200:
        raise SystemExit(
            f"Telegram getMe вернул HTTP {resp.status_code}; проверьте PRICE_BOT_TOKEN."
        )
    try:
        data = resp.json()
    except ValueError as exc:
        raise SystemExit("Telegram getMe вернул не-JSON; проверьте PRICE_BOT_TOKEN.") from exc
    if not data.get("ok"):
        raise SystemExit(INVALID_TOKEN_API_MSG)
