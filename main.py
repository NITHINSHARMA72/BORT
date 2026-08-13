import asyncio
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import time
from typing import Optional

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv
import qrcode
from supabase import create_client, Client

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

# Supabase Config
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

# Admin IDs for Broadcast
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "10000")))

SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@Help_desk3_bot").strip()

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
supabase: Optional[Client] = None


# =========================
# FSM FOR BROADCAST
# =========================
class BroadcastState(StatesGroup):
    waiting_for_message = State()


# =========================
# SUPABASE DATABASE HELPERS
# =========================
def init_supabase():
    global supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables!")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def save_user(user_id: int, username: str, first_name: str):
    try:
        supabase.table("bot_users").upsert({
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "created_at": int(time.time())
        }, on_conflict="user_id").execute()
    except Exception:
        logger.exception("Failed to save user")


def save_order(reference_id, user_id, plan_key, amount_paise, payment_link_id, payment_link_url):
    try:
        supabase.table("orders").insert({
            "reference_id": reference_id,
            "user_id": user_id,
            "plan_key": plan_key,
            "amount_paise": amount_paise,
            "payment_link_id": payment_link_id,
            "payment_link_url": payment_link_url,
            "status": "created",
            "created_at": int(time.time()),
            "access_sent": 0
        }).execute()
    except Exception:
        logger.exception("Failed to save order")


def get_order(reference_id):
    try:
        res = supabase.table("orders").select("*").eq("reference_id", reference_id).execute()
        return res.data[0] if res.data else None
    except Exception:
        logger.exception("Failed to get order")
        return None


def get_latest_order(user_id):
    try:
        res = supabase.table("orders").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception:
        logger.exception("Failed to get latest order")
        return None


def mark_paid(reference_id, payment_id):
    try:
        supabase.table("orders").update({
            "status": "paid",
            "payment_id": payment_id,
            "paid_at": int(time.time())
        }).eq("reference_id", reference_id).execute()
    except Exception:
        logger.exception("Failed to mark order paid")


def mark_access_sent(reference_id):
    try:
        supabase.table("orders").update({"access_sent": 1}).eq("reference_id", reference_id).execute()
    except Exception:
        logger.exception("Failed to mark access sent")


def event_already_processed(event_id):
    if not event_id:
        return False
    try:
        res = supabase.table("processed_events").select("event_id").eq("event_id", event_id).execute()
        return len(res.data) > 0
    except Exception:
        return False


def save_event(event_id):
    if not event_id:
        return
    try:
        supabase.table("processed_events").insert({
            "event_id": event_id,
            "created_at": int(time.time())
        }).execute()
    except Exception:
        pass


def get_all_users():
    try:
        res = supabase.table("bot_users").select("user_id").execute()
        return [row["user_id"] for row in res.data]
    except Exception:
        logger.exception("Failed to fetch users for broadcast")
        return []


# =========================
# RAZORPAY CONFIG & API
# =========================
def validate_config():
    missing = []
    if not BOT_TOKEN: missing.append("BOT_TOKEN")
    if not RAZORPAY_KEY_ID: missing.append("RAZORPAY_KEY_ID")
    if not RAZORPAY_KEY_SECRET: missing.append("RAZORPAY_KEY_SECRET")
    if not RAZORPAY_WEBHOOK_SECRET: missing.append("RAZORPAY_WEBHOOK_SECRET")
    if not SUPABASE_URL: missing.append("SUPABASE_URL")
    if not SUPABASE_KEY: missing.append("SUPABASE_KEY")
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
# TELEGRAM UI & KEYBOARDS
# =========================
def support_url():
    return f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}"


