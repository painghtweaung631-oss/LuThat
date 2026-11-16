import os
import json
import random
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional
from telegram import (
    Update,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==========================================
# CONFIGURATION & RENDER KEEP-ALIVE SERVER
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
DATA_FILE = "luthat_users.json"

NIGHT_GIF_URL = os.getenv(
    "NIGHT_GIF_URL",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExaG5sY2E3enJqazl0d3R5eHFoZnl3ZnY2ejZ0NHF3ZzBqZnl0eSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7aD2saalBwwftBIY/giphy.gif",
)
DAY_GIF_URL = os.getenv(
    "DAY_GIF_URL",
    "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExY2Z5NTh5Mmp5bnM5c2J3eGN5eTlyNG52a2x2ZG84em11eXJ5aCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/xT9IgzoKnwFNmISR8I/giphy.gif",
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"LuThat Game Bot is alive on Render!")

    def log_message(self, format, *args):
        return  # Keep logs clean


def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"🌐 Keep-Alive HTTP Server listening on port {port}")
    server.serve_forever()


# ==========================================
# PERSISTENT COIN & SHOP STORAGE
# ==========================================
def load_user_db() -> Dict[str, dict]:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load user DB: {e}")
    return {}


def save_user_db():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(user_db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save user DB: {e}")


user_db: Dict[str, dict] = load_user_db()


def get_user_profile(user_id: int, name: str = "Player") -> dict:
    uid_s = str(user_id)
    if uid_s not in user_db:
        user_db[uid_s] = {
            "name": name,
            "coins": 100,  # Starter bonus
            "wins": 0,
            "games": 0,
            "items": {
                "shield": 0,      # 🛡️ ညဘက် တိုက်ခိုက်မှု ၁ ကြိမ် ကာကွယ်ပေးမည့် ဒိုင်း
                "role_pass": 0,   # 🎟️ နောက်ပွဲတွင် အထူး Role ရနိုင်ခြေ မြှင့်ပေးမည့် လက်မှတ်
                "double_coin": 0, # 💰 နိုင်ပွဲရလျှင် Coin ၂ ဆ ရမည့် ဘောနပ်စ်
            },
        }
    else:
        user_db[uid_s]["name"] = name
        if "items" not in user_db[uid_s]:
            user_db[uid_s]["items"] = {"shield": 0, "role_pass": 0, "double_coin": 0}
    return user_db[uid_s]


SHOP_ITEMS = {
    "shield": {
        "price": 150,
        "mm": "🛡️ ညစောင့်ဒိုင်း (Night Shield)",
        "en": "🛡️ Night Shield",
        "desc_mm": "ညဘက် လာသတ်ခံရပါက အသက် ၁ ကြိမ် အလိုအလျောက် ကယ်တင်ပေးမည်။",
        "desc_en": "Automatically blocks 1 night kill attack against you.",
    },
    "double_coin": {
        "price": 120,
        "mm": "💰 ၂ ဆ Coin ကတ် (2x Coin Boost)",
        "en": "💰 2x Coin Boost",
        "desc_mm": "နောက်တစ်ပွဲ အနိုင်ရပါက ရရှိမည့် Coin ကို ၂ ဆ တိုးပေးမည်။",
        "desc_en": "Doubles your coin reward on your next victory.",
    },
    "role_pass": {
        "price": 200,
        "mm": "🎟️ အထူး Role လက်မှတ် (VIP Role Pass)",
        "en": "🎟️ VIP Role Pass",
        "desc_mm": "ဂိမ်းစတင်ချိန်တွင် ဂိုဏ်းချုပ်၊ စုံထောက် သို့မဟုတ် စိတ္တဇလူသတ်သမား ဖြစ်နိုင်ခြေ မြှင့်ပေးမည်။",
        "desc_en": "Increases your chance of getting a key power role at game start.",
    },
}

# ==========================================
# LUTHAT GAME CUSTOM ROLES (11 ROLES)
# ==========================================
ROLES = {
    # --- 🔴 လူသတ်ဂိုဏ်းအုပ်စု (Killer Syndicate) ---
    "gang_boss": {
        "mm": "🤵🏻 လူသတ်ခေါင်းဆောင် ဂိုဏ်းချုပ်",
        "en": "🤵🏻 Gang Boss (Leader)",
        "team": "killer",
        "active_night": True,
        "desc_mm": "လူသတ်ဂိုဏ်း၏ အဓိကခေါင်းဆောင်ဖြစ်သည်။ ညဘက်တွင် သတ်မည့်သူကို အတည်ပြုဆုံးဖြတ်ခွင့်ရှိပြီး စုံထောက်စစ်ဆေးလျှင်လည်း လူကောင်းဟုသာ ပေါ်မည်။",
        "desc_en": "Leader of the Killer Syndicate. Decides the night target and appears innocent to Detective checks.",
    },
    "gang_member": {
        "mm": "🤵🏼 အဖွဲ့ဝင်",
        "en": "🤵🏼 Syndicate Member",
        "team": "killer",
        "active_night": True,
        "desc_mm": "ဂိုဏ်းချုပ်နှင့်အတူ ညဘက်တွင် ပစ်မှတ်ကို အကြံပြုရွေးချယ်ပြီး လုပ်ကြံရမည့် အဖွဲ့ဝင်ဖြစ်သည်။",
        "desc_en": "Assists the Gang Boss at night in selecting and eliminating targets.",
    },
    "spy": {
        "mm": "🕵️‍♂️ သူလျှို",
        "en": "🕵️‍♂️ Syndicate Spy",
        "team": "killer",
        "active_night": True,
        "desc_mm": "လူသတ်ဂိုဏ်းဘက်မှ သူလျှိုဖြစ်သည်။ ညဘက်တွင် ကစားသမားတစ်ဦး၏ Role အစစ်ကို ထောက်လှမ်းသိရှိနိုင်သည်။",
        "desc_en": "Killer faction spy. Investigates a player at night to learn their exact role.",
    },

    # --- 🔵 တရားဥပဒေနှင့် မြို့သူမြို့သားအုပ်စု (Law & Citizens) ---
    "detective": {
        "mm": "🕵🏻‍♂️ စုံထောက်",
        "en": "🕵🏻‍♂️ Detective",
        "team": "town",
        "active_night": True,
        "desc_mm": "ညဘက်တွင် သံသယရှိသူ တစ်ဦးကို စစ်ဆေးခြင်း သို့မဟုတ် ပစ်သတ်ခြင်း လုပ်ဆောင်နိုင်သည်။",
        "desc_en": "Each night, choose either to investigate a suspect or shoot them.",
    },
    "deputy": {
        "mm": "🕵🏼 စုံထောက်အကူ",
        "en": "🕵🏼 Assistant Detective",
        "team": "town",
        "active_night": False,
        "desc_mm": "စုံထောက်နှင့် ချိတ်ဆက်ကူညီပေးသူဖြစ်သည်။ စုံထောက် သေဆုံးသွားပါက စုံထောက်နေရာကို အလိုအလျောက် ဆက်ခံတာဝန်ယူရမည်။",
        "desc_en": "Partners with the Detective. Automatically becomes the Detective if the Detective dies.",
    },
    "police": {
        "mm": "👮🏻‍♂️ ရဲ",
        "en": "👮🏻‍♂️ Police Officer",
        "team": "town",
        "active_night": True,
        "desc_mm": "ညဘက်တွင် ကစားသမားတစ်ဦးကို ဖမ်းဆီးထိန်းသိမ်း (Jail) နိုင်သည်။ အဖမ်းခံရသူသည် ထိုညအတွက် လှုပ်ရှားခွင့်မရသလို လာသတ်ခံရခြင်းမှလည်း လွတ်မြောက်မည်။",
        "desc_en": "Jails one player at night, blocking their night action and protecting them from attacks.",
    },
    "doctor": {
        "mm": "👨🏼‍⚕️ ဆရာဝန်",
        "en": "👨🏼‍⚕️ Doctor",
        "team": "town",
        "active_night": True,
        "desc_mm": "ညဘက်တွင် လုပ်ကြံခံရမည့်သူ တစ်ဦးကို ကယ်တင်နိုင်သည်။ (မိမိကိုယ်ကို တစ်ဂိမ်းလျှင် ၁ ကြိမ်သာ ကယ်နိုင်သည်)",
        "desc_en": "Saves one player from being killed at night (can self-heal only once per game).",
    },
    "citizen": {
        "mm": "🧑🏻 မြို့သူမြို့သား",
        "en": "🧑🏻 Citizen",
        "team": "town",
        "active_night": False,
        "desc_mm": "နေ့ဘက် ဆွေးနွေးပွဲများတွင် အချက်အလက်သုံးသပ်ပြီး လူသတ်ဂိုဏ်းကို မဲခွဲဖော်ထုတ်ရမည်။",
        "desc_en": "Discuss during the day and vote out the Killer Syndicate.",
    },

    # --- 🟣 သီးသန့်အုပ်စု (Neutral / Wildcards) ---
    "psychopath": {
        "mm": "🔪 စိတ္တဇလူသတ်သမား",
        "en": "🔪 Psychopath",
        "team": "neutral",
        "active_night": True,
        "desc_mm": "တစ်ကိုယ်တော် လူသတ်သမားဖြစ်သည်။ ညဘက်တွင် ကိုယ့်သဘောဖြင့် လိုက်သတ်နိုင်ပြီး နောက်ဆုံးကျန်ရစ်သူဖြစ်ပါက အနိုင်ရမည်။",
        "desc_en": "Solo serial killer. Kills every night and wins as the last survivor.",
    },
    "drunkard": {
        "mm": "🍺 အရက်သမား",
        "en": "🍺 Drunkard",
        "team": "neutral",
        "active_night": True,
        "desc_mm": "ညဘက်တွင် အရက်မူးပြီး တစ်ယောက်ယောက်အိမ်သို့ မှားဝင်အိပ်တတ်သည်။ မိမိအိမ်တွင် မရှိသောကြောင့် ညဘက် လာသတ်ခံရခြင်းမှ ရှောင်လွှဲနိုင်သော်လည်း သွားအိပ်သည့်အိမ် တိုက်ခိုက်ခံရပါက ရောပါသွားနိုင်သည်။",
        "desc_en": "Gets drunk and sleeps at another player's house at night, avoiding home attacks unless the host is attacked.",
    },
    "jester": {
        "mm": "🎭 အရူး (Jester)",
        "en": "🎭 Jester",
        "team": "neutral",
        "active_night": False,
        "desc_mm": "နေ့ဘက် မဲပေးချိန်တွင် မြို့သူမြို့သားများ အထင်လွဲပြီး မိမိကို ကြိုးပေးစီရင်မိအောင် လှည့်စားနိုင်ပါက တစ်ကိုယ်တော် အနိုင်ရမည်။",
        "desc_en": "Tricks the town into lynching them during the day vote to win solo.",
    },
}

# ==========================================
# IN-MEMORY GAME STATE
# ==========================================
games: Dict[int, dict] = {}
user_active_game: Dict[int, int] = {}


def mention_html(user_id: int, name: str) -> str:
    safe_name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'


def t(lang: str, mm_text: str, en_text: str) -> str:
    return mm_text if lang == "mm" else en_text


def assign_roles(player_ids: List[int]) -> Dict[int, str]:
    n = len(player_ids)
    base_order = [
        "gang_boss",    # 1. လူသတ်ခေါင်းဆောင် ဂိုဏ်းချုပ်
        "detective",    # 2. စုံထောက်
        "doctor",       # 3. ဆရာဝန်
        "citizen",      # 4. မြို့သူမြို့သား
        "psychopath",   # 5. စိတ္တဇလူသတ်သမား
        "police",       # 6. ရဲ
        "gang_member",  # 7. အဖွဲ့ဝင်
        "deputy",       # 8. စုံထောက်အကူ
        "drunkard",     # 9. အရက်သမား
        "spy",          # 10. သူလျှို
        "jester",       # 11. အရူး (Jester)
    ]
    pool = base_order[:n]
    while len(pool) < n:
        pool.append("gang_member" if len(pool) % 4 == 0 else "citizen")

    # VIP Role Pass handling
    power_roles = [r for r in pool if r in ("gang_boss", "detective", "psychopath", "police", "doctor")]
    normal_roles = [r for r in pool if r not in power_roles]
    random.shuffle(power_roles)
    random.shuffle(normal_roles)

    vip_users = []
    regular_users = []
    for uid in player_ids:
        prof = get_user_profile(uid)
        if prof["items"].get("role_pass", 0) > 0:
            prof["items"]["role_pass"] -= 1
            vip_users.append(uid)
        else:
            regular_users.append(uid)
    save_user_db()

    random.shuffle(vip_users)
    random.shuffle(regular_users)
    ordered_users = vip_users + regular_users
    ordered_roles = power_roles + normal_roles

    return {uid: ordered_roles[i] for i, uid in enumerate(ordered_users)}


def check_win_condition(game: dict) -> Optional[str]:
    alive = [p for p in game["players"].values() if p["alive"]]
    killers = [p for p in alive if ROLES[p["role"]]["team"] == "killer"]
    psychos = [p for p in alive if p["role"] == "psychopath"]
    town_and_neutral = [p for p in alive if ROLES[p["role"]]["team"] != "killer" and p["role"] != "psychopath"]

    if psychos and len(alive) == 1:
        return "psychopath"
    if not killers and not psychos:
        return "town"
    if len(killers) >= (len(town_and_neutral) + len(psychos)) and not psychos:
        return "killer"
    return None


async def set_group_mute(context: ContextTypes.DEFAULT_TYPE, chat_id: int, mute: bool):
    try:
        perms = ChatPermissions(
            can_send_messages=not mute,
            can_send_polls=not mute,
            can_send_other_messages=not mute,
            can_add_web_page_previews=not mute,
        )
        await context.bot.set_chat_permissions(chat_id=chat_id, permissions=perms)
    except Exception as e:
        logger.warning(f"Could not set chat permissions in {chat_id}: {e}")


# ==========================================
# SHOP, PROFILE & PRIVATE COMMANDS
# ==========================================
async def cmd_start_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user = update.effective_user
    prof = get_user_profile(user.id, user.full_name)
    save_user_db()

    await update.message.reply_text(
        f"🎭 <b>LuThat Game Bot</b> မှ ကြိုဆိုပါတယ် {mention_html(user.id, user.full_name)}!\n\n"
        f"💰 <b>သင်၏ လက်ကျန် Coin:</b> <code>{prof['coins']} Coins</code>\n"
        f"🏆 <b>နိုင်ပွဲစုစုပေါင်း:</b> {prof['wins']} ပွဲ\n\n"
        f"• Group Chat ထဲတွင် <code>/open</code> ရိုက်ပြီး ဂိမ်းဖွင့်ကာ ပါဝင်နိုင်ပါသည်။\n"
        f"• ပွဲနိုင်တိုင်း Bot DM ထဲသို့ <b>Coins</b> များ အလိုအလျောက် ရရှိပါမည်။\n"
        f"• <code>/shop</code> နှိပ်ပြီး Coin များဖြင့် အထူးပစ္စည်းများ ဝယ်ယူနိုင်ပါသည်။\n"
        f"• <code>/profile</code> နှိပ်ပြီး မိမိ Coin နှင့် ပစ္စည်းစာရင်းကို ကြည့်နိုင်ပါသည်။",
        parse_mode="HTML",
    )


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    prof = get_user_profile(user.id, user.full_name)
    save_user_db()
    items = prof["items"]

    text = (
        f"👤 <b>ကစားသမား ပရိုဖိုင် ({mention_html(user.id, user.full_name)})</b>\n\n"
        f"💰 <b>လက်ကျန် Coin:</b> <code>{prof['coins']} Coins</code>\n"
        f"🏆 <b>နိုင်ပွဲ:</b> {prof['wins']} ပွဲ / စုစုပေါင်း {prof['games']} ပွဲ\n\n"
        f"🎒 <b>ပိုင်ဆိုင်ထားသော ပစ္စည်းများ (Inventory):</b>\n"
        f"• 🛡️ ညစောင့်ဒိုင်း (Night Shield): <b>{items.get('shield', 0)} ခု</b>\n"
        f"• 💰 ၂ ဆ Coin ကတ် (2x Boost): <b>{items.get('double_coin', 0)} ခု</b>\n"
        f"• 🎟️ အထူး Role လက်မှတ် (VIP Pass): <b>{items.get('role_pass', 0)} ခု</b>\n\n"
        f"🛒 ပစ္စည်းအသစ်ဝယ်ရန် <code>/shop</code> ကို နှိပ်ပါ။"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    prof = get_user_profile(user.id, user.full_name)
    save_user_db()

    lines = [
        f"🛒 <b>LuThat Game Shop (ဈေးဆိုင်)</b>\n"
        f"💰 <b>သင်၏ လက်ကျန်ငွေ:</b> <code>{prof['coins']} Coins</code>\n"
    ]
    btns = []
    for key, item in SHOP_ITEMS.items():
        lines.append(
            f"━━━━━━━━━━━━━━\n"
            f"<b>{item['mm']}</b> — <code>{item['price']} Coins</code>\n"
            f"<i>{item['desc_mm']}</i>"
        )
        btns.append(
            [InlineKeyboardButton(f"ဝယ်မည်: {item['mm']} ({item['price']} Coins)", callback_data=f"buy:{user.id}:{key}")]
        )

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode="HTML",
    )


async def cb_buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, owner_s, item_key = query.data.split(":")
    owner_id = int(owner_s)
    uid = query.from_user.id

    if uid != owner_id:
        await query.answer("⚠️ သင်ကိုယ်တိုင် /shop ရိုက်ပြီး ဝယ်ယူပါ!", show_alert=True)
        return

    item = SHOP_ITEMS.get(item_key)
    if not item:
        return

    prof = get_user_profile(uid, query.from_user.full_name)
    if prof["coins"] < item["price"]:
        await query.answer(
            f"❌ Coin မလုံလောက်ပါ! (လိုအပ်ငွေ: {item['price']} Coins, လက်ကျန်: {prof['coins']} Coins)",
            show_alert=True,
        )
        return

    prof["coins"] -= item["price"]
    prof["items"][item_key] = prof["items"].get(item_key, 0) + 1
    save_user_db()

    await query.answer(f"✅ {item['mm']} ဝယ်ယူပြီးပါပြီ! (လက်ကျန်: {prof['coins']} Coins)", show_alert=True)

    # Refresh shop message
    lines = [
        f"🛒 <b>LuThat Game Shop (ဈေးဆိုင်)</b>\n"
        f"💰 <b>သင်၏ လက်ကျန်ငွေ:</b> <code>{prof['coins']} Coins</code>\n"
        f"✅ <i>နောက်ဆုံးဝယ်ယူမှု: {item['mm']} (ပိုင်ဆိုင်မှု: {prof['items'][item_key]} ခု)</i>\n"
    ]
    btns = []
    for k, it in SHOP_ITEMS.items():
        lines.append(
            f"━━━━━━━━━━━━━━\n"
            f"<b>{it['mm']}</b> — <code>{it['price']} Coins</code>\n"
            f"<i>{it['desc_mm']}</i>"
        )
        btns.append(
            [InlineKeyboardButton(f"ဝယ်မည်: {it['mm']} ({it['price']} Coins)", callback_data=f"buy:{uid}:{k}")]
        )
    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML")


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in games:
        games[chat_id] = {"lang": "mm", "phase": "idle", "players": {}}
    cur = games[chat_id].get("lang", "mm")
    new_lang = "en" if cur == "mm" else "mm"
    games[chat_id]["lang"] = new_lang
    await update.message.reply_text(
        t(
            new_lang,
            "🌐 ဘာသာစကားကို <b>မြန်မာ (Burmese)</b> သို့ ပြောင်းလဲလိုက်ပါပြီ။",
            "🌐 Language switched to <b>English</b>.",
        ),
        parse_mode="HTML",
    )


async def cmd_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("⚠️ Group Chat ထဲတွင်သာ /open အသုံးပြုနိုင်ပါသည်။")
        return

    chat_id = chat.id
    lang = games.get(chat_id, {}).get("lang", "mm")

    if chat_id in games and games[chat_id].get("phase") not in ("idle", "ended"):
        await update.message.reply_text(
            t(lang, "⚠️ လက်ရှိ ဂိမ်းဝိုင်း ဖွင့်ထားပြီးသား ဖြစ်ပါသည်။", "⚠️ A game is already active in this group.")
        )
        return

    user = update.effective_user
    get_user_profile(user.id, user.full_name)
    save_user_db()

    games[chat_id] = {
        "chat_id": chat_id,
        "chat_title": chat.title or "LuThat Group",
        "lang": lang,
        "phase": "lobby",
        "day_num": 0,
        "players": {
            user.id: {
                "id": user.id,
                "name": user.full_name,
                "role": None,
                "alive": True,
                "self_healed": False,
                "afk_strikes": 0,
                "last_word_available": False,
                "last_word_used": False,
            }
        },
        "night_actions": {},
        "votes": {},
        "confirm_votes": {},
        "confirm_target": None,
        "task": None,
    }
    user_active_game[user.id] = chat_id

    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(t(lang, "➕ ဂိမ်းထဲဝင်မည် (Join)", "➕ Join Game"), callback_data=f"join:{chat_id}")]]
    )
    plist = f"1. {mention_html(user.id, user.full_name)}"
    await update.message.reply_text(
        t(
            lang,
            f"🎭 <b>LuThat Game — ဂိမ်းဝိုင်း ဖွင့်လှစ်လိုက်ပါပြီ</b>\n\n"
            f"• အနည်းဆုံး ကစားသမား: <b>၃ ဦး</b>\n"
            f"• အဆင်သင့်ဖြစ်လျှင် <code>/start</code> ရိုက်၍ စတင်ပါ\n\n"
            f"<b>ပါဝင်ထားသူများ (1 ဦး):</b>\n{plist}",
            f"🎭 <b>LuThat Game — Registration Open</b>\n\n"
            f"• Minimum Players: <b>3</b>\n"
            f"• Type <code>/start</code> when ready\n\n"
            f"<b>Joined Players (1):</b>\n{plist}",
        ),
        reply_markup=kb,
        parse_mode="HTML",
    )


