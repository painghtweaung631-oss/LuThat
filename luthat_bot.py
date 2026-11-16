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
    BotCommandScopeDefault,
    BotCommandScopeChat,
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
# CONFIGURATION & OWNER / TEST GROUP IDS
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
OWNER_ID = int(os.getenv("OWNER_ID", "8966139030"))
TEST_GROUP_ID = int(os.getenv("TEST_GROUP_ID", "-1004443610414"))
DATA_FILE = "luthat_users.json"
CONFIG_FILE = "luthat_config.json"

DEFAULT_NIGHT_GIF = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExaG5sY2E3enJqazl0d3R5eHFoZnl3ZnY2ejZ0NHF3ZzBqZnl0eSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7aD2saalBwwftBIY/giphy.gif"
DEFAULT_DAY_GIF = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExY2Z5NTh5Mmp5bnM5c2J3eGN5eTlyNG52a2x2ZG84em11eXJ5aCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/xT9IgzoKnwFNmISR8I/giphy.gif"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# ==========================================
# RENDER KEEP-ALIVE HTTP SERVER (PORT 8080)
# ==========================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"LuThat Game Bot is alive on Render!")

    def log_message(self, format, *args):
        return


def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"🌐 Keep-Alive HTTP Server listening on port {port}")
    server.serve_forever()


# ==========================================
# PERSISTENT STORAGE (USERS, ECONOMY, CONFIG)
# ==========================================
def load_json(path: str, default: dict) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {path}: {e}")
    return default


def save_json(path: str, data: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving {path}: {e}")


user_db: Dict[str, dict] = load_json(DATA_FILE, {})
bot_config: dict = load_json(
    CONFIG_FILE,
    {
        "night_gif": DEFAULT_NIGHT_GIF,
        "day_gif": DEFAULT_DAY_GIF,
        "banned_users": [],
    },
)


def save_all():
    save_json(DATA_FILE, user_db)
    save_json(CONFIG_FILE, bot_config)


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def is_banned(user_id: int) -> bool:
    if is_owner(user_id):
        return False
    return user_id in bot_config.get("banned_users", [])


def get_user_profile(user_id: int, name: str = "Player", username: str = "") -> dict:
    uid_s = str(user_id)
    if uid_s not in user_db:
        user_db[uid_s] = {
            "id": user_id,
            "name": name,
            "username": username.lower() if username else "",
            "coins": 100,
            "crystals": 0,
            "shields": 0,
            "chosen_role": None,
            "wins": 0,
            "games": 0,
        }
    else:
        if name:
            user_db[uid_s]["name"] = name
        if username:
            user_db[uid_s]["username"] = username.lower()
        for k, v in [("crystals", 0), ("shields", 0), ("chosen_role", None), ("wins", 0), ("games", 0)]:
            if k not in user_db[uid_s]:
                user_db[uid_s][k] = v
    if is_owner(user_id):
        user_db[uid_s]["coins"] = 999999999
    return user_db[uid_s]


def find_user_by_username(username: str) -> Optional[dict]:
    clean = username.lstrip("@").lower()
    for prof in user_db.values():
        if prof.get("username") == clean:
            return prof
    return None


# ==========================================
# LUTHAT GAME ROLES (11 ROLES - FULL MM & EN)
# ==========================================
ROLES = {
    "gang_boss": {
        "mm": "🤵🏻 လူသတ်ခေါင်းဆောင် ဂိုဏ်းချုပ်",
        "en": "🤵🏻 Gang Boss",
        "team": "killer",
        "active_night": True,
        "desc_mm": "လူသတ်ဂိုဏ်း၏ အဓိကခေါင်းဆောင်ဖြစ်သည်။ ညဘက်တွင် သတ်မည့်သူကို အတည်ပြုဆုံးဖြတ်ခွင့်ရှိပြီး စုံထောက်စစ်ဆေးလျှင်လည်း လူကောင်းဟုသာ ပေါ်မည်။",
        "desc_en": "Leader of the Killer Syndicate. Decides the night kill target and appears innocent to Detective investigations.",
    },
    "gang_member": {
        "mm": "🤵🏼 အဖွဲ့ဝင်",
        "en": "🤵🏼 Syndicate Member",
        "team": "killer",
        "active_night": True,
        "desc_mm": "ဂိုဏ်းချုပ်နှင့်အတူ ညဘက်တွင် ပစ်မှတ်ကို အကြံပြုရွေးချယ်ပြီး လုပ်ကြံရမည့် အဖွဲ့ဝင်ဖြစ်သည်။",
        "desc_en": "Assists the Gang Boss at night in suggesting and eliminating targets.",
    },
    "spy": {
        "mm": "🕵️‍♂️ သူလျှို",
        "en": "🕵️‍♂️ Syndicate Spy",
        "team": "killer",
        "active_night": True,
        "desc_mm": "လူသတ်ဂိုဏ်းဘက်မှ သူလျှိုဖြစ်သည်။ ညဘက်တွင် ကစားသမားတစ်ဦး၏ Role အစစ်ကို ထောက်လှမ်းသိရှိနိုင်သည်။",
        "desc_en": "Killer faction spy. Investigates a player each night to uncover their exact role.",
    },
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
        "desc_en": "Partners with the Detective. Automatically promoted to Detective if the Detective dies.",
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
        "mm": "🎭 အရူး",
        "en": "🎭 Jester",
        "team": "neutral",
        "active_night": False,
        "desc_mm": "နေ့ဘက် မဲပေးချိန်တွင် မြို့သူမြို့သားများ အထင်လွဲပြီး မိမိကို ကြိုးပေးစီရင်မိအောင် လှည့်စားနိုင်ပါက တစ်ကိုယ်တော် အနိုင်ရမည်။",
        "desc_en": "Tricks the town into lynching them during the day vote to win solo.",
    },
}

# ==========================================
# IN-MEMORY GAME STATE & MESSAGE TRACKER
# ==========================================
games: Dict[int, dict] = {}
user_active_game: Dict[int, int] = {}
chat_lang_pref: Dict[int, str] = {}


def get_lang(chat_id: int) -> str:
    if chat_id in games:
        return games[chat_id].get("lang", "mm")
    return chat_lang_pref.get(chat_id, "mm")


def t(lang: str, mm_text: str, en_text: str) -> str:
    return mm_text if lang == "mm" else en_text


def mention_html(user_id: int, name: str) -> str:
    safe_name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'


def track_msg(game: dict, message_id: int):
    if game and "msg_ids" in game:
        game["msg_ids"].append(message_id)


async def send_tracked(context: ContextTypes.DEFAULT_TYPE, game: Optional[dict], chat_id: int, text: str, **kwargs):
    msg = await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
    if game:
        track_msg(game, msg.message_id)
    return msg


