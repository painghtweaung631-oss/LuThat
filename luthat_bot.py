import os
import json
import random
import asyncio
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest

# ================= CONFIG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
TEST_GROUP_ID = int(os.environ.get("TEST_GROUP_ID", "0"))
JSONBIN_ID = os.environ.get("JSONBIN_ID", "")
JSONBIN_KEY = os.environ.get("JSONBIN_KEY", "")
DATA_FILE = "luthat_data.json"
NL = chr(10)

JOIN_DURATION = 60
NIGHT_DURATION = 35
DAY_DURATION = 45
VOTE_DURATION = 30
WIN_COIN_REWARD = 10

# ================= ROLE DEFINITIONS =================
ROLES_INFO = {
    "don": {
        "team": "mafia",
        "mm": "ဂိုဏ်းခေါင်းဆောင် (Don)",
        "en": "Mafia Don",
        "desc_mm": "ညဘက်တွင် သတ်မည့်သူကို အတည်ပြု ရွေးချယ်ပိုင်ခွင့်ရှိသည်။",
        "desc_en": "Choose and confirm the target to eliminate each night.",
    },
    "mafia": {
        "team": "mafia",
        "mm": "ဂိုဏ်းဝင် (Mafia)",
        "en": "Mafia Member",
        "desc_mm": "ညဘက်တွင် သတ်မည့်သူကို အကြံပြုနိုင်သည်။ ခေါင်းဆောင်သေဆုံးပါက ခေါင်းဆောင်အသစ် ဖြစ်လာမည်။",
        "desc_en": "Suggest a target at night. You become the new Don if the Don dies.",
    },
    "detective": {
        "team": "town",
        "mm": "စုံထောက် (Detective)",
        "en": "Detective",
        "desc_mm": "ညဘက်တွင် တစ်ဦးကို စစ်ဆေးခြင်း သို့မဟုတ် ပစ်သတ်ခြင်း ပြုလုပ်နိုင်သည်။",
        "desc_en": "Investigate or shoot one player each night.",
    },
    "deputy": {
        "team": "town",
        "mm": "လက်ထောက် (Deputy)",
        "en": "Deputy",
        "desc_mm": "စုံထောက် စစ်ဆေးသည့်ရလဒ်ကို သိခွင့်ရသည်။ စုံထောက်သေဆုံးပါက စုံထောက်အသစ် ဖြစ်လာမည်။",
        "desc_en": "See the Detective's investigation results. Promote to Detective if they die.",
    },
    "doctor": {
        "team": "town",
        "mm": "ဒေါက်တာ (Doctor)",
        "en": "Doctor",
        "desc_mm": "ညဘက်တွင် တစ်ဦး (သို့မဟုတ် ကိုယ့်ကိုယ်ကိုယ်) ဆေးကုသပေးနိုင်သည်။",
        "desc_en": "Heal one player (including yourself) each night.",
    },
    "police": {
        "team": "town",
        "mm": "ရဲ (Police)",
        "en": "Police / Bodyguard",
        "desc_mm": "ညဘက်တွင် တစ်ဦးကို အကာအကွယ်ပေးနိုင်သည်။ လာသတ်သူရှိပါက သင်က အသက်စွန့်ကာကွယ်မည်။",
        "desc_en": "Guard a player at night. If attacked, you sacrifice yourself to save them.",
    },
    "drunk": {
        "team": "town",
        "mm": "အရက်သမား (Drunk)",
        "en": "Drunk (Roleblocker)",
        "desc_mm": "ညဘက်တွင် တစ်ဦးအိမ်သို့ သွားရောက်အရက်တိုက်နိုင်သည်။ အတိုက်ခံရသူ ညဘက် Action လုပ်မရပါ။",
        "desc_en": "Visit a player and get them drunk, blocking their night action.",
    },
    "sk": {
        "team": "sk",
        "mm": "စိတ္တဇလူသတ်သမား (Serial Killer)",
        "en": "Serial Killer",
        "desc_mm": "ညတိုင်း တစ်ဦးကို သီးသန့်လိုက်သတ်နိုင်သည်။ အားလုံးကိုသတ်ပြီး တစ်ဦးတည်းကျန်မှ နိုင်မည်။",
        "desc_en": "Kill one player every night. Be the last one standing to win.",
    },
    "villager": {
        "team": "town",
        "mm": "မြို့သူမြို့သား (Villager)",
        "en": "Villager",
        "desc_mm": "နေ့ဘက် မဲပေးချိန်တွင် မသင်္ကာသူကို မဲပေးရွေးချယ်ရမည်။",
        "desc_en": "Discuss and vote to lynch suspects during the day.",
    },
}

