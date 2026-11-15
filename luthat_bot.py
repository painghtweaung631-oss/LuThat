import os
import json
import time
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
    BotCommandScopeChat,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

# ================= CONFIG =================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
TEST_GROUP_ID = int(os.environ.get("TEST_GROUP_ID", "0"))
JSONBIN_ID = os.environ.get("JSONBIN_ID", "")
JSONBIN_KEY = os.environ.get("JSONBIN_KEY", "")
DATA_FILE = "luthat_data.json"
NL = chr(10)

MIN_PLAYERS = 3          # Minimum 3 players to start & test easily
JOIN_DURATION = 180      # 3 minutes
EXTEND_DURATION = 60     # +1 minute
NIGHT_DURATION = 60      # 60 seconds
DAY_DURATION = 75        # 75 seconds
VOTE_DURATION = 45       # 45 seconds
CONFIRM_DURATION = 25    # 25 seconds for secret 👍 / 👎 confirmation
WIN_COIN_REWARD = 10
DAILY_COOLDOWN = 86400   # 24 hours

# ================= TRANSITION & VICTORY ANIMATIONS (GIF) =================
NIGHT_GIF_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExaG5tM2l0N25uOGE3M2J3MWM5aXh4dnh6aXh4dnh6aXh4dnh6aXh4diZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l41lFw057lAJQMwg0/giphy.gif"
DAY_GIF_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExN2J3MWM5aXh4dnh6aXh4dnh6aXh4dnh6aXh4dnh6aXh4dnh6aXh4diZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7TKz50Rg6C8Z2G1G/giphy.gif"

WIN_GIFS = {
    # 1. Mafia / Don Victory Animation
    "mafia": "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2Z4aXh4dnh6aXh4dnh6aXh4dnh6aXh4dnh6aXh4dnh6aXh4diZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7abKhOpu0NwenH3O/giphy.gif",
    # 2. Pure Villagers / Town Only Victory Animation (when Detective/Deputy are dead or not alive)
    "town_pure": "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExb2J4aXh4dnh6aXh4dnh6aXh4dnh6aXh4dnh6aXh4dnh6aXh4diZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/26tOZ42Mg6pbTUPHW/giphy.gif",
    # 3. Detective + Town Joint Victory Animation (when Detective or Deputy survives with Town)
    "town_det": "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExY3J4aXh4dnh6aXh4dnh6aXh4dnh6aXh4dnh6aXh4dnh6aXh4diZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/l0MYt5jPR6QX5pnqM/giphy.gif",
    # 4. Serial Killer Solo Victory Animation
    "sk": "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZ3R4aXh4dnh6aXh4dnh6aXh4dnh6aXh4dnh6aXh4dnh6aXh4diZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7TKSjRrfIPjeiVyM/giphy.gif",
}

# ================= BOT COMMAND MENUS =================
COMMANDS_EN = [
    BotCommand("lang", "Switch language (English / Myanmar)"),
    BotCommand("role", "View all game roles and abilities"),
    BotCommand("open", "Open a new game lobby (3 mins)"),
    BotCommand("start", "Start the game immediately (min 3 players)"),
    BotCommand("extend", "Extend join timer by 1 minute"),
    BotCommand("quit", "Leave the current game"),
    BotCommand("bill", "Check your balance (or reply to check others)"),
    BotCommand("shop", "Buy Shields, Diamonds, and Role Tickets"),
    BotCommand("dailybox", "Open daily reward box"),
    BotCommand("kiss", "Send a kiss to someone"),
    BotCommand("giftc", "Gift Coins to a player"),
    BotCommand("giftd", "Gift Diamonds to a player"),
    BotCommand("reportx", "Report a rule-breaker"),
    BotCommand("delemsg", "Delete all bot messages in this chat (Admin)"),
    BotCommand("close", "Warn 15s before lobby closes (Admin)"),
    BotCommand("cancel", "Cancel the active game (Admin)"),
]

COMMANDS_MM = [
    BotCommand("lang", "ဘာသာစကား ပြောင်းရန် (English / မြန်မာ)"),
    BotCommand("role", "ပါဝင်သော Role များနှင့် စွမ်းရည်ကြည့်ရန်"),
    BotCommand("open", "ဂိမ်းဝိုင်းအသစ် ဖွင့်လှစ်ရန် (၃ မိနစ်)"),
    BotCommand("start", "ဂိမ်းကို ချက်ချင်း စတင်ရန် (အနည်းဆုံး ၃ ဦး)"),
    BotCommand("extend", "ဝင်ရောက်ချိန် ၁ မိနစ် ထပ်တိုးရန်"),
    BotCommand("quit", "ဂိမ်းထဲမှ နှုတ်ထွက်ရန်"),
    BotCommand("bill", "လက်ကျန်စာရင်း စစ်ရန် (Reply ထောက်ပြီး သူများဟာစစ်နိုင်သည်)"),
    BotCommand("shop", "အကာအကွယ်နှင့် စိန် ဝယ်ယူရန်"),
    BotCommand("dailybox", "နေ့စဉ် ကျပန်းဆုလာဘ် ဖွင့်ယူရန်"),
    BotCommand("kiss", "အနမ်းပေးရန်"),
    BotCommand("giftc", "Coin လက်ဆောင်ပေးရန်"),
    BotCommand("giftd", "Diamond လက်ဆောင်ပေးရန်"),
    BotCommand("reportx", "စည်းကမ်းဖောက်သူကို တိုင်ကြားရန်"),
    BotCommand("delemsg", "Bot ပို့ထားသော စာများအားလုံး ဖျက်ရန် (Admin)"),
    BotCommand("close", "ပိတ်ရန် ၁၅ စက္ကန့်အလို သတိပေးရန် (Admin)"),
    BotCommand("cancel", "ဂိမ်းကို ချက်ချင်း ဖျက်သိမ်းရန် (Admin)"),
]

# ================= ROLE DEFINITIONS =================
ROLES_INFO = {
    "don": {
        "team": "mafia",
        "en": "Mafia Don",
        "mm": "ဂိုဏ်းခေါင်းဆောင် (Don)",
        "desc_en": "Choose and confirm the target to eliminate each night.",
        "desc_mm": "ညဘက်တွင် သတ်မည့်သူကို အတည်ပြု ရွေးချယ်ပိုင်ခွင့်ရှိသည်။",
    },
    "mafia": {
        "team": "mafia",
        "en": "Mafia Member",
        "mm": "ဂိုဏ်းဝင် (Mafia)",
        "desc_en": "Suggest a target at night. You become the new Don if the Don dies.",
        "desc_mm": "ညဘက်တွင် သတ်မည့်သူကို အကြံပြုနိုင်သည်။ ခေါင်းဆောင်သေဆုံးပါက ခေါင်းဆောင်အသစ် ဖြစ်လာမည်။",
    },
    "detective": {
        "team": "town",
        "en": "Detective",
        "mm": "စုံထောက် (Detective)",
        "desc_en": "Investigate or shoot one player each night.",
        "desc_mm": "ညဘက်တွင် တစ်ဦးကို စစ်ဆေးခြင်း သို့မဟုတ် ပစ်သတ်ခြင်း ပြုလုပ်နိုင်သည်။",
    },
    "deputy": {
        "team": "town",
        "en": "Deputy",
        "mm": "လက်ထောက် (Deputy)",
        "desc_en": "Receive the Detective's investigation results. Promote to Detective if they die.",
        "desc_mm": "စုံထောက် စစ်ဆေးသည့်ရလဒ်ကို သိခွင့်ရသည်။ စုံထောက်သေဆုံးပါက စုံထောက်အသစ် ဖြစ်လာမည်။",
    },
    "doctor": {
        "team": "town",
        "en": "Doctor",
        "mm": "ဒေါက်တာ (Doctor)",
        "desc_en": "Heal one player (including yourself) each night.",
        "desc_mm": "ညဘက်တွင် တစ်ဦး (သို့မဟုတ် ကိုယ့်ကိုယ်ကိုယ်) ဆေးကုသပေးနိုင်သည်။",
    },
    "police": {
        "team": "town",
        "en": "Police",
        "mm": "ရဲ (Police)",
        "desc_en": "Guard a player at night. If attacked, you sacrifice yourself to save them.",
        "desc_mm": "ညဘက်တွင် တစ်ဦးကို အကာအကွယ်ပေးနိုင်သည်။ လာသတ်သူရှိပါက သင်က အသက်စွန့်ကာကွယ်မည်။",
    },
    "drunk": {
        "team": "town",
        "en": "Drunk",
        "mm": "အရက်သမား (Drunk)",
        "desc_en": "Visit a player and get them drunk, blocking their night action.",
        "desc_mm": "ညဘက်တွင် တစ်ဦးအိမ်သို့ သွားရောက်အရက်တိုက်နိုင်သည်။ အတိုက်ခံရသူ ညဘက် Action လုပ်မရပါ။",
    },
    "sk": {
        "team": "sk",
        "en": "Serial Killer",
        "mm": "စိတ္တဇလူသတ်သမား (Serial Killer)",
        "desc_en": "Kill one player every night. Be the last one standing to win.",
        "desc_mm": "ညတိုင်း တစ်ဦးကို သီးသန့်လိုက်သတ်နိုင်သည်။ အားလုံးကိုသတ်ပြီး တစ်ဦးတည်းကျန်မှ နိုင်မည်။",
    },
    "villager": {
        "team": "town",
        "en": "Villager",
        "mm": "မြို့သူမြို့သား (Villager)",
        "desc_en": "Discuss and vote to eliminate suspects during the day.",
        "desc_mm": "နေ့ဘက် မဲပေးချိန်တွင် မသင်္ကာသူကို မဲပေးရွေးချယ်ရမည်။",
    },
}

