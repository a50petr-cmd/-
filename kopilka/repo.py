"""Запись в базу. Считает виртуальную копилку и не ходит в платёжные API."""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from kopilka.categories import breaks_challenge
from kopilka.db import session_scope
from kopilka.models import CancelLink, Card, CardRate, Challenge, Expense, Impulse, User
from kopilka.money import DEFAULT_WORK_HOURS, challenge_finished, q2, virtual_roundup
from kopilka.recurring import TransactionView, norm_label
from kopilka.timeutil import ensure_naive_utc, start_of_week_utc_naive, to_local, utcnow
from kopilka.views import (
    CardView,
    ChallengeView,
    ExpenseRow,
    ImpulseView,
    LoggedExpense,
    Summary,
    UserProfile,
)


def _profile(user: User) -> UserProfile:
    return UserProfile(
        id=user.id,
        telegram_id=user.telegram_id,
        salary=q2(user.salary),
        weekly_budget=q2(user.weekly_budget),
        timezone=user.timezone,
        work_hours_per_month=user.work_hours_per_month,
        last_digest_month=user.last_digest_month,
    )


def _impulse(row: Impulse) -> ImpulseView:
    return ImpulseView(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        price=q2(row.price),
        created_at=ensure_naive_utc(row.created_at),
        status=row.status,
    )


def _challenge(row: Challenge) -> ChallengeView:
    return ChallengeView(
        category=row.category,
        started_at=ensure_naive_utc(row.started_at),
        saved=q2(row.saved),
        status=row.status,
    )


def create_user(
    telegram_id: int,
    salary: Decimal,
    weekly_budget: Decimal,
    timezone: str,
    *,
    now: datetime | None = None,
) -> UserProfile:
    moment = ensure_naive_utc(now or utcnow())
    with session_scope() as db:
        existing = db.scalar(select(User).where(User.telegram_id == telegram_id))
        if existing is None:
            existing = User(
                telegram_id=telegram_id,
                salary=q2(salary),
                weekly_budget=q2(weekly_budget),
                timezone=timezone,
                work_hours_per_month=DEFAULT_WORK_HOURS,
                created_at=moment,
            )
            db.add(existing)
        else:
            existing.salary = q2(salary)
            existing.weekly_budget = q2(weekly_budget)
            existing.timezone = timezone
        db.flush()
        return _profile(existing)


def get_user(telegram_id: int) -> UserProfile | None:
    with session_scope() as db:
        row = db.scalar(select(User).where(User.telegram_id == telegram_id))
        return _profile(row) if row else None


def get_user_by_id(user_id: int) -> UserProfile | None:
    with session_scope() as db:
        row = db.get(User, user_id)
        return _profile(row) if row else None


def update_profile(
    user_id: int,
    *,
    salary: Decimal | None = None,
    weekly_budget: Decimal | None = None,
    timezone: str | None = None,
) -> UserProfile:
    with session_scope() as db:
        row = db.get(User, user_id)
        if row is None:
            raise LookupError("user")
        if salary is not None:
            row.salary = q2(salary)
        if weekly_budget is not None:
            row.weekly_budget = q2(weekly_budget)
        if timezone is not None:
            row.timezone = timezone
        db.flush()
        return _profile(row)


def mark_digest(user_id: int, month_key: str) -> None:
    with session_scope() as db:
        row = db.get(User, user_id)
        if row is None:
            raise LookupError("user")
        row.last_digest_month = month_key


def _sum_amount(
    db,
    user_id: int,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    category: str | None = None,
    exclude_id: int | None = None,
) -> Decimal:
    query = select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.user_id == user_id)
    if since is not None:
        query = query.where(Expense.created_at >= since)
    if until is not None:
        query = query.where(Expense.created_at < until)
    if category is not None:
        query = query.where(Expense.category == category)
    if exclude_id is not None:
        query = query.where(Expense.id != exclude_id)
    return q2(db.scalar(query) or 0)


def _piggy(db, user_id: int) -> Decimal:
    total = db.scalar(select(func.coalesce(func.sum(Expense.roundup), 0)).where(Expense.user_id == user_id))
    return q2(total or 0)


def summary(user_id: int, *, now: datetime | None = None) -> Summary:
    moment = ensure_naive_utc(now or utcnow())
    with session_scope() as db:
        user = db.get(User, user_id)
        if user is None:
            raise LookupError("user")
        week_start = start_of_week_utc_naive(moment, user.timezone)
        spent = _sum_amount(db, user_id, since=week_start)
        budget = q2(user.weekly_budget)
        return Summary(
            salary=q2(user.salary),
            weekly_budget=budget,
            week_spent=spent,
            budget_left=q2(budget - spent),
            piggy_total=_piggy(db, user_id),
            timezone=user.timezone,
        )