# ================= BILINGUAL TEXTS =================
TEXTS = {
    "mm": {
        "welcome": (
            "🎭 **LuThat Game Bot** မှ ကြိုဆိုပါတယ်!\n\n"
            "• Group ထဲတွင် ဂိမ်းဖွင့်ရန် `/Open` နှိပ်ပါ။\n"
            "• ဘာသာစကားပြောင်းရန် `/Lang` နှိပ်ပါ။\n"
            "• ပိုက်ဆံနှင့် စိန်စစ်ရန် `/Bill` နှင့် ဆိုင်ဝင်ရန် `/Shop` နှိပ်ပါ။\n\n"
            "⚠️ _ဂိမ်းထဲမဝင်မီ ဤ Bot Chat တွင် Start နှိပ်ထားရန် လိုအပ်ပါသည်။_"
        ),
        "choose_lang": "🌐 ဘာသာစကား ရွေးချယ်ပါ / Choose Language:",
        "lang_set": "✅ ဘာသာစကားကို **မြန်မာဘာသာ** သို့ ပြောင်းလဲပြီးပါပြီ။",
        "group_only": "⚠️ ဤ Command ကို Group ထဲတွင်သာ အသုံးပြုနိုင်ပါသည်။",
        "admin_only": "⛔ ဤ Command ကို Group Admin နှင့် Bot Owner သာ အသုံးပြုနိုင်ပါသည်။",
        "owner_only": "⛔ ဤ Special Command ကို Bot Owner တစ်ဦးတည်းသာ အသုံးပြုနိုင်ပါသည်။",
        "banned": "🚫 သင်သည် ဂိမ်းကစားခွင့် ပိတ်ပင် (Ban) ခံထားရပါသည်။",
        "game_already": "⚠️ လက်ရှိ ဂိမ်းဝိုင်းတစ်ခု ရှိနေပါပြီ။ ဖျက်သိမ်းလိုပါက `/Cancel` နှိပ်ပါ။",
        "no_game": "ℹ️ လက်ရှိ ဖွင့်ထားသော ဂိမ်းဝိုင်း မရှိပါ။ `/Open` ဖြင့် အသစ်ဖွင့်ပါ။",
        "lobby_open": (
            "🔪 **LuThat Game — ဂိမ်းဝိုင်းအသစ် ဖွင့်လှစ်လိုက်ပါပြီ!**\n\n"
            "👥 အနည်းဆုံး ကစားသမား: **၅ ဦး**\n"
            "⏳ ဝင်ရောက်ရန် အချိန်: **{sec} စက္ကန့်**\n\n"
            "👇 အောက်ပါ ခလုတ်ကို နှိပ်ပြီး ဂိမ်းထဲ ဝင်ရောက်ပါ (Bot DM ကို အရင် Start နှိပ်ထားပါ)။"
        ),
        "join_btn": "✅ ဂိမ်းထဲဝင်မည် (Join)",
        "leave_btn": "❌ ထွက်မည် (Leave)",
        "joined_ok": "✅ {name} ဂိမ်းထဲသို့ ဝင်ရောက်လာပါပြီ! (စုစုပေါင်း: {count} ဦး)",
        "left_ok": "🚪 {name} ဂိမ်းထဲမှ ပြန်လည်ထွက်ခွာသွားပါသည်။ (စုစုပေါင်း: {count} ဦး)",
        "dm_required": "⚠️ {name} ခင်ဗျာ — Bot ထံသို့ Private Chat (DM) သွားပြီး Start အရင်နှိပ်ပေးပါ။",
        "not_enough": "❌ ကစားသမား အနည်းဆုံး **၅ ဦး** မပြည့်သေးပါ (လက်ရှိ: {count} ဦး)။ ဂိမ်းဖျက်သိမ်းလိုက်ပါသည်။",
        "extended": "⏳ ဝင်ရောက်ခြင်း အချိန်ကို **၃၀ စက္ကန့်** ထပ်တိုးလိုက်ပါပြီ! (ကျန်ရှိချိန်: {sec} စက္ကန့်)",
        "closing_15": "⚠️ **သတိပေးချက်:** ဝင်ရောက်ခြင်း ပိတ်ရန် **၁၅ စက္ကန့်** သာ လိုပါတော့သည်!",
        "cancelled": "🛑 ဂိမ်းဝိုင်းကို ဖျက်သိမ်းရပ်နားလိုက်ပါပြီ။",
        "game_starting": "🎬 **LuThat Game စတင်ပါပြီ!** ကစားသမား **{count} ဦး** ၏ Bot DM ဆီသို့ Role များ ပေးပို့လိုက်ပါပြီ။",
        "night_start": "🌙 **ညအချိန် ရောက်ရှိလာပါပြီ (ည {night})**\nအထူး Role ရှိသူများ Bot DM ထဲတွင် မိမိတို့ လုပ်ဆောင်ချက်ကို **{sec} စက္ကန့်** အတွင်း ရွေးချယ်ပါ။",
        "day_start": "☀️ **မနက်မိုးလင်းပါပြီ (နေ့ {day})**\n\n{report}\n\n🗣️ ဆွေးနွေးရန် အချိန် **{sec} စက္ကန့်** ရပါမည်။",
        "vote_start": "⚖️ **မဲပေး ကြိုးပေးချိန် (Lynch Vote)**\nမသင်္ကာသူ တစ်ဦးကို **{sec} စက္ကန့်** အတွင်း မဲပေးရွေးချယ်ပါ:",
        "skip_vote": "⏭️ မဲမပေးဘဲ ကျော်မည် (Skip)",
    },
    "en": {
        "welcome": (
            "🎭 Welcome to **LuThat Game Bot**!\n\n"
            "• Use `/Open` in a group to open a new game lobby.\n"
            "• Use `/Lang` to switch between Myanmar and English.\n"
            "• Use `/Bill` to check your Coins/Diamonds and `/Shop` to buy items.\n\n"
            "⚠️ _Please press Start in this Bot DM before joining a game._"
        ),
        "choose_lang": "🌐 Choose Language / ဘာသာစကား ရွေးချယ်ပါ:",
        "lang_set": "✅ Language has been set to **English**.",
        "group_only": "⚠️ This command can only be used in a group.",
        "admin_only": "⛔ Only Group Admins and Bot Owner can use this command.",
        "owner_only": "⛔ This special command is restricted to the Bot Owner only.",
        "banned": "🚫 You are banned from playing LuThat Game.",
        "game_already": "⚠️ A game is already active in this group. Use `/Cancel` to stop it.",
        "no_game": "ℹ️ No active game in this group. Use `/Open` to start one.",
        "lobby_open": (
            "🔪 **LuThat Game — Lobby Opened!**\n\n"
            "👥 Minimum Players: **5**\n"
            "⏳ Join Timer: **{sec} seconds**\n\n"
            "👇 Tap below to join the game (make sure you started the Bot in DM first)."
        ),
        "join_btn": "✅ Join Game",
        "leave_btn": "❌ Leave",
        "joined_ok": "✅ {name} joined the game! (Total: {count})",
        "left_ok": "🚪 {name} left the game. (Total: {count})",
        "dm_required": "⚠️ {name} — Please open the Bot DM and press Start first!",
        "not_enough": "❌ Not enough players (minimum **5**, current: {count}). Game cancelled.",
        "extended": "⏳ Join timer extended by **30 seconds**! (Remaining: {sec}s)",
        "closing_15": "⚠️ **Warning:** Only **15 seconds** left before registration closes!",
        "cancelled": "🛑 The game has been cancelled.",
        "game_starting": "🎬 **LuThat Game has started!** Roles have been sent to **{count} players** via Bot DM.",
        "night_start": "🌙 **Night {night} has fallen.**\nPlayers with night abilities, check your Bot DM and choose within **{sec} seconds**.",
        "day_start": "☀️ **Day {day} has dawned.**\n\n{report}\n\n🗣️ You have **{sec} seconds** to discuss.",
        "vote_start": "⚖️ **Voting Phase (Lynch)**\nVote for a suspect within **{sec} seconds**:",
        "skip_vote": "⏭️ Skip Vote",
    },
}

# ================= PERSISTENT STORAGE =================
def default_store() -> dict:
    return {
        "users": {},
        "group_langs": {},
        "banned": [],
    }

def load_store() -> dict:
    if JSONBIN_ID and JSONBIN_KEY:
        try:
            url = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}/latest"
            res = requests.get(url, headers={"X-Master-Key": JSONBIN_KEY}, timeout=8)
            if res.status_code == 200:
                rec = res.json().get("record", {})
                if isinstance(rec, dict) and "users" in rec:
                    return rec
        except Exception:
            pass
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                rec = json.load(f)
                if isinstance(rec, dict) and "users" in rec:
                    return rec
        except Exception:
            pass
    return default_store()

