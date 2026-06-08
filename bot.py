import time
import io
import os
import uuid
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import storage

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

ADMIN_ID = 961566966
waiting_for_photo = {}


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


def is_authorized(user_id):
    return ADMIN_ID > 0 and user_id == ADMIN_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text(
        "Бот для управления сайтом.\n\n"
        "Токены (без БД, всё в самом токене):\n"
        "/generate <duration> [имя] - создать токен\n"
        "/setphoto <token> - добавить фото к токену\n"
        "/setname <token> <имя> - изменить имя в токене\n"
        "/clean <token> - удалить фото из токена\n"
        "/help - это сообщение"
    )


async def setname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Укажите токен и имя: /setname <токен> <Новое Имя>")
        return

    token = context.args[0]
    payload = storage.verify_token(token)
    if not payload:
        await update.message.reply_text("Токен недействителен или истёк.")
        return

    new_name = " ".join(context.args[1:])
    new_payload = {
        "exp": payload["exp"],
        "name": new_name,
        "photo_id": payload.get("photo_id", "")
    }
    new_token = storage.sign_token(new_payload)
    await update.message.reply_text(
        f"Имя изменено на «{new_name}».\n\n"
        f"Новый токен:\n<code>{new_token}</code>\n\n"
        f"Замените старый токен на этот.",
        parse_mode="HTML"
    )


async def clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Укажите токен: /clean <токен>")
        return

    token = context.args[0]
    payload = storage.verify_token(token)
    if not payload:
        await update.message.reply_text("Токен недействителен или истёк.")
        return

    new_payload = {
        "exp": payload["exp"],
        "name": payload.get("name", ""),
    }
    new_token = storage.sign_token(new_payload)
    await update.message.reply_text(
        f"Фото удалено из токена.\n\n"
        f"Новый токен:\n<code>{new_token}</code>\n\n"
        f"Замените старый токен на этот.",
        parse_mode="HTML"
    )


async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Укажите срок. Например: /generate 24h Іван Петренко")
        return

    duration_sec = parse_duration(context.args[0])
    if duration_sec is None or duration_sec <= 0:
        await update.message.reply_text("Неверный формат. Используйте: 30m, 1h, 7d")
        return

    name = " ".join(context.args[1:]) if len(context.args) > 1 else ""

    payload = {
        "exp": time.time() + duration_sec,
        "name": name
    }
    token = storage.sign_token(payload)

    expires_str = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    msg = (
        f"Токен создан!\n\n"
        f"Токен:\n<code>{token}</code>\n\n"
        f"Истекает: {expires_str}\n"
        f"Срок: {context.args[0]}"
    )
    if name:
        msg += f"\nФИО: {name}"
    await update.message.reply_text(msg, parse_mode="HTML")


async def setphoto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return

    if not context.args:
        await update.message.reply_text("Укажите токен: /setphoto <токен>")
        return

    token = context.args[0]
    payload = storage.verify_token(token)
    if not payload:
        await update.message.reply_text("Токен недействителен или истёк.")
        return

    waiting_for_photo[update.effective_user.id] = token
    await update.message.reply_text("Отправьте фото. Оно будет уменьшено и встроено в новый токен.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in waiting_for_photo:
        return

    old_token = waiting_for_photo.pop(user_id)
    old_payload = storage.verify_token(old_token)
    if not old_payload:
        await update.message.reply_text("Истекло время ожидания. Создайте токен заново.")
        return

    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()

    # Resize photo and save to server
    if HAS_PILLOW:
        img = Image.open(io.BytesIO(photo_bytes))
        img.thumbnail((200, 200), Image.LANCZOS)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="WEBP", quality=85)
        photo_bytes = buf.getvalue()

    photo_id = uuid.uuid4().hex[:12]
    photo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photos")
    os.makedirs(photo_dir, exist_ok=True)
    with open(os.path.join(photo_dir, f"{photo_id}.webp"), "wb") as f:
        f.write(photo_bytes)

    payload = {
        "exp": old_payload["exp"],
        "name": old_payload.get("name", ""),
        "photo_id": photo_id
    }
    new_token = storage.sign_token(payload)
    await update.message.reply_text(
        f"Фото добавлено.\n\n"
        f"Новый токен:\n<code>{new_token}</code>\n\n"
        f"Замените старый токен на этот.",
        parse_mode="HTML"
    )


def main():
    token = "8871737326:AAEVsplyMgf9i7Gzt_zv0S1D98JCkfQZnn4"

    if not HAS_PILLOW:
        print("WARNING: Pillow not installed — photos will not be resized. Install with: pip install Pillow", flush=True)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("setphoto", setphoto))
    app.add_handler(CommandHandler("setname", setname))
    app.add_handler(CommandHandler("clean", clean))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("Bot started (stateless mode)", flush=True)
    app.run_polling()


if __name__ == "__main__":
    main()
