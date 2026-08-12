import asyncio
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import sqlite3
import time
from contextlib import closing
from typing import Optional

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv
import qrcode

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
# Render supplies PORT automatically for web services.
WEBHOOK_PORT = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "10000")))

SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@Help_desk3_bot").strip()
DB_PATH = os.getenv("DB_PATH", "store.db").strip()

PLANS = {
    "gold": {
        "name": "⚡ Gold Dark (Channel 1)",
        "price": 1499,
        "description": "Gold Dark — Lifetime Access",
        "channel_id": os.getenv("GOLD_CHANNEL_ID", "").strip(),
        "access_link": os.getenv("GOLD_ACCESS_LINK", "").strip(),
    },
    "silver": {
        "name": "⚡ Silver Dark (Channel 2)",
        "price": 1499,
        "description": "Silver Dark — Lifetime Access",
        "channel_id": os.getenv("SILVER_CHANNEL_ID", "").strip(),
        "access_link": os.getenv("SILVER_ACCESS_LINK", "").strip(),
    },
    "bronze": {
        "name": "⚡ Bronze Dark (Channel 3)",
        "price": 1499,
        "description": "Bronze Dark — Lifetime Access",
        "channel_id": os.getenv("BRONZE_CHANNEL_ID", "").strip(),
        "access_link": os.getenv("BRONZE_ACCESS_LINK", "").strip(),
    },
    "iron": {
        "name": "⚡ Iron Dark (Channel 4)",
        "price": 1499,
        "description": "Iron Dark — Lifetime Access",
        "channel_id": os.getenv("IRON_CHANNEL_ID", "").strip(),
        "access_link": os.getenv("IRON_ACCESS_LINK", "").strip(),
    },
}

router = Router()
bot: Optional[Bot] = None


# =========================
# DATABASE
# =========================
def db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with closing(db()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                reference_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                plan_key TEXT NOT NULL,
                amount_paise INTEGER NOT NULL,
                payment_link_id TEXT,
                payment_link_url TEXT,
                status TEXT NOT NULL DEFAULT 'created',
                payment_id TEXT,
                created_at INTEGER NOT NULL,
                paid_at INTEGER,
                access_sent INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def save_order(reference_id, user_id, plan_key, amount_paise, payment_link_id, payment_link_url):
    with closing(db()) as conn:
        conn.execute(
            """
            INSERT INTO orders
            (reference_id, user_id, plan_key, amount_paise, payment_link_id,
             payment_link_url, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'created', ?)
            """,
            (
                reference_id,
                user_id,
                plan_key,
                amount_paise,
                payment_link_id,
                payment_link_url,
                int(time.time()),
            ),
        )
        conn.commit()


def get_order(reference_id):
    with closing(db()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM orders WHERE reference_id = ?", (reference_id,)
        ).fetchone()
        return dict(row) if row else None


def get_latest_order(user_id):
    with closing(db()) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT * FROM orders
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def mark_paid(reference_id, payment_id):
    with closing(db()) as conn:
        conn.execute(
            """
            UPDATE orders
            SET status = 'paid', payment_id = ?, paid_at = ?
            WHERE reference_id = ?
            """,
            (payment_id, int(time.time()), reference_id),
        )
        conn.commit()


def mark_access_sent(reference_id):
    with closing(db()) as conn:
        conn.execute(
            "UPDATE orders SET access_sent = 1 WHERE reference_id = ?",
            (reference_id,),
        )
        conn.commit()


def event_already_processed(event_id):
    if not event_id:
        return False
    with closing(db()) as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        return bool(row)


def save_event(event_id):
    if not event_id:
        return
    with closing(db()) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_events (event_id, created_at) VALUES (?, ?)",
            (event_id, int(time.time())),
        )
        conn.commit()


# =========================
# RAZORPAY
# =========================
def validate_razorpay_config():
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not RAZORPAY_KEY_ID:
        missing.append("RAZORPAY_KEY_ID")
    if not RAZORPAY_KEY_SECRET:
        missing.append("RAZORPAY_KEY_SECRET")
    if not RAZORPAY_WEBHOOK_SECRET:
        missing.append("RAZORPAY_WEBHOOK_SECRET")
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))


