"""Виртуальные деньги. Переводов и банковских API здесь нет и не должно появиться в v1."""

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING

from kopilka.timeutil import deadline_reached

ROUND_STEP = Decimal("100")
SALARY_THRESHOLD = Decimal("0.10")
DEFAULT_WORK_HOURS = 160
STOP_WAIT = timedelta(hours=24)
CHALLENGE_LENGTH = timedelta(days=7)
CENT = Decimal("0.01")


def q2(value: Decimal) -> Decimal:
    if isinstance(value, float):
        return Decimal(str(value)).quantize(CENT)
    return Decimal(value).quantize(CENT)


def virtual_roundup(amount: Decimal) -> tuple[Decimal, Decimal]:
    """Округление вверх до 100 ₽. Возвращает (сумма после округления, сколько в копилку).

    180 → (200, 20). Кратные 100 дают 0 в копилку. Это учёт, не платёж.
    """
    amount = Decimal(amount)
    if amount <= 0:
        raise ValueError("amount must be positive")
    units = (amount / ROUND_STEP).to_integral_value(rounding=ROUND_CEILING)
    rounded = q2(units * ROUND_STEP)
    piggy = q2(rounded - amount)
    return rounded, piggy


def exceeds_salary_share(
    price: Decimal,
    salary: Decimal,
    share: Decimal = SALARY_THRESHOLD,
) -> bool:
    """Строго больше доли зарплаты. Ровно 10% стоп-кран не включает."""
    if price <= 0:
        raise ValueError("price must be positive")
    if salary <= 0:
        raise ValueError("salary must be positive")
    return Decimal(price) > Decimal(salary) * Decimal(share)


def hours_of_work(
    price: Decimal,
    salary: Decimal,
    hours_per_month: int = DEFAULT_WORK_HOURS,
) -> Decimal:
    if salary <= 0:
        raise ValueError("salary must be positive")
    if hours_per_month <= 0:
        raise ValueError("hours_per_month must be positive")
    hourly = Decimal(salary) / Decimal(hours_per_month)
    return (Decimal(price) / hourly).quantize(Decimal("0.1"))


def confirmation_allowed(requested_at: datetime, now: datetime) -> bool:
    """ДА по стоп-крану можно нажать, когда с момента желания прошли сутки."""
    return deadline_reached(requested_at, now, STOP_WAIT)


def challenge_finished(started_at: datetime, now: datetime) -> bool:
    return deadline_reached(started_at, now, CHALLENGE_LENGTH)
