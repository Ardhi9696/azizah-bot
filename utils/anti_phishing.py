import os
import re
import json
import logging
from telegram import Update
from telegram.ext import ContextTypes
from .constants import BANNED_FILE, BLACKLIST_LINK, WHITELIST_LINK
from dotenv import load_dotenv

load_dotenv()


def _parse_admin_ids(raw: str) -> list[int]:
    """Parse ADMIN_LIST dengan aman, abaikan nilai kosong/non-int."""
    ids = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_LIST", ""))
OWNER_ID = int(os.getenv("MY_TELEGRAM_ID", "0"))

CACHE_PHISHING_FILE = "data/cache_phishing_links.json"
MODERASI_LOG_FILE = "logs/moderasi.log"

# === Setup Logger Moderasi ===
moderasi_logger = logging.getLogger("moderasi")
moderasi_logger.setLevel(logging.INFO)
if not moderasi_logger.handlers:
    handler = logging.FileHandler(MODERASI_LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    moderasi_logger.addHandler(handler)


# === Utilitas JSON ===
def load_json_list(path: str) -> list:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"⚠️ Gagal memuat {path}: {e}")
        return []


def load_phishing_cache() -> set:
    try:
        with open(CACHE_PHISHING_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_phishing_cache(links: set):
    with open(CACHE_PHISHING_FILE, "w", encoding="utf-8") as f:
        json.dump(list(links), f, indent=2)


def save_banned_user(user_id: int):
    try:
        with open(BANNED_FILE, "r", encoding="utf-8") as f:
            data = set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        data = set()
    data.add(user_id)
    with open(BANNED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(data), f, indent=2)
    logging.info(f"📁 User {user_id} ditambahkan ke banned_users.json")


# === Proses Link ===
WHITELIST = [w.strip() for w in load_json_list(WHITELIST_LINK)]
BLACKLIST = [b.strip().lower() for b in load_json_list(BLACKLIST_LINK)]
PHISHING_CACHE = load_phishing_cache()


def normalize_url(url: str) -> str:
    return re.sub(r"^(https?:\/\/|https\/\/|www\.)", "", url.strip().lower())


def extract_links(text: str) -> list:
    pattern = r"(https?:\/\/[^\s]+|https\/\/[^\s]+|t\.me\/[^\s]+|www\.[^\s]+)"
    return re.findall(pattern, text)


def censor_link(link: str) -> str:
    return re.sub(
        r"(https?:\/\/|https\/\/|www\.|t\.me\/|telegram\.me\/)", "[LINK] ", link
    )


def is_suspicious(
    link: str, whitelist: list, blacklist: list, bot_username: str
) -> bool:
    domain = normalize_url(link)
    bot_username = bot_username or "azizah_bot"
    bot_username = bot_username.lower().strip("@")

    normalized_whitelist = [normalize_url(w) for w in whitelist]

    # ✅ Cek whitelist dulu
    if any(w in domain for w in normalized_whitelist):
        logging.info(f"🟢 Link {link} cocok whitelist.")
        return False

    if domain in PHISHING_CACHE:
        logging.info(f"⚠️ Link {link} ditemukan dalam cache phishing.")
        return True

    if any(b in domain for b in blacklist):
        logging.warning(f"⚠️ Link {link} cocok blacklist.")
        PHISHING_CACHE.add(domain)
        return True

    # ✅ Grup Telegram asing: t.me/link yang bukan milik bot & tidak di-whitelist
    if re.search(r"(t\.me\/|telegram\.me\/)", domain):
        if not domain.endswith(bot_username) and all(
            w not in domain for w in normalized_whitelist
        ):
            logging.warning(f"⚠️ Grup Telegram asing: {link}")
            PHISHING_CACHE.add(domain)
            return True

    if re.search(
        r"(bokep|judi|slot|phising|claim|\.xyz|\.click|bit\.ly|tinyurl|grabify|xxx)",
        domain,
    ):
        logging.warning(f"⚠️ Pola link mencurigakan: {link}")
        PHISHING_CACHE.add(domain)
        return True

    logging.info(f"ℹ️ Link {link} dianggap aman.")
    return False


# === Handler Utama ===
async def handle_phishing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    msg = update.message
    if not msg or not msg.text:
        logging.debug("🔍 Tidak ada teks untuk dicek.")
        return False

    text = msg.text
    user_id = msg.from_user.id
    chat_id = msg.chat.id
    links = extract_links(text)

    if not links:
        logging.info("✅ Tidak ada link yang terdeteksi.")
        return False

    for link in links:
        logging.info(f"🔗 Ditemukan link: {link}")

        if not is_suspicious(link, WHITELIST, BLACKLIST, context.bot.username):
            continue

        moderasi_logger.info(
            f"[DETEKSI] user_id={user_id} chat_id={chat_id} link={link}"
        )

        try:
            await msg.delete()
            logging.info(f"🧹 Pesan user {user_id} dihapus.")
        except Exception as e:
            logging.error(f"❌ Gagal menghapus pesan: {e}")

        sensor = censor_link(link)

        if user_id == OWNER_ID or user_id in ADMIN_IDS:
            logging.info(
                f"🙈 Link mencurigakan dari admin/owner {user_id}. Tidak diban."
            )
            await context.bot.send_message(
                chat_id,
                f"⚠️ Admin/Owner mengirim link mencurigakan.\n🔗 Link: <code>{sensor}</code>",
                parse_mode="HTML",
            )
            save_phishing_cache(PHISHING_CACHE)
            return True

        try:
            await context.bot.ban_chat_member(chat_id, user_id)
            logging.warning(f"🚫 User {user_id} dibanned karena link mencurigakan.")
            save_banned_user(user_id)
        except Exception as e:
            logging.error(f"❌ Gagal memban user: {e}")

        await context.bot.send_message(
            chat_id,
            f"🚨 <b>Link mencurigakan terdeteksi</b>\n"
            f"User {msg.from_user.mention_html()} telah diban.\n"
            f"🔗 Link: <code>{sensor}</code>",
            parse_mode="HTML",
        )

        save_phishing_cache(PHISHING_CACHE)
        return True

    return False