# ================= BILINGUAL TEXTS =================
TEXTS = {
    "en": {
        "welcome": (
            "**LuThat Game Bot**

"
            "• `/Open` — Open a new game lobby in a group
"
            "• `/Role` — View all roles and abilities
"
            "• `/Lang` — Switch language (English / Myanmar)
"
            "• `/Bill` — Check balance | `/Shop` — Buy items | `/Dailybox` — Daily reward

"
            "_Note: Start this bot in DM before joining a game._"
        ),
        "choose_lang": "Select Language / ဘာသာစကား ရွေးချယ်ပါ:",
        "lang_set": "Language set to **English**. All commands and messages in this chat will now use English.",
        "group_only": "This command can only be used in a group.",
        "admin_only": "Only Group Admins and Bot Owner can use this command.",
        "owner_only": "This command is restricted to the Bot Owner.",
        "banned": "You are banned from playing LuThat Game.",
        "game_already": "A game is already active in this group. Use `/Cancel` to stop it.",
        "no_game": "No active game in this group. Use `/Open` to start one.",
        "lobby_header": (
            "**LuThat Game — Lobby Open**

"
            "• Minimum Players: **3**
"
            "• Join Timer: **{sec}s**

"
            "**Joined Players ({count}):**
{plist}"
        ),
        "no_players_yet": "_No players yet_",
        "join_btn": "Join Game",
        "dm_required": "{name} — Please open the Bot DM and press Start first.",
        "not_enough": "Not enough players (minimum 3, current: {count}). Game cancelled.",
        "extended": "Join timer extended by **60s**. Remaining: **{sec}s**.",
        "closing_15": "**Warning:** Only **15 seconds** left before registration closes.",
        "cancelled": "The game has been cancelled.",
        "game_starting": "**The game begins!**
Roles and descriptions have been sent to **{count} players** in Bot DM.",
        "check_role_btn": "Check your role",
        "go_to_bot_btn": "Go to bot",
        "night_start": "**Night {night} — The Night Falls**
Players with night abilities, check your Bot DM and make your choice within **{sec} seconds**.",
        "day_start": "**Day {day}**

{report}

Discussion time: **{sec} seconds**.",
        "vote_start": "**Voting Phase**
Vote for the most suspicious player within **{sec} seconds**:",
        "skip_vote": "Skip Vote",
        "confirm_lynch_prompt": (
            "**Final Verdict on {name}**
"
            "Should **{name}** be eliminated? Vote secretly below within **{sec} seconds** (voters remain anonymous):

"
            "👍 Execute: **{up}**  |  👎 Spare: **{down}**"
        ),
        "confirm_up_btn": "👍 Execute",
        "confirm_down_btn": "👎 Spare",
    },
    "mm": {
        "welcome": (
            "**LuThat Game Bot**

"
            "• `/Open` — Group ထဲတွင် ဂိမ်းဖွင့်ရန်
"
            "• `/Role` — Role များနှင့် စွမ်းရည်ကြည့်ရန်
"
            "• `/Lang` — ဘာသာစကား ပြောင်းရန် (English / မြန်မာ)
"
            "• `/Bill` — လက်ကျန်စစ်ရန် | `/Shop` — ဆိုင်ဝင်ရန် | `/Dailybox` — နေ့စဉ်ဆုယူရန်

"
            "_မှတ်ချက်: ဂိမ်းထဲမဝင်မီ ဤ Bot Chat တွင် Start နှိပ်ထားရန် လိုအပ်ပါသည်။_"
        ),
        "choose_lang": "Select Language / ဘာသာစကား ရွေးချယ်ပါ:",
        "lang_set": "ဘာသာစကားကို **မြန်မာဘာသာ** သို့ ပြောင်းလဲပြီးပါပြီ။ ဤ Chat ရှိ Command နှင့် စာသားအားလုံး မြန်မာလို ပြသပေးပါမည်။",
        "group_only": "ဤ Command ကို Group ထဲတွင်သာ အသုံးပြုနိုင်ပါသည်။",
        "admin_only": "ဤ Command ကို Group Admin နှင့် Bot Owner သာ အသုံးပြုနိုင်ပါသည်။",
        "owner_only": "ဤ Command ကို Bot Owner တစ်ဦးတည်းသာ အသုံးပြုနိုင်ပါသည်။",
        "banned": "သင်သည် ဂိမ်းကစားခွင့် ပိတ်ပင်ခံထားရပါသည်။",
        "game_already": "လက်ရှိ ဂိမ်းဝိုင်းတစ်ခု ရှိနေပါပြီ။ ဖျက်သိမ်းလိုပါက `/Cancel` နှိပ်ပါ။",
        "no_game": "လက်ရှိ ဖွင့်ထားသော ဂိမ်းဝိုင်း မရှိပါ။ `/Open` ဖြင့် အသစ်ဖွင့်ပါ။",
        "lobby_header": (
            "**LuThat Game — ဂိမ်းဝိုင်း ဖွင့်လှစ်လိုက်ပါပြီ**

"
            "• အနည်းဆုံး ကစားသမား: **၃ ဦး**
"
            "• ဝင်ရောက်ရန် အချိန်: **{sec} စက္ကန့်**

"
            "**ပါဝင်ထားသူများ ({count} ဦး):**
{plist}"
        ),
        "no_players_yet": "_မရှိသေးပါ_",
        "join_btn": "Join Game",
        "dm_required": "{name} — Bot DM ထဲသို့ သွားပြီး Start အရင်နှိပ်ပေးပါ။",
        "not_enough": "ကစားသမား အနည်းဆုံး ၃ ဦး မပြည့်သေးပါ (လက်ရှိ: {count} ဦး)။ ဂိမ်းဖျက်သိမ်းလိုက်ပါသည်။",
        "extended": "ဝင်ရောက်ချိန်ကို **၆၀ စက္ကန့်** ထပ်တိုးလိုက်ပါပြီ။ ကျန်ရှိချိန်: **{sec} စက္ကန့်**။",
        "closing_15": "**သတိပေးချက်:** ဝင်ရောက်ခြင်း ပိတ်ရန် **၁၅ စက္ကန့်** သာ လိုပါတော့သည်။",
        "cancelled": "ဂိမ်းဝိုင်းကို ဖျက်သိမ်းလိုက်ပါပြီ။",
        "game_starting": "**ဂိမ်းစတင်ပါပြီ!**
ကစားသမား **{count} ဦး** ၏ Bot DM ဆီသို့ Role များ ပေးပို့လိုက်ပါပြီ။",
        "check_role_btn": "သင်၏ Role ကြည့်ရန်",
        "go_to_bot_btn": "Bot DM သို့သွားရန်",
        "night_start": "**ည {night} — ညအချိန် ရောက်ရှိလာပါပြီ**
အထူး Role ရှိသူများ Bot DM ထဲတွင် မိမိတို့ လုပ်ဆောင်ချက်ကို **{sec} စက္ကန့်** အတွင်း ရွေးချယ်ပါ။",
        "day_start": "**နေ့ {day}**

{report}

ဆွေးနွေးရန် အချိန်: **{sec} စက္ကန့်**။",
        "vote_start": "**မဲပေးချိန်**
မသင်္ကာသူ တစ်ဦးကို **{sec} စက္ကန့်** အတွင်း မဲပေးရွေးချယ်ပါ:",
        "skip_vote": "မဲမပေးဘဲ ကျော်မည် (Skip)",
        "confirm_lynch_prompt": (
            "**{name} အပေါ် နောက်ဆုံး အတည်ပြုချက်**
"
            "**{name}** ကို ကြိုးပေးသင့်/မသင့် လျှို့ဝှက်မဲပေးပါ (ဘယ်သူ ဘာနှိပ်မှန်း မမြင်ရပါ) — အချိန် **{sec} စက္ကန့်**:

"
            "👍 ကြိုးပေးမည်: **{up}**  |  👎 လွှတ်ပေးမည်: **{down}**"
        ),
        "confirm_up_btn": "👍 ကြိုးပေးမည်",
        "confirm_down_btn": "👎 လွှတ်ပေးမည်",
    },
}

# ================= PERSISTENT STORAGE & LANGUAGE RESOLVER =================
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
            "lang": "en",
            "wins": 0,
            "last_daily": 0,
        }
    if "last_daily" not in store["users"][uid]:
        store["users"][uid]["last_daily"] = 0
    return store["users"][uid]

