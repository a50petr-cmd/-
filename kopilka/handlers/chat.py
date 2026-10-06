"""Сообщения уже знакомого пользователя. Онбординг живёт отдельно."""

import contextlib
import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from kopilka import render
from kopilka.categories import CATEGORY_ORDER, category_list, resolve_category
from kopilka.format import format_percent, format_rub
from kopilka.money import STOP_WAIT, confirmation_allowed, exceeds_salary_share, hours_of_work
from kopilka.parsing import ParsedExpense, ParsedImpulse, looks_like_impulse, parse_decision, parse_user_text
from kopilka.recurring import detect_recurring
from kopilka.repo import (
    active_challenge,
    add_card,
    add_expense,
    best_cashback,
    decide_impulse,
    finish_challenge_if_due,
    get_impulse,
    get_user,
    get_user_by_id,
    last_declined,
    last_done_challenge,
    latest_open_impulse,
    list_cards,
    load_transactions,
    mark_digest,
    open_impulse,
    recent_expenses,
    save_cancel_link,
    set_cashback,
    start_challenge,
    summary,
    update_profile,
)
from kopilka.timeutil import parse_timezone, to_local, utcnow
from kopilka.utility import Utility, interpret
from kopilka.views import ImpulseView, UserProfile

logger = logging.getLogger(__name__)
router = Router(name="chat")


def _keyboard(impulse_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="ДА", callback_data=f"imp:y:{impulse_id}"),
            InlineKeyboardButton(text="НЕТ", callback_data=f"imp:n:{impulse_id}"),
        ]]
    )


def _fit(text: str) -> str:
    if len(text) <= 4000:
        return text
    return text[:3990] + "\n…"


async def _say(message: Message, text: str, **kwargs) -> None:
    await message.answer(_fit(text), **kwargs)


@router.message(StateFilter(None), F.text)
async def on_text(message: Message) -> None:
    if message.from_user is None or not message.text:
        return
    try:
        user = get_user(message.from_user.id)
        if user is None:
            await message.answer("Сначала /start — спрошу зарплату и недельный бюджет.")
            return
        await _dispatch(message, user)
    except Exception:
        logger.exception("message failed")
        await message.answer("Не смог записать. Проверь, что PostgreSQL запущен и DATABASE_URL верный.")


async def _dispatch(message: Message, user: UserProfile) -> None:
    text = message.text or ""
    now = utcnow()
    parsed = parse_user_text(text)
    if isinstance(parsed, ParsedExpense):
        await _expense(message, user, parsed, text, now)
        await _maybe_digest(message, user.id, now)
        return

    decision = parse_decision(text)
    utility = None
    if decision is None and not isinstance(parsed, ParsedImpulse) and not looks_like_impulse(text):
        utility = interpret(text)
    if not (utility and utility.kind == "challenge_status"):
        finished = finish_challenge_if_due(user.id, now=now)
        if finished is not None:
            await _say(message, render.challenge_done_text(finished.category, finished.saved))

    if isinstance(parsed, ParsedImpulse):
        await _impulse(message, user, parsed, now)
    elif looks_like_impulse(text):
        await _say(message, "Напиши цену: «хочу купить PS5 за 60к».")
    elif decision is not None:
        await _decision_word(message, user, decision, now)
    elif utility is not None:
        await _utility(message, user, utility, now)
    else:
        await _say(
            message,
            "Не разобрал. Пример траты: «купил бургер за 450». "
            "Крупная хотелка: «хочу купить PS5 за 60к». Команды: /help",
        )
    await _maybe_digest(message, user.id, now)


async def _expense(message: Message, user: UserProfile, parsed: ParsedExpense, raw: str, now) -> None:
    result = add_expense(
        user.id,
        title=parsed.title,
        amount=parsed.amount,
        category=parsed.category,
        raw_text=raw,
        now=now,
    )
    await _say(message, render.expense_text(result))