def main_keyboard(is_admin: bool = False):
    kb = [
        [InlineKeyboardButton(text="⚡ Gold Dark (Channel 1)", callback_data="plan:gold")],
        [InlineKeyboardButton(text="⚡ Silver Dark (Channel 2)", callback_data="plan:silver")],
        [InlineKeyboardButton(text="⚡ Bronze Dark (Channel 3)", callback_data="plan:bronze")],
        [InlineKeyboardButton(text="⚡ Iron Dark (Channel 4)", callback_data="plan:iron")],
        [InlineKeyboardButton(text="📋 My Plan", callback_data="myplan")],
        [InlineKeyboardButton(text="📞 Support", url=support_url())],
    ]
    if is_admin:
        kb.append([InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


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


async def show_home(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_admin = user_id in ADMIN_IDS
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
    try:
        await callback.message.edit_text(text, reply_markup=main_keyboard(is_admin))
    except Exception:
        await callback.message.answer(text, reply_markup=main_keyboard(is_admin))


@router.message(CommandStart())
async def start_handler(message: Message):
    save_user(message.from_user.id, message.from_user.username or "", message.from_user.first_name or "")
    user_id = message.from_user.id
    is_admin = user_id in ADMIN_IDS
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
    await message.answer(text, reply_markup=main_keyboard(is_admin))


@router.callback_query(F.data == "home")
async def home_callback(callback: CallbackQuery):
    await callback.answer()
    await show_home(callback)


@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ You are not authorized!", show_alert=True)
        return
    await callback.answer()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Back", callback_data="home")]])
    await callback.message.edit_text(
        "📢 <b>Broadcast Setup</b>\n\n"
        "Apna message bhejein (Aap <b>Image</b> sath me caption ke roop me ya sirf <b>Text</b> bhej sakte hain).",
        reply_markup=kb
    )
    await state.set_state(BroadcastState.waiting_for_message)


@router.message(BroadcastState.waiting_for_message)
async def broadcast_send(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return

    await state.clear()
    users = get_all_users()
    
    status_msg = await message.answer(f"🚀 Broadcast started to {len(users)} users...")
    success, failed = 0, 0

    for user_id in users:
        try:
            if message.photo:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=message.photo[-1].file_id,
                    caption=message.caption or "",
                    parse_mode=ParseMode.HTML
                )
            else:
                await bot.send_message(chat_id=user_id, text=message.text, parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ <b>Broadcast Completed!</b>\n\n"
        f"📤 Successful: <b>{success}</b>\n"
        f"❌ Failed: <b>{failed}</b>"
    )


@router.callback_query(F.data.startswith("plan:"))
async def plan_callback(callback: CallbackQuery):
    await callback.answer()
    plan_key = callback.data.split(":", 1)[1]
    if plan_key not in PLANS:
        await callback.answer("❌ Invalid plan.", show_alert=True)
        return

    plan = PLANS[plan_key]
    text = f"<b>{plan['name']}</b>\n━━━━━━━━━━━━━━━━━━\n\nSelect your plan:"
    await callback.message.edit_text(text, reply_markup=plan_keyboard(plan_key))


@router.callback_query(F.data.startswith("buy:"))
async def buy_callback(callback: CallbackQuery):
    await callback.answer("Generating dynamic QR code…")
    plan_key = callback.data.split(":", 1)[1]
    if plan_key not in PLANS:
        await callback.answer("❌ Invalid plan.", show_alert=True)
        return

    try:
        result = await create_payment_link(callback.from_user.id, plan_key)
    except Exception:
        logger.exception("Payment link creation failed")
        await callback.answer("❌ Payment QR create nahi ho paya.", show_alert=True)
        return

    plan = PLANS[plan_key]
    payment_url = result["short_url"]

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
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
        "📱 <b>GPay / PhonePe / Paytm / UPI app se scan karein.</b>\n\n"
        "⏱️ Payment hone ke baad <b>Check Payment</b> dabayein."
    )

    # Delete photo/old message safely and send new QR photo
    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer_photo(
        photo=qr_file,
        caption=text,
        reply_markup=payment_keyboard(plan_key),
    )


async def make_access_link(plan_key: str) -> Optional[str]:
    plan = PLANS[plan_key]
    if plan["channel_id"]:
        try:
            invite = await bot.create_chat_invite_link(chat_id=plan["channel_id"], member_limit=1)
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
            f"✅ <b>Payment confirmed.</b>\n\nLekin access link configure nahi hai.\n📞 Support: {SUPPORT_USERNAME}",
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
        return

    order = get_order(reference_id)
    if not order:
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
    await send_my_plan(callback)


@router.message(Command("myplan"))
async def myplan_message(message: Message):
    # For command text, simulate callback object wrapper or handle via message edit/send
    order = get_latest_order(message.from_user.id)
    is_admin = message.from_user.id in ADMIN_IDS

    if not order:
        text = "📋 <b>My Plan</b>\n━━━━━━━━━━━━━━━━━━\n\n❌ <b>You have no plans!</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Back", callback_data="home")]])
        await message.answer(text, reply_markup=kb)
        return

    plan = PLANS.get(order["plan_key"], {})
    if order["status"] == "paid":
        text = (
            "📋 <b>My Plan</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 Plan: <b>{plan.get('name', order['plan_key'])}</b>\n"
            f"💰 Amount: <b>₹{order['amount_paise'] / 100:.2f}</b>\n"
            "📌 Status: <b>PAID</b>\n"
            f"🧾 Payment ID: <code>{order.get('payment_id') or '-'}</code>\n\n"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Send Access Link", callback_data=f"access:{order['reference_id']}")],
                [InlineKeyboardButton(text="↩️ Back", callback_data="home")],
            ]
        )
        await message.answer(text, reply_markup=kb)
    else:
        text = (
            "📋 <b>My Plan</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 Plan: <b>{plan.get('name', order['plan_key'])}</b>\n"
            f"💰 Amount: <b>₹{order['amount_paise'] / 100:.2f}</b>\n"
            "📌 Status: <b>CREATED</b>\n\nPayment complete nahi hua hai."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Back", callback_data="home")]])
        await message.answer(text, reply_markup=kb)


async def send_my_plan(callback: CallbackQuery):
    order = get_latest_order(callback.from_user.id)

    if not order:
        text = "📋 <b>My Plan</b>\n━━━━━━━━━━━━━━━━━━\n\n❌ <b>You have no plans!</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Back", callback_data="home")]])
        await callback.message.edit_text(text, reply_markup=kb)
        return

    plan = PLANS.get(order["plan_key"], {})
    if order["status"] == "paid":
        text = (
            "📋 <b>My Plan</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 Plan: <b>{plan.get('name', order['plan_key'])}</b>\n"
            f"💰 Amount: <b>₹{order['amount_paise'] / 100:.2f}</b>\n"
            "📌 Status: <b>PAID</b>\n"
            f"🧾 Payment ID: <code>{order.get('payment_id') or '-'}</code>\n\n"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔗 Send Access Link", callback_data=f"access:{order['reference_id']}")],
                [InlineKeyboardButton(text="↩️ Back", callback_data="home")],
            ]
        )
        await callback.message.edit_text(text, reply_markup=kb)
    else:
        text = (
            "📋 <b>My Plan</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 Plan: <b>{plan.get('name', order['plan_key'])}</b>\n"
            f"💰 Amount: <b>₹{order['amount_paise'] / 100:.2f}</b>\n"
            "📌 Status: <b>CREATED</b>\n\nPayment complete nahi hua hai."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Back", callback_data="home")]])
        await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("access:"))
