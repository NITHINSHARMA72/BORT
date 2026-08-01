import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, LabeledPrice
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest

# ==================== PRODUCTION CONFIGURATION (EDIT ANYTIME) ====================
TOKEN = "8894339879:AAGieiK1UG2JqNEhMuaiWqYIjv9JfAtqz18"
ADMIN_CHAT_ID = 8793053750

# --- RAZORPAY CUSTOM LINKS PER PRICE TIER ---
RAZORPAY_LINKS = {
    "$50.00 USD": "https://razorpay.me/@solutionsbysatyamyadav", # Link for $50 plans
    "$150.00 USD": "https://razorpay.me/@solutionsbysatyamyadav" # Link for $150 plan (Phone)
}

# --- WALLET & PAYMENT GATEWAY ADDRESSES/INSTRUCTIONS ---
WALLET_ADDRESSES = {
    "BTC": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
    "TON": "UQDASYHrZvLdywOgNVnKnKisL9G2oZLxJH0qd7u-ZDyRqU-R",
    "USDT (TON)": "UQDASYHrZvLdywOgNVnKnKisL9G2oZLxJH0qd7u-ZDyRqU-R",
}

# --- WARRANTY / REVIEWS / RULES URL CONFIGURATION (DIRECT LINK OPEN ON CLICK) ---
RULES_URLS = {
    "warranty": "https://t.me/your_warranty_channel_link",
    "reviews": "https://t.me/your_reviews_channel",
    "rules": "https://t.me/your_rules_channel_link"
}

# --- PRODUCTS, PRICES, DESCRIPTIONS & IMAGES ---
PRODUCTS_CONFIG = {
    "Instagram": {
        "price": "$50.00 USD",
        "stars_amount": 250,
        "image": "https://i.ibb.co/yFtD23fZ/i.jpg",
        "text": (
            "<b>Instagram</b>\n\n"
            "When you order access to a target Instagram account, you get full and anonymous access to the account you ordered. "
            "Your login session is not displayed on the account itself, as the login occurs under the target's current IP address. "
            "The account owner will never know that you are viewing their account. On average, it will take 3 hours to complete your order. "
            "You are guaranteed access for 12 months. As a bonus, you get the ability to view all deleted messages on that account.\n\n"
            "💰 <b>Price: $50.00 USD</b>"
        )
    },
    "Snapchat": {
        "price": "$50.00 USD",
        "stars_amount": 250,
        "image": "https://i.ibb.co/4w7xsmm9/s.jpg",
        "text": (
            "<b>Snapchat</b>\n\n"
            "When you order access to a Snapchat account, you get full and anonymous access to the target account online, including "
            "access to the hidden 'My Eyes Only' archive. The account owner will never know that you have access. Authorization "
            "occurs under the target's IP address. The approximate time to complete the order is 3 hours. Access is guaranteed for 12 "
            "months. As a bonus, you get the ability to view all deleted messages.\n\n"
            "💰 <b>Price: $50.00 USD</b>"
        )
    },
    "WhatsApp": {
        "price": "$50.00 USD",
        "stars_amount": 250,
        "image": "https://i.ibb.co/nNLCCbgZ/5149876920366337198.jpg",
        "text": (
            "<b>WhatsApp</b>\n\n"
            "When you order access to a WhatsApp account, you get full and anonymous access to the target account. All features are "
            "available including viewing messages and listening to conversation recordings. The account owner will never know "
            "that you have access. As a bonus, you get the ability to view all deleted messages. The approximate time to complete the "
            "order is 3 hours. Access is guaranteed for 12 months.\n\n"
            "💰 <b>Price: $50.00 USD</b>"
        )
    },
    "Facebook": {
        "price": "$50.00 USD",
        "stars_amount": 250,
        "image": "https://i.ibb.co/bM5gFntr/fm.jpg",
        "text": (
            "<b>Facebook & Messenger</b>\n\n"
            "When you order access to a Facebook account, you also get access to Messenger. You will have access to full functionality "
            "including viewing all deleted chats. Access is completely anonymous. The approximate time to complete the order is 3 "
            "hours. Access is guaranteed for 12 months.\n\n"
            "💰 <b>Price: $50.00 USD</b>"
        )
    },
    "Telegram": {
        "price": "$50.00 USD",
        "stars_amount": 250,
        "image": "https://i.ibb.co/HLK45RHy/ttt.jpg",
        "text": (
            "<b>Telegram</b>\n\n"
            "When you order access to a Telegram account, you get full and anonymous access to the target account online. You can view "
            "all private chats and deleted chats. Access to all saved contacts and media is included. Your login session is hidden. "
            "The approximate time to complete the order is 3 hours. Access is guaranteed for 12 months.\n\n"
            "💰 <b>Price: $50.00 USD</b>"
        )
    },
    "TikTok": {
        "price": "$50.00 USD",
        "stars_amount": 250,
        "image": "https://i.ibb.co/ym6ps2FX/tik.jpg",
        "text": (
            "<b>TikTok</b>\n\n"
            "When you order access to a TikTok account, you get full and anonymous access to the target account. You will have access "
            "to all features. The account owner will never find out. Your login session is hidden. The approximate time to complete the "
            "order is 3 hours. Access is guaranteed for 12 months.\n\n"
            "💰 <b>Price: $50.00 USD</b>"
        )
    },
    "Email": {
        "price": "$50.00 USD",
        "stars_amount": 250,
        "image": "https://i.ibb.co/hF8LvX1r/mes.jpg",
        "text": (
            "<b>E-Mail</b>\n\n"
            "When you order access to a mailbox, you get full and anonymous access to the target's mail online. The account "
            "owner will never know that you have access. You will have access to full functionality including viewing deleted emails. "
            "You can download or forward all emails. The approximate time to complete the order is 3 hours. Access is guaranteed for 12 "
            "months.\n\n"
            "💰 <b>Price: $50.00 USD</b>"
        )
    },
    "Phone": {
        "price": "$150.00 USD",
        "stars_amount": 750,
        "image": "https://i.ibb.co/tpmkQ23V/svs.jpg",
        "text": (
            "<b>Phone (Android \\ iOS)</b>\n\n"
            "Using our service, you can order access to a phone on Android or iOS platform. You get online access to the target phone "
            "anonymously. Access includes all social networks, messengers, location, photos, videos, and calls. As a bonus, "
            "you get the ability to view all deleted chats. The approximate time to complete the order is 3 hours. Access is guaranteed for "
            "12 months.\n\n"
            "💰 <b>Price: $150.00 USD</b>"
        )
    }
}
# =======================================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

