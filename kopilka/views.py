from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class UserProfile:
    id: int
    telegram_id: int
    salary: Decimal
    weekly_budget: Decimal
    timezone: str
    work_hours_per_month: int
    last_digest_month: str | None


@dataclass(frozen=True)
class Summary:
    salary: Decimal
    weekly_budget: Decimal
    week_spent: Decimal
    budget_left: Decimal
    piggy_total: Decimal
    timezone: str


@dataclass(frozen=True)
class LoggedExpense:
    title: str
    amount: Decimal
    category: str
    rounded: Decimal
    piggy_delta: Decimal
    week_count: int
    budget_left: Decimal
    piggy_total: Decimal
    cashback_card: str | None
    cashback_percent: Decimal | None
    challenge_reset: bool
    challenge_completed: bool
    challenge_category: str | None
    challenge_saved: Decimal | None


@dataclass(frozen=True)
class ExpenseRow:
    title: str
    amount: Decimal
    category: str
    roundup: Decimal
    created_at: datetime


@dataclass(frozen=True)
class ImpulseView:
    id: int
    user_id: int
    title: str
    price: Decimal
    created_at: datetime
    status: str


@dataclass(frozen=True)
class ChallengeView:
    category: str
    started_at: datetime
    saved: Decimal
    status: str


@dataclass(frozen=True)
class CardView:
    name: str
    rates: tuple[tuple[str, Decimal], ...]