def _best_cashback(db, user_id: int, category: str) -> tuple[str, Decimal] | None:
    rows = db.execute(
        select(Card.name, CardRate.percent)
        .join(CardRate, CardRate.card_id == Card.id)
        .where(Card.user_id == user_id, CardRate.category == category)
        .order_by(CardRate.percent.desc(), Card.name.asc())
    ).all()
    if not rows:
        return None
    return rows[0][0], q2(rows[0][1])


def _apply_challenge(
    db,
    user: User,
    *,
    category: str,
    title: str,
    now: datetime,
    exclude_id: int | None = None,
) -> tuple[bool, bool, str | None, Decimal | None]:
    row = db.scalar(
        select(Challenge).where(Challenge.user_id == user.id, Challenge.status == "active")
    )
    if row is None:
        return False, False, None, None
    if breaks_challenge(row.category, category, title):
        row.started_at = now
        row.saved = _sum_amount(
            db,
            user.id,
            since=now - timedelta(days=7),
            until=now,
            category=row.category,
            exclude_id=exclude_id,
        )
        return True, False, row.category, row.saved
    if challenge_finished(row.started_at, now):
        row.status = "done"
        return False, True, row.category, q2(row.saved)
    return False, False, None, None


def add_expense(
    user_id: int,
    *,
    title: str,
    amount: Decimal,
    category: str,
    raw_text: str,
    now: datetime | None = None,
) -> LoggedExpense:
    moment = ensure_naive_utc(now or utcnow())
    rounded, piggy_delta = virtual_roundup(q2(amount))
    with session_scope() as db:
        user = db.get(User, user_id)
        if user is None:
            raise LookupError("user")
        expense = Expense(
            user_id=user_id,
            amount=q2(amount),
            roundup=piggy_delta,
            category=category[:64],
            title=title[:200],
            raw_text=raw_text[:500],
            created_at=moment,
        )
        db.add(expense)
        db.flush()
        reset, completed, challenge_category, saved = _apply_challenge(
            db,
            user,
            category=category,
            title=title,
            now=moment,
            exclude_id=expense.id,
        )
        week_start = start_of_week_utc_naive(moment, user.timezone)
        week_count = db.scalar(
            select(func.count(Expense.id)).where(
                Expense.user_id == user_id,
                Expense.category == category,
                Expense.created_at >= week_start,
            )
        )
        spent = _sum_amount(db, user_id, since=week_start)
        cashback = _best_cashback(db, user_id, category)
        return LoggedExpense(
            title=title[:200],
            amount=q2(amount),
            category=category[:64],
            rounded=rounded,
            piggy_delta=piggy_delta,
            week_count=int(week_count or 0),
            budget_left=q2(q2(user.weekly_budget) - spent),
            piggy_total=_piggy(db, user_id),
            cashback_card=cashback[0] if cashback else None,
            cashback_percent=cashback[1] if cashback else None,
            challenge_reset=reset,
            challenge_completed=completed,
            challenge_category=challenge_category,
            challenge_saved=q2(saved) if saved is not None else None,
        )


def recent_expenses(user_id: int, limit: int = 10) -> list[ExpenseRow]:
    with session_scope() as db:
        rows = db.scalars(
            select(Expense).where(Expense.user_id == user_id).order_by(Expense.created_at.desc()).limit(limit)
        ).all()
        return [
            ExpenseRow(
                title=row.title,
                amount=q2(row.amount),
                category=row.category,
                roundup=q2(row.roundup),
                created_at=ensure_naive_utc(row.created_at),
            )
            for row in rows
        ]


def open_impulse(user_id: int, title: str, price: Decimal, *, now: datetime | None = None) -> ImpulseView:
    moment = ensure_naive_utc(now or utcnow())
    with session_scope() as db:
        row = Impulse(
            user_id=user_id,
            title=title[:200],
            price=q2(price),
            status="open",
            created_at=moment,
        )
        db.add(row)
        db.flush()
        return _impulse(row)


def latest_open_impulse(user_id: int) -> ImpulseView | None:
    with session_scope() as db:
        row = db.scalar(
            select(Impulse)
            .where(Impulse.user_id == user_id, Impulse.status == "open")
            .order_by(Impulse.created_at.desc(), Impulse.id.desc())
        )
        return _impulse(row) if row else None


def get_impulse(impulse_id: int) -> ImpulseView | None:
    with session_scope() as db:
        row = db.get(Impulse, impulse_id)
        return _impulse(row) if row else None


def decide_impulse(impulse_id: int, status: str, *, now: datetime | None = None) -> ImpulseView:
    moment = ensure_naive_utc(now or utcnow())
    with session_scope() as db:
        row = db.get(Impulse, impulse_id)
        if row is None:
            raise LookupError("impulse")
        row.status = status
        row.decided_at = moment
        db.flush()
        return _impulse(row)


