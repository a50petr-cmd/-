from __future__ import annotations

import argparse
import json
import logging
import sys

from job_agent.config import PROFILE_YAML, RESUME_PDF, SCORE_NOTIFY_THRESHOLD
from job_agent.pending import approve, list_pending
from job_agent.pipeline import run_search
from job_agent.profile import load_profile
from job_agent.resume import analyze_resume_pdf


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


def cmd_analyze_resume(args: argparse.Namespace) -> int:
    from job_agent.config import PROFILE_YAML as py

    pdf = args.pdf
    profile, _text = analyze_resume_pdf(pdf, py)
    print(f"Профиль сохранён: {py}")
    print(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    profile = load_profile(PROFILE_YAML)
    scored = run_search(
        profile,
        limit=args.limit,
        use_hh_fixture=args.use_fixtures,
        hh_web_only=args.hh_web_only,
        persist_pending_min_score=args.min_pending_score,
        notify=not args.no_notify,
    )
    for s in scored[: args.show]:
        v = s.vacancy
        print(f"{s.score:3d} [{v.source}] {v.title} @ {v.company}\n    {v.url}\n    {s.rationale}\n")
    print(f"Всего оценено: {len(scored)}; порог Telegram: {SCORE_NOTIFY_THRESHOLD}")
    return 0


def cmd_pending_list(_args: argparse.Namespace) -> int:
    for item in list_pending():
        v = item.get("vacancy", {})
        print(f"{item.get('status')} score={item.get('score')} id={item.get('id')}")
        print(f"  {v.get('title')} — {v.get('url')}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    from job_agent.telegram_notifier import send_pending_cover_letter

    data = approve(args.id)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if not getattr(args, "no_telegram", False):
        profile = load_profile(PROFILE_YAML)
        if send_pending_cover_letter(args.id, profile):
            print("Сопроводительное отправлено в Telegram.")
    return 0


def cmd_telegram_letter(args: argparse.Namespace) -> int:
    from job_agent.telegram_notifier import send_pending_cover_letter

    profile = load_profile(PROFILE_YAML)
    ok = send_pending_cover_letter(args.id, profile)
    print("Письмо отправлено в Telegram." if ok else "Не удалось отправить (нет pending или бот).")
    return 0 if ok else 1


def cmd_telegram_test(_args: argparse.Namespace) -> int:
    from job_agent.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    from job_agent.telegram_notifier import resolve_chat_id_from_updates, send_message

    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN не задан (env или internal/secrets.env)")
        return 1
    chat_id = TELEGRAM_CHAT_ID or resolve_chat_id_from_updates(TELEGRAM_BOT_TOKEN)
    if chat_id and not TELEGRAM_CHAT_ID:
        print(f"Найден chat_id из getUpdates: {chat_id}")
        print("Добавьте в internal/secrets.env: TELEGRAM_CHAT_ID=" + chat_id)
    elif TELEGRAM_CHAT_ID:
        print(f"Используется TELEGRAM_CHAT_ID={TELEGRAM_CHAT_ID}")
    else:
        print("chat_id не найден. Откройте @HH_Alekseev_bot и нажмите /start, затем повторите команду.")
        return 1
    ok = send_message("PetroJobAgent: тестовое сообщение. Пайплайн поиска работы активен.")
    print("Сообщение отправлено." if ok else "Не удалось отправить сообщение.")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="job_agent", description="Поиск вакансий и assist откликов (runet)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    p_an = sub.add_parser("analyze-resume", help="Извлечь профиль из PDF резюме")
    p_an.add_argument("pdf", nargs="?", type=lambda p: __import__("pathlib").Path(p), default=__import__("pathlib").Path(RESUME_PDF))

    p_search = sub.add_parser("search", help="Поиск, скoring, pending, Telegram digest")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--show", type=int, default=15)
    p_search.add_argument("--use-fixtures", action="store_true", help="HH: использовать локальный fixture")
    p_search.add_argument(
        "--hh-web-only",
        action="store_true",
        help="HH: только поиск через сайт hh.ru (без api.hh.ru)",
    )
    p_search.add_argument("--min-pending-score", type=int, default=55)
    p_search.add_argument("--no-notify", action="store_true")

    sub.add_parser("pending", help="Список pending-откликов")

    p_app = sub.add_parser("approve", help="Одобрить отклик (без автоотправки без AUTO_APPLY)")
    p_app.add_argument("id", help="id вида hh:12345 или habr:67890")
    p_app.add_argument("--no-telegram", action="store_true", help="Не слать письмо в Telegram")

    p_tl = sub.add_parser("telegram-letter", help="Отправить cover_letter_ru из pending в Telegram")
    p_tl.add_argument("id", help="id вида hh_web:12345")

    sub.add_parser("telegram-test", help="Проверить TELEGRAM_BOT_TOKEN / CHAT_ID")

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    handlers = {
        "analyze-resume": cmd_analyze_resume,
        "search": cmd_search,
        "pending": cmd_pending_list,
        "approve": cmd_approve,
        "telegram-letter": cmd_telegram_letter,
        "telegram-test": cmd_telegram_test,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
