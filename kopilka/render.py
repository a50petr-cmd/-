"""Тексты бота. Деньги в ответах — учёт, не обещание перевода."""

from datetime import datetime
from decimal import Decimal

from kopilka.format import format_digest, format_hours, format_percent, format_rub
from kopilka.money import CHALLENGE_LENGTH, STOP_WAIT, exceeds_salary_share
from kopilka.timeutil import ensure_naive_utc, to_local
from kopilka.views import CardView, ChallengeView, ExpenseRow, ImpulseView, LoggedExpense, Summary, UserProfile

HELLO = (
    "Я Копилка. Записываю траты и спорю, когда хочется слить деньги.\n"
    "Переводов нет: банк не трогаю, округление виртуальное.\n\n"
    "Какая зарплата в месяц, в рублях? Например: 120000"
)

HELP = """Копилка записывает траты и тормозит крупные хотелки. Переводов нет.

Трата: купил бургер за 450
или: потратил 500 на такси

Стоп-кран: хочу купить PS5 за 60к
Если это больше 10% зарплаты — сутки на подумать. ДА или НЕТ.

Ещё фразы:
бюджет — остаток недели
бюджет 7000 — новый лимит
зарплата 120000
копилка — виртуальный остаток
траты
челлендж такси
карта зарплатная
кэшбэк зарплатная продукты 5
подсказка продукты
подписки
дайджест
отписка Кинопоиск https://example.com
пояс Europe/Moscow
категории

Те же действия есть командами: /help /week /piggy /expenses /challenge /digest /subs /cards /hint
"""

_TIPS = {
    "фастфуд": "Паста дома выходит примерно в 150 ₽.",
    "такси": "Если не горит — общественный транспорт почти всегда дешевле.",
    "кафе": "Кофе из дома снимает половину таких строчек.",
    "доставка": "Зайти в магазин обычно дешевле доставки.",
}


def threshold_clause(price: Decimal, salary: Decimal) -> str:
    exceeds = exceeds_salary_share(price, salary)
    shown = (Decimal(price) / Decimal(salary) * Decimal(100)).quantize(Decimal("0.1"))
    money = f"{format_rub(price)} при зарплате {format_rub(salary)}"
    if exceeds and shown <= Decimal("10"):
        return f"{money} — это больше 10%."
    if exceeds:
        return f"{money} — это {format_percent(shown)}% зарплаты, порог 10% пробит."
    if shown >= Decimal("10"):
        return f"{money} — это не больше 10% зарплаты. Порог не пробит."
    return f"{money} — это {format_percent(shown)}% зарплаты, порог 10% не пробит."


def stop_text(
    *,
    title: str,
    price: Decimal,
    salary: Decimal,
    hours: Decimal,
    hours_per_month: int,
    regret: ImpulseView | None,
) -> str:
    lines = [
        f"Стоп. {title}.",
        threshold_clause(price, salary),
        f"По работе это около {format_hours(hours)} ч при {hours_per_month} ч в месяц.",
    ]
    if hours >= 8:
        days = (hours / Decimal(8)).quantize(Decimal("0.1"))
        lines.append(f"Это примерно {format_hours(days)} рабочих дней по 8 часов.")
    if regret is not None:
        lines.append(
            f"В прошлый раз ты отказался от «{regret.title}» за {format_rub(regret.price)}. "
            "Деньги тогда остались."
        )
    lines.append("Правило суток: если завтра желание живое — жми ДА. НЕТ — и покупку не записываю.")
    lines.append("Перевода нет, банк я не трогаю.")
    return "\n".join(lines)


def calm_text(title: str, price: Decimal, salary: Decimal) -> str:
    return (
        f"{title}. {threshold_clause(price, salary)}\n"
        "Стоп-кран молчит. Когда купишь — напиши «купил … за …»."
    )


def too_early_text(unlock_local: datetime) -> str:
    return (
        "Рано. Сутки ещё не прошли. "
        f"После {unlock_local.strftime('%d.%m %H:%M')} нажми ДА ещё раз, если желание живое."
    )


def confirmed_text(title: str, price: Decimal) -> str:
    return (
        f"Сутки прошли. «{title}» за {format_rub(price)} — покупать можно, это твоё решение. "
        "Деньги не списываю. Если купишь, запиши трату фразой."
    )


def declined_text(title: str, price: Decimal) -> str:
    return f"Хорошо. «{title}» за {format_rub(price)} не берём. Запомнил отказ."


def _budget_line(left: Decimal) -> str:
    if left >= 0:
        return f"Остаток бюджета на неделю: {format_rub(left)}."
    return f"Недельный бюджет превышен на {format_rub(abs(left))}."