user_data_storage = {}

TRANSLATIONS = {
    "en": {
        "select_lang": "🌐 Select your language:",
        "lang_set": "✅ Language set to: English",
        "region_prompt": "👋 Welcome! Please select your region to continue.",
        "services_btn": "📋 Services",
        "warranty_btn": "🧵 Warranty / Reviews / Rules",
        "lang_btn": "🌐 Language",
        "back_btn": "🔙 Back",
        "services_title": "📋 Choose a service:",
        "rules_title": "🧵 Choose an option:",
        "warranty": "🛡️ Warranty",
        "reviews": "⭐ Reviews",
        "rules": "📋 Rules",
        "place_order": "🛒 Place order",
        "order_details_prompt": "📝 Please send your order details (text, photos, or files). All fields are optional. Press Continue when ready.",
        "continue_to_payment": "➡️ Continue to payment",
        "cancel": "❌ Cancel",
        "choose_payment": "✅ Order details received. Please choose a payment method:",
        "how_to_buy": "💳 How to buy crypto",
        "i_have_paid": "✅ I have paid",
        "payment_confirmation_prompt": "📎 Please send payment confirmation:\n\n• Screenshot of the payment, or\n• Link to the transaction\n\nSend /cancel to abort.",
        "thank_you_paid": "⏳ Thank you! Your payment notification has been sent. Please wait for confirmation.",
    },
    "fr": {
        "select_lang": "🌐 Sélectionnez votre langue :",
        "lang_set": "✅ Langue définie : Français",
        "region_prompt": "👋 Bienvenue ! Veuillez sélectionner votre région pour continuer.",
        "services_btn": "📋 Prestations",
        "warranty_btn": "🧵 Garantie / Avis / Règles",
        "lang_btn": "🌐 Langue",
        "back_btn": "🔙 Retour",
        "services_title": "📋 Choisissez un service :",
        "rules_title": "🧵 Choisissez une option :",
        "warranty": "🛡️ Garantie",
        "reviews": "⭐ Avis",
        "rules": "📋 Règles",
        "place_order": "🛒 Passer commande",
        "order_details_prompt": "📝 Veuillez envoyer les détails de votre commande. Appuyez sur Continuer lorsque vous êtes prêt.",
        "continue_to_payment": "➡️ Continuer vers le paiement",
        "cancel": "❌ Annuler",
        "choose_payment": "✅ Détails reçus. Veuillez choisir un mode de paiement :",
        "how_to_buy": "💳 Comment acheter de la crypto",
        "i_have_paid": "✅ J'ai payé",
        "payment_confirmation_prompt": "📎 Veuillez envoyer la confirmation de paiement :\n\n• Capture d'écran ou\n• Lien de transaction\n\nEnvoyez /cancel pour annuler.",
        "thank_you_paid": "⏳ Merci ! Votre notification de paiement a été envoyée.",
    },
    "es": {
        "select_lang": "🌐 Selecciona tu idioma:",
        "lang_set": "✅ Idioma establecido: Español",
        "region_prompt": "👋 ¡Bienvenido! Selecciona tu región para continuar.",
        "services_btn": "📋 Servicios",
        "warranty_btn": "🧵 Garantía / Reseñas / Reglas",
        "lang_btn": "🌐 Idioma",
        "back_btn": "🔙 Volver",
        "services_title": "📋 Elige un servicio:",
        "rules_title": "🧵 Elige una opción:",
        "warranty": "🛡️ Garantía",
        "reviews": "⭐ Reseñas",
        "rules": "📋 Reglas",
        "place_order": "🛒 Hacer pedido",
        "order_details_prompt": "📝 Envía los detalles de tu pedido. Presiona Continuar cuando estés listo.",
        "continue_to_payment": "➡️ Continuar al pago",
        "cancel": "❌ Cancelar",
        "choose_payment": "✅ Detalles recibidos. Elige un método de pago:",
        "how_to_buy": "💳 Cómo comprar cripto",
        "i_have_paid": "✅ Ya pagué",
        "payment_confirmation_prompt": "📎 Envía la confirmación de pago (captura o enlace). Envía /cancel para cancelar.",
        "thank_you_paid": "⏳ ¡Gracias! Tu notificación de pago ha sido enviada.",
    },
    "it": {
        "select_lang": "🌐 Seleziona la tua lingua:",
        "lang_set": "✅ Lingua impostata: Italiano",
        "region_prompt": "👋 Benvenuto! Seleziona la tua regione per continuare.",
        "services_btn": "📋 Servizi",
        "warranty_btn": "🧵 Garanzia / Recensioni / Regole",
        "lang_btn": "🌐 Lingua",
        "back_btn": "🔙 Indietro",
        "services_title": "📋 Scegli un servizio:",
        "rules_title": "🧵 Scegli un'opzione:",
        "warranty": "🛡️ Garanzia",
        "reviews": "⭐ Recensioni",
        "rules": "📋 Regole",
        "place_order": "🛒 Effettua ordine",
        "order_details_prompt": "📝 Invia i dettagli dell'ordine. Premi Continua quando pronto.",
        "continue_to_payment": "➡️ Continua al pagamento",
        "cancel": "❌ Annulla",
        "choose_payment": "✅ Dettagli ricevuti. Scegli un metodo di pagamento:",
        "how_to_buy": "💳 Come comprare criptovalute",
        "i_have_paid": "✅ Ho pagato",
        "payment_confirmation_prompt": "📎 Invia la conferma di pagamento (screenshot o link). Invia /cancel per annullare.",
        "thank_you_paid": "⏳ Grazie! La tua notifica di pagamento è stata inviata.",
    },
    "de": {
        "select_lang": "🌐 Wähle deine Sprache:",
        "lang_set": "✅ Sprache eingestellt: Deutsch",
        "region_prompt": "👋 Willkommen! Bitte wähle deine Region.",
        "services_btn": "📋 Dienste",
        "warranty_btn": "🧵 Garantie / Bewertungen / Regeln",
        "lang_btn": "🌐 Sprache",
        "back_btn": "🔙 Zurück",
        "services_title": "📋 Wähle einen Dienst:",
        "rules_title": "🧵 Wähle eine Option:",
        "warranty": "🛡️ Garantie",
        "reviews": "⭐ Bewertungen",
        "rules": "📋 Regeln",
        "place_order": "🛒 Bestellung aufgeben",
        "order_details_prompt": "📝 Sende deine Bestelldetails. Drücke Weiter, wenn du bereit bist.",
        "continue_to_payment": "➡️ Weiter zur Zahlung",
        "cancel": "❌ Abbrechen",
        "choose_payment": "✅ Details erhalten. Wähle eine Zahlungsmethode:",
        "how_to_buy": "💳 Krypto kaufen Anleitung",
        "i_have_paid": "✅ Ich habe bezahlt",
        "payment_confirmation_prompt": "📎 Bitte sende die Zahlungsbestätigung (Screenshot oder Link). Sende /cancel zum Abbrechen.",
        "thank_you_paid": "⏳ Danke! Deine Benachrichtigung wurde gesendet.",
    },
    "tr": {
        "select_lang": "🌐 Dilinizi seçin:",
        "lang_set": "✅ Dil ayarlandı: Türkçe",
        "region_prompt": "🌐 Hoş geldiniz! Devam etmek için bölgenizi seçin.",
        "services_btn": "📋 Hizmetler",
        "warranty_btn": "🧵 Garanti / Değerlendirmeler / Kurallar",
        "lang_btn": "🌐 Dil",
        "back_btn": "🔙 Geri",
        "services_title": "📋 Bir hizmet seçin:",
        "rules_title": "🧵 Bir seçenek seçin:",
        "warranty": "🛡️ Garanti",
        "reviews": "⭐ Değerlendirmeler",
        "rules": "📋 Kurallar",
        "place_order": "🛒 Sipariş Ver",
        "order_details_prompt": "📝 Sipariş detaylarınızı gönderin. Hazır olduğunuzda Devam'a basın.",
        "continue_to_payment": "➡️ Ödemeye devam et",
        "cancel": "❌ İptal",
        "choose_payment": "✅ Detaylar alındı. Bir ödeme yöntemi seçin:",
        "how_to_buy": "💳 Kripto Nasıl Alınır",
        "i_have_paid": "✅ Ödeme Yaptım",
        "payment_confirmation_prompt": "📎 Lütfen ödeme kanıtını (ekran görüntüsü veya bağlantı) gönderin. İptal için /cancel yazın.",
        "thank_you_paid": "⏳ Teşekkürler! Ödeme bildiriminiz gönderildi.",
    },
}