async def cb_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = query.from_user

    game = games.get(chat_id)
    if not game or game["phase"] != "lobby":
        await query.answer("Lobby is closed.", show_alert=True)
        return

    lang = game["lang"]
    if user.id in game["players"]:
        await query.answer(t(lang, "သင် စာရင်းသွင်းပြီးသား ဖြစ်ပါသည်။", "You already joined!"), show_alert=True)
        return

    prof = get_user_profile(user.id, user.full_name)
    save_user_db()

    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=t(
                lang,
                f"✅ <b>{game['chat_title']}</b> ဂိမ်းဝိုင်းထဲသို့ ဝင်ရောက်ပြီးပါပြီ!\n💰 လက်ကျန် Coin: <code>{prof['coins']} Coins</code>",
                f"✅ You joined the game in <b>{game['chat_title']}</b>!\n💰 Balance: <code>{prof['coins']} Coins</code>",
            ),
            parse_mode="HTML",
        )
    except Exception:
        bot_username = (await context.bot.get_me()).username
        await query.answer(
            t(
                lang,
                f"Bot DM ကို အရင် Start နှိပ်ပေးပါ (@{bot_username})",
                f"Please start the bot in DM first (@{bot_username})",
            ),
            show_alert=True,
        )
        return

    game["players"][user.id] = {
        "id": user.id,
        "name": user.full_name,
        "role": None,
        "alive": True,
        "self_healed": False,
        "afk_strikes": 0,
        "last_word_available": False,
        "last_word_used": False,
    }
    user_active_game[user.id] = chat_id
    await query.answer(t(lang, "ဂိမ်းထဲ ဝင်ရောက်ပြီးပါပြီ!", "Joined!"))

    plist = "\n".join(
        f"{i+1}. {mention_html(p['id'], p['name'])}"
        for i, p in enumerate(game["players"].values())
    )
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(t(lang, "➕ ဂိမ်းထဲဝင်မည် (Join)", "➕ Join Game"), callback_data=f"join:{chat_id}")]]
    )
    await query.edit_message_text(
        t(
            lang,
            f"🎭 <b>LuThat Game — ဂိမ်းဝိုင်း ဖွင့်လှစ်လိုက်ပါပြီ</b>\n\n"
            f"• အနည်းဆုံး ကစားသမား: <b>၃ ဦး</b>\n"
            f"• အဆင်သင့်ဖြစ်လျှင် <code>/start</code> ရိုက်၍ စတင်ပါ\n\n"
            f"<b>ပါဝင်ထားသူများ ({len(game['players'])} ဦး):</b>\n{plist}",
            f"🎭 <b>LuThat Game — Registration Open</b>\n\n"
            f"• Minimum Players: <b>3</b>\n"
            f"• Type <code>/start</code> when ready\n\n"
            f"<b>Joined Players ({len(game['players'])}):</b>\n{plist}",
        ),
        reply_markup=kb,
        parse_mode="HTML",
    )