async def is_group_admin_or_owner(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    if is_owner(user_id):
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


def assign_roles(player_ids: List[int]) -> Dict[int, str]:
    n = len(player_ids)
    base_order = [
        "gang_boss",
        "detective",
        "doctor",
        "citizen",
        "psychopath",
        "police",
        "gang_member",
        "deputy",
        "drunkard",
        "spy",
        "jester",
    ]
    pool = base_order[:n]
    while len(pool) < n:
        pool.append("gang_member" if len(pool) % 4 == 0 else "citizen")

    assigned: Dict[int, str] = {}
    remaining_users = player_ids[:]
    random.shuffle(remaining_users)

    # Apply purchased Crystal Role Selection first!
    for uid in list(remaining_users):
        prof = get_user_profile(uid)
        chosen = prof.get("chosen_role")
        if chosen and chosen in ROLES:
            assigned[uid] = chosen
            prof["chosen_role"] = None
            remaining_users.remove(uid)
            if chosen in pool:
                pool.remove(chosen)
            elif pool:
                pool.pop()

    save_all()
    random.shuffle(pool)
    for i, uid in enumerate(remaining_users):
        assigned[uid] = pool[i]

    return assigned


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
# LANGUAGE COMMAND (/lang - STRICT FULL MM / FULL EN)
# ==========================================
async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cur = get_lang(chat_id)
    new_lang = "en" if cur == "mm" else "mm"
    chat_lang_pref[chat_id] = new_lang
    if chat_id in games:
        games[chat_id]["lang"] = new_lang

    await update.message.reply_text(
        t(
            new_lang,
            "🌐 ဘာသာစကားကို <b>မြန်မာဘာသာ</b> သို့ အပြည့်အဝ ပြောင်းလဲလိုက်ပါပြီ။",
            "🌐 Language has been switched completely to <b>English</b>.",
        ),
        parse_mode="HTML",
    )


# ==========================================
# ECONOMY, SHOP, BILL, GIFT, KISS, GTOP, ROLE
# ==========================================
async def cmd_bill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = get_lang(chat_id)
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.effective_user
    prof = get_user_profile(target.id, target.full_name, target.username or "")
    save_all()

    coin_display = "♾️" if is_owner(target.id) else f"{prof['coins']} Coins"
    crystal_display = "♾️" if is_owner(target.id) else f"{prof['crystals']} 💎"
    shield_display = "♾️" if is_owner(target.id) else f"{prof['shields']} 🛡️"
    chosen_text = (
        ROLES[prof["chosen_role"]][lang]
        if prof.get("chosen_role") in ROLES
        else t(lang, "မရှိသေးပါ", "None")
    )

    msg = t(
        lang,
        f"💳 <b>လက်ကျန်ငွေနှင့် ပစ္စည်းစာရင်း ({mention_html(target.id, target.full_name)})</b>\n\n"
        f"💰 <b>Coin လက်ကျန်:</b> <code>{coin_display}</code>\n"
        f"💎 <b>ခရစ်စတယ် (Crystal):</b> <code>{crystal_display}</code>\n"
        f"🛡️ <b>အကာအကွယ်ဒိုင်း (Shield):</b> <code>{shield_display}</code>\n"
        f"🎭 <b>ရွေးချယ်ထားသော Role:</b> {chosen_text}\n"
        f"🏆 <b>နိုင်ပွဲစုစုပေါင်း:</b> {prof['wins']} ပွဲ",
        f"💳 <b>Account Balance ({mention_html(target.id, target.full_name)})</b>\n\n"
        f"💰 <b>Coins:</b> <code>{coin_display}</code>\n"
        f"💎 <b>Crystals:</b> <code>{crystal_display}</code>\n"
        f"🛡️ <b>Shields:</b> <code>{shield_display}</code>\n"
        f"🎭 <b>Selected Next Role:</b> {chosen_text}\n"
        f"🏆 <b>Total Wins:</b> {prof['wins']}",
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_gift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = get_lang(chat_id)
    sender = update.effective_user

    if is_banned(sender.id):
        await update.message.reply_text(t(lang, "🚫 သင်သည် ဂိမ်းကစားခွင့် ပိတ်ပင်ခံထားရပါသည်။", "🚫 You are banned from using this bot."))
        return

    if not update.message.reply_to_message:
        await update.message.reply_text(
            t(
                lang,
                "⚠️ Coin လွှဲပေးလိုသူ၏ စာကို Reply (ထောက်) ပြီး <code>/gift 500</code> ဟု ရိုက်ပါ။",
                "⚠️ Reply to a user's message and type <code>/gift 500</code>.",
            ),
            parse_mode="HTML",
        )
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            t(lang, "⚠️ လွှဲပေးမည့် Coin ပမာဏ ဂဏန်းထည့်ပါ (ဥပမာ: <code>/gift 200</code>)", "⚠️ Specify a valid coin amount (e.g. <code>/gift 200</code>)"),
            parse_mode="HTML",
        )
        return

    amount = int(context.args[0])
    if amount <= 0:
        await update.message.reply_text(t(lang, "⚠️ 0 ထက်ကြီးသော ပမာဏ ထည့်ပါ။", "⚠️ Amount must be greater than 0."))
        return

    receiver = update.message.reply_to_message.from_user
    if receiver.id == sender.id or receiver.is_bot:
        await update.message.reply_text(t(lang, "⚠️ မိမိကိုယ်တိုင် သို့မဟုတ် Bot ထံ လွှဲပေး၍မရပါ။", "⚠️ Cannot gift coins to yourself or a bot."))
        return

    s_prof = get_user_profile(sender.id, sender.full_name, sender.username or "")
    r_prof = get_user_profile(receiver.id, receiver.full_name, receiver.username or "")

    if not is_owner(sender.id):
        if s_prof["coins"] < amount:
            await update.message.reply_text(
                t(
                    lang,
                    f"❌ Coin မလုံလောက်ပါ! သင့်လက်ကျန်: <code>{s_prof['coins']} Coins</code>",
                    f"❌ Insufficient coins! Your balance: <code>{s_prof['coins']} Coins</code>",
                ),
                parse_mode="HTML",
            )
            return
        s_prof["coins"] -= amount

    if not is_owner(receiver.id):
        r_prof["coins"] += amount
    save_all()

    await update.message.reply_text(
        t(
            lang,
            f"🎁 {mention_html(sender.id, sender.full_name)} က {mention_html(receiver.id, receiver.full_name)} ထံသို့ <b>{amount} Coins</b> လက်ဆောင်ပေးလိုက်ပါပြီ!",
            f"🎁 {mention_html(sender.id, sender.full_name)} gifted <b>{amount} Coins</b> to {mention_html(receiver.id, receiver.full_name)}!",
        ),
        parse_mode="HTML",
    )


async def cmd_kiss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = get_lang(chat_id)
    sender = update.effective_user
    if not update.message.reply_to_message:
        await update.message.reply_text(
            t(lang, "💋 အနမ်းပေးလိုသူ၏ စာကို Reply ထောက်ပြီး <code>/kiss</code> ရိုက်ပါ။", "💋 Reply to someone's message with <code>/kiss</code>."),
            parse_mode="HTML",
        )
        return
    target = update.message.reply_to_message.from_user
    await update.message.reply_text(
        t(
            lang,
            f"💋 {mention_html(sender.id, sender.full_name)} က {mention_html(target.id, target.full_name)} ကို ချိုမြိန်သော အနမ်းတစ်ပွင့် ပေးလိုက်ပါသည်! 😘",
            f"💋 {mention_html(sender.id, sender.full_name)} gave {mention_html(target.id, target.full_name)} a sweet kiss! 😘",
        ),
        parse_mode="HTML",
    )


async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = get_lang(chat_id)
    user = update.effective_user
    prof = get_user_profile(user.id, user.full_name, user.username or "")
    save_all()

    bal_str = "♾️" if is_owner(user.id) else f"{prof['coins']} Coins"
    cry_str = "♾️" if is_owner(user.id) else f"{prof['crystals']} 💎"

    text = t(
        lang,
        f"🛒 <b>LuThat Game ဆိုင်ခန်း (Shop)</b>\n"
        f"💰 <b>လက်ကျန် Coin:</b> <code>{bal_str}</code>  |  💎 <b>ခရစ်စတယ်:</b> <code>{cry_str}</code>\n"
        f"━━━━━━━━━━━━━━\n"
        f"1️⃣ <b>🛡️ အကာအကွယ်ဒိုင်း (Shield)</b> — <code>1000 Coins</code>\n"
        f"<i>ညဘက် လာသတ်ခံရပါက အသက် ၁ ကြိမ် အလိုအလျောက် ကယ်တင်ပေးမည်။</i>\n\n"
        f"2️⃣ <b>💎 ခရစ်စတယ် ၁ ပွင့် (1 Crystal)</b> — <code>5000 Coins</code>\n"
        f"<i>ခရစ်စတယ် ၁ ပွင့်ဖြင့် နောက်ပွဲအတွက် ကြိုက်ရာ Role တစ်ခု ဝယ်ယူနိုင်မည်။</i>\n\n"
        f"3️⃣ <b>🎭 ကြိုက်ရာ Role ရွေးချယ်ဝယ်ယူရန်</b> — <code>1 Crystal 💎</code>",
        f"🛒 <b>LuThat Game Shop</b>\n"
        f"💰 <b>Coins:</b> <code>{bal_str}</code>  |  💎 <b>Crystals:</b> <code>{cry_str}</code>\n"
        f"━━━━━━━━━━━━━━\n"
        f"1️⃣ <b>🛡️ Night Shield</b> — <code>1000 Coins</code>\n"
        f"<i>Automatically blocks 1 night attack against you.</i>\n\n"
        f"2️⃣ <b>💎 1 Crystal</b> — <code>5000 Coins</code>\n"
        f"<i>Exchange 1 Crystal to pick any role you want for the next game.</i>\n\n"
        f"3️⃣ <b>🎭 Pick Any Role</b> — <code>1 Crystal 💎</code>",
    )

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t(lang, "🛡️ အကာအကွယ်ဒိုင်း ဝယ်မည် (1000 Coins)", "🛡️ Buy Shield (1000 Coins)"), callback_data=f"shop:{user.id}:shield")],
            [InlineKeyboardButton(t(lang, "💎 ခရစ်စတယ် ၁ ပွင့် ဝယ်မည် (5000 Coins)", "💎 Buy 1 Crystal (5000 Coins)"), callback_data=f"shop:{user.id}:crystal")],
            [InlineKeyboardButton(t(lang, "🎭 ခရစ်စတယ် ၁ ပွင့်ဖြင့် Role ရွေးဝယ်မည်", "🎭 Use 1 Crystal to Pick Role"), callback_data=f"shop:{user.id}:pickrole")],
        ]
    )
    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def cb_shop_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, owner_s, action = query.data.split(":")
    owner_id = int(owner_s)
    uid = query.from_user.id
    chat_id = update.effective_chat.id
    lang = get_lang(chat_id)

    if uid != owner_id:
        await query.answer(t(lang, "⚠️ သင်ကိုယ်တိုင် /shop ရိုက်ပြီး ဝယ်ယူပါ!", "⚠️ Type /shop yourself to purchase!"), show_alert=True)
        return

    prof = get_user_profile(uid, query.from_user.full_name, query.from_user.username or "")

    if action == "shield":
        if not is_owner(uid) and prof["coins"] < 1000:
            await query.answer(t(lang, "❌ Coin 1000 မပြည့်သေးပါ!", "❌ Need 1000 Coins!"), show_alert=True)
            return
        if not is_owner(uid):
            prof["coins"] -= 1000
        prof["shields"] += 1
        save_all()
        await query.answer(
            t(lang, f"✅ အကာအကွယ်ဒိုင်း ၁ ခု ဝယ်ယူပြီးပါပြီ! (စုစုပေါင်း: {prof['shields']} ခု)", f"✅ Purchased 1 Shield! (Total: {prof['shields']})"),
            show_alert=True,
        )

    elif action == "crystal":
        if not is_owner(uid) and prof["coins"] < 5000:
            await query.answer(t(lang, "❌ Coin 5000 မပြည့်သေးပါ!", "❌ Need 5000 Coins!"), show_alert=True)
            return
        if not is_owner(uid):
            prof["coins"] -= 5000
        prof["crystals"] += 1
        save_all()
        await query.answer(
            t(lang, f"💎 ခရစ်စတယ် ၁ ပွင့် ရရှိပါပြီ! (စုစုပေါင်း: {prof['crystals']} ပွင့်)", f"💎 Purchased 1 Crystal! (Total: {prof['crystals']})"),
            show_alert=True,
        )

    elif action == "pickrole":
        if not is_owner(uid) and prof["crystals"] < 1:
            await query.answer(t(lang, "❌ ခရစ်စတယ် ၁ ပွင့် မရှိသေးပါ! (5000 Coins ဖြင့် အရင်ဝယ်ပါ)", "❌ You need 1 Crystal first! (Buy for 5000 Coins)"), show_alert=True)
            return

        btns = []
        row = []
        for r_key, r_info in ROLES.items():
            row.append(InlineKeyboardButton(r_info[lang], callback_data=f"buyrole:{uid}:{r_key}"))
            if len(row) == 2:
                btns.append(row)
                row = []
        if row:
            btns.append(row)

        await query.edit_message_text(
            t(
                lang,
                "💎 <b>ခရစ်စတယ် ၁ ပွင့်ဖြင့် နောက်ပွဲတွင် ကစားလိုသော Role ကို ရွေးချယ်ပါ:</b>",
                "💎 <b>Choose any Role for your next game (1 Crystal):</b>",
            ),
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode="HTML",
        )


