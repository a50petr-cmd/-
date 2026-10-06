"""
Stub: автоматизация отклика на hh.ru через Playwright на машине пользователя.

Пароли и OAuth HH НЕ хранятся в репозитории. Пользователь один раз логинится
в persistent context (user_data_dir), дальше скрипт открывает страницу вакансии
и подставляет текст сопроводительного письма — финальный клик «Откликнуться»
оставляем пользователю или включаем только с явным флагом.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="HH apply assist (Playwright stub)")
    parser.add_argument("--pending-json", type=Path, required=True)
    parser.add_argument("--user-data-dir", type=Path, default=Path.home() / ".hh-playwright-profile")
    parser.add_argument("--headed", action="store_true", default=True)
    args = parser.parse_args()

    data = json.loads(args.pending_json.read_text(encoding="utf-8"))
    url = data["vacancy"]["url"]
    letter = data["cover_letter_ru"]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("Установите playwright: pip install playwright && playwright install chromium") from exc

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(args.user_data_dir),
            headless=not args.headed,
            locale="ru-RU",
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        print("Откройте форму отклика вручную если не авторизованы.")
        print("--- Текст письма (скопируйте) ---")
        print(letter)
        print("--- Конец ---")
        input("Нажмите Enter после отправки отклика или для выхода...")
        context.close()


if __name__ == "__main__":
    main()