async def cmd_start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await cmd_start_private(update, context)
        return

    chat_id = chat.id
    game = games.get(chat_id)
    if not game or game["phase"] != "lobby":
        return

    lang = game["lang"]
    if len(game["players"]) < 3:
        await update.message.reply_text(
            t(lang, "⚠️ အနည်းဆုံး ကစားသမား <b>၃ ဦး</b> ရှိမှ စတင်နိုင်ပါမည်။", "⚠️ Need at least <b>3 players</b> to start."),
            parse_mode="HTML",
        )
        return

    assigned = assign_roles(list(game["players"].keys()))
    for uid, role in assigned.items():
        game["players"][uid]["role"] = role

    bot_username = (await context.bot.get_me()).username
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(t(lang, "Check your role", "Check your role"), url=f"https://t.me/{bot_username}")]]
    )
    await update.message.reply_text(
        t(
            lang,
            "<b>ဂိမ်းစတင်ပါပြီ!</b>\n\nစက္ကန့်အနည်းငယ်အတွင်း သင်၏ Bot DM ဆီသို့ Role နှင့် စွမ်းရည်များကို ပေးပို့ပေးပါမည်။",
            "<b>The game begins!</b>\n\nWithin a few seconds, the bot will send you a personal message with your role.",
        ),
        reply_markup=kb,
        parse_mode="HTML",
    )

    killers = [p for p in game["players"].values() if ROLES[p["role"]]["team"] == "killer"]
    det_team = [p for p in game["players"].values() if p["role"] in ("detective", "deputy")]

    for p in game["players"].values():
        r = p["role"]
        r_title = ROLES[r][lang]
        r_desc = ROLES[r][f"desc_{lang}"]
        extra = ""

        if ROLES[r]["team"] == "killer" and len(killers) > 1:
            allies = ", ".join(f"{m['name']} ({ROLES[m['role']][lang]})" for m in killers if m["id"] != p["id"])
            extra = t(lang, f"\n\n🤝 <b>လူသတ်ဂိုဏ်း အဖွဲ့ဖော်များ:</b> {allies}", f"\n\n🤝 <b>Syndicate Allies:</b> {allies}")
        elif r in ("detective", "deputy") and len(det_team) > 1:
            partner = ", ".join(f"{m['name']} ({ROLES[m['role']][lang]})" for m in det_team if m["id"] != p["id"])
            extra = t(lang, f"\n\n🔍 <b>စုံထောက်အဖွဲ့ဖော်:</b> {partner}", f"\n\n🔍 <b>Detective Partner:</b> {partner}")

        try:
            await context.bot.send_message(
                chat_id=p["id"],
                text=t(
                    lang,
                    f"🎭 <b>သင်၏ Role မှာ {r_title}!</b>\n\n{r_desc}{extra}",
                    f"🎭 <b>You are {r_title}!</b>\n\n{r_desc}{extra}",
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"DM role send failed for {p['id']}: {e}")

    game["task"] = asyncio.create_task(run_game_loop(context, chat_id))


# ==========================================
# MAIN GAME LOOP (NIGHT -> DAY -> VOTE -> CONFIRM)
# ==========================================
async def run_game_loop(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = games.get(chat_id)
    if not game:
        return
    lang = game["lang"]
    bot_username = (await context.bot.get_me()).username

    while True:
        # 1. NIGHT PHASE
        game["day_num"] += 1
        game["phase"] = "night"
        game["night_actions"] = {}
        await set_group_mute(context, chat_id, True)

        kb_bot = InlineKeyboardMarkup([[InlineKeyboardButton("Go to bot", url=f"https://t.me/{bot_username}")]])
        night_caption = t(
            lang,
            f"🌃 <b>ည {game['day_num']}</b>\n"
            f"မြို့ပေါ်သို့ ညအမှောင်ထု ကျရောက်လာပါပြီ။ ညဘက် Role ရှိသူများ Bot DM ထဲတွင် <b>45 စက္ကန့်</b> အတွင်း ရွေးချယ်ပါ! (၂ ညဆက်တိုက် မလှုပ်ရှားပါက AFK ဖြင့် သေဆုံးမည်)",
            f"🌃 <b>Night {game['day_num']}</b>\n"
            f"Night falls on the city. Active roles have <b>45 seconds</b> in Bot DM! (2 missed nights = AFK death)",
        )
        try:
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=NIGHT_GIF_URL,
                caption=night_caption,
                reply_markup=kb_bot,
                parse_mode="HTML",
            )
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=night_caption, reply_markup=kb_bot, parse_mode="HTML")

        alive_players = [p for p in game["players"].values() if p["alive"]]
        alive_list = "\n".join(f"{i+1}. {mention_html(p['id'], p['name'])}" for i, p in enumerate(alive_players))
        role_summary = ", ".join(ROLES[p["role"]][lang] for p in alive_players)
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(
                lang,
                f"<b>အသက်ရှင်ကျန်သူများ:</b>\n{alive_list}\n\n<b>ပါဝင်နေသော Role များ:</b>\n{role_summary}\nစုစုပေါင်း: {len(alive_players)} ဦး။",
                f"<b>Players alive:</b>\n{alive_list}\n\n<b>Roles in play:</b>\n{role_summary}\nTotal: {len(alive_players)} people.",
            ),
            parse_mode="HTML",
        )

        for p in alive_players:
            await send_night_prompt(context, game, p)

        await asyncio.sleep(45)

        # Check AFK Strikes
        afk_deaths = []
        for p in [pl for pl in game["players"].values() if pl["alive"]]:
            if ROLES[p["role"]]["active_night"]:
                if p["id"] in game["night_actions"]:
                    p["afk_strikes"] = 0
                else:
                    p["afk_strikes"] += 1
                    if p["afk_strikes"] >= 2:
                        p["alive"] = False
                        p["last_word_available"] = True
                        p["last_word_used"] = False
                        afk_deaths.append(p)
                        try:
                            await context.bot.send_message(
                                chat_id=p["id"],
                                text=t(
                                    lang,
                                    "⏳ <b>၂ ညဆက်တိုက် မလှုပ်ရှားခဲ့သဖြင့် AFK ဖြင့် သေဆုံးသွားပါပြီ!</b>",
                                    "⏳ <b>You died of AFK after 2 inactive nights!</b>",
                                ),
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass
                    else:
                        try:
                            await context.bot.send_message(
                                chat_id=p["id"],
                                text=t(
                                    lang,
                                    "⚠️ <b>သတိပေးချက် (AFK 1/2):</b> ယနေ့ည ဘာမှမရွေးချယ်ခဲ့ပါ။ နောက်တစ်ည ထပ်မံပျက်ကွက်ပါက AFK ဖြင့် သေဆုံးပါမည်!",
                                    "⚠️ <b>Warning (AFK 1/2):</b> You missed tonight's action. One more missed night will result in AFK death!",
                                ),
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass

        report_lines = await resolve_night(context, game, afk_deaths)
        await promote_deputy_if_needed(context, game)

        # 2. DAY PHASE
        game["phase"] = "day"
        await set_group_mute(context, chat_id, False)

        day_caption = t(
            lang,
            f"🏙 <b>နေ့ {game['day_num']}</b>\n"
            f"နေမင်းကြီး ထွက်ပေါ်လာပြီး မနေ့ညက လမ်းမပေါ်မှ သွေးစက်များကို ခြောက်သွေ့စေခဲ့ပြီ...\n\n"
            f"{report_lines}\n\n💬 ဆွေးနွေးရန် အချိန်: <b>60 စက္ကန့်</b>။",
            f"🏙 <b>Day {game['day_num']}</b>\n"
            f"The sun rises and dries the blood spilled on the asphalt last night...\n\n"
            f"{report_lines}\n\n💬 Discussion time: <b>60 seconds</b>.",
        )
        try:
            await context.bot.send_animation(
                chat_id=chat_id,
                animation=DAY_GIF_URL,
                caption=day_caption,
                parse_mode="HTML",
            )
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=day_caption, parse_mode="HTML")

        win = check_win_condition(game)
        if win:
            await announce_winner(context, game, win)
            return

        await asyncio.sleep(60)

        # 3. VOTING PHASE (Private in Bot DM)
        game["phase"] = "vote"
        game["votes"] = {}
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(
                lang,
                "🗳 <b>မဲပေးချိန်</b>\nတရားခံကို ဖော်ထုတ်အပြစ်ပေးရန် <b>40 စက္ကန့်</b> အတွင်း <b>Bot DM</b> ထဲသို့ သွားရောက်မဲပေးပါ!",
                "🗳 <b>Voting Phase</b>\nOpen <b>Bot DM</b> to cast your vote within <b>40 seconds</b>!",
            ),
            reply_markup=kb_bot,
            parse_mode="HTML",
        )

        alive_now = [p for p in game["players"].values() if p["alive"]]
        for voter in alive_now:
            btns = [
                [InlineKeyboardButton(t_p["name"], callback_data=f"dmvote:{chat_id}:{t_p['id']}")]
                for t_p in alive_now
                if t_p["id"] != voter["id"]
            ]
            btns.append([InlineKeyboardButton(t(lang, "⏭ မဲမပေးဘဲ ကျော်မည် (Skip)", "⏭ Skip Vote"), callback_data=f"dmvote:{chat_id}:0")])
            try:
                await context.bot.send_message(
                    chat_id=voter["id"],
                    text=t(
                        lang,
                        f"🗳 <b>မဲပေးချိန် ({game['chat_title']})</b>\nကြိုးပေးမည့်သူကို ရွေးချယ်မဲပေးပါ:",
                        f"🗳 <b>Voting Phase ({game['chat_title']})</b>\nChoose a suspect to lynch:",
                    ),
                    reply_markup=InlineKeyboardMarkup(btns),
                    parse_mode="HTML",
                )
            except Exception:
                pass

        await asyncio.sleep(40)

        tally: Dict[int, int] = {}
        for target_id in game["votes"].values():
            if target_id != 0:
                tally[target_id] = tally.get(target_id, 0) + 1

        if not tally:
            await context.bot.send_message(
                chat_id=chat_id,
                text=t(lang, "⏭ မဲအများစုက မည်သူ့ကိုမျှ ကြိုးမပေးရန် ဆုံးဖြတ်လိုက်ပါသည်။", "⏭ The town decided not to lynch anyone."),
            )
            continue

        top_target_id = max(tally, key=lambda k: tally[k])
        top_votes = tally[top_target_id]
        if list(tally.values()).count(top_votes) > 1:
            await context.bot.send_message(
                chat_id=chat_id,
                text=t(lang, "⚖️ မဲအရေအတွက် တူညီနေပါသဖြင့် မည်သူ့ကိုမျှ ကြိုးမပေးပါ။", "⚖️ Votes are tied. Nobody was lynched."),
            )
            continue

        # 4. CONFIRMATION POLL (👍 / 👎)
        game["phase"] = "confirm"
        game["confirm_target"] = top_target_id
        game["confirm_votes"] = {}
        target_p = game["players"][top_target_id]

        confirm_kb = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("👍", callback_data=f"confirm:{chat_id}:up"),
                InlineKeyboardButton("👎", callback_data=f"confirm:{chat_id}:down"),
            ]]
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(
                lang,
                f"⚖️ <b>{mention_html(target_p['id'], target_p['name'])} အပေါ် နောက်ဆုံး အတည်ပြုချက်</b>\n"
                f"တကယ်ပဲ ကြိုးပေးသင့်သလား? <b>25 စက္ကန့်</b> အတွင်း မဲပေးပါ:\n\n"
                f"👍 <b>ကြိုးပေးမည်</b>  |  👎 <b>လွှတ်ပေးမည်</b>",
                f"⚖️ <b>Final Verdict on {mention_html(target_p['id'], target_p['name'])}</b>\n"
                f"Do you really want to lynch them? Vote within <b>25 seconds</b>:\n\n"
                f"👍 <b>Execute</b>  |  👎 <b>Spare</b>",
            ),
            reply_markup=confirm_kb,
            parse_mode="HTML",
        )

        await asyncio.sleep(25)

        up_cnt = sum(1 for v in game["confirm_votes"].values() if v == "up")
        down_cnt = sum(1 for v in game["confirm_votes"].values() if v == "down")

        if up_cnt > down_cnt:
            target_p["alive"] = False
            target_p["last_word_available"] = True
            target_p["last_word_used"] = False
            await context.bot.send_message(
                chat_id=chat_id,
                text=t(
                    lang,
                    f"<b>မဲရလဒ်:</b>\n{up_cnt} 👍 | {down_cnt} 👎\n\n"
                    f"{mention_html(target_p['id'], target_p['name'])} ကို ကြိုးပေးစီရင်လိုက်ပါပြီ!\n"
                    f"{mention_html(target_p['id'], target_p['name'])} ၏ Role မှာ <b>{ROLES[target_p['role']][lang]}</b> ဖြစ်ပါသည်။",
                    f"<b>Poll results:</b>\n{up_cnt} 👍 | {down_cnt} 👎\n\n"
                    f"Lynching {mention_html(target_p['id'], target_p['name'])}! :)\n"
                    f"{mention_html(target_p['id'], target_p['name'])} was a <b>{ROLES[target_p['role']][lang]}</b>",
                ),
                parse_mode="HTML",
            )
            await notify_victim_last_word(context, game, target_p)

            if target_p["role"] == "jester":
                await announce_winner(context, game, "jester", jester_winner=target_p)
                return

            await promote_deputy_if_needed(context, game)
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=t(
                    lang,
                    f"<b>မဲရလဒ်:</b>\n{up_cnt} 👍 | {down_cnt} 👎\n\nမြို့သူမြို့သားများက {mention_html(target_p['id'], target_p['name'])} ကို ပြန်လည်လွှတ်ပေးလိုက်ပါသည်။",
                    f"<b>Poll results:</b>\n{up_cnt} 👍 | {down_cnt} 👎\n\nThe town spared {mention_html(target_p['id'], target_p['name'])}!",
                ),
                parse_mode="HTML",
            )

        win = check_win_condition(game)
        if win:
            await announce_winner(context, game, win)
            return