async def access_callback(callback: CallbackQuery):
    await callback.answer("Checking…")
    reference_id = callback.data.split(":", 1)[1]
    order = get_order(reference_id)

    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("❌ Order not found.", show_alert=True)
        return

    if order["status"] != "paid":
        await callback.answer("❌ Payment abhi confirmed nahi hai.", show_alert=True)
        return

    try:
        await deliver_access(order)
        await callback.answer("✅ Access sent successfully!", show_alert=True)
    except Exception:
        await callback.answer(f"❌ Access send nahi ho paya.", show_alert=True)


@router.callback_query(F.data.startswith("check:"))
async def check_payment_callback(callback: CallbackQuery):
    await callback.answer("Checking payment…")
    order = get_latest_order(callback.from_user.id)

    if not order:
        await callback.answer("❌ You have no plans!", show_alert=True)
        return

    if order["status"] == "paid":
        await callback.answer("✅ Payment already confirmed!", show_alert=True)
        return

    try:
        result = await razorpay_request("GET", f"payment_links/{order['payment_link_id']}")
        if result.get("status") == "paid":
            payments = result.get("payments") or []
            payment_id = payments[0].get("payment_id") or payments[0].get("id") if payments else ""
            mark_paid(order["reference_id"], payment_id)
            updated = get_order(order["reference_id"])
            await deliver_access(updated)
            await callback.answer("✅ Payment verified!", show_alert=True)
            # Refresh My Plan view automatically
            await send_my_plan(callback)
        else:
            status_text = result.get('status', 'unknown')
            await callback.answer(f"⏳ Status: {status_text}. Payment pending.", show_alert=True)
    except Exception:
        await callback.answer("❌ Payment status check nahi ho paya.", show_alert=True)


# =========================
# WEBHOOK SERVER
# =========================
async def razorpay_webhook(request: web.Request):
    raw_body = await request.read()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not verify_webhook(raw_body, signature):
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
    validate_config()
    init_supabase()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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