def expense_text(result: LoggedExpense) -> str:
    lines = [
        f"Принято. {result.title} — {format_rub(result.amount)}, категория «{result.category}».",
        f"Это {result.week_count}-й раз в категории «{result.category}» за эту неделю.",
    ]
    if result.piggy_delta == 0:
        lines.append("Сумма уже кратна 100 ₽, в виртуальную копилку ничего не ушло.")
    else:
        lines.append(
            f"В копилку ушло {format_rub(result.piggy_delta)} "
            f"округлением вверх до {format_rub(result.rounded)}."
        )
    lines.append(_budget_line(result.budget_left))
    lines.append(f"В копилке сейчас {format_rub(result.piggy_total)}. Перевод не делаю.")
    tip = _TIPS.get(result.category)
    if tip:
        lines.append(tip)
    if result.cashback_card is not None and result.cashback_percent is not None:
        lines.append(
            f"По кэшбэку, который ты завёл: карта «{result.cashback_card}», "
            f"{format_percent(result.cashback_percent)}%."
        )
    if result.challenge_reset and result.challenge_category:
        lines.append(f"Челлендж «{result.challenge_category}» сброшен. Эх. Семь суток считаем заново.")
    elif result.challenge_completed and result.challenge_category is not None and result.challenge_saved is not None:
        lines.append(challenge_done_text(result.challenge_category, result.challenge_saved))
    return "\n".join(lines)


def week_text(summary: Summary) -> str:
    return (
        f"Бюджет недели {format_rub(summary.weekly_budget)}, уже записано {format_rub(summary.week_spent)}.\n"
        f"{_budget_line(summary.budget_left)}\n"
        f"В копилке {format_rub(summary.piggy_total)}."
    )


def onboarded(user: UserProfile) -> str:
    return (
        f"Записал. Зарплата {format_rub(user.salary)} в месяц, "
        f"неделя {format_rub(user.weekly_budget)}, пояс {user.timezone}.\n"
        "Трата: «купил бургер за 450».\n"
        "Если рука тянется к крупному: «хочу купить PS5 за 60к».\n"
        "Команды: /help"
    )


def welcome_back(summary: Summary, pending: ImpulseView | None) -> str:
    lines = [
        "Снова я. Деньги по-прежнему не перевожу.",
        f"Зарплата {format_rub(summary.salary)} в месяц, бюджет недели {format_rub(summary.weekly_budget)}.",
        _budget_line(summary.budget_left),
        f"В виртуальной копилке {format_rub(summary.piggy_total)}.",
        "Трата: «купил бургер за 450». Сомнение: «хочу купить PS5 за 60к».",
    ]
    if pending is not None:
        unlock = to_local(pending.created_at + STOP_WAIT, summary.timezone)
        lines.append(
            f"Ждёт решения «{pending.title}» за {format_rub(pending.price)}. "
            f"ДА имеет силу после {unlock.strftime('%d.%m %H:%M')}."
        )
    return "\n".join(lines)


def challenge_done_text(category: str, saved: Decimal) -> str:
    if saved > 0:
        return (
            f"Семь суток без «{category}». Красава. "
            f"За неделю до старта в этой категории было {format_rub(saved)} — на этих сутках они остались."
        )
    return (
        f"Семь суток без «{category}». Красава. "
        "За неделю до старта таких трат не было, и сейчас тоже чисто."
    )


def challenge_started_text(category: str, saved: Decimal, replaced: str | None) -> str:
    head = ""
    if replaced and replaced != category:
        head = f"Прошлый челлендж «{replaced}» закрыл. "
    if saved > 0:
        tail = f"За прошлые 7 суток там было {format_rub(saved)}."
    else:
        tail = "За прошлые 7 суток таких трат не было."
    return f"{head}Семь суток без «{category}». Любая трата в ней обнулит срок. {tail}"


def challenge_status_text(challenge: ChallengeView, now: datetime) -> str:
    end = ensure_naive_utc(challenge.started_at) + CHALLENGE_LENGTH
    remaining = end - ensure_naive_utc(now)
    hours = 0 if remaining.total_seconds() <= 0 else int(remaining.total_seconds() // 3600)
    if challenge.saved > 0:
        saved = f"Если дотерпишь, засчитаю {format_rub(challenge.saved)} — столько ушло за 7 суток до старта."
    else:
        saved = "До старта трат в этой категории не было."
    return f"Челлендж «{challenge.category}» идёт. До конца ещё {hours} ч. {saved}"


def cards_text(cards: list[CardView]) -> str:
    if not cards:
        return "Карт пока нет. Добавь: карта зарплатная"
    lines = ["Карты, которые ты завёл. Проценты тоже твои, я их нигде не проверяю."]
    for card in cards:
        if not card.rates:
            lines.append(f"• {card.name} — ставки не заданы")
            continue
        rates = ", ".join(f"{category} {format_percent(percent)}%" for category, percent in card.rates)
        lines.append(f"• {card.name} — {rates}")
    return "\n".join(lines)


def hint_text(category: str, card: str | None, percent: Decimal | None) -> str:
    if card is None or percent is None:
        return f"По «{category}» кэшбэка ты не задавал. Команда: кэшбэк зарплатная {category} 5"
    return f"По «{category}» выгоднее карта «{card}»: {format_percent(percent)}%."


def expenses_text(rows: list[ExpenseRow], tz_name: str) -> str:
    if not rows:
        return "Трат пока нет. Пример: купил бургер за 450"
    lines = ["Последние траты:"]
    for row in rows:
        when = to_local(row.created_at, tz_name).strftime("%d.%m %H:%M")
        lines.append(
            f"• {when} — {row.title}, {format_rub(row.amount)}, {row.category}, "
            f"в копилку {format_rub(row.roundup)}"
        )
    return "\n".join(lines)


def digest_text(hits) -> str:
    return format_digest(hits)
