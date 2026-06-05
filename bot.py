import os
import json
import secrets
import time
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKENS_FILE = "tokens.json"
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
waiting_for_photo = {}  # user_id -> token_key

def load_tokens():
    if not os.path.exists(TOKENS_FILE):
        return {}
    with open(TOKENS_FILE, "r") as f:
        return json.load(f)

def save_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)

def clean_expired(tokens):
    now = time.time()
    expired = [k for k, v in tokens.items() if v.get("expires_at", 0) <= now]
    for k in expired:
        del tokens[k]
    if expired:
        save_tokens(tokens)
    return tokens

def parse_duration(text):
    text = text.strip().lower()
    if text.endswith("m"):
        return int(text[:-1]) * 60
    if text.endswith("h"):
        return int(text[:-1]) * 3600
    if text.endswith("d"):
        return int(text[:-1]) * 86400
    if text.endswith("s"):
        return int(text[:-1])
    try:
        return int(text) * 3600
    except ValueError:
        return None

def get_token_prefix(full_token):
    """First 16 chars of token for filename"""
    return full_token[:16]

def is_authorized(user_id):
    return ADMIN_ID > 0 and user_id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text(
        "Бот для управления сайтом.\n\n"
        "Токены:\n"
        "/generate <duration> [имя] - создать токен\n"
        "/revoke <token> - отозвать токен\n"
        "/list - список активных токенов\n"
        "/clean - удалить истекшие\n\n"
        "Профиль токена:\n"
        "/setname <token> <имя> - установить ФИО\n"
        "/setphoto <token> - установить фото (отправьте фото после)\n"
        "/showconfig <token> - показать настройки токена"
    )

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Укажите срок. Например: /generate 1h Имя Фамилия")
        return

    duration_sec = parse_duration(context.args[0])
    if duration_sec is None or duration_sec <= 0:
        await update.message.reply_text("Неверный формат. Используйте: 30m, 1h, 7d")
        return

    name = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    token = secrets.token_urlsafe(32)
    now = time.time()
    tokens = load_tokens()
    tokens["full:" + token] = {
        "created_at": now,
        "expires_at": now + duration_sec,
        "created_by": update.effective_user.id
    }
    if name:
        tokens["full:" + token]["name"] = name
    save_tokens(tokens)

    expires_str = datetime.fromtimestamp(now + duration_sec, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    msg = (
        f"Токен создан!\n\n"
        f"Токен: <code>{token}</code>\n"
        f"Истекает: {expires_str}\n"
        f"Срок: {context.args[0]}"
    )
    if name:
        msg += f"\nФИО: {name}"
    await update.message.reply_text(msg, parse_mode="HTML")

async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Укажите токен: /revoke <token>")
        return

    token_key = "full:" + context.args[0]
    tokens = load_tokens()
    if token_key in tokens:
        del tokens[token_key]
        save_tokens(tokens)
        # Remove associated photo
        prefix = get_token_prefix(context.args[0])
        for fname in os.listdir("."):
            if fname.startswith("custom_photo_" + prefix):
                os.remove(fname)
                break
        await update.message.reply_text("Токен отозван.")
    else:
        found = [k for k in tokens if k.endswith(context.args[0])]
        if found:
            for k in found:
                del tokens[k]
            save_tokens(tokens)
            await update.message.reply_text(f"Отозвано {len(found)} токен(ов).")
        else:
            await update.message.reply_text("Токен не найден.")

async def list_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    tokens = load_tokens()
    clean_expired(tokens)
    tokens = load_tokens()

    if not tokens:
        await update.message.reply_text("Нет активных токенов.")
        return

    now = time.time()
    lines = []
    for key, data in tokens.items():
        token_short = key[len("full:"):]
        remaining = data.get("expires_at", 0) - now
        remaining_str = f"{int(remaining // 3600)}ч {int((remaining % 3600) // 60)}м" if remaining > 0 else "истек"
        created = datetime.fromtimestamp(data.get("created_at", 0), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        name = data.get("name", "")
        name_str = f" | {name}" if name else ""
        lines.append(f"<code>{token_short[:16]}...</code> | ост. {remaining_str} | {created}{name_str}")

    await update.message.reply_text(
        "Активные токены:\n\n" + "\n".join(lines),
        parse_mode="HTML"
    )

async def clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    tokens = load_tokens()
    before = len(tokens)
    clean_expired(tokens)
    after = len(load_tokens())
    await update.message.reply_text(f"Удалено истекших токенов: {before - after}")

async def setname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Укажите токен и имя: /setname <token> <имя>")
        return

    token_raw = context.args[0]
    name = " ".join(context.args[1:])
    token_key = "full:" + token_raw
    tokens = load_tokens()

    if token_key in tokens:
        tokens[token_key]["name"] = name
        save_tokens(tokens)
        await update.message.reply_text(f"ФИО для токена установлено:\n{name}")
    else:
        found = [k for k in tokens if k.endswith(token_raw)]
        if found:
            for k in found:
                tokens[k]["name"] = name
            save_tokens(tokens)
            await update.message.reply_text(f"ФИО обновлено для {len(found)} токена(ов)")
        else:
            await update.message.reply_text("Токен не найден.")

async def setphoto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Укажите токен: /setphoto <token>\nЗатем отправьте фото.")
        return

    token_raw = context.args[0]
    token_key = "full:" + token_raw
    tokens = load_tokens()

    if token_key in tokens:
        waiting_for_photo[update.effective_user.id] = token_raw
        await update.message.reply_text("Отправьте фото для этого токена.")
    else:
        found = [k for k in tokens if k.endswith(token_raw)]
        if found:
            waiting_for_photo[update.effective_user.id] = found[0][len("full:"):]
            await update.message.reply_text("Отправьте фото для этого токена.")
        else:
            await update.message.reply_text("Токен не найден.")

async def showconfig(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Укажите токен: /showconfig <token>")
        return

    token_raw = context.args[0]
    token_key = "full:" + token_raw
    tokens = load_tokens()
    data = tokens.get(token_key)
    if not data:
        found = [k for k in tokens if k.endswith(token_raw)]
        if found:
            data = tokens[found[0]]
        else:
            await update.message.reply_text("Токен не найден.")
            return

    name = data.get("name", "не задано")
    expires = datetime.fromtimestamp(data.get("expires_at", 0), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    has_photo = "да" if os.path.exists(f"custom_photo_{get_token_prefix(token_raw)}.jpg") else "нет"
    await update.message.reply_text(
        f"Настройки токена:\n\n"
        f"ФИО: {name}\n"
        f"Фото: {has_photo}\n"
        f"Истекает: {expires}"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in waiting_for_photo:
        return

    token_raw = waiting_for_photo.pop(user_id)
    token_key = "full:" + token_raw

    photo_file = await update.message.photo[-1].get_file()
    prefix = get_token_prefix(token_raw)
    dest = f"custom_photo_{prefix}.jpg"
    await photo_file.download_to_drive(dest)

    tokens = load_tokens()
    if token_key in tokens:
        tokens[token_key]["photo_updated"] = time.time()
        save_tokens(tokens)

    await update.message.reply_text("Фото для токена сохранено. Обновите страницу сайта.")

def main():
    token = os.environ.get("TG_BOT_TOKEN")
    if not token:
        print("ERROR: TG_BOT_TOKEN environment variable not set", flush=True)
        return

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("revoke", revoke))
    app.add_handler(CommandHandler("list", list_tokens))
    app.add_handler(CommandHandler("clean", clean))
    app.add_handler(CommandHandler("setname", setname))
    app.add_handler(CommandHandler("setphoto", setphoto))
    app.add_handler(CommandHandler("showconfig", showconfig))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Bot started", flush=True)
    app.run_polling()

if __name__ == "__main__":
    main()
