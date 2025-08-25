import json
import random
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.markdown import hlink

API_TOKEN = "8493652517:AAF-0_XnnIflzh0lAx5mQisHdX3ILkAXcKE"

# --- Настройки ---
SPONSORS = [
    "S1eepy_Stars",
    "RussiansDurov",
    "star_yum",
    "ygolokamika",
    "spirix_nft",
    "shizonick"
]

DATA_FILE = "data.json"

# --- Заготовки капчи ---
CAPTCHAS = [(f"{a}+{b}", str(a+b)) for a in range(1, 13) for b in range(1, 13)]
CAPTCHAS = CAPTCHAS[:25]  # оставляем только 25 примеров

# --- Бот ---
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)


# --- Работа с JSON ---
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# --- Проверка подписки ---
async def check_subscriptions(user_id):
    for channel in SPONSORS:
        try:
            member = await bot.get_chat_member(f"@{channel}", user_id)
            if member.status == "left":
                return False
        except:
            return False
    return True


# --- Клавиатуры ---
def reply_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("Заработать звёзды ⭐️"), KeyboardButton("Буст за звёзды 💎"))
    kb.add(KeyboardButton("Вывести звёзды ⭐️"), KeyboardButton("Подарок 🎁"))
    return kb


def sponsors_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for channel in SPONSORS:
        kb.insert(InlineKeyboardButton(text=f"@{channel}", url=f"https://t.me/{channel}"))
    kb.add(InlineKeyboardButton("✅ Я подписался", callback_data="check_subs"))
    return kb


def withdraw_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("15 ⭐️", callback_data="withdraw_15"),
        InlineKeyboardButton("25 ⭐️", callback_data="withdraw_25"),
        InlineKeyboardButton("50 ⭐️", callback_data="withdraw_50"),
        InlineKeyboardButton("75 ⭐️", callback_data="withdraw_75"),
        InlineKeyboardButton("100 ⭐️", callback_data="withdraw_100")
    )
    return kb


# --- Старт ---
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    user_id = str(msg.from_user.id)
    data = load_data()

    # Если новый → проверяем реферальную систему
    args = msg.get_args()
    if user_id not in data:
        data[user_id] = {"stars": 0, "invited": [], "captcha_ok": False, "subscribed": False, "boosted": False}
        save_data(data)

        if args and args.isdigit() and args != user_id:
            if args in data and user_id not in data[args]["invited"]:
                data[args]["stars"] += 0.5
                data[args]["invited"].append(user_id)
                save_data(data)
                await bot.send_message(args, f"👥 Новый друг зарегистрировался по твоей ссылке! +0.5 ⭐️")

    # Проверка капчи
    if not data[user_id]["captcha_ok"]:
        expr, ans = random.choice(CAPTCHAS)
        data[user_id]["captcha"] = ans
        save_data(data)
        await msg.answer(f"🤖 Для защиты от ботов реши пример:\n\n<b>{expr} = ?</b>")
        return

    # Если капча уже пройдена
    if not data[user_id]["subscribed"]:
        await msg.answer("Чтобы пользоваться ботом необходимо подписаться на наших спонсоров:", reply_markup=sponsors_kb())
    else:
        await msg.answer("Добро пожаловать! ✨", reply_markup=reply_kb())


# --- Проверка капчи ---
@dp.message_handler(lambda m: m.text and m.text.isdigit())
async def captcha_check(msg: types.Message):
    user_id = str(msg.from_user.id)
    data = load_data()

    if user_id in data and not data[user_id]["captcha_ok"]:
        if msg.text == data[user_id]["captcha"]:
            data[user_id]["captcha_ok"] = True
            save_data(data)
            await msg.answer("✅ Верно!\nТеперь подпишись на спонсоров:", reply_markup=sponsors_kb())
        else:
            await msg.answer("❌ Неверно. Попробуй ещё раз командой /start")


# --- Проверка подписки ---
@dp.callback_query_handler(lambda c: c.data == "check_subs")
async def check_subs(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    if await check_subscriptions(user_id):
        data = load_data()
        data[user_id]["subscribed"] = True
        save_data(data)
        await call.message.answer("🎉 Доступ открыт!", reply_markup=reply_kb())
    else:
        await call.message.answer("❌ Ты не подписался на все каналы!")


# --- Заработать ---
@dp.message_handler(lambda m: m.text == "Заработать звёзды ⭐️")
async def earn(msg: types.Message):
    user_id = str(msg.from_user.id)
    data = load_data()
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    await msg.answer(
        f"<b>🤝 За каждого приглашённого друга ты получишь 0.5 ⭐️</b>\n\n"
        f"🔗 Твоя ссылка: <b>{ref_link}</b>\n"
        f"👥 Всего пригласил: <b>{len(data[user_id]['invited'])}</b> чел.\n"
        f"⭐ Баланс: <b>{data[user_id]['stars']}</b>"
    )


# --- Буст ---
@dp.message_handler(lambda m: m.text == "Буст за звёзды 💎")
async def boost(msg: types.Message):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Забустить канал", url="https://t.me/boost/Vestelll1"))
    kb.add(InlineKeyboardButton("✅ Я забустил", callback_data="check_boost"))
    await msg.answer("За буст вы получите +2 ⭐️", reply_markup=kb)


from datetime import datetime

@dp.message_handler(lambda m: m.text == "Подарок 🎁")
async def gift(msg: types.Message):
    user_id = str(msg.from_user.id)
    data = load_data()

    today = datetime.now().strftime("%Y-%m-%d")  # текущая дата
    last_gift = data[user_id].get("last_gift", "")

    if last_gift == today:
        await msg.answer("❌ Ты уже получал подарок сегодня! Попробуй завтра.")
    else:
        data[user_id]["stars"] += 1
        data[user_id]["last_gift"] = today
        save_data(data)
        await msg.answer("🎉 Поздравляю! Ты получил +1 ⭐️ за сегодняшний подарок!", reply_markup=reply_kb())

@dp.callback_query_handler(lambda c: c.data == "check_boost")
async def check_boost(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    data = load_data()

    member = await bot.get_chat_member("@Vestelll1", user_id)
    if getattr(member, "is_premium", False):  # проверяем премиум/буст
        if not data[user_id]["boosted"]:
            data[user_id]["stars"] += 2
            data[user_id]["boosted"] = True
            save_data(data)
            await call.message.answer("🎉 Спасибо за буст! +2 ⭐️ начислено.")
        else:
            await call.message.answer("❌ Ты уже забустил, награду получил.")
    else:
        await call.message.answer("❌ Буст не обнаружен.")


# --- Вывод ---
@dp.message_handler(lambda m: m.text == "Вывести звёзды ⭐️")
async def withdraw(msg: types.Message):
    user_id = str(msg.from_user.id)
    data = load_data()
    await msg.answer(
        f"Вывод звёзд\n\nБаланс: {data[user_id]['stars']} ⭐️\n\nСколько хотите вывести?",
        reply_markup=withdraw_kb()
    )


@dp.callback_query_handler(lambda c: c.data.startswith("withdraw_"))
async def withdraw_handler(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    data = load_data()

    # суммм по callback_data
    amount = int(call.data.split("_")[1])
    
    if data[user_id]["stars"] >= amount:
        data[user_id]["stars"] -= amount
        save_data(data)
        await call.message.answer(f"✅ <b>Вывод {amount} ⭐️ успешно поставлен!</b> Придут в течение 48 часов.")
    else:
        await call.message.answer("❌ <b>Недостаточно ⭐️ для вывода.</b>")


# --- Запуск ---
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
