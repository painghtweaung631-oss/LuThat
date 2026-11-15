import os
import random
import asyncio
import logging
from typing import Dict, List, Optional
from telegram import (
    Update,
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
# CONFIGURATION (Set your Bot Token & GIFs)
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
NIGHT_GIF_URL = os.getenv("NIGHT_GIF_URL", "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExaG5sY2E3enJqazl0d3R5eHFoZnl3ZnY2ejZ0NHF3ZzBqZnl0eSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7aD2saalBwwftBIY/giphy.gif")
DAY_GIF_URL = os.getenv("DAY_GIF_URL", "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExY2Z5NTh5Mmp5bnM5c2J3eGN5eTlyNG52a2x2ZG84em11eXJ5aCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/xT9IgzoKnwFNmISR8I/giphy.gif")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================================
# ROLE DEFINITIONS (Bilingual: MM / EN)
# ==========================================
ROLES = {
    "don": {
        "mm": "🤵🏻 ဂိုဏ်းခေါင်းဆောင် (Don)",
        "en": "🤵🏻 Don",
        "team": "mafia",
        "desc_mm": "မာဖီးယားခေါင်းဆောင်ဖြစ်သည်။ ညဘက်တွင် သတ်မည့်သူကို ရွေးချယ်နိုင်ပြီး စုံထောက်စစ်ဆေးလျှင်လည်း သာမန်မြို့သားဟုသာ ပေါ်မည်။",
        "desc_en": "Leader of the Mafia. Chooses the night victim and appears innocent to Detective checks.",
    },
    "mafia": {
        "mm": "🤵🏼 မာဖီးယား (Mafia)",
        "en": "🤵🏼 Mafia",
        "team": "mafia",
        "desc_mm": "Don နှင့်အတူ ညဘက်တွင် မြို့သူမြို့သားများကို လုပ်ကြံရမည်။",
        "desc_en": "Works with the Don to eliminate townspeople at night.",
    },
    "detective": {
        "mm": "🕵🏻‍♂️ စုံထောက် (Detective)",
        "en": "🕵🏻‍♂️ Detective",
        "team": "town",
        "desc_mm": "ညဘက်တွင် တစ်ဦးကို စစ်ဆေးခြင်း သို့မဟုတ် ပစ်သတ်ခြင်း ပြုလုပ်နိုင်သည်။",
        "desc_en": "Each night, choose either to investigate a player or shoot a suspect.",
    },
    "doctor": {
        "mm": "👨🏼‍⚕️ ဒေါက်တာ (Doctor)",
        "en": "👨🏼‍⚕️ Doctor",
        "team": "town",
        "desc_mm": "ညဘက်တွင် တစ်ဦးကို ကယ်တင်နိုင်သည်။ (မိမိကိုယ်ကို တစ်ဂိမ်းလျှင် တစ်ကြိမ်သာ ကယ်နိုင်သည်)",
        "desc_en": "Save one player each night (can self-heal only once per game).",
    },
    "maniac": {
        "mm": "🔪 လူသတ်သမား (Maniac)",
        "en": "🔪 Maniac",
        "team": "neutral",
        "desc_mm": "တစ်ကိုယ်တော် လူသတ်သမားဖြစ်သည်။ အားလုံးသေဆုံးပြီး နောက်ဆုံးကျန်ရစ်သူဖြစ်ပါက အနိုင်ရမည်။",
        "desc_en": "Solo killer. Wins if everyone else is eliminated.",
    },
    "lawyer": {
        "mm": "👨🏼‍⚖️ ရှေ့နေ (Lawyer)",
        "en": "👨🏼‍⚖️ Lawyer",
        "team": "mafia",
        "desc_mm": "ညဘက်တွင် မာဖီးယားတစ်ဦးကို ရွေးချယ်ကာ စုံထောက်စစ်ဆေးမှုမှ ဖုံးကွယ်ပေးနိုင်သည်။",
        "desc_en": "Protects a Mafia member from appearing guilty to Detective checks.",
    },
    "hobo": {
        "mm": "🧙🏼‍♂️ သူတောင်းစား (Hobo)",
        "en": "🧙🏼‍♂️ Hobo",
        "team": "town",
        "desc_mm": "ညဘက်တွင် တစ်ဦးအိမ်သို့ ပုလင်းခွံသွားတောင်းရင်း ထိုသူ့အိမ်သို့ မည်သူလာသည်ကို မြင်တွေ့နိုင်သည်။",
        "desc_en": "Visits someone's house at night and sees if anyone else visited them.",
    },
    "villager": {
        "mm": "👨🏼 မြို့သား (Villager)",
        "en": "👨🏼 Villager",
        "team": "town",
        "desc_mm": "နေ့ဘက်ဆွေးနွေးပွဲများတွင် မာဖီးယားများကို ဖော်ထုတ်မဲပေးရမည်။",
        "desc_en": "Discuss during the day and vote out the Mafia.",
    },
}

# ==========================================
# IN-MEMORY GAME STATE
# ==========================================
games: Dict[int, dict] = {}
user_active_game: Dict[int, int] = {}  # user_id -> chat_id


def mention_html(user_id: int, name: str) -> str:
    safe_name = (
        name.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f'<a href="tg://user?id={user_id}">{safe_name}</a>'


def t(lang: str, mm_text: str, en_text: str) -> str:
    return mm_text if lang == "mm" else en_text


def assign_roles(player_ids: List[int]) -> Dict[int, str]:
    shuffled = player_ids[:]
    random.shuffle(shuffled)
    n = len(shuffled)
    pool = ["don", "detective", "doctor"]
    if n >= 4:
        pool.append("villager")
    if n >= 5:
        pool.append("maniac")
    if n >= 6:
        pool.append("lawyer")
    if n >= 7:
        pool.append("hobo")
    while len(pool) < n:
        pool.append("mafia" if len(pool) % 4 == 0 else "villager")
    random.shuffle(pool)
    return {uid: pool[i] for i, uid in enumerate(shuffled)}


def check_win_condition(game: dict) -> Optional[str]:
    alive = [p for p in game["players"].values() if p["alive"]]
    mafia_cnt = sum(1 for p in alive if ROLES[p["role"]]["team"] == "mafia")
    maniac_cnt = sum(1 for p in alive if p["role"] == "maniac")
    town_cnt = sum(1 for p in alive if ROLES[p["role"]]["team"] == "town")

    if maniac_cnt > 0 and len(alive) == 1:
        return "maniac"
    if mafia_cnt == 0 and maniac_cnt == 0:
        return "town"
    if mafia_cnt >= (town_cnt + maniac_cnt) and maniac_cnt == 0:
        return "mafia"
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
        logger.warning(f"Could not change group permissions in {chat_id}: {e}")


# ==========================================
# COMMAND HANDLERS
# ==========================================
async def cmd_start_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    await update.message.reply_text(
        "🎭 <b>LuThat Game Bot</b> မှ ကြိုဆိုပါတယ်!\n\n"
        "Group Chat ထဲတွင် <code>/open</code> ရိုက်ပြီး ဂိမ်းဖွင့်ကာ <b>Join Game</b> နှိပ်၍ ပါဝင်နိုင်ပါသည်။\n"
        "ညဘက်စွမ်းရည်များ၊ မဲပေးခြင်းနှင့် နောက်ဆုံးစကား (Last Words) များကို ဤ Bot DM ထဲတွင် လုပ်ဆောင်ရပါမည်။",
        parse_mode="HTML",
    )


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
    games[chat_id] = {
        "chat_id": chat_id,
        "chat_title": chat.title or "Mafia Group",
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
    games[chat_id]["lobby_msg_id"] = msg.message_id


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

    # Verify bot can DM user
    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=t(
                lang,
                f"✅ <b>{game['chat_title']}</b> ဂိမ်းဝိုင်းထဲသို့ ဝင်ရောက်ပြီးပါပြီ!",
                f"✅ You joined the game in <b>{game['chat_title']}</b>!",
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

    # Send secret role info in DM
    mafia_members = [p for p in game["players"].values() if ROLES[p["role"]]["team"] == "mafia"]
    for p in game["players"].values():
        r = p["role"]
        r_title = ROLES[r][lang]
        r_desc = ROLES[r][f"desc_{lang}"]
        extra = ""
        if ROLES[r]["team"] == "mafia" and len(mafia_members) > 1:
            teammates = ", ".join(f"{m['name']} ({ROLES[m['role']][lang]})" for m in mafia_members if m["id"] != p["id"])
            extra = t(lang, f"\n\n🤝 <b>မာဖီးယား အဖွဲ့ဖော်များ:</b> {teammates}", f"\n\n🤝 <b>Mafia Allies:</b> {teammates}")

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
            f"မြို့ပေါ်သို့ ညအမှောင်ထု ကျရောက်လာပါပြီ။ အထူး Role ရှိသူများ Bot DM ထဲတွင် <b>60 စက္ကန့်</b> အတွင်း ရွေးချယ်ပါ!",
            f"🌃 <b>Night {game['day_num']}</b>\n"
            f"The night falls on the city. <b>1 min.</b> is left to sleep! Check your Bot DM.",
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
                f"<b>Players alive:</b>\n{alive_list}\n\n<b>Some of them are:</b>\n{role_summary}\nTotal: {len(alive_players)} people.",
            ),
            parse_mode="HTML",
        )

        # Send Night Action prompts in DM
        for p in alive_players:
            await send_night_prompt(context, game, p)

        await asyncio.sleep(45)

        # Resolve Night Actions
        report_lines = await resolve_night(context, game)

        # 2. DAY PHASE
        game["phase"] = "day"
        await set_group_mute(context, chat_id, False)

        # Lock any unused last words from previous night once new day starts?
        # Keep last_word_available active until used (1 time only)
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

        # Tally DM Votes
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
        # Check tie
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
# NIGHT PROMPTS & CALLBACKS
# ==========================================
async def send_night_prompt(context: ContextTypes.DEFAULT_TYPE, game: dict, player: dict):
    lang = game["lang"]
    chat_id = game["chat_id"]
    role = player["role"]
    uid = player["id"]

    if role == "villager":
        return

    # Detective Step 1: ONLY 2 buttons (Check & Shoot)
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

    # Other active roles
    targets = [p for p in game["players"].values() if p["alive"]]
    if role != "doctor":
        targets = [p for p in targets if p["id"] != uid]
    elif player["self_healed"]:
        targets = [p for p in targets if p["id"] != uid]

    btns = [[InlineKeyboardButton(tp["name"], callback_data=f"nact:{chat_id}:{role}:{tp['id']}")] for tp in targets]
    prompts = {
        "don": t(lang, "🤵🏻 ယနေ့ည လုပ်ကြံမည့် သားကောင်ကို ရွေးချယ်ပါ:", "🤵🏻 Choose a victim to eliminate tonight:"),
        "mafia": t(lang, "🤵🏼 သတ်မည့်သူကို အကြံပြုရွေးချယ်ပါ:", "🤵🏼 Vote for tonight's Mafia target:"),
        "doctor": t(lang, "👨🏼‍⚕️ ယနေ့ည ကုသကယ်တင်မည့်သူကို ရွေးချယ်ပါ:", "👨🏼‍⚕️ Choose a player to heal tonight:"),
        "maniac": t(lang, "🔪 ယနေ့ည သတ်ဖြတ်မည့်သူကို ရွေးချယ်ပါ:", "🔪 Choose your victim tonight:"),
        "lawyer": t(lang, "👨🏼‍⚖️ စုံထောက်စစ်ဆေးမှုမှ ကာကွယ်ပေးမည့်သူကို ရွေးချယ်ပါ:", "👨🏼‍⚖️ Choose a player to protect from Detective:"),
        "hobo": t(lang, "🧙🏼‍♂️ ပုလင်းခွံသွားတောင်းမည့် အိမ်ကို ရွေးချယ်ပါ:", "🧙🏼‍♂️ Choose whose house to visit tonight:"),
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
            "don": t(lang, "🤵🏻 မာဖီးယားက သားကောင်ကို ရွေးချယ်လိုက်ပါပြီ...", "🤵🏻 Mafia chose a victim..."),
            "mafia": t(lang, "🤵🏼 မာဖီးယားအဖွဲ့ဝင်က ပစ်မှတ်ကို အကြံပြုလိုက်ပါပြီ...", "🤵🏼 Mafia member suggested a target..."),
            "det_check": t(lang, "🕵🏻‍♂️ စုံထောက်က လျှို့ဝှက်စုံစမ်းရန် ထွက်ခွာသွားပါပြီ...", "🕵🏻‍♂️ Detective went on a secret investigation..."),
            "det_shoot": t(lang, "🕵🏻‍♂️ စုံထောက်က သေနတ်မောင်းတင်လိုက်ပါပြီ...", "🕵🏻‍♂️ Detective loaded his gun..."),
            "doctor": t(lang, "👨🏼‍⚕️ ဒေါက်တာ ညဂျူတီ စတင်ထမ်းဆောင်နေပါပြီ...", "👨🏼‍⚕️ Doctor went on night duty..."),
            "maniac": t(lang, "🔪 လူသတ်သမား (Maniac) ချုံပုတ်ထဲတွင် ပုန်းအောင်းနေပါပြီ...", "🔪 Maniac hid deep in the bushes..."),
            "lawyer": t(lang, "👨🏼‍⚖️ ရှေ့နေက ကာကွယ်ပေးမည့် မာဖီးယားအဖွဲ့ဝင်ကို ရှာဖွေနေပါသည်...", "👨🏼‍⚖️ Lawyer is looking for a mafia member to protect..."),
            "hobo": t(lang, "🧙🏼‍♂️ သူတောင်းစား (Hobo) ပုလင်းခွံသွားတောင်းနေပါပြီ...", "🧙🏼‍♂️ Hobo went to ask someone to not throw their bottles away..."),
        }
        if act_type in log_map:
            await context.bot.send_message(chat_id=chat_id, text=log_map[act_type])


async def resolve_night(context: ContextTypes.DEFAULT_TYPE, game: dict) -> str:
    lang = game["lang"]
    actions = game["night_actions"]
    players = game["players"]

    healed_id = None
    lawyer_protected_id = None
    kills: List[int] = []

    # 1. Doctor & Lawyer
    for uid, act in actions.items():
        if act["type"] == "doctor":
            healed_id = act["target"]
            if healed_id == uid:
                players[uid]["self_healed"] = True
        elif act["type"] == "lawyer":
            lawyer_protected_id = act["target"]

    # 2. Mafia Kill (Don priority)
    don_target = None
    mafia_votes = []
    for uid, act in actions.items():
        if act["type"] == "don":
            don_target = act["target"]
        elif act["type"] == "mafia":
            mafia_votes.append(act["target"])
    mafia_victim = don_target or (mafia_votes[0] if mafia_votes else None)
    if mafia_victim:
        kills.append(mafia_victim)

    # 3. Maniac & Detective
    for uid, act in actions.items():
        if act["type"] == "maniac":
            kills.append(act["target"])
        elif act["type"] == "det_shoot":
            kills.append(act["target"])
        elif act["type"] == "det_check":
            t_p = players[act["target"]]
            is_mafia = ROLES[t_p["role"]]["team"] == "mafia"
            if t_p["role"] == "don" or t_p["id"] == lawyer_protected_id:
                is_mafia = False
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=t(
                        lang,
                        f"🔍 စစ်ဆေးချက်ရလဒ်: <b>{t_p['name']}</b> သည် "
                        + ("<b>မာဖီးယား (Mafia) ဖြစ်သည်!</b>" if is_mafia else "အပြစ်ကင်းသူ ဖြစ်သည်။"),
                        f"🔍 Investigation Result: <b>{t_p['name']}</b> is "
                        + ("<b>Mafia!</b>" if is_mafia else "Innocent."),
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        elif act["type"] == "hobo":
            house_id = act["target"]
            visitors = [
                players[v_uid]["name"]
                for v_uid, v_act in actions.items()
                if v_uid != uid and v_act["target"] == house_id
            ]
            v_str = ", ".join(visitors) if visitors else t(lang, "မည်သူမျှ မလာပါ", "Nobody")
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=t(
                        lang,
                        f"🧙🏼‍♂️ <b>{players[house_id]['name']}</b> အိမ်သို့ ညက လာရောက်ခဲ့သူများ: <b>{v_str}</b>",
                        f"🧙🏼‍♂️ Visitors at <b>{players[house_id]['name']}</b>'s house last night: <b>{v_str}</b>",
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass

    # 4. Apply Deaths (excluding Doctor save)
    dead_tonight = []
    for k_id in set(kills):
        if k_id == healed_id:
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
    safe_text = (
        update.message.text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

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
# END GAME & MUTE ENFORCEMENT
# ==========================================
async def announce_winner(context: ContextTypes.DEFAULT_TYPE, game: dict, winner: str):
    lang = game["lang"]
    chat_id = game["chat_id"]
    game["phase"] = "ended"
    await set_group_mute(context, chat_id, False)

    titles = {
        "town": t(lang, "🏆 <b>မြို့သူမြို့သားများ (Town) အနိုင်ရရှိပါပြီ!</b>", "🏆 <b>Townspeople Win!</b>"),
        "mafia": t(lang, "🏆 <b>မာဖီးယားဂိုဏ်း (Mafia) အနိုင်ရရှိပါပြီ!</b>", "🏆 <b>Mafia Wins!</b>"),
        "maniac": t(lang, "🏆 <b>လူသတ်သမား (Maniac) တစ်ကိုယ်တော် အနိုင်ရရှိပါပြီ!</b>", "🏆 <b>Maniac Wins!</b>"),
    }

    summary = "\n".join(
        f"• {mention_html(p['id'], p['name'])} — {ROLES[p['role']][lang]} ({'✅' if p['alive'] else '💀'})"
        for p in game["players"].values()
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"{titles[winner]}\n\n<b>ကစားသမားများ၏ Role စာရင်း:</b>\n{summary}\n\nနောက်တစ်ပွဲဆော့ရန် <code>/open</code> ရိုက်ပါ။",
        parse_mode="HTML",
    )


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
    # Delete messages from dead players or during night
    if game["phase"] == "night" or (player and not player["alive"]):
        try:
            await update.message.delete()
        except Exception:
            pass


# ==========================================
# ENTRYPOINT
# ==========================================
def main():
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("⚠️ Please set BOT_TOKEN environment variable or edit BOT_TOKEN in luthat_bot.py")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("open", cmd_open))
    app.add_handler(CommandHandler("start", cmd_start_game))
    app.add_handler(CommandHandler("lang", cmd_lang))

    app.add_handler(CallbackQueryHandler(cb_join, pattern=r"^join:"))
    app.add_handler(CallbackQueryHandler(cb_detective_mode, pattern=r"^det_mode:"))
    app.add_handler(CallbackQueryHandler(cb_night_action, pattern=r"^nact:"))
    app.add_handler(CallbackQueryHandler(cb_dm_vote, pattern=r"^dmvote:"))
    app.add_handler(CallbackQueryHandler(cb_confirm_vote, pattern=r"^confirm:"))

    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_private_last_word))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, enforce_group_silence))

    print("🤖 LuThat Game Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