def save_store(store: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    if JSONBIN_ID and JSONBIN_KEY:
        try:
            url = f"https://api.jsonbin.io/v3/b/{JSONBIN_ID}"
            headers = {"Content-Type": "application/json", "X-Master-Key": JSONBIN_KEY}
            requests.put(url, json=store, headers=headers, timeout=8)
        except Exception:
            pass

def get_user_record(store: dict, user_id: int) -> dict:
    uid = str(user_id)
    if uid not in store["users"]:
        store["users"][uid] = {
            "coins": 0,
            "diamonds": 0,
            "shields": 0,
            "role_tickets": 0,
            "preferred_role": None,
            "lang": "mm",
            "wins": 0,
        }
    return store["users"][uid]

def get_lang(chat_id: int, user_id: int = None) -> str:
    store = load_store()
    if chat_id < 0:
        return store.get("group_langs", {}).get(str(chat_id), "mm")
    if user_id:
        return get_user_record(store, user_id).get("lang", "mm")
    return "mm"

def t(lang: str, key: str, **kwargs) -> str:
    base = TEXTS.get(lang, TEXTS["mm"]).get(key, key)
    return base.format(**kwargs) if kwargs else base

def role_label(role_key: str, lang: str) -> str:
    info = ROLES_INFO.get(role_key, ROLES_INFO["villager"])
    return info["mm"] if lang == "mm" else info["en"]

# ================= ACTIVE GAMES STATE =================
games = {}

# ================= PERMISSION HELPERS =================
def is_owner(user_id: int) -> bool:
    return OWNER_ID != 0 and user_id == OWNER_ID

async def is_group_admin_or_owner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    if is_owner(user.id):
        return True
    chat = update.effective_chat
    if chat.type == "private":
        return False
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False

def is_banned(user_id: int) -> bool:
    if is_owner(user_id):
        return False
    store = load_store()
    return user_id in store.get("banned", [])

# ================= ROLE ASSIGNMENT LOGIC =================
def build_role_list(count: int) -> list:
    if count == 5:
        return ["don", "detective", "doctor", "villager", "villager"]
    elif count == 6:
        return ["don", "mafia", "detective", "doctor", "villager", "villager"]
    elif count == 7:
        return ["don", "mafia", "detective", "doctor", "police", "villager", "villager"]
    elif count == 8:
        return ["don", "mafia", "detective", "deputy", "doctor", "police", "villager", "villager"]
    elif count == 9:
        return ["don", "mafia", "detective", "deputy", "doctor", "police", "drunk", "villager", "villager"]
    else:
        roles = [
            "don", "mafia", "mafia",
            "detective", "deputy",
            "sk", "police", "doctor", "drunk"
        ]
        while len(roles) < count:
            roles.append("villager")
        return roles

# ================= COMMANDS: /Lang, /Open, /Start, /Extend, /Close, /Cancel =================
async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_lang(chat.id, user.id)
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇲🇲 မြန်မာ", callback_data=f"setlang:mm:{chat.id}"),
            InlineKeyboardButton("🇬🇧 English", callback_data=f"setlang:en:{chat.id}"),
        ]
    ])
    await update.message.reply_text(t(lang, "choose_lang"), reply_markup=kb)

async def cmd_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_lang(chat.id, user.id)

    if chat.type == "private":
        await update.message.reply_text(t(lang, "group_only"))
        return

    if is_banned(user.id):
        await update.message.reply_text(t(lang, "banned"))
        return

    if chat.id in games:
        await update.message.reply_text(t(lang, "game_already"))
        return

    game = {
        "chat_id": chat.id,
        "chat_title": chat.title or "Group",
        "phase": "lobby",
        "time_left": JOIN_DURATION,
        "players": {},
        "original_roles": {},
        "night_num": 0,
        "day_num": 0,
        "night_actions": {},
        "votes": {},
        "task": None,
        "lobby_msg_id": None,
    }
    games[chat.id] = game

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "join_btn"), callback_data=f"join:{chat.id}"),
            InlineKeyboardButton(t(lang, "leave_btn"), callback_data=f"leave:{chat.id}"),
        ]
    ])
    msg = await update.message.reply_text(
        t(lang, "lobby_open", sec=JOIN_DURATION),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )
    game["lobby_msg_id"] = msg.message_id
    game["task"] = asyncio.create_task(lobby_countdown(chat.id, context))