async def cb_buy_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, owner_s, r_key = query.data.split(":")
    owner_id = int(owner_s)
    uid = query.from_user.id
    lang = get_lang(update.effective_chat.id)

    if uid != owner_id:
        await query.answer(t(lang, "⚠️ သင့် Menu မဟုတ်ပါ!", "⚠️ Not your menu!"), show_alert=True)
        return

    prof = get_user_profile(uid)
    if not is_owner(uid) and prof["crystals"] < 1:
        await query.answer(t(lang, "❌ ခရစ်စတယ် မလုံလောက်ပါ!", "❌ Not enough Crystals!"), show_alert=True)
        return

    if not is_owner(uid):
        prof["crystals"] -= 1
    prof["chosen_role"] = r_key
    save_all()

    await query.edit_message_text(
        t(
            lang,
            f"✅ <b>ဝယ်ယူမှု အောင်မြင်ပါသည်!</b>\nနောက်တစ်ပွဲ စတင်သည့်အခါ သင်သည် <b>{ROLES[r_key][lang]}</b> Role ကို ရရှိပါမည်။",
            f"✅ <b>Role Purchased!</b>\nYou will receive <b>{ROLES[r_key][lang]}</b> when the next game starts.",
        ),
        parse_mode="HTML",
    )


async def cmd_role_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_chat.id)
    lines = [
        t(
            lang,
            "📖 <b>LuThat Game တွင် ပါဝင်သော Role များနှင့် စွမ်းရည်များ</b>\n",
            "📖 <b>All LuThat Game Roles & Abilities</b>\n",
        )
    ]
    for r_info in ROLES.values():
        lines.append(f"• <b>{r_info[lang]}</b> — {r_info[f'desc_{lang}']}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_gtop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(update.effective_chat.id)
    ranked = sorted(user_db.values(), key=lambda x: (x.get("wins", 0), x.get("coins", 0)), reverse=True)[:10]
    if not ranked:
        await update.message.reply_text(t(lang, "📊 မှတ်တမ်း မရှိသေးပါ။", "📊 No leaderboard records yet."))
        return

    lines = [t(lang, "🏆 <b>နိုင်ပွဲအများဆုံး ထိပ်တန်းကစားသမားများ (Top 10)</b>\n", "🏆 <b>Top Winners Leaderboard (Top 10)</b>\n")]
    medals = ["🥇", "🥈", "🥉"]
    for idx, p in enumerate(ranked):
        icon = medals[idx] if idx < 3 else f"<b>{idx+1}.</b>"
        c_str = "♾️" if is_owner(p["id"]) else f"{p.get('coins', 0)} Coins"
        lines.append(
            t(
                lang,
                f"{icon} {mention_html(p['id'], p.get('name', 'Player'))} — <b>{p.get('wins', 0)} နိုင်</b> ({c_str})",
                f"{icon} {mention_html(p['id'], p.get('name', 'Player'))} — <b>{p.get('wins', 0)} Wins</b> ({c_str})",
            )
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_extend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = get_lang(chat_id)
    game = games.get(chat_id)
    if not game or game["phase"] not in ("lobby", "night", "day", "vote", "confirm"):
        await update.message.reply_text(t(lang, "⚠️ လက်ရှိ အချိန်တိုးစရာ ဂိမ်းမရှိပါ။", "⚠️ No active game phase to extend."))
        return

    game["extra_seconds"] = game.get("extra_seconds", 0) + 60
    msg = await update.message.reply_text(
        t(
            lang,
            "⏳ <b>အချိန် ၁ မိနစ် (60 စက္ကန့်) ထပ်မံတိုးမြှင့်လိုက်ပါပြီ!</b>",
            "⏳ <b>Extended current phase timer by 1 minute (60 seconds)!</b>",
        ),
        parse_mode="HTML",
    )
    track_msg(game, msg.message_id)


# ==========================================
# ADMINS & OWNER COMMANDS (/cancel, /stop, /delegmsg)
# ==========================================
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = get_lang(chat_id)
    if not await is_group_admin_or_owner(context, chat_id, update.effective_user.id):
        await update.message.reply_text(t(lang, "🚫 Admin သို့မဟုတ် Bot Owner သာ သုံးနိုင်ပါသည်။", "🚫 Admins or Bot Owner only."))
        return

    game = games.get(chat_id)
    if not game or game["phase"] != "lobby":
        await update.message.reply_text(t(lang, "⚠️ ဖျက်သိမ်းရန် ဖွင့်ထားသော Lobby မရှိပါ။", "⚠️ No open registration lobby to cancel."))
        return

    game["phase"] = "ended"
    await update.message.reply_text(
        t(lang, "❌ <b>ဂိမ်းဝိုင်း စာရင်းသွင်းခြင်းကို ပြန်လည်ဖျက်သိမ်းလိုက်ပါပြီ။</b>", "❌ <b>Game registration has been cancelled.</b>"),
        parse_mode="HTML",
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = get_lang(chat_id)
    if not await is_group_admin_or_owner(context, chat_id, update.effective_user.id):
        await update.message.reply_text(t(lang, "🚫 Admin သို့မဟုတ် Bot Owner သာ သုံးနိုင်ပါသည်။", "🚫 Admins or Bot Owner only."))
        return

    game = games.get(chat_id)
    if not game or game["phase"] in ("idle", "ended"):
        await update.message.reply_text(t(lang, "⚠️ လက်ရှိ ကစားနေသော ဂိမ်းမရှိပါ။", "⚠️ No active game running right now."))
        return

    game["phase"] = "ended"
    if game.get("task"):
        game["task"].cancel()
    await set_group_mute(context, chat_id, False)
    await update.message.reply_text(
        t(lang, "🛑 <b>လက်ရှိ ကစားနေသော ဂိမ်းကို ချက်ချင်း ရပ်တန့်ဖျက်သိမ်းလိုက်ပါပြီ။</b>", "🛑 <b>The ongoing game has been forcefully stopped.</b>"),
        parse_mode="HTML",
    )


async def cmd_delegmsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = get_lang(chat_id)
    if not await is_group_admin_or_owner(context, chat_id, update.effective_user.id):
        await update.message.reply_text(t(lang, "🚫 Admin သို့မဟုတ် Bot Owner သာ သုံးနိုင်ပါသည်။", "🚫 Admins or Bot Owner only."))
        return

    game = games.get(chat_id)
    if not game or not game.get("msg_ids"):
        await update.message.reply_text(t(lang, "⚠️ ဖျက်ရန် ဂိမ်းစာတို မှတ်တမ်းမရှိပါ။", "⚠️ No tracked game messages to delete."))
        return

    ids = list(set(game["msg_ids"] + [update.message.message_id]))
    game["msg_ids"] = []
    deleted = 0
    for mid in ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
            deleted += 1
        except Exception:
            pass

    notice = await context.bot.send_message(
        chat_id=chat_id,
        text=t(
            lang,
            f"🧹 ဂိမ်းကစားထားသော စာတို စုစုပေါင်း <b>{deleted}</b> ခုကို ရှင်းလင်းဖျက်သိမ်းပြီးပါပြီ။",
            f"🧹 Cleaned up <b>{deleted}</b> game messages.",
        ),
        parse_mode="HTML",
    )
    await asyncio.sleep(5)
    try:
        await notice.delete()
    except Exception:
        pass


# ==========================================
# OWNER-ONLY SPECIAL COMMANDS
# ==========================================
async def cmd_hack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    chat_id = update.effective_chat.id
    lang = get_lang(chat_id)
    game = games.get(chat_id)

    try:
        await update.message.delete()
    except Exception:
        pass

    if not game or game["phase"] in ("idle", "lobby", "ended"):
        await context.bot.send_message(
            chat_id=TEST_GROUP_ID,
            text="⚠️ Hack failed: No active game in progress in that group.",
        )
        return

    lines = [
        f"🔓 <b>[HACK INTEL] {game['chat_title']} (Day/Night {game['day_num']})</b>\n"
    ]
    for p in game["players"].values():
        status = "✅ Alive" if p["alive"] else "💀 Dead"
        lines.append(f"• {mention_html(p['id'], p['name'])} (<code>{p['id']}</code>) → <b>{ROLES[p['role']][lang]}</b> [{status}]")

    await context.bot.send_message(
        chat_id=TEST_GROUP_ID,
        text="\n".join(lines),
        parse_mode="HTML",
    )


async def cmd_kick_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    chat_id = update.effective_chat.id
    lang = get_lang(chat_id)
    game = games.get(chat_id)

    if not game or game["phase"] in ("idle", "ended"):
        await update.message.reply_text("⚠️ No active game in this group.")
        return

    target_uid: Optional[int] = None
    if update.message.reply_to_message:
        target_uid = update.message.reply_to_message.from_user.id
    elif context.args:
        arg = context.args[0].lstrip("@").lower()
        for p in game["players"].values():
            prof = get_user_profile(p["id"], p["name"])
            if str(p["id"]) == arg or prof.get("username") == arg or arg in p["name"].lower():
                target_uid = p["id"]
                break

    if not target_uid or target_uid not in game["players"]:
        await update.message.reply_text("⚠️ Reply to the player or type <code>/kick @username</code>.", parse_mode="HTML")
        return

    tp = game["players"][target_uid]
    if game["phase"] == "lobby":
        del game["players"][target_uid]
        await update.message.reply_text(
            t(
                lang,
                f"👢 Bot Owner က {mention_html(tp['id'], tp['name'])} ကို ဂိမ်းဝိုင်းထဲမှ ထုတ်ပယ်လိုက်ပါသည်။",
                f"👢 Bot Owner kicked {mention_html(tp['id'], tp['name'])} from the lobby.",
            ),
            parse_mode="HTML",
        )
    else:
        tp["alive"] = False
        await update.message.reply_text(
            t(
                lang,
                f"⚡ Bot Owner က {mention_html(tp['id'], tp['name'])} ({ROLES[tp['role']][lang]}) ကို ဂိမ်းထဲမှ ချက်ချင်း ထုတ်ပယ်လိုက်ပါသည်။",
                f"⚡ Bot Owner eliminated {mention_html(tp['id'], tp['name'])} ({ROLES[tp['role']][lang]}) from the match.",
            ),
            parse_mode="HTML",
        )
        win = check_win_condition(game)
        if win:
            await announce_winner(context, game, win)


async def cmd_rmcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    lang = get_lang(update.effective_chat.id)
    if not update.message.reply_to_message or not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ Reply to a user and type <code>/rmcoin 500</code>.", parse_mode="HTML")
        return

    amount = int(context.args[0])
    target = update.message.reply_to_message.from_user
    prof = get_user_profile(target.id, target.full_name, target.username or "")
    prof["coins"] = max(0, prof["coins"] - amount)
    save_all()

    await update.message.reply_text(
        t(
            lang,
            f"💸 {mention_html(target.id, target.full_name)} ထံမှ <b>{amount} Coins</b> ပြန်လည်သိမ်းဆည်းလိုက်ပါပြီ။ (လက်ကျန်: <code>{prof['coins']} Coins</code>)",
            f"💸 Removed <b>{amount} Coins</b> from {mention_html(target.id, target.full_name)}. (Remaining: <code>{prof['coins']} Coins</code>)",
        ),
        parse_mode="HTML",
    )


async def cmd_gban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    lang = get_lang(update.effective_chat.id)
    target_id: Optional[int] = None
    target_name = "User"

    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        target_name = update.message.reply_to_message.from_user.full_name
    elif context.args:
        arg = context.args[0]
        if arg.isdigit():
            target_id = int(arg)
        else:
            p = find_user_by_username(arg)
            if p:
                target_id = p["id"]
                target_name = p["name"]

    if not target_id or is_owner(target_id):
        await update.message.reply_text("⚠️ Reply to a user or provide valid user ID / @username.")
        return

    if target_id not in bot_config["banned_users"]:
        bot_config["banned_users"].append(target_id)
        save_all()

    await update.message.reply_text(
        t(
            lang,
            f"🚫 {mention_html(target_id, target_name)} (<code>{target_id}</code>) ကို LuThat Game ကစားခွင့် ပိတ်ပင် (Global Ban) လိုက်ပါပြီ။",
            f"🚫 {mention_html(target_id, target_name)} (<code>{target_id}</code>) has been Globally Banned from LuThat Game.",
        ),
        parse_mode="HTML",
    )


async def cmd_ugban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    lang = get_lang(update.effective_chat.id)
    target_id: Optional[int] = None
    target_name = "User"

    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        target_name = update.message.reply_to_message.from_user.full_name
    elif context.args:
        arg = context.args[0]
        if arg.isdigit():
            target_id = int(arg)
        else:
            p = find_user_by_username(arg)
            if p:
                target_id = p["id"]
                target_name = p["name"]

    if not target_id:
        await update.message.reply_text("⚠️ Reply to a user or provide valid user ID / @username.")
        return

    if target_id in bot_config["banned_users"]:
        bot_config["banned_users"].remove(target_id)
        save_all()

    await update.message.reply_text(
        t(
            lang,
            f"✅ {mention_html(target_id, target_name)} (<code>{target_id}</code>) ၏ Ban ကို ပြန်လည်ဖြေလျှော့ပေးလိုက်ပါပြီ။",
            f"✅ {mention_html(target_id, target_name)} (<code>{target_id}</code>) has been Unbanned.",
        ),
        parse_mode="HTML",
    )


async def cmd_gifs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        return
    lang = get_lang(update.effective_chat.id)
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🌃 Change Night GIF", callback_data="gifcfg:set_night"),
                InlineKeyboardButton("🏙 Change Day GIF", callback_data="gifcfg:set_day"),
            ],
            [
                InlineKeyboardButton("🗑 Reset Night GIF", callback_data="gifcfg:del_night"),
                InlineKeyboardButton("🗑 Reset Day GIF", callback_data="gifcfg:del_day"),
            ],
        ]
    )
    await update.message.reply_text(
        t(
            lang,
            "🎬 <b>Day / Night GIF ပြင်ဆင်ရန် (Bot Owner Only)</b>\nအောက်ပါခလုတ်များမှ ရွေးချယ်ပြင်ဆင်နိုင်ပါသည်:",
            "🎬 <b>Day / Night GIF Manager (Bot Owner Only)</b>\nChoose an action below:",
        ),
        reply_markup=kb,
        parse_mode="HTML",
    )