def get_chat_lang(chat_id: int, user_id: int = None) -> str:
    store = load_store()
    if chat_id < 0:
        return store.get("group_langs", {}).get(str(chat_id), "en")
    if user_id:
        return get_user_record(store, user_id).get("lang", "en")
    return "en"

def t(lang: str, key: str, **kwargs) -> str:
    base = TEXTS.get(lang, TEXTS["en"]).get(key, key)
    return base.format(**kwargs) if kwargs else base

def role_label(role_key: str, lang: str) -> str:
    info = ROLES_INFO.get(role_key, ROLES_INFO["villager"])
    return info["mm"] if lang == "mm" else info["en"]

# Track bot messages for /delemsg
bot_msg_history = {}
BOT_USERNAME = ""

def record_bot_msg(chat_id: int, message_id: int):
    bot_msg_history.setdefault(chat_id, []).append(message_id)
    if len(bot_msg_history[chat_id]) > 250:
        bot_msg_history[chat_id] = bot_msg_history[chat_id][-250:]

async def send_tracked(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, **kwargs):
    msg = await context.bot.send_message(chat_id, text, **kwargs)
    record_bot_msg(chat_id, msg.message_id)
    return msg

async def send_anim_tracked(context: ContextTypes.DEFAULT_TYPE, chat_id: int, anim_url: str, caption: str, **kwargs):
    try:
        msg = await context.bot.send_animation(
            chat_id=chat_id,
            animation=anim_url,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            **kwargs,
        )
        record_bot_msg(chat_id, msg.message_id)
        return msg
    except Exception:
        return await send_tracked(context, chat_id, caption, parse_mode=ParseMode.MARKDOWN, **kwargs)

async def reply_tracked(update: Update, text: str, **kwargs):
    msg = await update.message.reply_text(text, **kwargs)
    record_bot_msg(update.effective_chat.id, msg.message_id)
    return msg

# ================= ACTIVE GAMES STATE =================
games = {}

def format_lobby_text(game: dict, lang: str) -> str:
    players = list(game["players"].values())
    if players:
        plist = NL.join(f"{idx}. {p['name']}" for idx, p in enumerate(players, 1))
    else:
        plist = t(lang, "no_players_yet")
    return t(
        lang,
        "lobby_header",
        sec=max(0, game["time_left"]),
        count=len(players),
        plist=plist,
    )

def lobby_keyboard(chat_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "join_btn"), callback_data=f"join:{chat_id}")]
    ])

def bot_dm_button(label: str) -> InlineKeyboardMarkup:
    url = f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else "https://t.me/"
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, url=url)]])

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

# ================= ROLE ASSIGNMENT LOGIC (SUPPORTS 3+ PLAYERS) =================
def build_role_list(count: int) -> list:
    if count == 3:
        return ["don", "detective", "doctor"]
    elif count == 4:
        return ["don", "detective", "doctor", "villager"]
    elif count == 5:
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

# ================= COMMANDS =================
async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_chat_lang(chat.id, user.id)
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("English", callback_data=f"setlang:en:{chat.id}"),
            InlineKeyboardButton("မြန်မာ", callback_data=f"setlang:mm:{chat.id}"),
        ]
    ])
    await reply_tracked(update, t(lang, "choose_lang"), reply_markup=kb)

async def cmd_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_chat_lang(chat.id, user.id)

    header = "**LuThat Game — Roles & Abilities**" if lang == "en" else "**LuThat Game — ပါဝင်သော Role များနှင့် စွမ်းရည်များ**"
    lines = [header, ""]
    for r_key, info in ROLES_INFO.items():
        title = info["en"] if lang == "en" else info["mm"]
        desc = info["desc_en"] if lang == "en" else info["desc_mm"]
        lines.append(f"• **{title}** (`{r_key}`): {desc}")

    await reply_tracked(update, NL.join(lines), parse_mode=ParseMode.MARKDOWN)

async def cmd_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_chat_lang(chat.id, user.id)

    if chat.type == "private":
        await reply_tracked(update, t(lang, "group_only"))
        return

    if is_banned(user.id):
        await reply_tracked(update, t(lang, "banned"))
        return

    if chat.id in games:
        await reply_tracked(update, t(lang, "game_already"))
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
        "confirm_votes": {},
        "confirm_target": None,
        "confirm_msg_id": None,
        "task": None,
        "lobby_msg_id": None,
    }
    games[chat.id] = game

    msg = await reply_tracked(
        update,
        format_lobby_text(game, lang),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=lobby_keyboard(chat.id, lang),
    )
    game["lobby_msg_id"] = msg.message_id
    game["task"] = asyncio.create_task(lobby_countdown(chat.id, context))

async def refresh_lobby_message(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = games.get(chat_id)
    if not game or game["phase"] != "lobby" or not game.get("lobby_msg_id"):
        return
    lang = get_chat_lang(chat_id)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=game["lobby_msg_id"],
            text=format_lobby_text(game, lang),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=lobby_keyboard(chat_id, lang),
        )
    except Exception:
        pass

async def lobby_countdown(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        while chat_id in games and games[chat_id]["phase"] == "lobby":
            await asyncio.sleep(1)
            game = games.get(chat_id)
            if not game or game["phase"] != "lobby":
                return
            game["time_left"] -= 1
            if game["time_left"] == 15:
                lang = get_chat_lang(chat_id)
                await send_tracked(context, chat_id, t(lang, "closing_15"), parse_mode=ParseMode.MARKDOWN)
            if game["time_left"] <= 0:
                await begin_game(chat_id, context)
                return
    except asyncio.CancelledError:
        return

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_chat_lang(chat.id, user.id)

    if chat.type == "private":
        await reply_tracked(update, t(lang, "welcome"), parse_mode=ParseMode.MARKDOWN)
        return

    game = games.get(chat.id)
    if not game or game["phase"] != "lobby":
        await reply_tracked(update, t(lang, "no_game"))
        return

    if len(game["players"]) < MIN_PLAYERS:
        await reply_tracked(
            update,
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
    lang = get_chat_lang(chat.id, user.id)

    if chat.type == "private":
        await reply_tracked(update, t(lang, "group_only"))
        return

    game = games.get(chat.id)
    if not game or game["phase"] != "lobby":
        await reply_tracked(update, t(lang, "no_game"))
        return

    game["time_left"] += EXTEND_DURATION
    await refresh_lobby_message(chat.id, context)
    await reply_tracked(update, t(lang, "extended", sec=game["time_left"]), parse_mode=ParseMode.MARKDOWN)

async def cmd_quit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_chat_lang(chat.id, user.id)

    if chat.type == "private":
        await reply_tracked(update, t(lang, "group_only"))
        return

    game = games.get(chat.id)
    if not game or user.id not in game["players"]:
        msg = "You are not in an active game." if lang == "en" else "သင်သည် လက်ရှိဂိမ်းထဲတွင် ပါဝင်နေခြင်း မရှိပါ။"
        await reply_tracked(update, msg)
        return

    if game["phase"] == "lobby":
        game["players"].pop(user.id, None)
        await refresh_lobby_message(chat.id, context)
        msg = f"{user.first_name} left the lobby." if lang == "en" else f"{user.first_name} ဂိမ်းဝိုင်းထဲမှ ထွက်သွားပါသည်။"
        await reply_tracked(update, msg)
        return

    pdata = game["players"][user.id]
    if not pdata["alive"]:
        msg = "You are already dead." if lang == "en" else "သင်သည် သေဆုံးပြီးသား ဖြစ်ပါသည်။"
        await reply_tracked(update, msg)
        return

    pdata["alive"] = False
    r_name = role_label(pdata["role"], lang)
    quit_msg = (
        f"**{user.first_name}** ({r_name}) quit the game and died."
        if lang == "en"
        else f"**{user.first_name}** ({r_name}) သည် ဂိမ်းထဲမှ နှုတ်ထွက်သွားသဖြင့် သေဆုံးသွားပါပြီ။"
    )
    await reply_tracked(update, quit_msg, parse_mode=ParseMode.MARKDOWN)
    promote_successors(game)

    winner = check_winner(game)
    if winner:
        await end_game(chat.id, winner, "", context)

async def cmd_delemsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_chat_lang(chat.id, user.id)

    if chat.type != "private" and not await is_group_admin_or_owner(update, context):
        await reply_tracked(update, t(lang, "admin_only"))
        return

    msg_ids = bot_msg_history.get(chat.id, [])
    deleted_count = 0
    for mid in list(msg_ids):
        try:
            await context.bot.delete_message(chat_id=chat.id, message_id=mid)
            deleted_count += 1
        except Exception:
            pass
    bot_msg_history[chat.id] = []

    try:
        await update.message.delete()
    except Exception:
        pass

    done_txt = (
        f"Cleared {deleted_count} bot messages."
        if lang == "en"
        else f"Bot ပို့ထားသော စာ {deleted_count} စောင်ကို ရှင်းလင်းဖျက်သိမ်းပြီးပါပြီ။"
    )
    notice = await context.bot.send_message(chat.id, done_txt)
    await asyncio.sleep(4)
    try:
        await notice.delete()
    except Exception:
        pass

async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_chat_lang(chat.id, user.id)

    if chat.type == "private":
        await reply_tracked(update, t(lang, "group_only"))
        return

    if not await is_group_admin_or_owner(update, context):
        await reply_tracked(update, t(lang, "admin_only"))
        return

    game = games.get(chat.id)
    if not game or game["phase"] != "lobby":
        await reply_tracked(update, t(lang, "no_game"))
        return

    game["time_left"] = 15
    await reply_tracked(update, t(lang, "closing_15"), parse_mode=ParseMode.MARKDOWN)

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_chat_lang(chat.id, user.id)

    if chat.type == "private":
        await reply_tracked(update, t(lang, "group_only"))
        return

    if not await is_group_admin_or_owner(update, context):
        await reply_tracked(update, t(lang, "admin_only"))
        return

    game = games.get(chat.id)
    if not game:
        await reply_tracked(update, t(lang, "no_game"))
        return

    if game.get("task") and not game["task"].done():
        game["task"].cancel()
    games.pop(chat.id, None)
    await reply_tracked(update, t(lang, "cancelled"))

# ================= SOCIAL & DAILY REWARD (/Kiss, /Dailybox) =================
async def cmd_kiss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    lang = get_chat_lang(update.effective_chat.id, sender.id)

    if not update.message.reply_to_message:
        msg = "Reply to someone's message and type `/Kiss`." if lang == "en" else "အနမ်းပေးလိုသူ၏ စာကို Reply ပြန်ပြီး `/Kiss` ဟု ရိုက်ပါ။"
        await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)
        return

    target = update.message.reply_to_message.from_user
    if target.id == sender.id:
        msg = f"**{sender.first_name}** blew a kiss to themselves." if lang == "en" else f"**{sender.first_name}** က ကိုယ့်ကိုယ်ကိုယ် အနမ်းပေးလိုက်ပါသည်။"
    else:
        msg = (
            f"💋 **{sender.first_name}** gave a kiss to **{target.first_name}**."
            if lang == "en"
            else f"💋 **{sender.first_name}** က **{target.first_name}** ကို အနမ်းပေးလိုက်ပါသည်။"
        )
    await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_dailybox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_chat_lang(update.effective_chat.id, user.id)
    store = load_store()
    rec = get_user_record(store, user.id)

    now = int(time.time())
    elapsed = now - rec.get("last_daily", 0)
    if not is_owner(user.id) and elapsed < DAILY_COOLDOWN:
        rem = DAILY_COOLDOWN - elapsed
        hrs = rem // 3600
        mins = (rem % 3600) // 60
        msg = (
            f"Already claimed today. Try again in **{hrs}h {mins}m**."
            if lang == "en"
            else f"ယနေ့အတွက် Daily Box ဖွင့်ပြီးပါပြီ။ နောက်ထပ် **{hrs} နာရီ {mins} မိနစ်** ကြာမှ ပြန်ဖွင့်နိုင်ပါမည်။"
        )
        await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)
        return

    rec["last_daily"] = now
    won_coins = random.randint(15, 60)
    rec["coins"] += won_coins

    lucky_dia = 1 if random.random() < 0.15 else 0
    rec["diamonds"] += lucky_dia
    save_store(store)

    if lucky_dia > 0:
        msg = (
            f"**{user.first_name} — Daily Box**
• Coins: **+{won_coins}**
• Bonus: **+1 Diamond**"
            if lang == "en"
            else f"**{user.first_name} — Daily Box**
• Coins: **+{won_coins}**
• အထူးဆု: **+1 Diamond**"
        )
    else:
        msg = (
            f"**{user.first_name} — Daily Box**
• Coins: **+{won_coins}**"
            if lang == "en"
            else f"**{user.first_name} — Daily Box**
• Coins: **+{won_coins}**"
        )
    await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)