async def _impulse(message: Message, user: UserProfile, parsed: ParsedImpulse, now) -> None:
    if exceeds_salary_share(parsed.price, user.salary):
        regret = last_declined(user.id)
        impulse = open_impulse(user.id, parsed.title, parsed.price, now=now)
        hours = hours_of_work(parsed.price, user.salary, user.work_hours_per_month)
        await _say(
            message,
            render.stop_text(
                title=parsed.title,
                price=parsed.price,
                salary=user.salary,
                hours=hours,
                hours_per_month=user.work_hours_per_month,
                regret=regret,
            ),
            reply_markup=_keyboard(impulse.id),
        )
        return
    await _say(message, render.calm_text(parsed.title, parsed.price, user.salary))


def _apply_decision(user: UserProfile, impulse: ImpulseView, decision: str, now) -> tuple[str, str]:
    if impulse.status != "open":
        return "Это уже решено.", "Уже решено"
    if decision == "no":
        decide_impulse(impulse.id, "declined", now=now)
        return render.declined_text(impulse.title, impulse.price), "Деньги остаются"
    if not confirmation_allowed(impulse.created_at, now):
        unlock = to_local(impulse.created_at + STOP_WAIT, user.timezone)
        return render.too_early_text(unlock), "Рано"
    decide_impulse(impulse.id, "confirmed", now=now)
    return render.confirmed_text(impulse.title, impulse.price), "Сутки прошли"


async def _decision_word(message: Message, user: UserProfile, decision: str, now) -> None:
    impulse = latest_open_impulse(user.id)
    if impulse is None:
        await _say(message, "Сейчас нет покупки на паузе.")
        return
    text, _toast = _apply_decision(user, impulse, decision, now)
    await _say(message, text)


@router.callback_query(F.data.startswith("imp:"))
async def on_button(query: CallbackQuery) -> None:
    try:
        await _on_button(query)
    except Exception:
        logger.exception("callback failed")
        with contextlib.suppress(Exception):
            await query.answer("Не вышло")


async def _on_button(query: CallbackQuery) -> None:
    if query.from_user is None or not query.data:
        await query.answer()
        return
    try:
        _prefix, mark, raw_id = query.data.split(":")
        impulse_id = int(raw_id)
    except ValueError:
        await query.answer()
        return
    user = get_user(query.from_user.id)
    if user is None:
        await query.answer("Сначала /start")
        return
    impulse = get_impulse(impulse_id)
    if impulse is None or impulse.user_id != user.id:
        await query.answer("Не нашёл эту покупку")
        return
    text, toast = _apply_decision(user, impulse, "yes" if mark == "y" else "no", utcnow())
    await query.answer(toast)
    if query.message is not None and hasattr(query.message, "answer"):
        await query.message.answer(_fit(text))
        return
    await query.bot.send_message(query.from_user.id, _fit(text))