def get_language_keyboard(current_lang="en"):
    def mark(code, text):
        return f"✓ {text}" if code == current_lang else text

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(mark("en", "🇬🇧 English"), callback_data="lang_en"),
            InlineKeyboardButton(mark("fr", "🇫🇷 Français"), callback_data="lang_fr"),
        ],
        [
            InlineKeyboardButton(mark("es", "🇪🇸 Español"), callback_data="lang_es"),
            InlineKeyboardButton(mark("it", "🇮🇹 Italiano"), callback_data="lang_it"),
        ],
        [
            InlineKeyboardButton(mark("de", "🇩🇪 Deutsch"), callback_data="lang_de"),
            InlineKeyboardButton(mark("tr", "🇹🇷 Türkçe"), callback_data="lang_tr"),
        ],
    ])

def get_region_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇺🇸 USA", callback_data="reg_usa"),
            InlineKeyboardButton("🇨🇦 CANADA", callback_data="reg_canada"),
        ],
        [
            InlineKeyboardButton("🇪🇺 EU", callback_data="reg_eu"),
            InlineKeyboardButton("🌐 Other", callback_data="reg_other"),
        ],
        [
            InlineKeyboardButton("🇮🇳 INDIA", callback_data="reg_india"),
            InlineKeyboardButton("🌏 ASIA", callback_data="reg_asia"),
        ],
    ])