# ================= ECONOMY & SHOP (/Bill, /Shop, /Giftc, /Giftd, /Rmcoin) =================
async def cmd_bill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requester = update.effective_user
    lang = get_chat_lang(update.effective_chat.id, requester.id)

    target_user = update.message.reply_to_message.from_user if update.message.reply_to_message else requester
    store = load_store()
    rec = get_user_record(store, target_user.id)
    save_store(store)

    if is_owner(target_user.id):
        coins_str = "Unlimited" if lang == "en" else "အကန့်အသတ်မရှိ"
        dia_str = "Unlimited" if lang == "en" else "အကန့်အသတ်မရှိ"
    else:
        coins_str = str(rec["coins"])
        dia_str = str(rec["diamonds"])

    if lang == "en":
        msg = (
            f"**{target_user.first_name}**
"
            f"• Coins: `{coins_str}`
"
            f"• Diamonds: `{dia_str}`
"
            f"• Shields: `{rec['shields']}`
"
            f"• Wins: `{rec['wins']}`"
        )
    else:
        msg = (
            f"**{target_user.first_name}**
"
            f"• Coins: `{coins_str}`
"
            f"• Diamonds (စိန်): `{dia_str}`
"
            f"• Shields (အကာအကွယ်): `{rec['shields']}`
"
            f"• Wins (နိုင်ပွဲ): `{rec['wins']}`"
        )
    await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_chat_lang(update.effective_chat.id, user.id)
    if lang == "en":
        txt = (
            "**LuThat Game Shop**

"
            "1. **Night Shield** — `50 Coins`
"
            "   _Blocks one night attack automatically._

"
            "2. **1 Diamond** — `200 Coins`
"
            "   _Exchange 200 Coins for 1 Diamond._

"
            "3. **Role Ticket** — `1 Diamond`
"
            "   _Choose your preferred role in a game._"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Buy Shield (50 Coins)", callback_data=f"buy:shield:{user.id}")],
            [InlineKeyboardButton("Buy 1 Diamond (200 Coins)", callback_data=f"buy:dia:{user.id}")],
            [InlineKeyboardButton("Buy Role Ticket (1 Dia)", callback_data=f"buy:role:{user.id}")],
        ])
    else:
        txt = (
            "**LuThat Game Shop (ဈေးဆိုင်)**

"
            "1. **အကာအကွယ် (Shield)** — `50 Coins`
"
            "   _ညဘက် အသတ်ခံရပါက ၁ ကြိမ် အသက်ရှင်ကျန်မည်။_

"
            "2. **1 Diamond (စိန် ၁ လုံး)** — `200 Coins`
"
            "   _Coins 200 ဖြင့် စိန် ၁ လုံး လဲလှယ်နိုင်သည်။_

"
            "3. **Role Ticket** — `1 Diamond`
"
            "   _စိန် ၁ လုံးဖြင့် ဂိမ်းထဲတွင် ကြိုက်နှစ်သက်ရာ Role ရွေးယူနိုင်သည်။_"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Shield ဝယ်မည် (50 Coins)", callback_data=f"buy:shield:{user.id}")],
            [InlineKeyboardButton("1 Diamond ဝယ်မည် (200 Coins)", callback_data=f"buy:dia:{user.id}")],
            [InlineKeyboardButton("Role Ticket ဝယ်မည် (1 Dia)", callback_data=f"buy:role:{user.id}")],
        ])
    await reply_tracked(update, txt, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

async def cmd_giftc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    lang = get_chat_lang(update.effective_chat.id, sender.id)

    if not update.message.reply_to_message or not context.args or not context.args[0].isdigit():
        msg = "Reply to a user and type `/Giftc 50`." if lang == "en" else "လွှဲပေးလိုသူ၏ စာကို Reply ပြန်ပြီး `/Giftc 50` ဟု ရိုက်ပါ။"
        await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)
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
            msg = "Insufficient Coins." if lang == "en" else "သင့်တွင် Coins လုံလောက်စွာ မရှိပါ။"
            await reply_tracked(update, msg)
            return
        s_rec["coins"] -= amount

    t_rec["coins"] += amount
    save_store(store)

    msg = (
        f"**{sender.first_name}** gifted **{amount} Coins** to **{target.first_name}**."
        if lang == "en"
        else f"**{sender.first_name}** က **{target.first_name}** ထံသို့ **{amount} Coins** လက်ဆောင်ပေးလိုက်ပါပြီ။"
    )
    await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_giftd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.effective_user
    lang = get_chat_lang(update.effective_chat.id, sender.id)

    if not update.message.reply_to_message or not context.args or not context.args[0].isdigit():
        msg = "Reply to a user and type `/Giftd 1`." if lang == "en" else "လွှဲပေးလိုသူ၏ စာကို Reply ပြန်ပြီး `/Giftd 1` ဟု ရိုက်ပါ။"
        await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)
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
            msg = "Insufficient Diamonds." if lang == "en" else "သင့်တွင် Diamond လုံလောက်စွာ မရှိပါ။"
            await reply_tracked(update, msg)
            return
        s_rec["diamonds"] -= amount

    t_rec["diamonds"] += amount
    save_store(store)

    msg = (
        f"**{sender.first_name}** gifted **{amount} Diamond(s)** to **{target.first_name}**."
        if lang == "en"
        else f"**{sender.first_name}** က **{target.first_name}** ထံသို့ **{amount} Diamond(s)** လက်ဆောင်ပေးလိုက်ပါပြီ။"
    )
    await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_rmcoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_chat_lang(update.effective_chat.id, user.id)
    if not is_owner(user.id):
        await reply_tracked(update, t(lang, "owner_only"))
        return

    if not update.message.reply_to_message or not context.args or not context.args[0].isdigit():
        msg = "Reply to a user and type `/Rmcoin 50`." if lang == "en" else "Reply ပြန်ပြီး `/Rmcoin 50` ဟု ရိုက်ပါ။"
        await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)
        return

    amount = int(context.args[0])
    target = update.message.reply_to_message.from_user
    store = load_store()
    t_rec = get_user_record(store, target.id)
    t_rec["coins"] = max(0, t_rec["coins"] - amount)
    save_store(store)
    msg = (
        f"Removed **{amount} Coins** from **{target.first_name}** (Balance: {t_rec['coins']})."
        if lang == "en"
        else f"**{target.first_name}** ထံမှ **{amount} Coins** ပြန်လည်သိမ်းယူပြီးပါပြီ (လက်ကျန်: {t_rec['coins']})။"
    )
    await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)