async def razorpay_request(method: str, endpoint: str, payload=None):
    url = f"https://api.razorpay.com/v1/{endpoint.lstrip('/')}"
    auth = aiohttp.BasicAuth(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
    timeout = aiohttp.ClientTimeout(total=20)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.request(method, url, auth=auth, json=payload) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"Razorpay HTTP {resp.status}: {text[:1000]}")
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                raise RuntimeError(f"Razorpay returned invalid JSON: {text[:500]}")


async def create_payment_link(user_id: int, plan_key: str):
    plan = PLANS[plan_key]
    amount_paise = int(plan["price"] * 100)
    reference_id = f"{user_id}_{secrets.token_hex(8)}"

    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "reference_id": reference_id,
        "description": plan["description"],
        "notify": {"sms": False, "email": False, "whatsapp": False},
        "reminder_enable": False,
        "notes": {
            "telegram_user_id": str(user_id),
            "plan_key": plan_key,
        },
    }

    result = await razorpay_request("POST", "payment_links", payload)

    if not result.get("id") or not result.get("short_url"):
        raise RuntimeError(f"Invalid Razorpay payment-link response: {result}")

    save_order(
        reference_id=reference_id,
        user_id=user_id,
        plan_key=plan_key,
        amount_paise=amount_paise,
        payment_link_id=result["id"],
        payment_link_url=result["short_url"],
    )
    return result


def verify_webhook(raw_body: bytes, received_signature: str) -> bool:
    if not RAZORPAY_WEBHOOK_SECRET or not received_signature:
        return False

    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, received_signature)


# =========================
# TELEGRAM UI
# =========================
def support_url():
    return f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}"


def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Gold Dark (Channel 1)", callback_data="plan:gold")],
            [InlineKeyboardButton(text="⚡ Silver Dark (Channel 2)", callback_data="plan:silver")],
            [InlineKeyboardButton(text="⚡ Bronze Dark (Channel 3)", callback_data="plan:bronze")],
            [InlineKeyboardButton(text="⚡ Iron Dark (Channel 4)", callback_data="plan:iron")],
            [InlineKeyboardButton(text="📋 My Plan", callback_data="myplan")],
            [InlineKeyboardButton(text="📞 Support", url=support_url())],
        ]
    )


def plan_keyboard(plan_key: str):
    plan = PLANS[plan_key]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"⭐ Lifetime ₹{plan['price']}", callback_data=f"buy:{plan_key}")],
            [InlineKeyboardButton(text="↩️ Back", callback_data="home")],
        ]
    )


def payment_keyboard(plan_key: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Check Payment", callback_data=f"check:{plan_key}")],
            [InlineKeyboardButton(text="↩️ Back", callback_data="home")],
        ]
    )


async def send_home(chat_id: int):
    text = (
        "👋 <b>Welcome to DARK STORE!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "<blockquote><b>Channels:</b>\n"
        "⚡ Gold Dark (Channel 1)\n"
        "⚡ Silver Dark (Channel 2)\n"
        "⚡ Bronze Dark (Channel 3)\n"
        "⚡ Iron Dark (Channel 4)</blockquote>\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💬 Support: {SUPPORT_USERNAME}\n\n"
        "🤖 <i>Powered by Telegram Store Bot</i>"
    )
    await bot.send_message(chat_id, text, reply_markup=main_keyboard())


@router.message(CommandStart())
async def start_handler(message: Message):
    await send_home(message.chat.id)


@router.callback_query(F.data == "home")
async def home_callback(callback: CallbackQuery):
    await callback.answer()
    await send_home(callback.message.chat.id)


@router.callback_query(F.data.startswith("plan:"))
async def plan_callback(callback: CallbackQuery):
    await callback.answer()
    plan_key = callback.data.split(":", 1)[1]

    if plan_key not in PLANS:
        await callback.message.answer("❌ Invalid plan.")
        return

    plan = PLANS[plan_key]
    text = f"<b>{plan['name']}</b>\n━━━━━━━━━━━━━━━━━━\n\nSelect your plan:"
    await callback.message.answer(text, reply_markup=plan_keyboard(plan_key))