def last_declined(user_id: int) -> ImpulseView | None:
    with session_scope() as db:
        row = db.scalar(
            select(Impulse)
            .where(Impulse.user_id == user_id, Impulse.status == "declined")
            .order_by(Impulse.created_at.desc(), Impulse.id.desc())
        )
        return _impulse(row) if row else None


def _category_saved(db, user_id: int, category: str, now: datetime) -> Decimal:
    return _sum_amount(db, user_id, since=now - timedelta(days=7), until=now, category=category)


def start_challenge(user_id: int, category: str, *, now: datetime | None = None) -> tuple[ChallengeView, str | None]:
    moment = ensure_naive_utc(now or utcnow())
    with session_scope() as db:
        previous = db.scalar(
            select(Challenge).where(Challenge.user_id == user_id, Challenge.status == "active")
        )
        replaced = None
        if previous is not None:
            replaced = previous.category
            previous.status = "replaced"
        saved = _category_saved(db, user_id, category, moment)
        row = Challenge(
            user_id=user_id,
            category=category[:64],
            started_at=moment,
            saved=saved,
            status="active",
        )
        db.add(row)
        db.flush()
        return _challenge(row), replaced


def active_challenge(user_id: int) -> ChallengeView | None:
    with session_scope() as db:
        row = db.scalar(select(Challenge).where(Challenge.user_id == user_id, Challenge.status == "active"))
        return _challenge(row) if row else None


def last_done_challenge(user_id: int) -> ChallengeView | None:
    with session_scope() as db:
        row = db.scalar(
            select(Challenge)
            .where(Challenge.user_id == user_id, Challenge.status == "done")
            .order_by(Challenge.started_at.desc(), Challenge.id.desc())
        )
        return _challenge(row) if row else None


def finish_challenge_if_due(user_id: int, *, now: datetime | None = None) -> ChallengeView | None:
    moment = ensure_naive_utc(now or utcnow())
    with session_scope() as db:
        row = db.scalar(select(Challenge).where(Challenge.user_id == user_id, Challenge.status == "active"))
        if row is None or not challenge_finished(row.started_at, moment):
            return None
        row.status = "done"
        db.flush()
        return _challenge(row)


def add_card(user_id: int, name: str) -> str:
    cleaned = " ".join(name.split())[:80]
    with session_scope() as db:
        found = _find_card(db, user_id, cleaned)
        if found is not None:
            return found.name
        db.add(Card(user_id=user_id, name=cleaned))
        return cleaned


def _find_card(db, user_id: int, name: str) -> Card | None:
    target = name.casefold()
    rows = db.scalars(select(Card).where(Card.user_id == user_id)).all()
    for row in rows:
        if row.name.casefold() == target:
            return row
    return None


def set_cashback(user_id: int, card_name: str, category: str, percent: Decimal) -> bool:
    with session_scope() as db:
        card = _find_card(db, user_id, card_name)
        if card is None:
            return False
        rate = db.scalar(
            select(CardRate).where(CardRate.card_id == card.id, CardRate.category == category)
        )
        if rate is None:
            db.add(CardRate(card_id=card.id, category=category[:64], percent=q2(percent)))
        else:
            rate.percent = q2(percent)
        return True


def list_cards(user_id: int) -> list[CardView]:
    with session_scope() as db:
        cards = db.scalars(select(Card).where(Card.user_id == user_id).order_by(Card.name.asc())).all()
        views = []
        for card in cards:
            rates = db.execute(
                select(CardRate.category, CardRate.percent)
                .where(CardRate.card_id == card.id)
                .order_by(CardRate.category.asc())
            ).all()
            views.append(
                CardView(
                    name=card.name,
                    rates=tuple((category, q2(percent)) for category, percent in rates),
                )
            )
        return views


def best_cashback(user_id: int, category: str) -> tuple[str, Decimal] | None:
    with session_scope() as db:
        return _best_cashback(db, user_id, category)


def save_cancel_link(user_id: int, label: str, url: str) -> None:
    stored = norm_label(label)[:200] or label.strip()[:200]
    with session_scope() as db:
        row = db.scalar(select(CancelLink).where(CancelLink.user_id == user_id, CancelLink.label == stored))
        if row is None:
            db.add(CancelLink(user_id=user_id, label=stored, url=url[:500]))
        else:
            row.url = url[:500]


def load_transactions(user_id: int) -> list[TransactionView]:
    with session_scope() as db:
        user = db.get(User, user_id)
        if user is None:
            raise LookupError("user")
        links = {
            row.label: row.url
            for row in db.scalars(select(CancelLink).where(CancelLink.user_id == user_id)).all()
        }
        expenses = db.scalars(select(Expense).where(Expense.user_id == user_id)).all()
        views = []
        for row in expenses:
            key = norm_label(row.title)
            views.append(
                TransactionView(
                    amount=q2(row.amount),
                    label=row.title,
                    occurred_on=to_local(row.created_at, user.timezone).date(),
                    cancel_url=links.get(key),
                )
            )
        return views