# ================= OWNER SPECIAL COMMANDS & /ReportX =================
async def cmd_crole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_chat_lang(chat.id, user.id)

    if not is_owner(user.id):
        await reply_tracked(update, t(lang, "owner_only"))
        return

    game = games.get(chat.id)
    if not game or game["phase"] == "lobby":
        msg = "Game has not started yet." if lang == "en" else "ဂိမ်းစတင်နေချိန်မှသာ Role ပြောင်းလဲနိုင်ပါသည်။"
        await reply_tracked(update, msg)
        return

    target = update.message.reply_to_message.from_user if update.message.reply_to_message else user
    if target.id not in game["players"]:
        msg = "Player is not in the active game." if lang == "en" else "ထိုသူသည် လက်ရှိဂိမ်းထဲတွင် မပါဝင်ပါ။"
        await reply_tracked(update, msg)
        return

    if not context.args:
        valid = ", ".join(ROLES_INFO.keys())
        msg = f"Usage: `/Crole don`
Available: `{valid}`" if lang == "en" else f"အသုံးပြုပုံ: `/Crole don`
ရရှိနိုင်သော Role များ: `{valid}`"
        await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)
        return

    new_role = context.args[0].lower().strip()
    if new_role not in ROLES_INFO:
        msg = "Invalid role name." if lang == "en" else "Role အမည် မှားယွင်းနေပါသည်။"
        await reply_tracked(update, msg)
        return

    game["players"][target.id]["role"] = new_role
    msg = (
        f"Changed **{target.first_name}**'s role to **{role_label(new_role, lang)}**."
        if lang == "en"
        else f"**{target.first_name}** ၏ Role ကို **{role_label(new_role, lang)}** သို့ ပြောင်းလဲလိုက်ပါပြီ။"
    )
    await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)
    try:
        dm_msg = (
            f"Your role has been changed to **{role_label(new_role, lang)}**."
            if lang == "en"
            else f"သင်၏ Role ကို **{role_label(new_role, lang)}** သို့ ပြောင်းလဲသတ်မှတ်လိုက်ပါသည်။"
        )
        await send_tracked(context, target.id, dm_msg, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass

async def cmd_rsrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_chat_lang(chat.id, user.id)

    if not is_owner(user.id):
        await reply_tracked(update, t(lang, "owner_only"))
        return

    game = games.get(chat.id)
    target_id = update.message.reply_to_message.from_user.id if update.message.reply_to_message else user.id
    if not game or target_id not in game["original_roles"]:
        msg = "Original role record not found." if lang == "en" else "မူလ Role မှတ်တမ်း မတွေ့ပါ။"
        await reply_tracked(update, msg)
        return

    orig = game["original_roles"][target_id]
    game["players"][target_id]["role"] = orig
    t_name = game["players"][target_id]["name"]
    msg = (
        f"Reset **{t_name}**'s role to **{role_label(orig, lang)}**."
        if lang == "en"
        else f"**{t_name}** ၏ Role ကို မူလနဂို **{role_label(orig, lang)}** သို့ ပြန်လည်ထားရှိပြီးပါပြီ။"
    )
    await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_hack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_chat_lang(chat.id, user.id)

    if not is_owner(user.id):
        await reply_tracked(update, t(lang, "owner_only"))
        return

    game = games.get(chat.id)
    if not game or not game["players"]:
        await reply_tracked(update, t(lang, "no_game"))
        return

    lines = [f"**HACK REPORT — {game['chat_title']}**", ""]
    for pid, pdata in game["players"].items():
        status = "Alive" if pdata.get("alive", True) else "Dead"
        r_name = role_label(pdata.get("role", "villager"), lang)
        lines.append(f"• {pdata['name']} (`{pid}`) — **{r_name}** [{status}]")

    dest_id = TEST_GROUP_ID if TEST_GROUP_ID != 0 else user.id
    try:
        await send_tracked(context, dest_id, NL.join(lines), parse_mode=ParseMode.MARKDOWN)
        msg = "Hack data sent to Test Group." if lang == "en" else "Hack အချက်အလက်များကို Test Group ဆီ ပေးပို့ပြီးပါပြီ။"
        await reply_tracked(update, msg)
    except Exception:
        msg = "Failed to send to Test Group." if lang == "en" else "Test Group ဆီ စာပို့၍ မရပါ။"
        await reply_tracked(update, msg)

async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    lang = get_chat_lang(chat.id, user.id)

    if not is_owner(user.id):
        await reply_tracked(update, t(lang, "owner_only"))
        return

    if chat.type == "private":
        await reply_tracked(update, t(lang, "group_only"))
        return

    game = games.get(chat.id)
    if not game:
        await reply_tracked(update, t(lang, "no_game"))
        return

    target_id = None
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])

    if not target_id or target_id not in game["players"]:
        msg = "Reply to a player in the game and type `/Kick`." if lang == "en" else "ဂိမ်းထဲမှ ထုတ်လိုသူ၏ စာကို Reply ပြန်ပြီး `/Kick` နှိပ်ပါ။"
        await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)
        return

    pdata = game["players"][target_id]
    t_name = pdata["name"]

    if game["phase"] == "lobby":
        game["players"].pop(target_id, None)
        await refresh_lobby_message(chat.id, context)
        msg = f"Kicked **{t_name}** from the lobby." if lang == "en" else f"**{t_name}** ကို ဂိမ်းဝိုင်းထဲမှ ထုတ်ပစ်လိုက်ပါပြီ။"
        await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)
        return

    pdata["alive"] = False
    r_name = role_label(pdata["role"], lang)
    msg = (
        f"**{t_name}** ({r_name}) was kicked from the game by Owner."
        if lang == "en"
        else f"Bot Owner က **{t_name}** ({r_name}) ကို ဂိမ်းထဲမှ ထုတ်ပစ်လိုက်ပါပြီ။"
    )
    await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)
    promote_successors(game)
    winner = check_winner(game)
    if winner:
        await end_game(chat.id, winner, "", context)

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_chat_lang(update.effective_chat.id, user.id)
    if not is_owner(user.id):
        await reply_tracked(update, t(lang, "owner_only"))
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
        msg = "Reply to a user or pass a User ID." if lang == "en" else "Ban လိုသူ၏ စာကို Reply ပြန်ပါ သို့မဟုတ် User ID ထည့်ပါ။"
        await reply_tracked(update, msg)
        return

    store = load_store()
    if target_id not in store["banned"]:
        store["banned"].append(target_id)
        save_store(store)
    msg = (
        f"Banned **{target_name}** (`{target_id}`)."
        if lang == "en"
        else f"**{target_name}** (`{target_id}`) ကို ဂိမ်းဆော့ခွင့် ပိတ်ပင်လိုက်ပါပြီ။"
    )
    await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = get_chat_lang(update.effective_chat.id, user.id)
    if not is_owner(user.id):
        await reply_tracked(update, t(lang, "owner_only"))
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
        msg = "Reply to a user or pass a User ID." if lang == "en" else "Unban လိုသူ၏ စာကို Reply ပြန်ပါ သို့မဟုတ် User ID ထည့်ပါ။"
        await reply_tracked(update, msg)
        return

    store = load_store()
    if target_id in store["banned"]:
        store["banned"].remove(target_id)
        save_store(store)
    msg = (
        f"Unbanned **{target_name}** (`{target_id}`)."
        if lang == "en"
        else f"**{target_name}** (`{target_id}`) ကို Ban ပြန်ဖြေပေးလိုက်ပါပြီ။"
    )
    await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_reportx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    reporter = update.effective_user
    lang = get_chat_lang(chat.id, reporter.id)

    if not update.message.reply_to_message:
        msg = "Reply to a message and type `/ReportX reason`." if lang == "en" else "တိုင်ကြားလိုသူ၏ စာကို Reply ထောက်ပြီး `/ReportX အကြောင်းအရာ` ဟု ရိုက်ပို့ပါ။"
        await reply_tracked(update, msg, parse_mode=ParseMode.MARKDOWN)
        return

    accused = update.message.reply_to_message.from_user
    reason = " ".join(context.args).strip() or "(No reason provided)"
    quoted_msg = update.message.reply_to_message.text or "[Media/Sticker]"

    report_text = NL.join([
        "**PLAYER REPORT (/ReportX)**",
        f"• Group: {chat.title or 'Private'} (`{chat.id}`)",
        f"• Reporter: {reporter.first_name} (`{reporter.id}`)",
        f"• Reported User: {accused.first_name} (`{accused.id}`)",
        f"• Message: `{quoted_msg[:200]}`",
        f"• Reason: {reason}",
    ])

    dest_id = TEST_GROUP_ID if TEST_GROUP_ID != 0 else OWNER_ID
    try:
        await send_tracked(context, dest_id, report_text, parse_mode=ParseMode.MARKDOWN)
        confirm = "Your report has been sent." if lang == "en" else "တိုင်ကြားချက်ကို ပေးပို့ပြီးပါပြီ။"
        await reply_tracked(update, confirm)
    except Exception:
        msg = "Failed to send report." if lang == "en" else "တိုင်ကြားချက် ပေးပို့၍ မရပါ။"
        await reply_tracked(update, msg)