async def lobby_countdown(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        while chat_id in games and games[chat_id]["phase"] == "lobby":
            await asyncio.sleep(1)
            game = games.get(chat_id)
            if not game or game["phase"] != "lobby":
                return
            game["time_left"] -= 1
            if game["time_left"] == 15:
                lang = get_lang(chat_id)
                await context.bot.send_message(
                    chat_id, t(lang, "closing_15"), parse_mode=ParseMode.MARKDOWN
                )
            if game["time_left"] <= 0:
                await begin_game(chat_id, context)
                return
    except asyncio.CancelledError:
        return

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_lang(chat.id, user.id)

    if chat.type == "private":
        await update.message.reply_text(t(lang, "welcome"), parse_mode=ParseMode.MARKDOWN)
        return

    game = games.get(chat.id)
    if not game or game["phase"] != "lobby":
        await update.message.reply_text(t(lang, "no_game"))
        return

    if len(game["players"]) < 5:
        await update.message.reply_text(
            t(lang, "not_enough", count=len(game["players"])),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if game["task"] and not game["task"].done():
        game["task"].cancel()
    await begin_game(chat.id, context)

async def cmd_extend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_lang(chat.id, user.id)

    if chat.type == "private":
        await update.message.reply_text(t(lang, "group_only"))
        return

    game = games.get(chat.id)
    if not game or game["phase"] != "lobby":
        await update.message.reply_text(t(lang, "no_game"))
        return

    game["time_left"] += 30
    await update.message.reply_text(
        t(lang, "extended", sec=game["time_left"]), parse_mode=ParseMode.MARKDOWN
    )

async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_lang(chat.id, user.id)

    if chat.type == "private":
        await update.message.reply_text(t(lang, "group_only"))
        return

    if not await is_group_admin_or_owner(update, context):
        await update.message.reply_text(t(lang, "admin_only"))
        return

    game = games.get(chat.id)
    if not game or game["phase"] != "lobby":
        await update.message.reply_text(t(lang, "no_game"))
        return

    game["time_left"] = 15
    await update.message.reply_text(t(lang, "closing_15"), parse_mode=ParseMode.MARKDOWN)

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_lang(chat.id, user.id)

    if chat.type == "private":
        await update.message.reply_text(t(lang, "group_only"))
        return

    if not await is_group_admin_or_owner(update, context):
        await update.message.reply_text(t(lang, "admin_only"))
        return

    game = games.get(chat.id)
    if not game:
        await update.message.reply_text(t(lang, "no_game"))
        return

    if game.get("task") and not game["task"].done():
        game["task"].cancel()
    games.pop(chat.id, None)
    await update.message.reply_text(t(lang, "cancelled"))

# ================= ECONOMY & SHOP COMMANDS (/Bill, /Shop, /Giftc, /Giftd, /Rmcoin) =================
async def cmd_bill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_lang(update.effective_chat.id, user.id)
    store = load_store()
    rec = get_user_record(store, user.id)
    save_store(store)

    if is_owner(user.id):
        coins_str = "♾️ Unlimited"
        dia_str = "♾️ Unlimited"
    else:
        coins_str = f"{rec['coins']} Coins"
        dia_str = f"{rec['diamonds']} 💎"

    if lang == "mm":
        msg = (
            f"💳 **{user.first_name} ၏ လက်ကျန်စာရင်း (Bill)**\n\n"
            f"• 🪙 **Coins:** `{coins_str}`\n"
            f"• 💎 **Diamonds:** `{dia_str}`\n"
            f"• 🛡️ **အကာအကွယ် (Shields):** `{rec['shields']} ခု`\n"
            f"• 🎭 **Role ရွေးခွင့် Ticket:** `{rec['role_tickets']} ခု`\n"
            f"• 🏆 **နိုင်ပွဲစုစုပေါင်း:** `{rec['wins']} ပွဲ`"
        )
    else:
        msg = (
            f"💳 **{user.first_name}'s Account Bill**\n\n"
            f"• 🪙 **Coins:** `{coins_str}`\n"
            f"• 💎 **Diamonds:** `{dia_str}`\n"
            f"• 🛡️ **Shields:** `{rec['shields']}`\n"
            f"• 🎭 **Role Tickets:** `{rec['role_tickets']}`\n"
            f"• 🏆 **Total Wins:** `{rec['wins']}`"
        )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_lang(update.effective_chat.id, user.id)
    if lang == "mm":
        txt = (
            "🛒 **LuThat Game Shop (ဈေးဆိုင်)**\n\n"
            "1️⃣ **🛡️ အကာအကွယ် (Shield)** — `50 Coins`\n"
            "   _(ညဘက် အသတ်ခံရပါက ၁ ကြိမ် အသက်ရှင်ကျန်မည်)_\n\n"
            "2️⃣ **💎 1 Diamond (စိန် ၁ လုံး)** — `200 Coins`\n"
            "   _(Coins 200 ဖြင့် စိန် ၁ လုံး လဲလှယ်နိုင်သည်)_\n\n"
            "3️⃣ **🎭 Role ရွေးခွင့် (Role Ticket)** — `1 Diamond`\n"
            "   _(စိန် ၁ လုံးဖြင့် ဂိမ်းထဲတွင် ကြိုက်နှစ်သက်ရာ Role ၁ ခု ရွေးယူနိုင်သည်)_"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛡️ Shield ဝယ်မည် (50 Coins)", callback_data=f"buy:shield:{user.id}")],
            [InlineKeyboardButton("💎 1 Diamond ဝယ်မည် (200 Coins)", callback_data=f"buy:dia:{user.id}")],
            [InlineKeyboardButton("🎭 Role Ticket ဝယ်မည် (1 Dia)", callback_data=f"buy:role:{user.id}")],
        ])
    else:
        txt = (
            "🛒 **LuThat Game Shop**\n\n"
            "1️⃣ **🛡️ Night Shield** — `50 Coins`\n"
            "   _(Protects you once from a night attack)_\n\n"
            "2️⃣ **💎 1 Diamond** — `200 Coins`\n"
            "   _(Exchange 200 Coins for 1 Diamond)_\n\n"
            "3️⃣ **🎭 Role Ticket** — `1 Diamond`\n"
            "   _(Choose your desired Role in a game using 1 Diamond)_"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛡️ Buy Shield (50 Coins)", callback_data=f"buy:shield:{user.id}")],
            [InlineKeyboardButton("💎 Buy 1 Diamond (200 Coins)", callback_data=f"buy:dia:{user.id}")],
            [InlineKeyboardButton("🎭 Buy Role Ticket (1 Dia)", callback_data=f"buy:role:{user.id}")],
        ])
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def cmd_giftc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    lang = get_lang(update.effective_chat.id, sender.id)

    if not update.message.reply_to_message or not context.args or not context.args[0].isdigit():
        msg = "အသုံးပြုပုံ: လွှဲပေးလိုသူ၏ စာကို Reply ပြန်ပြီး `/Giftc 50` ဟု ရိုက်ပါ။" if lang == "mm" else "Usage: Reply to a user and type `/Giftc 50`."
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    amount = int(context.args[0])
    if amount <= 0:
        return

    target = update.message.reply_to_message.from_user
    store = load_store()
    s_rec = get_user_record(store, sender.id)
    t_rec = get_user_record(store, target.id)

    if not is_owner(sender.id):
        if s_rec["coins"] < amount:
            msg = "❌ သင့်တွင် Coins လုံလောက်စွာ မရှိပါ။" if lang == "mm" else "❌ Insufficient Coins."
            await update.message.reply_text(msg)
            return
        s_rec["coins"] -= amount

    t_rec["coins"] += amount
    save_store(store)

    msg = (
        f"🎁 **{sender.first_name}** က **{target.first_name}** ထံသို့ **{amount} Coins** လက်ဆောင်ပေးလိုက်ပါပြီ!"
        if lang == "mm"
        else f"🎁 **{sender.first_name}** gifted **{amount} Coins** to **{target.first_name}**!"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_giftd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    lang = get_lang(update.effective_chat.id, sender.id)

    if not update.message.reply_to_message or not context.args or not context.args[0].isdigit():
        msg = "အသုံးပြုပုံ: လွှဲပေးလိုသူ၏ စာကို Reply ပြန်ပြီး `/Giftd 1` ဟု ရိုက်ပါ။" if lang == "mm" else "Usage: Reply to a user and type `/Giftd 1`."
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    amount = int(context.args[0])
    if amount <= 0:
        return

    target = update.message.reply_to_message.from_user
    store = load_store()
    s_rec = get_user_record(store, sender.id)
    t_rec = get_user_record(store, target.id)

    if not is_owner(sender.id):
        if s_rec["diamonds"] < amount:
            msg = "❌ သင့်တွင် Diamond လုံလောက်စွာ မရှိပါ။" if lang == "mm" else "❌ Insufficient Diamonds."
            await update.message.reply_text(msg)
            return
        s_rec["diamonds"] -= amount

    t_rec["diamonds"] += amount
    save_store(store)

    msg = (
        f"💎 **{sender.first_name}** က **{target.first_name}** ထံသို့ **{amount} Diamond(s)** လက်ဆောင်ပေးလိုက်ပါပြီ!"
        if lang == "mm"
        else f"💎 **{sender.first_name}** gifted **{amount} Diamond(s)** to **{target.first_name}**!"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_rmcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_lang(update.effective_chat.id, user.id)
    if not is_owner(user.id):
        await update.message.reply_text(t(lang, "owner_only"))
        return

    if not update.message.reply_to_message or not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Reply ပြန်ပြီး `/Rmcoin 50` ဟု ရိုက်ပါ။", parse_mode=ParseMode.MARKDOWN)
        return

    amount = int(context.args[0])
    target = update.message.reply_to_message.from_user
    store = load_store()
    t_rec = get_user_record(store, target.id)
    t_rec["coins"] = max(0, t_rec["coins"] - amount)
    save_store(store)
    await update.message.reply_text(
        f"✅ **{target.first_name}** ထံမှ **{amount} Coins** ပြန်လည်သိမ်းယူပြီးပါပြီ (လက်ကျန်: {t_rec['coins']} Coins)။",
        parse_mode=ParseMode.MARKDOWN,
    )

# ================= OWNER SPECIAL COMMANDS (/Crole, /Rsrole, /Hack, /Ban, /Unban) & /ReportX =================
async def cmd_crole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_lang(chat.id, user.id)

    if not is_owner(user.id):
        await update.message.reply_text(t(lang, "owner_only"))
        return

    game = games.get(chat.id)
    if not game or game["phase"] == "lobby":
        await update.message.reply_text("⚠️ ဂိမ်းစတင်နေချိန်မှသာ Role ပြောင်းလဲနိုင်ပါသည်။")
        return

    target = update.message.reply_to_message.from_user if update.message.reply_to_message else user
    if target.id not in game["players"]:
        await update.message.reply_text("❌ ထိုသူသည် လက်ရှိဂိမ်းထဲတွင် မပါဝင်ပါ။")
        return

    if not context.args:
        valid = ", ".join(ROLES_INFO.keys())
        await update.message.reply_text(
            f"Role အမည် ထည့်ပါ: `/Crole don`\nရရှိနိုင်သော Role များ: `{valid}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    new_role = context.args[0].lower().strip()
    if new_role not in ROLES_INFO:
        await update.message.reply_text("❌ Role အမည် မှားယွင်းနေပါသည်။")
        return

    game["players"][target.id]["role"] = new_role
    await update.message.reply_text(
        f"✅ **{target.first_name}** ၏ Role ကို **{role_label(new_role, lang)}** သို့ ပြောင်းလဲလိုက်ပါပြီ။",
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        await context.bot.send_message(
            target.id,
            f"🎭 သင်၏ Role ကို **{role_label(new_role, 'mm')}** သို့ ပြောင်းလဲသတ်မှတ်လိုက်ပါသည်။",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass

async def cmd_rsrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_lang(chat.id, user.id)

    if not is_owner(user.id):
        await update.message.reply_text(t(lang, "owner_only"))
        return

    game = games.get(chat.id)
    if not game or target_id := (update.message.reply_to_message.from_user.id if update.message.reply_to_message else user.id):
        if not game or target_id not in game["original_roles"]:
            await update.message.reply_text("❌ မူလ Role မှတ်တမ်း မတွေ့ပါ။")
            return
        orig = game["original_roles"][target_id]
        game["players"][target_id]["role"] = orig
        t_name = game["players"][target_id]["name"]
        await update.message.reply_text(
            f"🔄 **{t_name}** ၏ Role ကို မူလနဂို **{role_label(orig, lang)}** သို့ ပြန်လည်ထားရှိပြီးပါပြီ။",
            parse_mode=ParseMode.MARKDOWN,
        )

async def cmd_hack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_lang(chat.id, user.id)

    if not is_owner(user.id):
        await update.message.reply_text(t(lang, "owner_only"))
        return

    game = games.get(chat.id)
    if not game or not game["players"]:
        await update.message.reply_text(t(lang, "no_game"))
        return

    lines = [f"🕵️ **HACK REPORT — {game['chat_title']}**", ""]
    for pid, pdata in game["players"].items():
        status = "🟢 Alive" if pdata.get("alive", True) else "💀 Dead"
        r_name = role_label(pdata.get("role", "villager"), "mm")
        lines.append(f"• {pdata['name']} (`{pid}`) — **{r_name}** [{status}]")

    dest_id = TEST_GROUP_ID if TEST_GROUP_ID != 0 else user.id
    try:
        await context.bot.send_message(dest_id, NL.join(lines), parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("✅ Hack အချက်အလက်များကို Test Group ဆီ ပေးပို့ပြီးပါပြီ။")
    except Exception:
        await update.message.reply_text("❌ Test Group ဆီ စာပို့၍ မရပါ (Bot ကို Test Group ထဲ ထည့်ထားပါ)။")

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_lang(update.effective_chat.id, user.id)
    if not is_owner(user.id):
        await update.message.reply_text(t(lang, "owner_only"))
        return

    target_id = None
    target_name = "User"
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        target_name = update.message.reply_to_message.from_user.first_name
    elif context.args and context.args[0].lstrip("-").isdigit():
        target_id = int(context.args[0])
        target_name = str(target_id)

    if not target_id:
        await update.message.reply_text("Ban လိုသူ၏ စာကို Reply ပြန်ပါ သို့မဟုတ် User ID ထည့်ပါ။")
        return

    store = load_store()
    if target_id not in store["banned"]:
        store["banned"].append(target_id)
        save_store(store)
    await update.message.reply_text(f"🚫 **{target_name}** (`{target_id}`) ကို ဂိမ်းဆော့ခွင့် ပိတ်ပင်လိုက်ပါပြီ။", parse_mode=ParseMode.MARKDOWN)

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_lang(update.effective_chat.id, user.id)
    if not is_owner(user.id):
        await update.message.reply_text(t(lang, "owner_only"))
        return

    target_id = None
    target_name = "User"
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        target_name = update.message.reply_to_message.from_user.first_name
    elif context.args and context.args[0].lstrip("-").isdigit():
        target_id = int(context.args[0])
        target_name = str(target_id)

    if not target_id:
        await update.message.reply_text("Unban လိုသူ၏ စာကို Reply ပြန်ပါ သို့မဟုတ် User ID ထည့်ပါ။")
        return

    store = load_store()
    if target_id in store["banned"]:
        store["banned"].remove(target_id)
        save_store(store)
    await update.message.reply_text(f"✅ **{target_name}** (`{target_id}`) ကို Ban ပြန်ဖြေပေးလိုက်ပါပြီ။", parse_mode=ParseMode.MARKDOWN)

async def cmd_reportx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    reporter = update.effective_user
    lang = get_lang(chat.id, reporter.id)

    if not update.message.reply_to_message:
        msg = "တိုင်ကြားလိုသူ၏ စာကို Reply ထောက်ပြီး `/ReportX အကြောင်းအရာ` ဟု ရိုက်ပို့ပါ။" if lang == "mm" else "Reply to a message and type `/ReportX reason`."
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    accused = update.message.reply_to_message.from_user
    reason = " ".join(context.args).strip() or "(အကြောင်းပြချက် မရေးထားပါ)"
    quoted_msg = update.message.reply_to_message.text or "[Media/Sticker]"

    report_text = NL.join([
        "🚨 **NEW PLAYER REPORT (/ReportX)**",
        f"• **Group:** {chat.title or 'Private'} (`{chat.id}`)",
        f"• **Reporter:** {reporter.first_name} (`{reporter.id}`)",
        f"• **Reported User:** {accused.first_name} (`{accused.id}`)",
        f"• **Reported Message:** `{quoted_msg[:200]}`",
        f"• **Reason:** {reason}",
    ])

    dest_id = TEST_GROUP_ID if TEST_GROUP_ID != 0 else OWNER_ID
    try:
        await context.bot.send_message(dest_id, report_text, parse_mode=ParseMode.MARKDOWN)
        confirm = "✅ တိုင်ကြားချက်ကို Admin / Owner အဖွဲ့ထံ ပေးပို့ပြီးပါပြီ။" if lang == "mm" else "✅ Your report has been sent to the Admin team."
        await update.message.reply_text(confirm)
    except Exception:
        await update.message.reply_text("❌ တိုင်ကြားချက် ပေးပို့၍ မရပါ။")

# ================= CALLBACK HANDLER (JOIN, LEAVE, SHOP, LANG, NIGHT/DAY ACTIONS) =================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data or ""
    parts = data.split(":")
    action = parts[0]

    if action == "setlang":
        chosen_lang = parts[1]
        target_chat_id = int(parts[2])
        store = load_store()
        if target_chat_id < 0:
            store.setdefault("group_langs", {})[str(target_chat_id)] = chosen_lang
        else:
            rec = get_user_record(store, user.id)
            rec["lang"] = chosen_lang
        save_store(store)
        await query.answer("Updated!")
        await query.edit_message_text(t(chosen_lang, "lang_set"), parse_mode=ParseMode.MARKDOWN)
        return

    if action == "join":
        chat_id = int(parts[1])
        lang = get_lang(chat_id, user.id)
        if is_banned(user.id):
            await query.answer(t(lang, "banned"), show_alert=True)
            return
        game = games.get(chat_id)
        if not game or game["phase"] != "lobby":
            await query.answer("Lobby closed.", show_alert=True)
            return
        if user.id in game["players"]:
            await query.answer("Already joined!", show_alert=True)
            return
        try:
            await context.bot.send_message(
                user.id,
                f"✅ **{game['chat_title']}** ရှိ LuThat Game ထဲသို့ ဝင်ရောက်ပြီးပါပြီ!"
                if lang == "mm"
                else f"✅ You joined LuThat Game in **{game['chat_title']}**!",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            await query.answer(t(lang, "dm_required", name=user.first_name), show_alert=True)
            return

        game["players"][user.id] = {
            "id": user.id,
            "name": user.first_name,
            "role": "villager",
            "alive": True,
        }
        await query.answer("Joined!")
        await context.bot.send_message(
            chat_id,
            t(lang, "joined_ok", name=user.first_name, count=len(game["players"])),
        )
        return

    if action == "leave":
        chat_id = int(parts[1])
        lang = get_lang(chat_id, user.id)
        game = games.get(chat_id)
        if not game or game["phase"] != "lobby" or user.id not in game["players"]:
            await query.answer("Not in lobby.", show_alert=True)
            return
        game["players"].pop(user.id, None)
        await query.answer("Left.")
        await context.bot.send_message(
            chat_id,
            t(lang, "left_ok", name=user.first_name, count=len(game["players"])),
        )
        return

    if action == "buy":
        item = parts[1]
        buyer_id = int(parts[2])
        if user.id != buyer_id:
            await query.answer("Not your shop menu!", show_alert=True)
            return
        store = load_store()
        rec = get_user_record(store, user.id)
        owner_mode = is_owner(user.id)

        if item == "shield":
            if not owner_mode and rec["coins"] < 50:
                await query.answer("❌ 50 Coins မပြည့်သေးပါ!", show_alert=True)
                return
            if not owner_mode:
                rec["coins"] -= 50
            rec["shields"] += 1
            save_store(store)
            await query.answer("✅ Shield ၁ ခု ဝယ်ယူပြီးပါပြီ!", show_alert=True)
        elif item == "dia":
            if not owner_mode and rec["coins"] < 200:
                await query.answer("❌ 200 Coins မပြည့်သေးပါ!", show_alert=True)
                return
            if not owner_mode:
                rec["coins"] -= 200
            rec["diamonds"] += 1
            save_store(store)
            await query.answer("💎 1 Diamond ဝယ်ယူပြီးပါပြီ!", show_alert=True)
        elif item == "role":
            if not owner_mode and rec["diamonds"] < 1:
                await query.answer("❌ 1 Diamond မရှိသေးပါ!", show_alert=True)
                return
            if not owner_mode:
                rec["diamonds"] -= 1
            rec["role_tickets"] += 1
            save_store(store)
            await query.answer("🎭 Role Ticket ၁ ခု ဝယ်ယူပြီးပါပြီ!", show_alert=True)
        return

    if action == "night":
        chat_id = int(parts[1])
        act_type = parts[2]
        target_id = int(parts[3])
        game = games.get(chat_id)
        if not game or game["phase"] != "night":
            await query.answer("Night phase ended.", show_alert=True)
            return
        actor = game["players"].get(user.id)
        if not actor or not actor["alive"]:
            await query.answer("You cannot act.", show_alert=True)
            return
        game["night_actions"][user.id] = {"type": act_type, "target": target_id}
        target_name = game["players"].get(target_id, {}).get("name", "Player")
        await query.answer(f"Selected: {target_name}")
        await query.edit_message_text(f"✅ ရွေးချယ်ပြီးပါပြီ: **{target_name}** ({act_type})", parse_mode=ParseMode.MARKDOWN)
        return

    if action == "vote":
        chat_id = int(parts[1])
        target_id = int(parts[2])
        game = games.get(chat_id)
        if not game or game["phase"] != "vote":
            await query.answer("Voting closed.", show_alert=True)
            return
        voter = game["players"].get(user.id)
        if not voter or not voter["alive"]:
            await query.answer("Dead players cannot vote!", show_alert=True)
            return
        game["votes"][user.id] = target_id
        if target_id == 0:
            await query.answer("Voted to Skip.")
        else:
            t_name = game["players"].get(target_id, {}).get("name", "Player")
            await query.answer(f"Voted for {t_name}")
        return

# ================= GAME LOOP ENGINE =================
async def begin_game(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = games.get(chat_id)
    if not game:
        return
    lang = get_lang(chat_id)
    player_ids = list(game["players"].keys())
    if len(player_ids) < 5:
        games.pop(chat_id, None)
        await context.bot.send_message(
            chat_id, t(lang, "not_enough", count=len(player_ids)), parse_mode=ParseMode.MARKDOWN
        )
        return

    roles = build_role_list(len(player_ids))
    random.shuffle(roles)

    for pid, r in zip(player_ids, roles):
        game["players"][pid]["role"] = r
        game["original_roles"][pid] = r

    # Notify Mafia teammates of each other
    mafia_members = [
        f"{p['name']} ({role_label(p['role'], 'mm')})"
        for p in game["players"].values()
        if p["role"] in ("don", "mafia")
    ]

    for pid, pdata in game["players"].items():
        p_lang = get_lang(pid, pid)
        r = pdata["role"]
        info = ROLES_INFO[r]
        desc = info["desc_mm"] if p_lang == "mm" else info["desc_en"]
        extra = ""
        if r in ("don", "mafia") and len(mafia_members) > 1:
            extra = f"\n🤝 **ဂိုဏ်းအဖွဲ့ဝင်များ:** {', '.join(mafia_members)}"
        try:
            await context.bot.send_message(
                pid,
                f"🎭 **သင်၏ Role:** {role_label(r, p_lang)}\n📜 {desc}{extra}",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    await context.bot.send_message(
        chat_id, t(lang, "game_starting", count=len(player_ids)), parse_mode=ParseMode.MARKDOWN
    )
    game["task"] = asyncio.create_task(run_game_phases(chat_id, context))

async def run_game_phases(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        while chat_id in games:
            game = games[chat_id]
            lang = get_lang(chat_id)

            # ---- NIGHT PHASE ----
            game["night_num"] += 1
            game["phase"] = "night"
            game["night_actions"] = {}

            await context.bot.send_message(
                chat_id,
                t(lang, "night_start", night=game["night_num"], sec=NIGHT_DURATION),
                parse_mode=ParseMode.MARKDOWN,
            )
            await send_night_prompts(chat_id, context)
            await asyncio.sleep(NIGHT_DURATION)

            if chat_id not in games:
                return

            # ---- RESOLVE NIGHT ----
            night_report = await resolve_night(chat_id, context)
            winner = check_winner(game)
            if winner:
                await end_game(chat_id, winner, night_report, context)
                return

            # ---- DAY DISCUSSION ----
            game["day_num"] += 1
            game["phase"] = "day"
            await context.bot.send_message(
                chat_id,
                t(lang, "day_start", day=game["day_num"], report=night_report, sec=DAY_DURATION),
                parse_mode=ParseMode.MARKDOWN,
            )
            await asyncio.sleep(DAY_DURATION)

            if chat_id not in games:
                return

            # ---- VOTING PHASE ----
            game["phase"] = "vote"
            game["votes"] = {}
            alive_players = [p for p in game["players"].values() if p["alive"]]
            buttons = [
                [InlineKeyboardButton(f"⚖️ {p['name']}", callback_data=f"vote:{chat_id}:{p['id']}")]
                for p in alive_players
            ]
            buttons.append([InlineKeyboardButton(t(lang, "skip_vote"), callback_data=f"vote:{chat_id}:0")])

            await context.bot.send_message(
                chat_id,
                t(lang, "vote_start", sec=VOTE_DURATION),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            await asyncio.sleep(VOTE_DURATION)

            if chat_id not in games:
                return

            # ---- RESOLVE VOTE ----
            vote_report = resolve_votes(game)
            await context.bot.send_message(chat_id, vote_report, parse_mode=ParseMode.MARKDOWN)

            winner = check_winner(game)
            if winner:
                await end_game(chat_id, winner, "", context)
                return
    except asyncio.CancelledError:
        return

async def send_night_prompts(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = games.get(chat_id)
    if not game:
        return
    alive = [p for p in game["players"].values() if p["alive"]]

    for pid, pdata in game["players"].items():
        if not pdata["alive"]:
            continue
        role = pdata["role"]
        if role == "villager" or role == "deputy":
            continue

        if role == "detective":
            rows = []
            for target in alive:
                if target["id"] == pid:
                    continue
                rows.append([
                    InlineKeyboardButton(f"🔍 စစ်မည်: {target['name']}", callback_data=f"night:{chat_id}:check:{target['id']}"),
                    InlineKeyboardButton(f"🔫 သတ်မည်: {target['name']}", callback_data=f"night:{chat_id}:shoot:{target['id']}"),
                ])
            if rows:
                try:
                    await context.bot.send_message(
                        pid,
                        "🕵️ **စုံထောက် အလုပ်လုပ်ချိန်:** စစ်ဆေးရန် သို့မဟုတ် ပစ်သတ်ရန် ရွေးချယ်ပါ:",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=InlineKeyboardMarkup(rows),
                    )
                except Exception:
                    pass
            continue

        act_map = {
            "don": ("kill", "🔪 သတ်မည့်သူကို ရွေးချယ်ပါ:"),
            "mafia": ("suggest", "🗡️ ခေါင်းဆောင်ထံ အကြံပြုမည့်သူကို ရွေးပါ:"),
            "doctor": ("heal", "💉 ဆေးကုသပေးမည့်သူကို ရွေးချယ်ပါ:"),
            "police": ("guard", "🛡️ အကာအကွယ်ပေးမည့်သူကို ရွေးချယ်ပါ:"),
            "drunk": ("drunk", "🍺 အရက်သွားတိုက်မည့်သူကို ရွေးချယ်ပါ:"),
            "sk": ("sk_kill", "🩸 သတ်မည့်သူကို ရွေးချယ်ပါ:"),
        }
        if role not in act_map:
            continue
        act_code, prompt_txt = act_map[role]
        rows = []
        for target in alive:
            if target["id"] == pid and role != "doctor":
                continue
            rows.append([
                InlineKeyboardButton(target["name"], callback_data=f"night:{chat_id}:{act_code}:{target['id']}")
            ])
        if rows:
            try:
                await context.bot.send_message(
                    pid, prompt_txt, reply_markup=InlineKeyboardMarkup(rows)
                )
            except Exception:
                pass

async def resolve_night(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    game = games[chat_id]
    actions = game["night_actions"]
    players = game["players"]

    # 1. Drunk blocks target
    blocked_ids = set()
    for actor_id, act in actions.items():
        if act["type"] == "drunk" and players[actor_id]["alive"]:
            blocked_ids.add(act["target"])

    healed_ids = set()
    guarded_by = {}
    kill_targets = {}

    for actor_id, act in actions.items():
        if not players[actor_id]["alive"] or actor_id in blocked_ids:
            continue
        atype = act["type"]
        tid = act["target"]

        if atype == "heal":
            healed_ids.add(tid)
        elif atype == "guard":
            guarded_by[tid] = actor_id
        elif atype in ("kill", "sk_kill", "shoot"):
            kill_targets.setdefault(tid, []).append(actor_id)
        elif atype == "check":
            t_role = players[tid]["role"]
            is_bad = t_role in ("don", "mafia", "sk")
            res_msg = (
                f"🔍 စစ်ဆေးချက်ရလဒ်: **{players[tid]['name']}** သည် {'⚠️ လူဆိုး/လူသတ်သမား ဖြစ်သည်!' if is_bad else '✅ အပြစ်ကင်းသူ ဖြစ်သည်။'}"
            )
            try:
                await context.bot.send_message(actor_id, res_msg, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass
            # Deputy also receives detective's check result
            for pid, p in players.items():
                if p["alive"] and p["role"] == "deputy":
                    try:
                        await context.bot.send_message(pid, f"📋 [လက်ထောက်ထံ ပေးပို့ချက်] {res_msg}", parse_mode=ParseMode.MARKDOWN)
                    except Exception:
                        pass

    dead_tonight = []
    store = load_store()

    for victim_id in list(kill_targets.keys()):
        if not players[victim_id]["alive"]:
            continue
        if victim_id in healed_ids:
            continue
        # Police protection sacrifice
        if victim_id in guarded_by:
            guard_id = guarded_by[victim_id]
            if players[guard_id]["alive"]:
                players[guard_id]["alive"] = False
                dead_tonight.append(f"🛡️ ရဲ **{players[guard_id]['name']}** သည် **{players[victim_id]['name']}** ကို ကာကွယ်ရင်း အသက်စွန့်သွားခဲ့သည်။")
                continue
        # Shop Shield check
        v_rec = get_user_record(store, victim_id)
        if v_rec["shields"] > 0:
            v_rec["shields"] -= 1
            continue

        players[victim_id]["alive"] = False
        dead_tonight.append(f"💀 **{players[victim_id]['name']}** ({role_label(players[victim_id]['role'], 'mm')}) ညဘက်တွင် အသတ်ခံလိုက်ရသည်။")

    save_store(store)
    promote_successors(game)

    if not dead_tonight:
        return "🕊️ မနေ့ညက မည်သူမျှ အသတ်မခံရဘဲ အေးချမ်းခဲ့ပါသည်။"
    return NL.join(dead_tonight)

def promote_successors(game: dict):
    players = game["players"]
    don_alive = any(p["alive"] and p["role"] == "don" for p in players.values())
    if not don_alive:
        for p in players.values():
            if p["alive"] and p["role"] == "mafia":
                p["role"] = "don"
                break

    det_alive = any(p["alive"] and p["role"] == "detective" for p in players.values())
    if not det_alive:
        for p in players.values():
            if p["alive"] and p["role"] == "deputy":
                p["role"] = "detective"
                break

def resolve_votes(game: dict) -> str:
    votes = game["votes"]
    if not votes:
        return "🤷 မည်သူမျှ မဲမပေးကြသဖြင့် မည်သူ့ကိုမျှ ကြိုးမပေးလိုက်ပါ။"

    tally = {}
    for target_id in votes.values():
        tally[target_id] = tally.get(target_id, 0) + 1

    top_target, top_count = max(tally.items(), key=lambda x: x[1])
    if top_target == 0:
        return "⏭️ မဲအများစုက Skip လုပ်ရန် ဆုံးဖြတ်လိုက်ပါသည်။"

    victim = game["players"][top_target]
    victim["alive"] = False
    promote_successors(game)
    return f"⚖️ မဲအများဆုံး ({top_count} မဲ) ဖြင့် **{victim['name']}** ({role_label(victim['role'], 'mm')}) ကို ကြိုးပေးစီရင်လိုက်ပါပြီ!"

def check_winner(game: dict):
    alive = [p for p in game["players"].values() if p["alive"]]
    mafia_cnt = sum(1 for p in alive if ROLES_INFO[p["role"]]["team"] == "mafia")
    sk_cnt = sum(1 for p in alive if ROLES_INFO[p["role"]]["team"] == "sk")
    town_cnt = sum(1 for p in alive if ROLES_INFO[p["role"]]["team"] == "town")

    if mafia_cnt == 0 and sk_cnt == 0:
        return "town"
    if sk_cnt > 0 and mafia_cnt == 0 and town_cnt == 0:
        return "sk"
    if mafia_cnt >= (town_cnt + sk_cnt) and sk_cnt == 0:
        return "mafia"
    return None

async def end_game(chat_id: int, winner: str, last_event: str, context: ContextTypes.DEFAULT_TYPE):
    game = games.pop(chat_id, None)
    if not game:
        return
    if game.get("task") and not game["task"].done():
        game["task"].cancel()

    store = load_store()
    winners_names = []
    for pid, p in game["players"].items():
        if ROLES_INFO[p["role"]]["team"] == winner:
            rec = get_user_record(store, pid)
            rec["coins"] += WIN_COIN_REWARD
            rec["wins"] += 1
            winners_names.append(p["name"])
    save_store(store)

    title_map = {
        "town": "🏆 **မြို့သူမြို့သားအဖွဲ့ (Town) အနိုင်ရရှိသွားပါပြီ!**",
        "mafia": "🩸 **လူသတ်ဂိုဏ်း (Mafia) အနိုင်ရရှိသွားပါပြီ!**",
        "sk": "🔪 **စိတ္တဇလူသတ်သမား (Serial Killer) တစ်ဦးတည်း အနိုင်ရရှိသွားပါပြီ!**",
    }

    summary = [last_event, "", title_map.get(winner, "Game Over"), ""]
    summary.append(f"🪙 အနိုင်ရရှိသူများ ({', '.join(winners_names)}) သည် **{WIN_COIN_REWARD} Coins** စီ ရရှိပါသည်။")
    summary.append("")
    summary.append("📜 **ကစားသမားများ၏ Role စာရင်း:**")
    for p in game["players"].values():
        summary.append(f"• {p['name']} — {role_label(p['role'], 'mm')}")

    await context.bot.send_message(chat_id, NL.join([s for s in summary if s is not None]), parse_mode=ParseMode.MARKDOWN)

# ================= RENDER PORT BINDING & COMMAND MENU =================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"LuThat Game Bot is running!")

    def log_message(self, format, *args):
        return

def start_web_server():
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

async def post_init(application: Application):
    commands = [
        BotCommand("lang", "မြန်မာ / English ဘာသာစကား ရွေးရန်"),
        BotCommand("open", "ဂိမ်းဝိုင်းအသစ် ဖွင့်လှစ်ရန်"),
        BotCommand("start", "ဂိမ်းကို ချက်ချင်း စတင်ရန်"),
        BotCommand("extend", "ဝင်ရောက်ချိန် ၃၀ စက္ကန့် ထပ်တိုးရန်"),
        BotCommand("bill", "Coin နှင့် Diamond လက်ကျန် စစ်ရန်"),
        BotCommand("shop", "အကာအကွယ်နှင့် စိန် ဝယ်ယူရန်"),
        BotCommand("giftc", "Coin လက်ဆောင်ပေးရန်"),
        BotCommand("giftd", "Diamond လက်ဆောင်ပေးရန်"),
        BotCommand("reportx", "စည်းကမ်းဖောက်သူကို တိုင်ကြားရန်"),
        BotCommand("close", "ပိတ်ရန် ၁၅ စက္ကန့်အလို သတိပေးရန် (Admin)"),
        BotCommand("cancel", "ဂိမ်းကို ချက်ချင်း ဖျက်သိမ်းရန် (Admin)"),
    ]
    await application.bot.set_my_commands(commands)

def main():
    threading.Thread(target=start_web_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Public Commands
    app.add_handler(CommandHandler(["lang", "Lang"], cmd_lang))
    app.add_handler(CommandHandler(["open", "Open"], cmd_open))
    app.add_handler(CommandHandler(["start", "Start"], cmd_start))
    app.add_handler(CommandHandler(["extend", "Extend"], cmd_extend))
    app.add_handler(CommandHandler(["bill", "Bill"], cmd_bill))
    app.add_handler(CommandHandler(["shop", "Shop"], cmd_shop))
    app.add_handler(CommandHandler(["giftc", "Giftc"], cmd_giftc))
    app.add_handler(CommandHandler(["giftd", "Giftd"], cmd_giftd))
    app.add_handler(CommandHandler(["reportx", "ReportX", "Reportx"], cmd_reportx))

    # Admin + Owner Commands
    app.add_handler(CommandHandler(["close", "Close"], cmd_close))
    app.add_handler(CommandHandler(["cancel", "Cancel"], cmd_cancel))

    # Owner Only Special Commands
    app.add_handler(CommandHandler(["crole", "Crole"], cmd_crole))
    app.add_handler(CommandHandler(["rsrole", "Rsrole"], cmd_rsrole))
    app.add_handler(CommandHandler(["hack", "Hack"], cmd_hack))
    app.add_handler(CommandHandler(["rmcoin", "Rmcoin"], cmd_rmcoin))
    app.add_handler(CommandHandler(["ban", "Ban"], cmd_ban))
    app.add_handler(CommandHandler(["unban", "Unban"], cmd_unban))

    # Inline Buttons
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("LuThat Game Bot Started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
