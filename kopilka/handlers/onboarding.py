import logging
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from kopilka import render
from kopilka.parsing import parse_money
from kopilka.repo import create_user, get_user, latest_open_impulse, summary
from kopilka.timeutil import parse_timezone, utcnow

logger = logging.getLogger(__name__)
router = Router(name="onboarding")


class Onboarding(StatesGroup):
    salary = State()
    budget = State()
    timezone = State()


def _skip_command(text: str) -> bool:
    return text.startswith("/")


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    try:
        await _start(message, state)
    except Exception:
        logger.exception("start failed")
        await message.answer("Не достучался до базы. Проверь DATABASE_URL и что Postgres запущен.")


async def _start(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    await state.clear()
    user = get_user(message.from_user.id)
    if user is not None:
        now = utcnow()
        text = render.welcome_back(summary(user.id, now=now), latest_open_impulse(user.id))
        await message.answer(text)
        return
    await state.set_state(Onboarding.salary)
    await message.answer(render.HELLO)


@router.message(Onboarding.salary, F.text)
async def ask_salary(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if _skip_command(text):
        await message.answer("Сначала цифра зарплаты. Начать заново: /start")
        return
    amount = parse_money(text)
    if amount is None:
        await message.answer("Нужно положительное число, например 120000.")
        return
    await state.update_data(salary=str(amount))
    await state.set_state(Onboarding.budget)
    await message.answer("Какой бюджет на неделю, в рублях? Например: 7000")


@router.message(Onboarding.budget, F.text)
async def ask_budget(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    if _skip_command(text):
        await message.answer("Сначала бюджет на неделю. Начать заново: /start")
        return
    amount = parse_money(text)
    if amount is None:
        await message.answer("Нужно положительное число, например 7000.")
        return
    await state.update_data(budget=str(amount))
    await state.set_state(Onboarding.timezone)
    await message.answer("Часовой пояс. Если живёшь по Москве — напиши «ок».\nИначе имя из IANA, например Asia/Yekaterinburg.")


@router.message(Onboarding.timezone, F.text)
async def ask_timezone(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    text = message.text or ""
    if _skip_command(text):
        await message.answer("Сначала пояс или «ок». Начать заново: /start")
        return
    tz_name = parse_timezone(text)
    if tz_name is None:
        await message.answer("Не знаю такой пояс. Москва — «ок». Иначе, например, Asia/Yekaterinburg.")
        return
    data = await state.get_data()
    try:
        user = create_user(
            message.from_user.id,
            Decimal(data["salary"]),
            Decimal(data["budget"]),
            tz_name,
        )
    except Exception:
        logger.exception("onboarding save failed")
        await message.answer("Не смог записать анкету. Проверь, что Postgres запущен.")
        return
    await state.clear()
    await message.answer(render.onboarded(user))