# ================= CALLBACK HANDLER =================
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

        # Update slash command menu language immediately for this chat
        try:
            cmds = COMMANDS_MM if chosen_lang == "mm" else COMMANDS_EN
            await context.bot.set_my_commands(cmds, scope=BotCommandScopeChat(chat_id=target_chat_id))
        except Exception:
            pass

        save_store(store)
        await query.answer("Updated")
        await query.edit_message_text(t(chosen_lang, "lang_set"), parse_mode=ParseMode.MARKDOWN)
        if target_chat_id in games and games[target_chat_id]["phase"] == "lobby":
            await refresh_lobby_message(target_chat_id, context)
        return

    if action == "join":
        chat_id = int(parts[1])
        lang = get_chat_lang(chat_id, user.id)
        if is_banned(user.id):
            await query.answer(t(lang, "banned"), show_alert=True)
            return
        game = games.get(chat_id)
        if not game or game["phase"] != "lobby":
            await query.answer("Lobby closed." if lang == "en" else "ဝင်ရောက်ချိန် ပိတ်သွားပါပြီ။", show_alert=True)
            return
        if user.id in game["players"]:
            await query.answer("You already joined." if lang == "en" else "သင် ဝင်ရောက်ပြီးသား ဖြစ်ပါသည်။", show_alert=True)
            return
        try:
            await send_tracked(
                context,
                user.id,
                f"You joined LuThat Game in **{game['chat_title']}**."
                if lang == "en"
                else f"**{game['chat_title']}** ရှိ LuThat Game ထဲသို့ ဝင်ရောက်ပြီးပါပြီ။",
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
        await query.answer("Joined!" if lang == "en" else "ဝင်ရောက်ပြီးပါပြီ!")
        await refresh_lobby_message(chat_id, context)
        return

    if action == "buy":
        item = parts[1]
        buyer_id = int(parts[2])
        lang = get_chat_lang(query.message.chat_id, user.id)
        if user.id != buyer_id:
            await query.answer("This shop menu is not yours." if lang == "en" else "သင်ဖွင့်ထားသော ဆိုင်မီနူး မဟုတ်ပါ။", show_alert=True)
            return
        store = load_store()
        rec = get_user_record(store, user.id)
        owner_mode = is_owner(user.id)

        if item == "shield":
            if not owner_mode and rec["coins"] < 50:
                await query.answer("Not enough Coins (need 50)." if lang == "en" else "50 Coins မပြည့်သေးပါ။", show_alert=True)
                return
            if not owner_mode:
                rec["coins"] -= 50
            rec["shields"] += 1
            save_store(store)
            await query.answer("Purchased 1 Shield." if lang == "en" else "Shield ၁ ခု ဝယ်ယူပြီးပါပြီ။", show_alert=True)
        elif item == "dia":
            if not owner_mode and rec["coins"] < 200:
                await query.answer("Not enough Coins (need 200)." if lang == "en" else "200 Coins မပြည့်သေးပါ။", show_alert=True)
                return
            if not owner_mode:
                rec["coins"] -= 200
            rec["diamonds"] += 1
            save_store(store)
            await query.answer("Purchased 1 Diamond." if lang == "en" else "1 Diamond ဝယ်ယူပြီးပါပြီ။", show_alert=True)
        elif item == "role":
            if not owner_mode and rec["diamonds"] < 1:
                await query.answer("Not enough Diamonds (need 1)." if lang == "en" else "1 Diamond မရှိသေးပါ။", show_alert=True)
                return
            if not owner_mode:
                rec["diamonds"] -= 1
            rec["role_tickets"] += 1
            save_store(store)
            await query.answer("Purchased 1 Role Ticket." if lang == "en" else "Role Ticket ၁ ခု ဝယ်ယူပြီးပါပြီ။", show_alert=True)
        return

    if action == "night":
        chat_id = int(parts[1])
        act_type = parts[2]
        target_id = int(parts[3])
        lang = get_chat_lang(chat_id, user.id)
        game = games.get(chat_id)
        if not game or game["phase"] != "night":
            await query.answer("Night phase ended." if lang == "en" else "ညအချိန် ပြီးဆုံးသွားပါပြီ။", show_alert=True)
            return
        actor = game["players"].get(user.id)
        if not actor or not actor["alive"]:
            await query.answer("You cannot act." if lang == "en" else "သင် လုပ်ဆောင်ခွင့် မရှိပါ။", show_alert=True)
            return
        game["night_actions"][user.id] = {"type": act_type, "target": target_id}
        target_name = game["players"].get(target_id, {}).get("name", "Player")
        await query.answer(f"Selected: {target_name}")
        done_txt = (
            f"Selected: **{target_name}** ({act_type})"
            if lang == "en"
            else f"ရွေးချယ်ပြီးပါပြီ: **{target_name}** ({act_type})"
        )
        await query.edit_message_text(done_txt, parse_mode=ParseMode.MARKDOWN)
        return

    if action == "vote":
        chat_id = int(parts[1])
        target_id = int(parts[2])
        lang = get_chat_lang(chat_id, user.id)
        game = games.get(chat_id)
        if not game or game["phase"] != "vote":
            await query.answer("Voting closed." if lang == "en" else "မဲပေးချိန် ပြီးဆုံးသွားပါပြီ။", show_alert=True)
            return
        voter = game["players"].get(user.id)
        if not voter or not voter["alive"]:
            await query.answer("Dead players cannot vote." if lang == "en" else "သေဆုံးပြီးသူများ မဲပေးခွင့် မရှိပါ။", show_alert=True)
            return
        game["votes"][user.id] = target_id
        if target_id == 0:
            await query.answer("Voted to Skip." if lang == "en" else "Skip မဲပေးလိုက်ပါသည်။")
        else:
            t_name = game["players"].get(target_id, {}).get("name", "Player")
            await query.answer(f"Voted for {t_name}" if lang == "en" else f"{t_name} ကို မဲပေးလိုက်ပါသည်။")
        return

    # Secret Anonymous 👍 / 👎 Confirmation Vote
    if action == "confirm":
        chat_id = int(parts[1])
        choice = parts[2]  # "up" or "down"
        lang = get_chat_lang(chat_id, user.id)
        game = games.get(chat_id)
        if not game or game["phase"] != "confirm":
            await query.answer("Confirmation closed." if lang == "en" else "အတည်ပြုချိန် ပြီးဆုံးသွားပါပြီ။", show_alert=True)
            return
        voter = game["players"].get(user.id)
        if not voter or not voter["alive"]:
            await query.answer("Dead players cannot vote." if lang == "en" else "သေဆုံးပြီးသူများ မဲပေးခွင့် မရှိပါ။", show_alert=True)
            return
        if user.id == game.get("confirm_target"):
            await query.answer("The accused cannot vote on themselves." if lang == "en" else "စွပ်စွဲခံရသူ ကိုယ်တိုင် မဲပေးခွင့် မရှိပါ။", show_alert=True)
            return

        game["confirm_votes"][user.id] = choice
        await query.answer(
            "Secret vote recorded (👍 Execute)." if (choice == "up" and lang == "en")
            else "Secret vote recorded (👎 Spare)." if (choice == "down" and lang == "en")
            else "လျှို့ဝှက်မဲ (👍 ကြိုးပေးမည်) မှတ်တမ်းတင်ပြီးပါပြီ။" if choice == "up"
            else "လျှို့ဝှက်မဲ (👎 လွှတ်ပေးမည်) မှတ်တမ်းတင်ပြီးပါပြီ။"
        )

        up_cnt = sum(1 for v in game["confirm_votes"].values() if v == "up")
        down_cnt = sum(1 for v in game["confirm_votes"].values() if v == "down")
        target_name = game["players"][game["confirm_target"]]["name"]
        try:
            await query.edit_message_text(
                t(lang, "confirm_lynch_prompt", name=target_name, sec=CONFIRM_DURATION, up=up_cnt, down=down_cnt),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=confirm_keyboard(chat_id, lang),
            )
        except Exception:
            pass
        return

def confirm_keyboard(chat_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "confirm_up_btn"), callback_data=f"confirm:{chat_id}:up"),
            InlineKeyboardButton(t(lang, "confirm_down_btn"), callback_data=f"confirm:{chat_id}:down"),
        ]
    ])