@router.callback_query(F.data.startswith("buy:"))
async def buy_callback(callback: CallbackQuery):
    await callback.answer("Generating dynamic QR code…")
    plan_key = callback.data.split(":", 1)[1]

    if plan_key not in PLANS:
        await callback.message.answer("❌ Invalid plan.")
        return

    try:
        result = await create_payment_link(callback.from_user.id, plan_key)
    except Exception:
        logger.exception("Payment link creation failed")
        await callback.message.answer(
            "❌ Payment QR create nahi ho paya.\n"
            "Thodi der baad try karein ya Support se contact karein."
        )
        return

    plan = PLANS[plan_key]
    payment_url = result["short_url"]

    # Dynamic QR contains the unique Razorpay Payment Link URL.
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payment_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_file = BufferedInputFile(buf.getvalue(), filename="payment_qr.png")

    text = (
        "💳 <b>Scan & Pay</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Plan: <b>{plan['name']}</b>\n"
        f"💰 Amount: <b>₹{plan['price']}</b>\n\n"
        "📱 <b>GPay / PhonePe / Paytm / any supported UPI app se QR scan karein.</b>\n\n"
        "⏱️ Payment complete hone ke baad neeche <b>Check Payment</b> dabayein."
    )

    await callback.message.answer_photo(
        photo=qr_file,
        caption=text,
        reply_markup=payment_keyboard(plan_key),
    )


async def make_access_link(plan_key: str) -> Optional[str]:
    plan = PLANS[plan_key]

    if plan["channel_id"]:
        try:
            invite = await bot.create_chat_invite_link(
                chat_id=plan["channel_id"],
                member_limit=1,
            )
            return invite.invite_link
        except Exception:
            logger.exception("Invite link creation failed for %s", plan_key)

    return plan["access_link"] or None


async def deliver_access(order: dict):
    if order.get("access_sent"):
        return True

    access_link = await make_access_link(order["plan_key"])

    if not access_link:
        await bot.send_message(
            order["user_id"],
            "✅ <b>Payment confirmed.</b>\n\n"
            "Lekin access link configure nahi hai.\n"
            f"📞 Support: {SUPPORT_USERNAME}",
        )
        return False

    plan = PLANS[order["plan_key"]]
    await bot.send_message(
        order["user_id"],
        "🎉 <b>Payment Confirmed!</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Plan: <b>{plan['name']}</b>\n"
        f"💰 Paid: <b>₹{order['amount_paise'] / 100:.2f}</b>\n"
        f"🧾 Payment ID: <code>{order.get('payment_id') or '-'}</code>\n\n"
        "🔗 <b>Your Access Link:</b>\n"
        f"{access_link}"
    )
    mark_access_sent(order["reference_id"])
    return True


async def process_paid_event(event: dict):
    pl = event.get("payload", {}).get("payment_link", {}).get("entity", {})
    payment = event.get("payload", {}).get("payment", {}).get("entity", {})

    reference_id = pl.get("reference_id")
    if not reference_id:
        logger.warning("payment_link.paid event has no reference_id")
        return

    order = get_order(reference_id)
    if not order:
        logger.warning("Order not found for reference_id=%s", reference_id)
        return

    payment_id = payment.get("id") or ""
    mark_paid(reference_id, payment_id)

    updated = get_order(reference_id)
    if updated and not updated["access_sent"]:
        try:
            await deliver_access(updated)
        except Exception:
            logger.exception("Access delivery failed")


@router.callback_query(F.data == "myplan")
async def myplan_callback(callback: CallbackQuery):
    await callback.answer()
    await send_my_plan(callback.message)


@router.message(Command("myplan"))
async def myplan_message(message: Message):
    await send_my_plan(message)