# ==========================================
# DEPUTY PROMOTION HELPER
# ==========================================
async def promote_deputy_if_needed(context: ContextTypes.DEFAULT_TYPE, game: dict):
    lang = game["lang"]
    det_alive = any(p["alive"] and p["role"] == "detective" for p in game["players"].values())
    if det_alive:
        return

    for p in game["players"].values():
        if p["alive"] and p["role"] == "deputy":
            p["role"] = "detective"
            try:
                await context.bot.send_message(
                    chat_id=p["id"],
                    text=t(
                        lang,
                        "🕵🏻‍♂️ <b>စုံထောက် ကွယ်လွန်သွားပါပြီ!</b>\nသင်သည် <b>စုံထောက် (Detective)</b> ရာထူးကို ဆက်ခံရရှိပါပြီ။ နောက်ညမှစ၍ စစ်ဆေးခြင်းနှင့် ပစ်သတ်ခြင်းတို့ကို လုပ်ဆောင်နိုင်ပါပြီ။",
                        "🕵🏻‍♂️ <b>The Detective has died!</b>\nYou have been promoted to <b>Detective</b>!",
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
            break


# ==========================================
# NIGHT PROMPTS & CALLBACKS
# ==========================================
async def send_night_prompt(context: ContextTypes.DEFAULT_TYPE, game: dict, player: dict):
    lang = game["lang"]
    chat_id = game["chat_id"]
    role = player["role"]
    uid = player["id"]

    if not ROLES[role]["active_night"]:
        return

    if role == "detective":
        kb = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(t(lang, "🔍 စစ်မည်", "🔍 Check"), callback_data=f"det_mode:{chat_id}:check"),
                InlineKeyboardButton(t(lang, "🔫 သတ်မည်", "🔫 Shoot"), callback_data=f"det_mode:{chat_id}:shoot"),
            ]]
        )
        await context.bot.send_message(
            chat_id=uid,
            text=t(lang, "🕵🏻‍♂️ ယနေ့ည ပြုလုပ်မည့် လုပ်ဆောင်ချက်ကို ရွေးချယ်ပါ:", "🕵🏻‍♂️ Choose your action tonight:"),
            reply_markup=kb,
        )
        return

    targets = [p for p in game["players"].values() if p["alive"]]
    if role != "doctor":
        targets = [p for p in targets if p["id"] != uid]
    elif player["self_healed"]:
        targets = [p for p in targets if p["id"] != uid]

    btns = [[InlineKeyboardButton(tp["name"], callback_data=f"nact:{chat_id}:{role}:{tp['id']}")] for tp in targets]
    prompts = {
        "gang_boss": t(lang, "🤵🏻 ယနေ့ည လုပ်ကြံမည့် သားကောင်ကို ရွေးချယ်ပါ:", "🤵🏻 Choose tonight's target to eliminate:"),
        "gang_member": t(lang, "🤵🏼 ဂိုဏ်းချုပ်ထံ သတ်မည့်သူ အကြံပြုရွေးချယ်ပါ:", "🤵🏼 Suggest a target to the Gang Boss:"),
        "spy": t(lang, "🕵️‍♂️ ယနေ့ည ထောက်လှမ်းစစ်ဆေးမည့်သူကို ရွေးချယ်ပါ:", "🕵️‍♂️ Choose a player to spy on tonight:"),
        "police": t(lang, "👮🏻‍♂️ ယနေ့ည ဖမ်းဆီးထိန်းသိမ်း (Jail) မည့်သူကို ရွေးချယ်ပါ:", "👮🏻‍♂️ Choose a suspect to jail tonight:"),
        "doctor": t(lang, "👨🏼‍⚕️ ယနေ့ည ကုသကယ်တင်မည့်သူကို ရွေးချယ်ပါ:", "👨🏼‍⚕️ Choose a patient to save tonight:"),
        "psychopath": t(lang, "🔪 ယနေ့ည သတ်ဖြတ်မည့်သူကို ရွေးချယ်ပါ:", "🔪 Choose your victim tonight:"),
        "drunkard": t(lang, "🍺 ယနေ့ည မူးပြီး သွားအိပ်မည့်အိမ်ကို ရွေးချယ်ပါ:", "🍺 Choose whose house to sleep at tonight:"),
    }
    await context.bot.send_message(chat_id=uid, text=prompts[role], reply_markup=InlineKeyboardMarkup(btns))