async def cb_gif_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_owner(query.from_user.id):
        await query.answer("Owner only!", show_alert=True)
        return

    action = query.data.split(":")[1]
    if action == "del_night":
        bot_config["night_gif"] = ""
        save_all()
        await query.edit_message_text("🗑 Night GIF has been removed (Text-only mode for Night).")
    elif action == "del_day":
        bot_config["day_gif"] = ""
        save_all()
        await query.edit_message_text("🗑 Day GIF has been removed (Text-only mode for Day).")
    elif action == "set_night":
        context.user_data["awaiting_gif"] = "night_gif"
        await query.edit_message_text("🌃 Send the new <b>Night GIF / Animation</b> now (or send a direct GIF URL):", parse_mode="HTML")
    elif action == "set_day":
        context.user_data["awaiting_gif"] = "day_gif"
        await query.edit_message_text("🏙 Send the new <b>Day GIF / Animation</b> now (or send a direct GIF URL):", parse_mode="HTML")


# ==========================================
# LOBBY & GAME START HANDLERS
# ==========================================
async def cmd_start_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user = update.effective_user
    lang = get_lang(user.id)
    prof = get_user_profile(user.id, user.full_name, user.username or "")
    save_all()

    bal = "♾️" if is_owner(user.id) else f"{prof['coins']} Coins"
    await update.message.reply_text(
        t(
            lang,
            f"🎭 <b>LuThat Game Bot</b> မှ ကြိုဆိုပါတယ် {mention_html(user.id, user.full_name)}!\n\n"
            f"💰 <b>လက်ကျန် Coin:</b> <code>{bal}</code>  |  💎 <b>ခရစ်စတယ်:</b> <code>{prof['crystals']}</code>\n"
            f"• Group ထဲတွင် <code>/open</code> ရိုက်ပြီး ဂိမ်းဖွင့်ပါ။\n"
            f"• <code>/shop</code> ဖြင့် အကာအကွယ်ဒိုင်း (1000) နှင့် ခရစ်စတယ် (5000) ဝယ်ယူနိုင်ပါသည်။",
            f"🎭 Welcome to <b>LuThat Game Bot</b>, {mention_html(user.id, user.full_name)}!\n\n"
            f"💰 <b>Balance:</b> <code>{bal}</code>  |  💎 <b>Crystals:</b> <code>{prof['crystals']}</code>\n"
            f"• Type <code>/open</code> in a group to start a game lobby.\n"
            f"• Use <code>/shop</code> to buy Shields (1000) and Crystals (5000).",
        ),
        parse_mode="HTML",
    )