def get_main_menu_keyboard(lang="en"):
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t["services_btn"], callback_data="menu_services")],
        [InlineKeyboardButton(t["warranty_btn"], callback_data="menu_rules")],
        [InlineKeyboardButton(t["lang_btn"], callback_data="menu_language")],
    ])

# --- MESSAGE TRACKING & AUTO-DELETE HELPERS ---

async def safe_delete_last_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    if "last_bot_message_id" in context.bot_data and chat_id in context.bot_data["last_bot_message_id"]:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=context.bot_data["last_bot_message_id"][chat_id])
        except Exception:
            pass

async def send_tracked_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text, reply_markup=None, parse_mode=None):
    chat_id = update.effective_chat.id
    await safe_delete_last_message(context, chat_id)
    try:
        msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        if "last_bot_message_id" not in context.bot_data:
            context.bot_data["last_bot_message_id"] = {}
        context.bot_data["last_bot_message_id"][chat_id] = msg.message_id
        return msg
    except Exception as e:
        logger.error(f"Failed to send tracked message: {e}")
        return None

async def send_tracked_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, photo, caption=None, reply_markup=None, parse_mode=None):
    chat_id = update.effective_chat.id
    await safe_delete_last_message(context, chat_id)
    try:
        msg = await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        if "last_bot_message_id" not in context.bot_data:
            context.bot_data["last_bot_message_id"] = {}
        context.bot_data["last_bot_message_id"][chat_id] = msg.message_id
        return msg
    except Exception as e:
        logger.error(f"Failed to send tracked photo: {e}")
        return None