async def _utility(message: Message, user: UserProfile, util: Utility, now) -> None:
    kind = util.kind
    if kind == "help":
        await _say(message, render.HELP)
    elif kind == "unknown":
        await _say(message, "Такой команды нет.\n\n" + render.HELP)
    elif kind == "week":
        await _say(message, render.week_text(summary(user.id, now=now)))
    elif kind == "piggy":
        current = summary(user.id, now=now)
        await _say(
            message,
            f"В виртуальной копилке {format_rub(current.piggy_total)}. "
            "Перевода нет, это сумма округлений.",
        )
    elif kind == "expenses":
        await _say(message, render.expenses_text(recent_expenses(user.id), user.timezone))
    elif kind in {"digest", "subs"}:
        await _send_digest(message, user, now)
    elif kind == "cards":
        await _say(message, render.cards_text(list_cards(user.id)))
    elif kind == "categories":
        await _say(message, "Категории: " + category_list())
    elif kind == "challenge_status":
        await _challenge_status(message, user, now)
    elif kind == "challenge_start":
        category = resolve_category(util.text)
        if not category:
            await _say(message, "Назови категорию: челлендж такси")
            return
        view, replaced = start_challenge(user.id, category, now=now)
        await _say(message, render.challenge_started_text(view.category, view.saved, replaced))
    elif kind == "challenge_bad":
        await _say(message, "Назови категорию: челлендж такси")
    elif kind == "card_add":
        name = add_card(user.id, util.text)
        await _say(message, f"Карта «{name}» записана. Ставка: кэшбэк {name} продукты 5")
    elif kind == "card_bad":
        await _say(message, "Напиши название: карта зарплатная")
    elif kind == "cashback":
        await _save_cashback(message, user, util)
    elif kind == "cashback_bad":
        await _say(message, "Так: кэшбэк зарплатная продукты 5")
    elif kind == "hint":
        await _hint(message, user, util.text)
    elif kind == "hint_bad":
        await _say(message, "Так: подсказка продукты")
    elif kind == "unsub":
        save_cancel_link(user.id, util.text, util.url)
        await _say(
            message,
            f"Ссылку для «{util.text}» запомнил. В дайджесте она появится, только если траты названы так же.",
        )
    elif kind == "unsub_bad":
        await _say(message, "Так: отписка Кинопоиск https://example.com")
    elif kind == "salary_show":
        await _say(message, f"Зарплата {format_rub(user.salary)} в месяц. Сменить: зарплата 120000")
    elif kind == "salary_set" and util.number is not None:
        updated = update_profile(user.id, salary=util.number)
        await _say(message, f"Зарплата теперь {format_rub(updated.salary)} в месяц.")
    elif kind == "salary_bad":
        await _say(message, "Нужно положительное число: зарплата 120000")
    elif kind == "budget_set" and util.number is not None:
        updated = update_profile(user.id, weekly_budget=util.number)
        await _say(message, f"Бюджет недели теперь {format_rub(updated.weekly_budget)}.")
    elif kind == "budget_bad":
        await _say(message, "Нужно положительное число: бюджет 7000")
    elif kind == "tz_set":
        tz_name = parse_timezone(util.text)
        if tz_name is None:
            await _say(message, "Не знаю такой пояс. Пример: Europe/Moscow или Asia/Yekaterinburg. Москва — «ок».")
            return
        update_profile(user.id, timezone=tz_name)
        await _say(message, f"Часовой пояс: {tz_name}.")
    elif kind == "tz_bad":
        await _say(message, "Напиши пояс: пояс Europe/Moscow")


async def _save_cashback(message: Message, user: UserProfile, util: Utility) -> None:
    category = resolve_category(util.extra)
    if category not in CATEGORY_ORDER:
        await _say(message, "Категорию не знаю. Напиши «категории» и выбери слово из списка.")
        return
    if util.number is None or not set_cashback(user.id, util.text, category, util.number):
        await _say(message, f"Сначала заведи карту: карта {util.text}")
        return
    await _say(message, f"Записал: «{util.text}», {category}, {format_percent(util.number)}%.")


async def _hint(message: Message, user: UserProfile, raw_category: str) -> None:
    category = resolve_category(raw_category)
    if category not in CATEGORY_ORDER:
        await _say(message, "Категорию не знаю. Список: категории")
        return
    found = best_cashback(user.id, category)
    if found is None:
        await _say(message, render.hint_text(category, None, None))
        return
    await _say(message, render.hint_text(category, found[0], found[1]))


async def _challenge_status(message: Message, user: UserProfile, now) -> None:
    finished = finish_challenge_if_due(user.id, now=now)
    if finished is not None:
        await _say(message, render.challenge_done_text(finished.category, finished.saved))
        return
    current = active_challenge(user.id)
    if current is not None:
        await _say(message, render.challenge_status_text(current, now))
        return
    last = last_done_challenge(user.id)
    if last is not None:
        await _say(message, f"Сейчас челленджа нет. Прошлый «{last.category}» ты закрыл. Новый: челлендж такси")
        return
    await _say(message, "Сейчас челленджа нет. Пример: челлендж такси")


async def _send_digest(message: Message, user: UserProfile, now) -> None:
    hits = detect_recurring(load_transactions(user.id))
    await _say(message, render.digest_text(hits))
    mark_digest(user.id, to_local(now, user.timezone).strftime("%Y-%m"))


async def _maybe_digest(message: Message, user_id: int, now) -> None:
    try:
        user = get_user_by_id(user_id)
        if user is None:
            return
        local = to_local(now, user.timezone)
        if local.day != 1 or user.last_digest_month == local.strftime("%Y-%m"):
            return
        hits = detect_recurring(load_transactions(user.id))
        await _say(message, render.digest_text(hits))
        mark_digest(user.id, local.strftime("%Y-%m"))
    except Exception:
        logger.exception("monthly digest failed")