async def send_my_plan(message: Message):
    order = get_latest_order(message.from_user.id)

    if not order:
        await message.answer(
            "📋 <b>My Plan</b>\n\nAapka koi order nahi mila.",
            reply_markup=main_keyboard(),
        )
        return

    plan = PLANS.get(order["plan_key"], {})
    status = order["status"].upper()

    if order["status"] == "paid":
        text = (
            "📋 <b>My Plan</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 Plan: <b>{plan.get('name', order['plan_key'])}</b>\n"
            f"💰 Amount: <b>₹{order['amount_paise'] / 100:.2f}</b>\n"
            "📌 Status: <b>PAID</b>\n"
            f"🧾 Payment ID: <code>{order.get('payment_id') or '-'}</code>\n\n"
            "Access lene ke liye neeche button dabayein."
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Send Access Link", callback_data=f"access:{order['reference_id']}")],
                [InlineKeyboardButton(text="↩️ Back", callback_data="home")],
            ]
        )
        await message.answer(text, reply_markup=kb)
    else:
        await message.answer(
            "📋 <b>My Plan</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 Plan: <b>{plan.get('name', order['plan_key'])}</b>\n"
            f"💰 Amount: <b>₹{order['amount_paise'] / 100:.2f}</b>\n"
            f"📌 Status: <b>{status}</b>\n\n"
            "Payment complete nahi hua hai.",
            reply_markup=main_keyboard(),
        )


@router.callback_query(F.data.startswith("access:"))
async def access_callback(callback: CallbackQuery):
    await callback.answer("Checking…")
    reference_id = callback.data.split(":", 1)[1]
    order = get_order(reference_id)

    if not order or order["user_id"] != callback.from_user.id:
        await callback.message.answer("❌ Order not found.")
        return

    if order["status"] != "paid":
        await callback.message.answer("❌ Payment abhi confirmed nahi hai.")
        return

    try:
        await deliver_access(order)
    except Exception:
        logger.exception("Manual access delivery failed")
        await callback.message.answer(f"❌ Access send nahi ho paya. Contact {SUPPORT_USERNAME}.")


@router.callback_query(F.data.startswith("check:"))
async def check_payment_callback(callback: CallbackQuery):
    await callback.answer("Checking payment…")
    order = get_latest_order(callback.from_user.id)

    if not order:
        await callback.message.answer("❌ Order not found.")
        return

    if order["status"] == "paid":
        await callback.message.answer("✅ Payment already confirmed. /myplan se access le sakte hain.")
        return

    if not order["payment_link_id"]:
        await callback.message.answer("❌ Payment link not found.")
        return

    try:
        result = await razorpay_request("GET", f"payment_links/{order['payment_link_id']}")
        if result.get("status") == "paid":
            payment_id = ""
            payments = result.get("payments") or []
            if isinstance(payments, list) and payments:
                payment_id = payments[0].get("payment_id") or payments[0].get("id") or ""
            elif isinstance(payments, dict):
                payment_id = payments.get("payment_id") or payments.get("id") or ""

            mark_paid(order["reference_id"], payment_id)
            updated = get_order(order["reference_id"])
            await deliver_access(updated)
        else:
            await callback.message.answer(
                f"⏳ Payment status: <b>{result.get('status', 'unknown')}</b>\n"
                "Agar aapne payment kar diya hai, thodi der baad dobara check karein."
            )
    except Exception:
        logger.exception("Payment status check failed")
        await callback.message.answer("❌ Payment status check nahi ho paya. Thodi der baad try karein.")


# =========================
# RAZORPAY WEBHOOK SERVER
# =========================
async def razorpay_webhook(request: web.Request):
    raw_body = await request.read()
    signature = request.headers.get("X-Razorpay-Signature", "")

    # Never bypass webhook verification in production.
    if not verify_webhook(raw_body, signature):
        logger.warning("Invalid Razorpay webhook signature")
        return web.Response(status=400, text="invalid signature")

    event_id = request.headers.get("x-razorpay-event-id", "")
    if event_id and event_already_processed(event_id):
        return web.Response(status=200, text="already processed")

    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        return web.Response(status=400, text="invalid json")

    if event_id:
        save_event(event_id)

    if event.get("event") == "payment_link.paid":
        asyncio.create_task(process_paid_event(event))

    return web.Response(status=200, text="ok")


async def health(request: web.Request):
    return web.json_response({"ok": True, "service": "telegram-store-bot", "time": int(time.time())})


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_post("/razorpay/webhook", razorpay_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT)
    await site.start()

    logger.info("HTTP server listening on %s:%s", WEBHOOK_HOST, WEBHOOK_PORT)
    return runner


# =========================
# MAIN
# =========================
async def main():
    global bot

    validate_razorpay_config()
    init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    runner = await start_web_server()

    try:
        logger.info("Bot polling started")
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