async def cmd_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("⚠️ Group Chat ထဲတွင်သာ /open အသုံးပြုနိုင်ပါသည်။")
        return

    user = update.effective_user
    chat_id = chat.id
    lang = get_lang(chat_id)

    if is_banned(user.id):
        await update.message.reply_text(t(lang, "🚫 သင်သည် ဂိမ်းကစားခွင့် ပိတ်ပင်ခံထားရပါသည်။", "🚫 You are globally banned from playing."))
        return

    if chat_id in games and games[chat_id].get("phase") not in ("idle", "ended"):
        await update.message.reply_text(
            t(lang, "⚠️ လက်ရှိ ဂိမ်းဝိုင်း ဖွင့်ထားပြီးသား ဖြစ်ပါသည်။", "⚠️ A game is already active in this group.")
        )
        return

    get_user_profile(user.id, user.full_name, user.username or "")
    save_all()

    games[chat_id] = {
        "chat_id": chat_id,
        "chat_title": chat.title or "LuThat Group",
        "lang": lang,
        "phase": "lobby",
        "day_num": 0,
        "extra_seconds": 0,
        "msg_ids": [update.message.message_id],
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
    msg = await update.message.reply_text(
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
    track_msg(games[chat_id], msg.message_id)


async def cb_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split(":")[1])
    user = query.from_user

    game = games.get(chat_id)
    if not game or game["phase"] != "lobby":
        await query.answer("Lobby is closed.", show_alert=True)
        return

    lang = game["lang"]
    if is_banned(user.id):
        await query.answer(t(lang, "🚫 သင်သည် ဂိမ်းကစားခွင့် ပိတ်ပင်ခံထားရပါသည်။", "🚫 You are banned from playing!"), show_alert=True)
        return

    if user.id in game["players"]:
        await query.answer(t(lang, "သင် စာရင်းသွင်းပြီးသား ဖြစ်ပါသည်။", "You already joined!"), show_alert=True)
        return

    prof = get_user_profile(user.id, user.full_name, user.username or "")
    save_all()

    try:
        bal_str = "♾️" if is_owner(user.id) else f"{prof['coins']} Coins"
        await context.bot.send_message(
            chat_id=user.id,
            text=t(
                lang,
                f"✅ <b>{game['chat_title']}</b> ဂိမ်းဝိုင်းထဲသို့ ဝင်ရောက်ပြီးပါပြီ!\n💰 လက်ကျန်: <code>{bal_str}</code>",
                f"✅ You joined the game in <b>{game['chat_title']}</b>!\n💰 Balance: <code>{bal_str}</code>",
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

    track_msg(game, update.message.message_id)
    lang = game["lang"]
    if len(game["players"]) < 3:
        msg = await update.message.reply_text(
            t(lang, "⚠️ အနည်းဆုံး ကစားသမား <b>၃ ဦး</b> ရှိမှ စတင်နိုင်ပါမည်။", "⚠️ Need at least <b>3 players</b> to start."),
            parse_mode="HTML",
        )
        track_msg(game, msg.message_id)
        return

    assigned = assign_roles(list(game["players"].keys()))
    for uid, role in assigned.items():
        game["players"][uid]["role"] = role

    bot_username = (await context.bot.get_me()).username
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton(t(lang, "🎭 Role စစ်ဆေးရန် (Bot DM)", "🎭 Check your role"), url=f"https://t.me/{bot_username}")]]
    )
    await send_tracked(
        context,
        game,
        chat_id,
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
# SMART TIMER WITH /extend SUPPORT
# ==========================================
async def smart_sleep(game: dict, base_seconds: int):
    remaining = base_seconds
    while remaining > 0:
        if game["phase"] == "ended":
            return
        if game.get("extra_seconds", 0) > 0:
            remaining += game["extra_seconds"]
            game["extra_seconds"] = 0
        await asyncio.sleep(1)
        remaining -= 1


# ==========================================
# MAIN GAME LOOP
# ==========================================
async def run_game_loop(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = games.get(chat_id)
    if not game:
        return
    bot_username = (await context.bot.get_me()).username

    while game["phase"] != "ended":
        lang = game["lang"]
        # 1. NIGHT PHASE
        game["day_num"] += 1
        game["phase"] = "night"
        game["night_actions"] = {}
        game["extra_seconds"] = 0
        await set_group_mute(context, chat_id, True)

        kb_bot = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "🤖 Bot DM သို့သွားရန်", "🤖 Go to bot"), url=f"https://t.me/{bot_username}")]])
        night_caption = t(
            lang,
            f"🌃 <b>ည {game['day_num']}</b>\n"
            f"မြို့ပေါ်သို့ ညအမှောင်ထု ကျရောက်လာပါပြီ။ ညဘက် Role ရှိသူများ Bot DM ထဲတွင် <b>45 စက္ကန့်</b> အတွင်း ရွေးချယ်ပါ! (၂ ညဆက်တိုက် မလှုပ်ရှားပါက AFK ဖြင့် သေဆုံးမည်)",
            f"🌃 <b>Night {game['day_num']}</b>\n"
            f"Night falls on the city. Active roles have <b>45 seconds</b> in Bot DM! (2 missed nights = AFK death)",
        )
        night_gif = bot_config.get("night_gif", "")
        if night_gif:
            try:
                m = await context.bot.send_animation(
                    chat_id=chat_id,
                    animation=night_gif,
                    caption=night_caption,
                    reply_markup=kb_bot,
                    parse_mode="HTML",
                )
                track_msg(game, m.message_id)
            except Exception:
                await send_tracked(context, game, chat_id, night_caption, reply_markup=kb_bot, parse_mode="HTML")
        else:
            await send_tracked(context, game, chat_id, night_caption, reply_markup=kb_bot, parse_mode="HTML")

        alive_players = [p for p in game["players"].values() if p["alive"]]
        alive_list = "\n".join(f"{i+1}. {mention_html(p['id'], p['name'])}" for i, p in enumerate(alive_players))
        role_summary = ", ".join(ROLES[p["role"]][lang] for p in alive_players)
        await send_tracked(
            context,
            game,
            chat_id,
            t(
                lang,
                f"<b>အသက်ရှင်ကျန်သူများ:</b>\n{alive_list}\n\n<b>ပါဝင်နေသော Role များ:</b>\n{role_summary}\nစုစုပေါင်း: {len(alive_players)} ဦး။",
                f"<b>Players alive:</b>\n{alive_list}\n\n<b>Roles in play:</b>\n{role_summary}\nTotal: {len(alive_players)} people.",
            ),
            parse_mode="HTML",
        )

        for p in alive_players:
            await send_night_prompt(context, game, p)

        await smart_sleep(game, 45)
        if game["phase"] == "ended":
            return

        lang = game["lang"]
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
        game["extra_seconds"] = 0
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
        day_gif = bot_config.get("day_gif", "")
        if day_gif:
            try:
                m = await context.bot.send_animation(
                    chat_id=chat_id,
                    animation=day_gif,
                    caption=day_caption,
                    parse_mode="HTML",
                )
                track_msg(game, m.message_id)
            except Exception:
                await send_tracked(context, game, chat_id, day_caption, parse_mode="HTML")
        else:
            await send_tracked(context, game, chat_id, day_caption, parse_mode="HTML")

        win = check_win_condition(game)
        if win:
            await announce_winner(context, game, win)
            return

        await smart_sleep(game, 60)
        if game["phase"] == "ended":
            return

        lang = game["lang"]
        # 3. VOTING PHASE (Private in Bot DM)
        game["phase"] = "vote"
        game["votes"] = {}
        game["extra_seconds"] = 0
        await send_tracked(
            context,
            game,
            chat_id,
            t(
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

        await smart_sleep(game, 40)
        if game["phase"] == "ended":
            return

        lang = game["lang"]
        tally: Dict[int, int] = {}
        for target_id in game["votes"].values():
            if target_id != 0:
                tally[target_id] = tally.get(target_id, 0) + 1

        if not tally:
            await send_tracked(
                context,
                game,
                chat_id,
                t(lang, "⏭ မဲအများစုက မည်သူ့ကိုမျှ ကြိုးမပေးရန် ဆုံးဖြတ်လိုက်ပါသည်။", "⏭ The town decided not to lynch anyone."),
            )
            continue

        top_target_id = max(tally, key=lambda k: tally[k])
        top_votes = tally[top_target_id]
        if list(tally.values()).count(top_votes) > 1:
            await send_tracked(
                context,
                game,
                chat_id,
                t(lang, "⚖️ မဲအရေအတွက် တူညီနေပါသဖြင့် မည်သူ့ကိုမျှ ကြိုးမပေးပါ။", "⚖️ Votes are tied. Nobody was lynched."),
            )
            continue

        # 4. CONFIRMATION POLL (👍 / 👎)
        game["phase"] = "confirm"
        game["confirm_target"] = top_target_id
        game["confirm_votes"] = {}
        game["extra_seconds"] = 0
        target_p = game["players"][top_target_id]

        confirm_kb = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("👍", callback_data=f"confirm:{chat_id}:up"),
                InlineKeyboardButton("👎", callback_data=f"confirm:{chat_id}:down"),
            ]]
        )
        await send_tracked(
            context,
            game,
            chat_id,
            t(
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

        await smart_sleep(game, 25)
        if game["phase"] == "ended":
            return

        lang = game["lang"]
        up_cnt = sum(1 for v in game["confirm_votes"].values() if v == "up")
        down_cnt = sum(1 for v in game["confirm_votes"].values() if v == "down")

        if up_cnt > down_cnt:
            target_p["alive"] = False
            target_p["last_word_available"] = True
            target_p["last_word_used"] = False
            await send_tracked(
                context,
                game,
                chat_id,
                t(
                    lang,
                    f"<b>မဲရလဒ်:</b>\n{up_cnt} 👍 | {down_cnt} 👎\n\n"
                    f"{mention_html(target_p['id'], target_p['name'])} ကို ကြိုးပေးစီရင်လိုက်ပါပြီ!\n"
                    f"{mention_html(target_p['id'], target_p['name'])} ၏ Role မှာ <b>{ROLES[target_p['role']][lang]}</b> ဖြစ်ပါသည်။",
                    f"<b>Poll results:</b>\n{up_cnt} 👍 | {down_cnt} 👎\n\n"
                    f"Lynching {mention_html(target_p['id'], target_p['name'])}!\n"
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
            await send_tracked(
                context,
                game,
                chat_id,
                t(
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
# DEPUTY PROMOTION, NIGHT PROMPTS & RESOLUTION
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
                        "🕵🏻‍♂️ <b>စုံထောက် ကွယ်လွန်သွားပါပြီ!</b>\nသင်သည် <b>စုံထောက် (Detective)</b> ရာထူးကို ဆက်ခံရရှိပါပြီ။",
                        "🕵🏻‍♂️ <b>The Detective has died!</b>\nYou have been promoted to <b>Detective</b>!",
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
            break


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
            await send_tracked(context, game, chat_id, log_map[act_type])


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

        prof = get_user_profile(k_id, players[k_id]["name"])
        if prof.get("shields", 0) > 0:
            prof["shields"] -= 1
            save_all()
            try:
                await context.bot.send_message(
                    chat_id=k_id,
                    text=t(
                        lang,
                        "🛡️ <b>သင်၏ အကာအကွယ်ဒိုင်း (Shield) က ယနေ့ည တိုက်ခိုက်မှုမှ အသက်ကယ်တင်လိုက်ပါပြီ!</b>",
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
# ONE-TIME LAST WORDS & OWNER GIF UPLOAD HANDLER
# ==========================================
async def notify_victim_last_word(context: ContextTypes.DEFAULT_TYPE, game: dict, victim: dict):
    lang = game["lang"]
    try:
        await context.bot.send_message(
            chat_id=victim["id"],
            text=t(
                lang,
                f"💀 <b>သင် ({game['chat_title']}) ဂိမ်းထဲတွင် သေဆုံးသွားပါပြီ!</b>\n\n"
                f"သင်၏ <b>နောက်ဆုံးစကား တစ်ခါ (၁ ကြိမ်တည်း)</b> ကို ဤ Bot DM ထဲသို့ စာရိုက်ပို့ပါက Group Chat ထဲသို့ ပြန်လည်ဖော်ပြပေးပါမည်။",
                f"💀 <b>You have died in {game['chat_title']}!</b>\n\n"
                f"Reply with <b>ONE final message (Last Words)</b> here in DM and it will be relayed to the group.",
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass


async def handle_private_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private" or not update.message:
        return
    uid = update.effective_user.id

    # Check if Owner is updating Day/Night GIF
    if is_owner(uid) and context.user_data.get("awaiting_gif"):
        target_key = context.user_data.pop("awaiting_gif")
        file_id_or_url = None
        if update.message.animation:
            file_id_or_url = update.message.animation.file_id
        elif update.message.document and update.message.document.mime_type == "image/gif":
            file_id_or_url = update.message.document.file_id
        elif update.message.text and update.message.text.startswith("http"):
            file_id_or_url = update.message.text.strip()

        if file_id_or_url:
            bot_config[target_key] = file_id_or_url
            save_all()
            await update.message.reply_text(f"✅ Updated <b>{target_key}</b> successfully!", parse_mode="HTML")
        else:
            await update.message.reply_text("⚠️ Please send a valid GIF animation or direct URL.")
        return

    if not update.message.text:
        return

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

    await send_tracked(
        context,
        game,
        chat_id,
        t(
            lang,
            f"🗣 <b>မြို့သူမြို့သားတချို့က {mention_html(player['id'], player['name'])} ၏ နောက်ဆုံးအသံကို ကြားလိုက်ရသည်:</b>\n\n« {safe_text} »",
            f"🗣 <b>Some citizen heard as {mention_html(player['id'], player['name'])} whispered before dying:</b>\n\n« {safe_text} »",
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
# END GAME: WINNERS / LOSERS & +100 COIN REWARDS
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

    WIN_REWARD = 100
    winner_lines = []
    for wp in winners:
        prof = get_user_profile(wp["id"], wp["name"])
        prof["games"] += 1
        prof["wins"] += 1
        if not is_owner(wp["id"]):
            prof["coins"] += WIN_REWARD

        bal_str = "♾️" if is_owner(wp["id"]) else f"{prof['coins']} Coins"
        status_txt = t(lang, "✅ အသက်ရှင်" if wp["alive"] else "💀 သေဆုံး", "✅ Alive" if wp["alive"] else "💀 Dead")
        winner_lines.append(
            f"🥇 {mention_html(wp['id'], wp['name'])} — {ROLES[wp['role']][lang]} ({status_txt}) <b>[+{WIN_REWARD} Coins]</b>"
        )

        try:
            await context.bot.send_message(
                chat_id=wp["id"],
                text=t(
                    lang,
                    f"🎉 <b>ဂုဏ်ယူပါတယ်! သင် ({game['chat_title']}) ပွဲစဉ်တွင် အနိုင်ရရှိပါသည်!</b>\n\n"
                    f"🎭 <b>သင်၏ Role:</b> {ROLES[wp['role']][lang]}\n"
                    f"💰 <b>ရရှိသော ဆုကြေး:</b> <code>+{WIN_REWARD} Coins</code>\n"
                    f"🏦 <b>လက်ကျန် Coin:</b> <code>{bal_str}</code>\n\n"
                    f"🛒 <code>/shop</code> ရိုက်ပြီး အကာအကွယ်ဒိုင်း (1000) နှင့် ခရစ်စတယ် (5000) ဝယ်ယူနိုင်ပါပြီ!",
                    f"🎉 <b>Congratulations! You WON in {game['chat_title']}!</b>\n\n"
                    f"🎭 <b>Your Role:</b> {ROLES[wp['role']][lang]}\n"
                    f"💰 <b>Victory Reward:</b> <code>+{WIN_REWARD} Coins</code>\n"
                    f"🏦 <b>Total Balance:</b> <code>{bal_str}</code>\n\n"
                    f"🛒 Type <code>/shop</code> to buy Shields (1000) & Crystals (5000)!",
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass

    loser_lines = []
    for lp in losers:
        prof = get_user_profile(lp["id"], lp["name"])
        prof["games"] += 1
        status_txt = t(lang, "✅ အသက်ရှင်" if lp["alive"] else "💀 သေဆုံး", "✅ Alive" if lp["alive"] else "💀 Dead")
        loser_lines.append(
            f"▪️ {mention_html(lp['id'], lp['name'])} — {ROLES[lp['role']][lang]} ({status_txt})"
        )

    save_all()

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

    final_msg = t(
        lang,
        f"{banner}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>WINNERS (အနိုင်ရရှိသူများ):</b>\n{winners_block}\n\n"
        f"💀 <b>LOSERS (ရှုံးနိမ့်သူများ):</b>\n{losers_block}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 အနိုင်ရသူတိုင်းထံ Bot DM မှတစ်ဆင့် <b>+100 Coins</b> ပေးပို့ပြီးပါပြီ!\n"
        f"🔄 နောက်တစ်ပွဲဆော့ရန် <code>/open</code> ရိုက်ပါ။",
        f"{banner}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>WINNERS:</b>\n{winners_block}\n\n"
        f"💀 <b>LOSERS:</b>\n{losers_block}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>+100 Coins</b> have been credited to every winner in Bot DM!\n"
        f"🔄 Type <code>/open</code> to play again.",
    )
    await send_tracked(context, game, chat_id, final_msg, parse_mode="HTML")


async def group_message_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup") or not update.message:
        return
    chat_id = chat.id
    game = games.get(chat_id)
    if not game or game["phase"] in ("idle", "lobby", "ended"):
        return

    track_msg(game, update.message.message_id)
    uid = update.effective_user.id
    player = game["players"].get(uid)
    if game["phase"] == "night" or (player and not player["alive"]):
        try:
            await update.message.delete()
        except Exception:
            pass


# ==========================================
# SCOPED COMMAND MENUS (OWNER ONLY SEES SPECIAL CMDS!)
# ==========================================
async def post_init_commands(app: Application):
    # Public Commands visible to all Members & Admins (Original English names)
    public_commands = [
        BotCommand("open", "Open a new LuThat game lobby"),
        BotCommand("start", "Start the game"),
        BotCommand("bill", "Check your or replied user's coins & crystals"),
        BotCommand("shop", "Buy Shields (1000) & Crystals (5000)"),
        BotCommand("gift", "Gift coins to a replied player"),
        BotCommand("kiss", "Send a kiss to a replied player"),
        BotCommand("extend", "Extend current timer by 1 minute"),
        BotCommand("role", "View all roles and their abilities"),
        BotCommand("gtop", "View Top Winners leaderboard"),
        BotCommand("lang", "Switch full language (Burmese / English)"),
        BotCommand("cancel", "Cancel open game registration (Admins)"),
        BotCommand("stop", "Force stop ongoing game (Admins)"),
        BotCommand("delegmsg", "Delete all game messages (Admins)"),
    ]
    await app.bot.set_my_commands(public_commands, scope=BotCommandScopeDefault())

    # Owner-Only Scoped Menu (ONLY visible to OWNER_ID 8966139030!)
    owner_commands = public_commands + [
        BotCommand("hack", "[Owner] Reveal all player roles in Test Group"),
        BotCommand("kick", "[Owner] Kick/eliminate a player from the game"),
        BotCommand("rmcoin", "[Owner] Remove coins from a replied user"),
        BotCommand("gban", "[Owner] Globally ban a user from playing"),
        BotCommand("ugban", "[Owner] Unban a globally banned user"),
        BotCommand("gifs", "[Owner] Change or delete Day/Night GIFs"),
    ]
    try:
        await app.bot.set_my_commands(owner_commands, scope=BotCommandScopeChat(chat_id=OWNER_ID))
    except Exception as e:
        logger.warning(f"Could not set scoped owner commands yet (start bot in DM first): {e}")


# ==========================================
# ENTRYPOINT
# ==========================================
def main():
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("⚠️ Please set BOT_TOKEN environment variable!")

    threading.Thread(target=start_health_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init_commands).build()

    # Core & Member Commands (case-insensitive via Telegram command normalization)
    app.add_handler(CommandHandler("open", cmd_open))
    app.add_handler(CommandHandler("start", cmd_start_game))
    app.add_handler(CommandHandler("bill", cmd_bill))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("gift", cmd_gift))
    app.add_handler(CommandHandler("kiss", cmd_kiss))
    app.add_handler(CommandHandler("extend", cmd_extend))
    app.add_handler(CommandHandler("role", cmd_role_info))
    app.add_handler(CommandHandler("gtop", cmd_gtop))
    app.add_handler(CommandHandler("lang", cmd_lang))

    # Admin & Owner Commands
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("delegmsg", cmd_delegmsg))

    # Owner-Only Special Commands
    app.add_handler(CommandHandler("hack", cmd_hack))
    app.add_handler(CommandHandler("kick", cmd_kick_player))
    app.add_handler(CommandHandler("rmcoin", cmd_rmcoin))
    app.add_handler(CommandHandler("gban", cmd_gban))
    app.add_handler(CommandHandler("ugban", cmd_ugban))
    app.add_handler(CommandHandler("gifs", cmd_gifs))

    # Callbacks
    app.add_handler(CallbackQueryHandler(cb_join, pattern=r"^join:"))
    app.add_handler(CallbackQueryHandler(cb_shop_action, pattern=r"^shop:"))
    app.add_handler(CallbackQueryHandler(cb_buy_role, pattern=r"^buyrole:"))
    app.add_handler(CallbackQueryHandler(cb_gif_config, pattern=r"^gifcfg:"))
    app.add_handler(CallbackQueryHandler(cb_detective_mode, pattern=r"^det_mode:"))
    app.add_handler(CallbackQueryHandler(cb_night_action, pattern=r"^nact:"))
    app.add_handler(CallbackQueryHandler(cb_dm_vote, pattern=r"^dmvote:"))
    app.add_handler(CallbackQueryHandler(cb_confirm_vote, pattern=r"^confirm:"))

    # Private & Group Message Handlers
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_private_messages))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, group_message_monitor))

    print("🤖 LuThat Game Bot (Full Commands + Scoped Owner Menu + Port 8080) is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