# ================= GAME LOOP ENGINE =================
async def begin_game(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = games.get(chat_id)
    if not game:
        return
    lang = get_chat_lang(chat_id)
    player_ids = list(game["players"].keys())
    if len(player_ids) < MIN_PLAYERS:
        games.pop(chat_id, None)
        await send_tracked(
            context, chat_id, t(lang, "not_enough", count=len(player_ids)), parse_mode=ParseMode.MARKDOWN
        )
        return

    roles = build_role_list(len(player_ids))
    random.shuffle(roles)

    for pid, r in zip(player_ids, roles):
        game["players"][pid]["role"] = r
        game["original_roles"][pid] = r

    mafia_members = [
        f"{p['name']} ({role_label(p['role'], lang)})"
        for p in game["players"].values()
        if p["role"] in ("don", "mafia")
    ]

    for pid, pdata in game["players"].items():
        r = pdata["role"]
        info = ROLES_INFO[r]
        desc = info["desc_en"] if lang == "en" else info["desc_mm"]
        extra = ""
        if r in ("don", "mafia") and len(mafia_members) > 1:
            label_team = "Mafia Team" if lang == "en" else "ဂိုဏ်းအဖွဲ့ဝင်များ"
            extra = f"
**{label_team}:** {', '.join(mafia_members)}"
        role_hdr = "Your Role" if lang == "en" else "သင်၏ Role"
        try:
            await send_tracked(
                context,
                pid,
                f"**{role_hdr}:** {role_label(r, lang)}
{desc}{extra}",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    await send_tracked(
        context,
        chat_id,
        t(lang, "game_starting", count=len(player_ids)),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=bot_dm_button(t(lang, "check_role_btn")),
    )
    game["task"] = asyncio.create_task(run_game_phases(chat_id, context))

def format_alive_list(game: dict, lang: str) -> str:
    alive = [p for p in game["players"].values() if p["alive"]]
    hdr = "**Players alive:**" if lang == "en" else "**အသက်ရှင်ကျန်သူများ:**"
    lines = [hdr] + [f"{idx}. {p['name']}" for idx, p in enumerate(alive, 1)]
    return NL.join(lines)

async def run_game_phases(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        while chat_id in games:
            game = games[chat_id]
            lang = get_chat_lang(chat_id)

            # ---- NIGHT PHASE (60s + GIF Animation + Go to bot button) ----
            game["night_num"] += 1
            game["phase"] = "night"
            game["night_actions"] = {}

            await send_anim_tracked(
                context,
                chat_id,
                NIGHT_GIF_URL,
                t(lang, "night_start", night=game["night_num"], sec=NIGHT_DURATION),
                reply_markup=bot_dm_button(t(lang, "go_to_bot_btn")),
            )
            await send_tracked(context, chat_id, format_alive_list(game, lang), parse_mode=ParseMode.MARKDOWN)
            await send_night_prompts(chat_id, context, lang)
            await asyncio.sleep(NIGHT_DURATION)

            if chat_id not in games:
                return

            # ---- RESOLVE NIGHT ----
            night_report = await resolve_night(chat_id, context, lang)
            winner = check_winner(game)
            if winner:
                await end_game(chat_id, winner, night_report, context)
                return

            # ---- DAY DISCUSSION (75s + GIF Animation) ----
            game["day_num"] += 1
            game["phase"] = "day"
            await send_anim_tracked(
                context,
                chat_id,
                DAY_GIF_URL,
                t(lang, "day_start", day=game["day_num"], report=night_report, sec=DAY_DURATION),
            )
            await send_tracked(context, chat_id, format_alive_list(game, lang), parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(DAY_DURATION)

            if chat_id not in games:
                return

            # ---- VOTING PHASE (45s) ----
            game["phase"] = "vote"
            game["votes"] = {}
            alive_players = [p for p in game["players"].values() if p["alive"]]
            buttons = [
                [InlineKeyboardButton(p["name"], callback_data=f"vote:{chat_id}:{p['id']}")]
                for p in alive_players
            ]
            buttons.append([InlineKeyboardButton(t(lang, "skip_vote"), callback_data=f"vote:{chat_id}:0")])

            await send_tracked(
                context,
                chat_id,
                t(lang, "vote_start", sec=VOTE_DURATION),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
            await asyncio.sleep(VOTE_DURATION)

            if chat_id not in games:
                return

            # ---- RESOLVE INITIAL VOTE & SECRET 👍 / 👎 CONFIRMATION ----
            top_target = get_top_voted_target(game)
            if top_target is None:
                msg = "No votes were cast." if lang == "en" else "မည်သူမျှ မဲမပေးကြသဖြင့် မည်သူ့ကိုမျှ ကြိုးမပေးလိုက်ပါ။"
                await send_tracked(context, chat_id, msg)
            elif top_target == 0:
                msg = "The town decided to skip voting." if lang == "en" else "မဲအများစုက Skip လုပ်ရန် ဆုံးဖြတ်လိုက်ပါသည်။"
                await send_tracked(context, chat_id, msg)
            else:
                game["phase"] = "confirm"
                game["confirm_target"] = top_target
                game["confirm_votes"] = {}
                target_name = game["players"][top_target]["name"]

                c_msg = await send_tracked(
                    context,
                    chat_id,
                    t(lang, "confirm_lynch_prompt", name=target_name, sec=CONFIRM_DURATION, up=0, down=0),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=confirm_keyboard(chat_id, lang),
                )
                game["confirm_msg_id"] = c_msg.message_id
                await asyncio.sleep(CONFIRM_DURATION)

                if chat_id not in games:
                    return

                up_cnt = sum(1 for v in game["confirm_votes"].values() if v == "up")
                down_cnt = sum(1 for v in game["confirm_votes"].values() if v == "down")
                victim = game["players"][top_target]

                if up_cnt > down_cnt:
                    victim["alive"] = False
                    promote_successors(game)
                    r_str = role_label(victim["role"], lang)
                    verdict_msg = (
                        f"👍 **{up_cnt}** vs 👎 **{down_cnt}** — **{victim['name']}** ({r_str}) has been executed."
                        if lang == "en"
                        else f"👍 **{up_cnt}** မဲ၊ 👎 **{down_cnt}** မဲ ဖြင့် **{victim['name']}** ({r_str}) ကို ကြိုးပေးစီရင်လိုက်ပါပြီ။"
                    )
                else:
                    verdict_msg = (
                        f"👍 **{up_cnt}** vs 👎 **{down_cnt}** — **{victim['name']}** was spared and released."
                        if lang == "en"
                        else f"👍 **{up_cnt}** မဲ၊ 👎 **{down_cnt}** မဲ ဖြင့် **{victim['name']}** ကို ပြန်လည်လွှတ်ပေးလိုက်ပါသည်။"
                    )
                await send_tracked(context, chat_id, verdict_msg, parse_mode=ParseMode.MARKDOWN)

            winner = check_winner(game)
            if winner:
                await end_game(chat_id, winner, "", context)
                return
    except asyncio.CancelledError:
        return

async def send_night_prompts(chat_id: int, context: ContextTypes.DEFAULT_TYPE, lang: str):
    game = games.get(chat_id)
    if not game:
        return
    alive = [p for p in game["players"].values() if p["alive"]]

    for pid, pdata in game["players"].items():
        if not pdata["alive"]:
            continue
        role = pdata["role"]
        if role in ("villager", "deputy"):
            continue

        if role == "detective":
            rows = []
            for target in alive:
                if target["id"] == pid:
                    continue
                chk_lbl = f"Check: {target['name']}" if lang == "en" else f"စစ်မည်: {target['name']}"
                sht_lbl = f"Shoot: {target['name']}" if lang == "en" else f"သတ်မည်: {target['name']}"
                rows.append([
                    InlineKeyboardButton(chk_lbl, callback_data=f"night:{chat_id}:check:{target['id']}"),
                    InlineKeyboardButton(sht_lbl, callback_data=f"night:{chat_id}:shoot:{target['id']}"),
                ])
            if rows:
                prompt = "Choose a player to check or shoot:" if lang == "en" else "စစ်ဆေးရန် သို့မဟုတ် ပစ်သတ်ရန် ရွေးချယ်ပါ:"
                try:
                    await send_tracked(context, pid, prompt, reply_markup=InlineKeyboardMarkup(rows))
                except Exception:
                    pass
            continue

        act_map = {
            "don": ("kill", "Choose a player to eliminate:" if lang == "en" else "သတ်မည့်သူကို ရွေးချယ်ပါ:"),
            "mafia": ("suggest", "Suggest a target to the Don:" if lang == "en" else "ခေါင်းဆောင်ထံ အကြံပြုမည့်သူကို ရွေးပါ:"),
            "doctor": ("heal", "Choose a player to heal:" if lang == "en" else "ဆေးကုသပေးမည့်သူကို ရွေးချယ်ပါ:"),
            "police": ("guard", "Choose a player to guard:" if lang == "en" else "အကာအကွယ်ပေးမည့်သူကို ရွေးချယ်ပါ:"),
            "drunk": ("drunk", "Choose a player to block:" if lang == "en" else "အရက်သွားတိုက်မည့်သူကို ရွေးချယ်ပါ:"),
            "sk": ("sk_kill", "Choose a player to kill:" if lang == "en" else "သတ်မည့်သူကို ရွေးချယ်ပါ:"),
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
                await send_tracked(context, pid, prompt_txt, reply_markup=InlineKeyboardMarkup(rows))
            except Exception:
                pass

async def resolve_night(chat_id: int, context: ContextTypes.DEFAULT_TYPE, lang: str) -> str:
    game = games[chat_id]
    actions = game["night_actions"]
    players = game["players"]

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
            if lang == "en":
                res_msg = f"Investigation Result: **{players[tid]['name']}** is {'Hostile (Mafia/SK)' if is_bad else 'Innocent'}."
            else:
                res_msg = f"စစ်ဆေးချက်ရလဒ်: **{players[tid]['name']}** သည် {'လူဆိုး/လူသတ်သမား ဖြစ်သည်' if is_bad else 'အပြစ်ကင်းသူ ဖြစ်သည်'}။"
            try:
                await send_tracked(context, actor_id, res_msg, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass
            for pid, p in players.items():
                if p["alive"] and p["role"] == "deputy":
                    try:
                        await send_tracked(context, pid, f"[Deputy] {res_msg}", parse_mode=ParseMode.MARKDOWN)
                    except Exception:
                        pass

    dead_tonight = []
    store = load_store()

    for victim_id in list(kill_targets.keys()):
        if not players[victim_id]["alive"]:
            continue
        if victim_id in healed_ids:
            continue
        if victim_id in guarded_by:
            guard_id = guarded_by[victim_id]
            if players[guard_id]["alive"]:
                players[guard_id]["alive"] = False
                line = (
                    f"Police **{players[guard_id]['name']}** died protecting **{players[victim_id]['name']}**."
                    if lang == "en"
                    else f"ရဲ **{players[guard_id]['name']}** သည် **{players[victim_id]['name']}** ကို ကာကွယ်ရင်း အသက်စွန့်သွားခဲ့သည်။"
                )
                dead_tonight.append(line)
                continue
        v_rec = get_user_record(store, victim_id)
        if v_rec["shields"] > 0:
            v_rec["shields"] -= 1
            continue

        players[victim_id]["alive"] = False
        r_str = role_label(players[victim_id]["role"], lang)
        line = (
            f"**{players[victim_id]['name']}** ({r_str}) was killed during the night."
            if lang == "en"
            else f"**{players[victim_id]['name']}** ({r_str}) ညဘက်တွင် အသတ်ခံလိုက်ရသည်။"
        )
        dead_tonight.append(line)

    save_store(store)
    promote_successors(game)

    if not dead_tonight:
        return "Nobody died last night." if lang == "en" else "မနေ့ညက မည်သူမျှ အသတ်မခံရပါ။"
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

def get_top_voted_target(game: dict):
    votes = game["votes"]
    if not votes:
        return None
    tally = {}
    for target_id in votes.values():
        tally[target_id] = tally.get(target_id, 0) + 1
    top_target, _ = max(tally.items(), key=lambda x: x[1])
    return top_target

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
    lang = get_chat_lang(chat_id)
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

    # Determine role-specific Victory Animation & Title
    alive_detective_or_deputy = any(
        p["alive"] and p["role"] in ("detective", "deputy")
        for p in game["players"].values()
    )

    if winner == "mafia":
        win_gif = WIN_GIFS["mafia"]
        win_title = (
            "**Mafia & Don Victory!**
The Mafia syndicate has taken over the city!"
            if lang == "en"
            else "**ဂိုဏ်းခေါင်းဆောင် (Don) နှင့် လူသတ်ဂိုဏ်း (Mafia) အနိုင်ရရှိသွားပါပြီ!**
မြို့တစ်ခုလုံးကို Mafia ဂိုဏ်းက သိမ်းပိုက်လိုက်ပါပြီ!"
        )
    elif winner == "sk":
        win_gif = WIN_GIFS["sk"]
        win_title = (
            "**Serial Killer Victory!**
Only the Serial Killer remains standing in the darkness!"
            if lang == "en"
            else "**စိတ္တဇလူသတ်သမား (Serial Killer) တစ်ဦးတည်း အနိုင်ရရှိသွားပါပြီ!**
အားလုံးကို ရှင်းလင်းပြီး တစ်ဦးတည်း အသက်ရှင်ကျန်ရစ်ခဲ့ပါပြီ!"
        )
    else:
        # Town Victory — Distinguish Detective + Town joint win vs Pure Villagers/Town win
        if alive_detective_or_deputy:
            win_gif = WIN_GIFS["town_det"]
            win_title = (
                "**Detective & Town Victory!**
With the Detective's investigation, the town eliminated all threats!"
                if lang == "en"
                else "**စုံထောက် (Detective) နှင့် မြို့သူမြို့သားများ ပူးပေါင်းအနိုင်ရရှိသွားပါပြီ!**
စုံထောက်၏ ဖော်ထုတ်မှုနှင့်အတူ မြို့ကို အောင်မြင်စွာ ကာကွယ်နိုင်ခဲ့ပါပြီ!"
            )
        else:
            win_gif = WIN_GIFS["town_pure"]
            win_title = (
                "**Pure Town / Villagers Victory!**
The townspeople stood together and defeated all killers on their own!"
                if lang == "en"
                else "**မြို့သူမြို့သား (Villagers) သီးသန့် အနိုင်ရရှိသွားပါပြီ!**
မြို့သူမြို့သားများ ကိုယ်တိုင်စည်းလုံးပြီး လူသတ်သမားအားလုံးကို နှိမ်နင်းနိုင်ခဲ့ပါပြီ!"
            )

    if lang == "en":
        reward_line = f"Winners ({', '.join(winners_names)}) earned **{WIN_COIN_REWARD} Coins** each."
        roles_hdr = "**Player Roles:**"
    else:
        reward_line = f"အနိုင်ရရှိသူများ ({', '.join(winners_names)}) သည် **{WIN_COIN_REWARD} Coins** စီ ရရှိပါသည်။"
        roles_hdr = "**ကစားသမားများ၏ Role စာရင်း:**"

    summary_parts = []
    if last_event:
        summary_parts.extend([last_event, ""])
    summary_parts.extend([win_title, "", reward_line, "", roles_hdr])
    for p in game["players"].values():
        status_tag = "Alive" if p["alive"] else "Dead"
        summary_parts.append(f"• {p['name']} — {role_label(p['role'], lang)} [{status_tag}]")

    await send_anim_tracked(
        context,
        chat_id,
        win_gif,
        NL.join(summary_parts),
    )

# ================= RENDER PORT BINDING & STARTUP =================
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
    global BOT_USERNAME
    me = await application.bot.get_me()
    BOT_USERNAME = me.username or ""
    await application.bot.set_my_commands(COMMANDS_EN)

def main():
    threading.Thread(target=start_web_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Public Commands
    app.add_handler(CommandHandler(["lang", "Lang"], cmd_lang))
    app.add_handler(CommandHandler(["role", "Role"], cmd_role))
    app.add_handler(CommandHandler(["open", "Open"], cmd_open))
    app.add_handler(CommandHandler(["start", "Start"], cmd_start))
    app.add_handler(CommandHandler(["extend", "Extend"], cmd_extend))
    app.add_handler(CommandHandler(["quit", "Quit"], cmd_quit))
    app.add_handler(CommandHandler(["bill", "Bill"], cmd_bill))
    app.add_handler(CommandHandler(["shop", "Shop"], cmd_shop))
    app.add_handler(CommandHandler(["dailybox", "Dailybox"], cmd_dailybox))
    app.add_handler(CommandHandler(["kiss", "Kiss"], cmd_kiss))
    app.add_handler(CommandHandler(["giftc", "Giftc"], cmd_giftc))
    app.add_handler(CommandHandler(["giftd", "Giftd"], cmd_giftd))
    app.add_handler(CommandHandler(["reportx", "ReportX", "Reportx"], cmd_reportx))

    # Admin + Owner Commands
    app.add_handler(CommandHandler(["delemsg", "Delemsg"], cmd_delemsg))
    app.add_handler(CommandHandler(["close", "Close"], cmd_close))
    app.add_handler(CommandHandler(["cancel", "Cancel"], cmd_cancel))

    # Owner Only Special Commands
    app.add_handler(CommandHandler(["crole", "Crole"], cmd_crole))
    app.add_handler(CommandHandler(["rsrole", "Rsrole"], cmd_rsrole))
    app.add_handler(CommandHandler(["hack", "Hack"], cmd_hack))
    app.add_handler(CommandHandler(["kick", "Kick"], cmd_kick))
    app.add_handler(CommandHandler(["rmcoin", "Rmcoin"], cmd_rmcoin))
    app.add_handler(CommandHandler(["ban", "Ban"], cmd_ban))
    app.add_handler(CommandHandler(["unban", "Unban"], cmd_unban))

    # Inline Buttons
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("LuThat Game Bot Started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