# --- CORE HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_chat:
        return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if user_id not in user_data_storage:
        user_data_storage[user_id] = {"lang": "en"}

    lang = user_data_storage[user_id].get("lang", "en")
    t = TRANSLATIONS[lang]
    user_data_storage[user_id]["state"] = None

    if "region" in user_data_storage[user_id]:
        text = f"{t['lang_set']}"
        reply_markup = get_main_menu_keyboard(lang)
    else:
        text = t["select_lang"]
        reply_markup = get_language_keyboard(lang)

    try:
        msg = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        if "last_bot_message_id" not in context.bot_data:
            context.bot_data["last_bot_message_id"] = {}
        context.bot_data["last_bot_message_id"][chat_id] = msg.message_id
    except Exception as e:
        logger.error(f"Failed to send initial start message: {e}")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_chat:
        return
    user_id = update.effective_user.id
    if user_id in user_data_storage:
        user_data_storage[user_id]["state"] = None
    lang = user_data_storage[user_id].get("lang", "en")
    t = TRANSLATIONS[lang]

    await send_tracked_message(update, context, "❌ Action cancelled.", reply_markup=get_main_menu_keyboard(lang))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not update.effective_user or not update.effective_chat:
        return
    
    try:
        await query.answer()
    except Exception:
        pass
    
    user_id = update.effective_user.id
    data = query.data

    if user_id not in user_data_storage:
        user_data_storage[user_id] = {"lang": "en"}

    lang = user_data_storage[user_id]["lang"]
    t = TRANSLATIONS[lang]

    if query.message:
        try:
            await query.message.delete()
            if "last_bot_message_id" in context.bot_data and update.effective_chat.id in context.bot_data["last_bot_message_id"]:
                if context.bot_data["last_bot_message_id"][update.effective_chat.id] == query.message.message_id:
                    context.bot_data["last_bot_message_id"].pop(update.effective_chat.id, None)
        except Exception:
            pass

    if data.startswith("lang_"):
        new_lang = data.split("_")[1]
        user_data_storage[user_id]["lang"] = new_lang
        t = TRANSLATIONS[new_lang]

        if "region" in user_data_storage[user_id]:
            await send_tracked_message(update, context, f"{t['lang_set']}", reply_markup=get_main_menu_keyboard(new_lang))
        else:
            await send_tracked_message(update, context, t["region_prompt"], reply_markup=get_region_keyboard())

    elif data.startswith("reg_"):
        region_map = {
            "reg_usa": "🇺🇸 USA",
            "reg_canada": "🇨🇦 CANADA",
            "reg_eu": "🇪🇺 EU",
            "reg_other": "🌐 Other",
            "reg_india": "🇮🇳 INDIA",
            "reg_asia": "🌏 ASIA",
        }
        selected_region = region_map.get(data, "INDIA")
        user_data_storage[user_id]["region"] = selected_region
        await send_tracked_message(update, context, f"✅ Region set to: {selected_region}", reply_markup=get_main_menu_keyboard(lang))

    elif data == "menu_services":
        services_keyboard = [
            [InlineKeyboardButton("Instagram", callback_data="srv_Instagram"), InlineKeyboardButton("Snapchat", callback_data="srv_Snapchat")],
            [InlineKeyboardButton("WhatsApp", callback_data="srv_WhatsApp"), InlineKeyboardButton("Facebook & Messenger", callback_data="srv_Facebook")],
            [InlineKeyboardButton("Telegram", callback_data="srv_Telegram"), InlineKeyboardButton("TikTok", callback_data="srv_TikTok")],
            [InlineKeyboardButton("E-Mail", callback_data="srv_Email"), InlineKeyboardButton("Phone (Android \\ iOS)", callback_data="srv_Phone")],
            [InlineKeyboardButton(t["back_btn"], callback_data="menu_back")]
        ]
        await send_tracked_message(update, context, t["services_title"], reply_markup=InlineKeyboardMarkup(services_keyboard))

    elif data == "menu_rules":
        rules_keyboard = [
            [InlineKeyboardButton(t["warranty"], url=RULES_URLS["warranty"])],
            [InlineKeyboardButton(t["reviews"], url=RULES_URLS["reviews"])],
            [InlineKeyboardButton(t["rules"], url=RULES_URLS["rules"])],
            [InlineKeyboardButton(t["back_btn"], callback_data="menu_back")]
        ]
        await send_tracked_message(update, context, t["rules_title"], reply_markup=InlineKeyboardMarkup(rules_keyboard))

    elif data == "menu_language":
        await send_tracked_message(update, context, t["select_lang"], reply_markup=get_language_keyboard(lang))

    elif data == "menu_back":
        user_data_storage[user_id]["state"] = None
        await send_tracked_message(update, context, f"{t['lang_set']}", reply_markup=get_main_menu_keyboard(lang))

    elif data.startswith("srv_"):
        service_key = data.split("_")[1]
        s_data = PRODUCTS_CONFIG.get(service_key, PRODUCTS_CONFIG["Instagram"])
        
        user_data_storage[user_id]["selected_plan"] = f"{service_key} Plan ({s_data['price']})"
        user_data_storage[user_id]["selected_product_key"] = service_key
        
        keyboard = [
            [InlineKeyboardButton(t["place_order"], callback_data="place_order")],
            [InlineKeyboardButton(t["back_btn"], callback_data="menu_services")]
        ]
        await send_tracked_photo(update, context, photo=s_data["image"], caption=s_data["text"], parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "place_order":
        user_data_storage[user_id]["state"] = "awaiting_order_details"
        keyboard = [
            [InlineKeyboardButton(t["continue_to_payment"], callback_data="continue_payment")],
            [InlineKeyboardButton(t["cancel"], callback_data="menu_back")]
        ]
        await send_tracked_message(update, context, f"✏️ {t['order_details_prompt']}", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "continue_payment":
        user_data_storage[user_id]["state"] = None
        
        selected_plan_str = user_data_storage[user_id].get("selected_plan", "")
        plan_price_key = "$150.00 USD" if "$150.00" in selected_plan_str else "$50.00 USD"
        razorpay_url = RAZORPAY_LINKS.get(plan_price_key, "https://razorpay.me/@solutionsbysatyamyadav")

        keyboard = [
            [InlineKeyboardButton("💳 Pay via Razorpay", url=razorpay_url)],
            [InlineKeyboardButton("🪙 BTC", callback_data="pay_BTC"), InlineKeyboardButton("💎 TON", callback_data="pay_TON")],
            [InlineKeyboardButton("💵 USDT (TON)", callback_data="pay_USDT_TON"), InlineKeyboardButton("⭐ Telegram Stars", callback_data="pay_Stars")],
            [InlineKeyboardButton("✅ I have paid (Razorpay)", callback_data="i_have_paid_razorpay")],
            [InlineKeyboardButton(t["cancel"], callback_data="menu_back")]
        ]
        await send_tracked_message(update, context, f"✅ {t['choose_payment']}", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "i_have_paid_razorpay":
        user_data_storage[user_id]["selected_crypto"] = "Razorpay"
        user_data_storage[user_id]["state"] = "awaiting_payment_proof"
        keyboard = [[InlineKeyboardButton(t["cancel"], callback_data="menu_back")]]
        await send_tracked_message(update, context, t["payment_confirmation_prompt"], reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("pay_"):
        pay_type = data.split("_")[1] if data != "pay_USDT_TON" else "USDT (TON)"
        
        if data == "pay_Stars":
            prod_key = user_data_storage[user_id].get("selected_product_key", "Instagram")
            p_data = PRODUCTS_CONFIG.get(prod_key, PRODUCTS_CONFIG["Instagram"])
            stars_amt = p_data.get("stars_amount", 250)
            
            title = f"Buy {prod_key}"
            description = f"Purchase access to {prod_key} plan for 12 months."
            payload = f"order_{user_id}_{prod_key}"
            currency = "XTR"
            prices = [LabeledPrice("Plan Access", stars_amt)]

            try:
                await context.bot.send_invoice(
                    chat_id=user_id,
                    title=title,
                    description=description,
                    payload=payload,
                    currency=currency,
                    prices=prices
                )
            except Exception as e:
                logger.error(f"Invoice sending failed: {e}")
                await send_tracked_message(update, context, "❌ Error opening Telegram Stars checkout. Please try another method.", reply_markup=get_main_menu_keyboard(lang))
            return

        user_data_storage[user_id]["selected_crypto"] = pay_type
        
        address_info = WALLET_ADDRESSES.get(pay_type, "Contact admin for details.")
        selected_plan_str = user_data_storage[user_id].get("selected_plan", "")
        plan_price = "150.00 USD" if "$150.00" in selected_plan_str else "50.00 USD"

        payment_text = (
            f"💰 <b>Payment Details ({pay_type})</b>\n\n"
            f"Amount to pay: ${plan_price} (pay equivalent via {pay_type})\n\n"
            f"Method: {pay_type}\n"
            f"Details / Address:\n<code>{address_info}</code>"
        )

        keyboard = [
            [InlineKeyboardButton(t["how_to_buy"], callback_data="how_to_buy")],
            [InlineKeyboardButton(t["i_have_paid"], callback_data="i_have_paid")],
            [InlineKeyboardButton(t["cancel"], callback_data="menu_back")]
        ]
        await send_tracked_message(update, context, payment_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "how_to_buy":
        guide_text = (
            "<b>Payment Instructions</b>\n\n"
            "1 - Complete the transaction via your chosen method.\n"
            "2 - Copy your transaction reference ID, hash, or take a screenshot.\n"
            "3 - Click 'I have paid' and submit proof."
        )
        keyboard = [[InlineKeyboardButton(t["back_btn"], callback_data="menu_back")]]
        await send_tracked_message(update, context, guide_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "i_have_paid":
        user_data_storage[user_id]["state"] = "awaiting_payment_proof"
        keyboard = [[InlineKeyboardButton(t["cancel"], callback_data="menu_back")]]
        await send_tracked_message(update, context, t["payment_confirmation_prompt"], reply_markup=InlineKeyboardMarkup(keyboard))

# --- TELEGRAM STARS PAYMENT FLOW ---

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query:
        try:
            await query.answer(ok=True)
        except Exception:
            pass

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_chat or not update.message:
        return
    user = update.effective_user
    user_id = user.id
    payment = update.message.successful_payment
    
    plan = user_data_storage.get(user_id, {}).get("selected_plan", "Unknown Plan")
    order_details = user_data_storage.get(user_id, {}).get("order_details", "No details provided")
    username = f"@{user.username}" if user.username else "No Username"
    
    admin_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Click to Message User", url=f"tg://user?id={user_id}")]
    ])

    admin_message = (
        f"🚨 <b>NEW SUCCESSFUL STARS PAYMENT!</b> 🚨\n\n"
        f"👤 <b>User:</b> {user.first_name} ({username})\n"
        f"🆔 <b>Chat ID:</b> <code>{user_id}</code>\n"
        f"📦 <b>Selected Plan:</b> {plan}\n"
        f"📝 <b>Order Details:</b> {order_details}\n"
        f"⭐ <b>Paid Stars:</b> {payment.total_amount if payment else 'Unknown'}"
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID, 
            text=admin_message, 
            parse_mode="HTML", 
            reply_markup=admin_keyboard
        )
    except Exception as e:
        logger.error(f"Failed to send stars notification to admin: {e}")

    lang = user_data_storage.get(user_id, {}).get("lang", "en")
    t = TRANSLATIONS[lang]
    await send_tracked_message(update, context, "✅ Payment via Telegram Stars successful! Your order has been placed.", reply_markup=get_main_menu_keyboard(lang))

# --- MESSAGE & PROOF HANDLER ---

async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_chat or not update.message:
        return
    user = update.effective_user
    user_id = user.id
    
    if user_id not in user_data_storage:
        return

    state = user_data_storage[user_id].get("state")
    lang = user_data_storage[user_id].get("lang", "en")
    t = TRANSLATIONS[lang]

    if state == "awaiting_order_details":
        order_details = update.message.text or "Media/File attached"
        user_data_storage[user_id]["order_details"] = order_details
        
        try:
            await update.message.delete()
        except Exception:
            pass

        keyboard = [
            [InlineKeyboardButton(t["continue_to_payment"], callback_data="continue_payment")],
            [InlineKeyboardButton(t["cancel"], callback_data="menu_back")]
        ]
        await send_tracked_message(update, context, "✅ Order details saved! Click below to proceed to payment:", reply_markup=InlineKeyboardMarkup(keyboard))
        user_data_storage[user_id]["state"] = None

    elif state == "awaiting_payment_proof":
        plan = user_data_storage[user_id].get("selected_plan", "Unknown Plan")
        crypto = user_data_storage[user_id].get("selected_crypto", "Unknown Payment Method")
        order_details = user_data_storage[user_id].get("order_details", "No details provided")
        username = f"@{user.username}" if user.username else "No Username"
        
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Click to Message User", url=f"tg://user?id={user_id}")]
        ])

        admin_message = (
            f"🚨 <b>NEW PAYMENT CONFIRMATION RECEIVED!</b> 🚨\n\n"
            f"👤 <b>User:</b> {user.first_name} ({username})\n"
            f"🆔 <b>Chat ID:</b> <code>{user_id}</code>\n"
            f"📦 <b>Selected Plan:</b> {plan}\n"
            f"📝 <b>Order Details:</b> {order_details}\n"
            f"💳 <b>Payment Method:</b> {crypto}"
        )

        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID, 
                text=admin_message, 
                parse_mode="HTML", 
                reply_markup=admin_keyboard
            )
            if update.message.photo or update.message.document or update.message.text:
                await context.bot.forward_message(
                    chat_id=ADMIN_CHAT_ID,
                    from_chat_id=user_id,
                    message_id=update.message.message_id
                )
        except Exception as e:
            logger.error(f"Failed to send alert to admin: {e}")

        try:
            await update.message.delete()
        except Exception:
            pass

        await send_tracked_message(update, context, t["thank_you_paid"], reply_markup=get_main_menu_keyboard(lang))
        user_data_storage[user_id]["state"] = None

# --- ERROR HANDLER ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

# --- MAIN SETUP ---

def main():
    custom_request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
    )

    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .request(custom_request)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_user_input))

    application.add_error_handler(error_handler)

    print("Advanced Production-Level Secure Crypto & Stars Bot is up and running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()