async def cb_detective_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id_s, mode = query.data.split(":")
    chat_id = int(chat_id_s)
    uid = query.from_user.id
    game = games.get(chat_id)

    if not game or game["phase"] != "night" or not game["players"].get(uid, {}).get("alive"):
        await query.answer("Action expired.", show_alert=True)
        return

    lang = game["lang"]
    targets = [p for p in game["players"].values() if p["alive"] and p["id"] != uid]
    btns = [[InlineKeyboardButton(tp["name"], callback_data=f"nact:{chat_id}:det_{mode}:{tp['id']}")] for tp in targets]
    title = (
        t(lang, "🔍 စစ်ဆေးမည့်သူကို ရွေးချယ်ပါ:", "🔍 Select a player to investigate:")
        if mode == "check"
        else t(lang, "🔫 ပစ်သတ်မည့်သူကို ရွေးချယ်ပါ:", "🔫 Select a player to shoot:")
    )
    await query.edit_message_text(text=title, reply_markup=InlineKeyboardMarkup(btns))


async def cb_night_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id_s, act_type, target_s = query.data.split(":")
    chat_id = int(chat_id_s)
    target_id = int(target_s)
    uid = query.from_user.id

    game = games.get(chat_id)
    if not game or game["phase"] != "night":
        await query.answer("Night is over.", show_alert=True)
        return

    player = game["players"].get(uid)
    if not player or not player["alive"]:
        await query.answer("You are dead.", show_alert=True)
        return

    lang = game["lang"]
    target_p = game["players"][target_id]
    first_time = uid not in game["night_actions"]
    game["night_actions"][uid] = {"type": act_type, "target": target_id}

    await query.edit_message_text(
        text=t(lang, f"✅ ရွေးချယ်ပြီးပါပြီ: <b>{target_p['name']}</b>", f"✅ Selected: <b>{target_p['name']}</b>"),
        parse_mode="HTML",
    )

    if first_time:
        log_map = {
            "gang_boss": t(lang, "🤵🏻 လူသတ်ခေါင်းဆောင် ဂိုဏ်းချုပ်က သားကောင်ကို ရွေးချယ်လိုက်ပါပြီ...", "🤵🏻 Gang Boss chose a victim..."),
            "gang_member": t(lang, "🤵🏼 လူသတ်ဂိုဏ်း အဖွဲ့ဝင်က ပစ်မှတ်ကို အကြံပြုလိုက်ပါပြီ...", "🤵🏼 Syndicate Member suggested a target..."),
            "spy": t(lang, "🕵️‍♂️ သူလျှိုက မှောင်ရိပ်ခို၍ ထောက်လှမ်းနေပါပြီ...", "🕵️‍♂️ Spy slipped into the shadows to gather intel..."),
            "det_check": t(lang, "🕵🏻‍♂️ စုံထောက်က လျှို့ဝှက်စုံစမ်းရန် ထွက်ခွာသွားပါပြီ...", "🕵🏻‍♂️ Detective went on a secret investigation..."),
            "det_shoot": t(lang, "🕵🏻‍♂️ စုံထောက်က သေနတ်မောင်းတင်လိုက်ပါပြီ...", "🕵🏻‍♂️ Detective loaded his gun..."),
            "police": t(lang, "👮🏻‍♂️ ရဲက ညဘက် ကင်းလှည့်ဖမ်းဆီးရန် ထွက်ခွာသွားပါပြီ...", "👮🏻‍♂️ Police Officer went out on night patrol..."),
            "doctor": t(lang, "👨🏼‍⚕️ ဆရာဝန် ညဂျူတီ စတင်ထမ်းဆောင်နေပါပြီ...", "👨🏼‍⚕️ Doctor went on night duty..."),
            "psychopath": t(lang, "🔪 စိတ္တဇလူသတ်သမား ချုံပုတ်ထဲတွင် ဓားသွေးနေပါပြီ...", "🔪 Psychopath hid deep in the bushes..."),
            "drunkard": t(lang, "🍺 အရက်သမား ပုလင်းကိုင်ပြီး လမ်းပေါ်ယိုင်တိုင်တိုင် ထွက်သွားပါပြီ...", "🍺 Drunkard stumbled down the street with a bottle..."),
        }
        if act_type in log_map:
            await context.bot.send_message(chat_id=chat_id, text=log_map[act_type])


async def resolve_night(context: ContextTypes.DEFAULT_TYPE, game: dict, afk_deaths: List[dict]) -> str:
    lang = game["lang"]
    actions = game["night_actions"]
    players = game["players"]

    jailed_id: Optional[int] = None
    healed_id: Optional[int] = None
    drunk_visits: Dict[int, int] = {}

    for uid, act in actions.items():
        if act["type"] == "police":
            jailed_id = act["target"]
            try:
                await context.bot.send_message(
                    chat_id=jailed_id,
                    text=t(
                        lang,
                        "👮🏻‍♂️ <b>ရဲက သင့်ကို ယနေ့ည ဖမ်းဆီးထိန်းသိမ်းထားပါသည်။</b> (ညဘက်လှုပ်ရှားခွင့် ပိတ်သွားသော်လည်း လာသတ်ခံရခြင်းမှ လွတ်မြောက်ပါသည်)",
                        "👮🏻‍♂️ <b>You were jailed by the Police tonight!</b> (Action blocked, but safe from attacks)",
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass

    effective_actions = {uid: act for uid, act in actions.items() if uid != jailed_id}

    for uid, act in effective_actions.items():
        if act["type"] == "doctor":
            healed_id = act["target"]
            if healed_id == uid:
                players[uid]["self_healed"] = True
        elif act["type"] == "drunkard":
            drunk_visits[uid] = act["target"]

    raw_kills: List[int] = []
    boss_target = None
    member_targets = []
    for uid, act in effective_actions.items():
        if act["type"] == "gang_boss":
            boss_target = act["target"]
        elif act["type"] == "gang_member":
            member_targets.append(act["target"])
        elif act["type"] in ("psychopath", "det_shoot"):
            raw_kills.append(act["target"])

    syndicate_victim = boss_target or (member_targets[0] if member_targets else None)
    if syndicate_victim:
        raw_kills.append(syndicate_victim)

    for uid, act in effective_actions.items():
        if act["type"] == "det_check":
            t_p = players[act["target"]]
            is_bad = (ROLES[t_p["role"]]["team"] == "killer" and t_p["role"] != "gang_boss") or t_p["role"] == "psychopath"
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=t(
                        lang,
                        f"🔍 စစ်ဆေးချက်ရလဒ်: <b>{t_p['name']}</b> သည် "
                        + ("<b>အန္တရာယ်ရှိသူ (လူဆိုး) ဖြစ်သည်!</b>" if is_bad else "အပြစ်ကင်းသူ ဖြစ်သည်။"),
                        f"🔍 Investigation Result: <b>{t_p['name']}</b> is "
                        + ("<b>Hostile!</b>" if is_bad else "Innocent."),
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        elif act["type"] == "spy":
            t_p = players[act["target"]]
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=t(
                        lang,
                        f"🕵️‍♂️ သူလျှို ထောက်လှမ်းချက်: <b>{t_p['name']}</b> ၏ Role အစစ်မှာ <b>{ROLES[t_p['role']][lang]}</b> ဖြစ်သည်။",
                        f"🕵️‍♂️ Spy Intel: <b>{t_p['name']}</b>'s exact role is <b>{ROLES[t_p['role']][lang]}</b>.",
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass

    final_kills: List[int] = []
    for k_id in set(raw_kills):
        if k_id in drunk_visits:
            continue
        final_kills.append(k_id)
        for d_uid, host_id in drunk_visits.items():
            if host_id == k_id:
                final_kills.append(d_uid)

    dead_tonight = list(afk_deaths)
    for k_id in set(final_kills):
        if k_id == healed_id or k_id == jailed_id:
            continue

        # Check Shop Item: Night Shield!
        prof = get_user_profile(k_id, players[k_id]["name"])
        if prof["items"].get("shield", 0) > 0:
            prof["items"]["shield"] -= 1
            save_user_db()
            try:
                await context.bot.send_message(
                    chat_id=k_id,
                    text=t(
                        lang,
                        "🛡️ <b>သင်၏ ညစောင့်ဒိုင်း (Night Shield) က ယနေ့ည တိုက်ခိုက်မှုမှ အသက်ကယ်တင်လိုက်ပါပြီ!</b>",
                        "🛡️ <b>Your Night Shield blocked a lethal attack tonight!</b>",
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
            continue

        vp = players[k_id]
        if vp["alive"]:
            vp["alive"] = False
            vp["last_word_available"] = True
            vp["last_word_used"] = False
            dead_tonight.append(vp)

    if not dead_tonight:
        return t(lang, "🕊 မနေ့ညက မည်သူမျှ အသတ်မခံရပါ။", "🕊 Nobody died last night.")

    lines = []
    for dp in dead_tonight:
        if dp in afk_deaths:
            lines.append(
                t(
                    lang,
                    f"⏳ {mention_html(dp['id'], dp['name'])} ({ROLES[dp['role']][lang]}) သည် ၂ ညဆက်တိုက် မလှုပ်ရှားဘဲ <b>AFK</b> ဖြင့် သေဆုံးသွားသည်။",
                    f"⏳ {mention_html(dp['id'], dp['name'])} ({ROLES[dp['role']][lang]}) died of <b>AFK</b> inactivity.",
                )
            )
        else:
            lines.append(
                t(
                    lang,
                    f"💀 {mention_html(dp['id'], dp['name'])} ({ROLES[dp['role']][lang]}) ညဘက်တွင် ရက်စက်စွာ အသတ်ခံလိုက်ရသည်။",
                    f"💀 {mention_html(dp['id'], dp['name'])} ({ROLES[dp['role']][lang]}) was brutally murdered tonight...",
                )
            )
        await notify_victim_last_word(context, game, dp)
    return "\n".join(lines)


# ==========================================
# ONE-TIME LAST WORDS SYSTEM (BOT DM -> GROUP)
# ==========================================
async def notify_victim_last_word(context: ContextTypes.DEFAULT_TYPE, game: dict, victim: dict):
    lang = game["lang"]
    try:
        await context.bot.send_message(
            chat_id=victim["id"],
            text=t(
                lang,
                f"💀 <b>သင် ({game['chat_title']}) ဂိမ်းထဲတွင် သေဆုံးသွားပါပြီ!</b>\n\n"
                f"သင်၏ <b>နောက်ဆုံးစကား တစ်ခါ (၁ ကြိမ်တည်း)</b> ကို ဤ Bot DM ထဲသို့ စာရိုက်ပို့ပါက Group Chat ထဲသို့ ပြန်လည်ဖော်ပြပေးပါမည်။\n"
                f"<i>(တစ်ကြိမ်ပို့ပြီးပါက ထပ်မံပို့ခွင့် မရှိတော့ပါ)</i>",
                f"💀 <b>You have died in {game['chat_title']}!</b>\n\n"
                f"Reply with <b>ONE final message (Last Words)</b> here in DM and it will be relayed to the group.\n"
                f"<i>(Strictly 1 message allowed)</i>",
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass


async def handle_private_last_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or not update.message or not update.message.text:
        return
    uid = update.effective_user.id
    chat_id = user_active_game.get(uid)
    if not chat_id or chat_id not in games:
        return

    game = games[chat_id]
    player = game["players"].get(uid)
    if not player or player["alive"]:
        return

    lang = game["lang"]
    if not player["last_word_available"] or player["last_word_used"]:
        await update.message.reply_text(
            t(
                lang,
                "🔒 သင်၏ တစ်ခါပြောခွင့် (Last Word) ကို အသုံးပြုပြီးပါပြီ။ ထပ်မံပို့ခွင့် မရှိတော့ပါ။",
                "🔒 You have already used your one-time Last Words.",
            )
        )
        return

    player["last_word_used"] = True
    player["last_word_available"] = False
    safe_text = update.message.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    await update.message.reply_text(
        t(
            lang,
            "✅ သင်၏ နောက်ဆုံးစကား (၁ ကြိမ်) ကို Group Chat ထဲသို့ ပို့ပေးလိုက်ပါပြီ။",
            "✅ Your one-time Last Words have been relayed to the group.",
        )
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=t(
            lang,
            f"🗣 <b>မြို့သူမြို့သားတချို့က {mention_html(player['id'], player['name'])} ၏ နောက်ဆုံးအသံကို ကြားလိုက်ရသည်:</b>\n\n"
            f"« {safe_text} »",
            f"🗣 <b>Some citizen heard as {mention_html(player['id'], player['name'])} whispered before dying:</b>\n\n"
            f"« {safe_text} »",
        ),
        parse_mode="HTML",
    )


# ==========================================
# VOTING & CONFIRMATION CALLBACKS
# ==========================================
async def cb_dm_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id_s, target_s = query.data.split(":")
    chat_id = int(chat_id_s)
    target_id = int(target_s)
    uid = query.from_user.id

    game = games.get(chat_id)
    if not game or game["phase"] != "vote":
        await query.answer("Voting phase ended.", show_alert=True)
        return

    player = game["players"].get(uid)
    if not player or not player["alive"]:
        await query.answer("Dead players cannot vote.", show_alert=True)
        return

    lang = game["lang"]
    game["votes"][uid] = target_id
    if target_id == 0:
        await query.edit_message_text(t(lang, "⏭ သင် <b>Skip</b> မဲပေးလိုက်ပါပြီ။", "⏭ You voted to <b>Skip</b>."), parse_mode="HTML")
    else:
        tp = game["players"][target_id]
        await query.edit_message_text(
            t(lang, f"🗳 သင် <b>{tp['name']}</b> ကို မဲပေးလိုက်ပါပြီ။", f"🗳 You voted for <b>{tp['name']}</b>."),
            parse_mode="HTML",
        )


async def cb_confirm_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, chat_id_s, choice = query.data.split(":")
    chat_id = int(chat_id_s)
    uid = query.from_user.id

    game = games.get(chat_id)
    if not game or game["phase"] != "confirm":
        await query.answer("Confirmation closed.", show_alert=True)
        return

    player = game["players"].get(uid)
    if not player or not player["alive"]:
        await query.answer("Only alive players can vote.", show_alert=True)
        return

    if uid == game["confirm_target"]:
        await query.answer("You cannot vote on yourself.", show_alert=True)
        return

    game["confirm_votes"][uid] = choice
    await query.answer("👍 Recorded!" if choice == "up" else "👎 Recorded!")


# ==========================================
# END GAME: CLEAR WINNERS / LOSERS & DM COIN REWARDS
# ==========================================
async def announce_winner(context: ContextTypes.DEFAULT_TYPE, game: dict, winner: str, jester_winner: Optional[dict] = None):
    lang = game["lang"]
    chat_id = game["chat_id"]
    game["phase"] = "ended"
    await set_group_mute(context, chat_id, False)

    winners: List[dict] = []
    losers: List[dict] = []

    for p in game["players"].values():
        r = p["role"]
        team = ROLES[r]["team"]
        is_win = False

        if winner == "jester" and jester_winner and p["id"] == jester_winner["id"]:
            is_win = True
        elif winner == "town" and team == "town":
            is_win = True
        elif winner == "killer" and team == "killer":
            is_win = True
        elif winner == "psychopath" and r == "psychopath":
            is_win = True

        if is_win:
            winners.append(p)
        else:
            losers.append(p)

    # Award Coins & Update Stats + Send Direct DM Receipt to Every Player!
    BASE_WIN_COIN = 100
    BASE_LOSE_COIN = 20

    winner_lines = []
    for wp in winners:
        prof = get_user_profile(wp["id"], wp["name"])
        prof["games"] += 1
        prof["wins"] += 1
        reward = BASE_WIN_COIN
        boost_note = ""
        if prof["items"].get("double_coin", 0) > 0:
            prof["items"]["double_coin"] -= 1
            reward *= 2
            boost_note = " (💰 2x Boost!)"
        prof["coins"] += reward

        status_icon = "✅ အသက်ရှင်" if wp["alive"] else "💀 သေဆုံး"
        winner_lines.append(
            f"🥇 {mention_html(wp['id'], wp['name'])} — {ROLES[wp['role']][lang]} ({status_icon}) <b>[+{reward} Coins]</b>"
        )

        try:
            await context.bot.send_message(
                chat_id=wp["id"],
                text=t(
                    lang,
                    f"🎉 <b>ဂုဏ်ယူပါတယ်! သင် ({game['chat_title']}) ပွဲစဉ်တွင် အနိုင်ရရှိပါသည်!</b>\n\n"
                    f"🎭 <b>သင်၏ Role:</b> {ROLES[wp['role']][lang]}\n"
                    f"💰 <b>ရရှိသော ဆုကြေး:</b> <code>+{reward} Coins</code>{boost_note}\n"
                    f"🏦 <b>လက်ကျန် Coin စုစုပေါင်း:</b> <code>{prof['coins']} Coins</code>\n\n"
                    f"🛒 <code>/shop</code> ရိုက်ပြီး Coin များဖြင့် အထူးပစ္စည်းများ ဝယ်ယူနိုင်ပါပြီ!",
                    f"🎉 <b>Congratulations! You WON in {game['chat_title']}!</b>\n\n"
                    f"🎭 <b>Your Role:</b> {ROLES[wp['role']][lang]}\n"
                    f"💰 <b>Reward Earned:</b> <code>+{reward} Coins</code>{boost_note}\n"
                    f"🏦 <b>Total Balance:</b> <code>{prof['coins']} Coins</code>\n\n"
                    f"🛒 Type <code>/shop</code> to spend your coins!",
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Failed to send win coin DM to {wp['id']}: {e}")

    loser_lines = []
    for lp in losers:
        prof = get_user_profile(lp["id"], lp["name"])
        prof["games"] += 1
        prof["coins"] += BASE_LOSE_COIN

        status_icon = "✅ အသက်ရှင်" if lp["alive"] else "💀 သေဆုံး"
        loser_lines.append(
            f"▪️ {mention_html(lp['id'], lp['name'])} — {ROLES[lp['role']][lang]} ({status_icon}) <b>[+{BASE_LOSE_COIN} Coins]</b>"
        )

        try:
            await context.bot.send_message(
                chat_id=lp["id"],
                text=t(
                    lang,
                    f"💔 <b>({game['chat_title']}) ပွဲစဉ် ပြီးဆုံးသွားပါပြီ (ရှုံးနိမ့်ပါသည်)</b>\n\n"
                    f"🎭 <b>သင်၏ Role:</b> {ROLES[lp['role']][lang]}\n"
                    f"💰 <b>ပါဝင်မှု နှစ်သိမ့်ဆု:</b> <code>+{BASE_LOSE_COIN} Coins</code>\n"
                    f"🏦 <b>လက်ကျန် Coin စုစုပေါင်း:</b> <code>{prof['coins']} Coins</code>",
                    f"💔 <b>Match Ended in {game['chat_title']} (Defeat)</b>\n\n"
                    f"🎭 <b>Your Role:</b> {ROLES[lp['role']][lang]}\n"
                    f"💰 <b>Participation Reward:</b> <code>+{BASE_LOSE_COIN} Coins</code>\n"
                    f"🏦 <b>Total Balance:</b> <code>{prof['coins']} Coins</code>",
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

    save_user_db()

    if winner == "jester" and jester_winner:
        banner = t(
            lang,
            f"🎭 <b>အရူး ({mention_html(jester_winner['id'], jester_winner['name'])}) က မြို့သူမြို့သားများကို လှည့်စားပြီး အနိုင်ရသွားပါပြီ!</b>",
            f"🎭 <b>Jester ({mention_html(jester_winner['id'], jester_winner['name'])}) tricked the town and WON!</b>",
        )
    else:
        banners = {
            "town": t(lang, "🏆 <b>မြို့သူမြို့သားများနှင့် တရားဥပဒေအဖွဲ့ အနိုင်ရရှိပါပြီ!</b>", "🏆 <b>Town & Law Enforcement WIN!</b>"),
            "killer": t(lang, "🏆 <b>လူသတ်ဂိုဏ်း (Killer Syndicate) အနိုင်ရရှိပါပြီ!</b>", "🏆 <b>Killer Syndicate WINS!</b>"),
            "psychopath": t(lang, "🏆 <b>စိတ္တဇလူသတ်သမား (Psychopath) တစ်ကိုယ်တော် အနိုင်ရရှိပါပြီ!</b>", "🏆 <b>Psychopath WINS Solo!</b>"),
        }
        banner = banners[winner]

    winners_block = "\n".join(winner_lines) if winner_lines else "• None"
    losers_block = "\n".join(loser_lines) if loser_lines else "• None"

    final_msg = (
        f"{banner}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>WINNERS (အနိုင်ရရှိသူများ):</b>\n{winners_block}\n\n"
        f"💀 <b>LOSERS (ရှုံးနိမ့်သူများ):</b>\n{losers_block}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 ဆုကြေး Coin များကို Bot DM ထဲသို့ ပေးပို့ပြီးပါပြီ! (<code>/shop</code> ဖြင့် ပစ္စည်းဝယ်နိုင်သည်)\n"
        f"🔄 နောက်တစ်ပွဲဆော့ရန် <code>/open</code> ရိုက်ပါ။"
    )

    await context.bot.send_message(chat_id=chat_id, text=final_msg, parse_mode="HTML")


async def enforce_group_silence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup") or not update.message:
        return
    chat_id = chat.id
    game = games.get(chat_id)
    if not game or game["phase"] in ("idle", "lobby", "ended"):
        return

    uid = update.effective_user.id
    player = game["players"].get(uid)
    if game["phase"] == "night" or (player and not player["alive"]):
        try:
            await update.message.delete()
        except Exception:
            pass


# ==========================================
# POST-INIT COMMAND MENU & ENTRYPOINT
# ==========================================
async def post_init_commands(app: Application):
    commands = [
        BotCommand("open", "ဂိမ်းဝိုင်းအသစ် ဖွင့်လှစ်ရန် (Group)"),
        BotCommand("start", "ဂိမ်းစတင်ရန် / Bot စတင်ရန်"),
        BotCommand("shop", "Coin များဖြင့် အထူးပစ္စည်းများ ဝယ်ယူရန်"),
        BotCommand("profile", "မိမိ Coin နှင့် ပစ္စည်းစာရင်း ကြည့်ရန်"),
        BotCommand("lang", "ဘာသာစကား ပြောင်းလဲရန် (MM / EN)"),
    ]
    await app.bot.set_my_commands(commands)


def main():
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("⚠️ Please set BOT_TOKEN environment variable or edit BOT_TOKEN in luthat_bot.py")

    # Start Render Keep-Alive HTTP Server (Port 8080 / Render PORT)
    threading.Thread(target=start_health_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init_commands).build()

    app.add_handler(CommandHandler("open", cmd_open))
    app.add_handler(CommandHandler("start", cmd_start_game))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("lang", cmd_lang))

    app.add_handler(CallbackQueryHandler(cb_join, pattern=r"^join:"))
    app.add_handler(CallbackQueryHandler(cb_buy_item, pattern=r"^buy:"))
    app.add_handler(CallbackQueryHandler(cb_detective_mode, pattern=r"^det_mode:"))
    app.add_handler(CallbackQueryHandler(cb_night_action, pattern=r"^nact:"))
    app.add_handler(CallbackQueryHandler(cb_dm_vote, pattern=r"^dmvote:"))
    app.add_handler(CallbackQueryHandler(cb_confirm_vote, pattern=r"^confirm:"))

    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_private_last_word))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, enforce_group_silence))

    print("🤖 LuThat Game Bot (Port 8080 + Winners/Losers + DM Coins & Shop) is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
