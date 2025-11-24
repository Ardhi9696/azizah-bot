import json
import os
import time
import random
import re
from telegram import Update
from telegram.ext import ContextTypes

from handlers.moderasi import is_admin
from utils.constants import AUTOREPLY_FILE


class AutoreplyManager:
    def __init__(self, json_path):
        self.json_path = json_path
        self.data = self._load()
        self.data.setdefault("chats", {})
        # cooldown per (chat_id, user_id)
        self.last_reply_ts = {}  # { (chat_id, user_id): timestamp }

    def _load(self):
        if not os.path.exists(self.json_path):
            return {"enabled": True, "chats": {}}
        with open(self.json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self):
        os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def set_chat_enabled(self, chat_id: int, enabled: bool):
        chat_key = str(chat_id)
        if "chats" not in self.data:
            self.data["chats"] = {}
        if chat_key not in self.data["chats"]:
            self.data["chats"][chat_key] = {
                "enabled": True,
                "topics": ["0"],
                "triggers": [],
            }
        self.data["chats"][chat_key]["enabled"] = enabled
        self._save()

    def is_chat_enabled(self, chat_id: int) -> bool:
        if not self.data.get("enabled", True):
            return False
        chat_cfg = self.data.get("chats", {}).get(str(chat_id))
        if not chat_cfg:
            return False
        return chat_cfg.get("enabled", True)

    def _contains_url(self, text: str) -> bool:
        # simple heuristic URL check
        text = text.lower()
        if "http://" in text or "https://" in text:
            return True
        if "t.me/" in text or "telegram.me/" in text:
            return True
        if re.search(r"\bwww\.[a-z0-9.-]+\.[a-z]{2,}\b", text):
            return True
        if re.search(r"\b[a-z0-9.-]+\.(com|net|org|io|id|kr)\b", text):
            return True
        return False

    def maybe_reply(
        self,
        *,
        chat_id: int,
        user_id: int,
        text: str,
        topic_id: int | None = None,
        logger=None,
    ):
        """
        Return reply_text or None jika tidak perlu auto-reply.
        topic_id: message_thread_id (None kalau non-thread)
        """

        if not text:
            return None

        # 1) global & chat enabled check
        if not self.is_chat_enabled(chat_id):
            return None

        chat_cfg = self.data["chats"].get(str(chat_id), {})

        # 2) topic guard
        allowed_topics = chat_cfg.get("topics", ["0"])
        # Kalau "0" ada di list → semua topic diperbolehkan
        if "0" not in allowed_topics:
            # Kalau message bukan di topic yang diizinkan → skip
            if topic_id is None or str(topic_id) not in allowed_topics:
                return None
        # blacklist topik
        blocked_topics = chat_cfg.get("blocked_topics", [])
        if blocked_topics and topic_id is not None:
            if str(topic_id) in blocked_topics:
                return None

        # 3) panjang maksimum
        if len(text) > 200:
            return None

        # 4) abaikan kalau mengandung URL
        if self._contains_url(text):
            return None

        # 5) cooldown per (chat_id, user_id): 5 detik
        now = time.time()
        key = (int(chat_id), int(user_id))
        last_ts = self.last_reply_ts.get(key)
        if last_ts is not None and (now - last_ts) < 5:
            return None

        # 7) cari trigger
        text_lower = text.lower()
        triggers = chat_cfg.get("triggers", [])
        matched = []

        for trig in triggers:
            keyword = trig.get("keyword", "")
            if not keyword:
                continue
            if keyword.lower() in text_lower:
                matched.append(trig)

        if not matched:
            return None

        # 8) kalau lebih dari 1 keyword match, pilih satu random
        trig = random.choice(matched)
        replies = trig.get("replies", [])
        if not replies:
            return None

        reply_text = random.choice(replies)

        # update cooldown
        self.last_reply_ts[key] = now

        # logging
        if logger:
            logger.info(
                f"[AUTOREPLY] chat={chat_id}, user={user_id}, "
                f"keyword='{trig.get('keyword')}', text='{text[:50]}'"
            )

        return reply_text


autoreply_manager = AutoreplyManager(AUTOREPLY_FILE)


async def handle_autoreply_off(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return await update.message.reply_text(
            "❌ Hanya admin yang bisa mematikan autoreply."
        )

    autoreply_manager.set_chat_enabled(chat_id, False)
    await update.message.reply_text("✅ Autoreply dimatikan untuk grup ini.")


async def handle_autoreply_on(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not is_admin(user_id):
        return await update.message.reply_text(
            "❌ Hanya admin yang bisa menyalakan autoreply."
        )

    autoreply_manager.set_chat_enabled(chat_id, True)
    await update.message.reply_text("✅ Autoreply dinyalakan untuk grup ini.")


async def handle_autoreply_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    topic_id = update.message.message_thread_id

    reply = autoreply_manager.maybe_reply(
        chat_id=chat_id,
        user_id=user_id,
        text=update.message.text,
        topic_id=topic_id,
    )
    if reply:
        await update.message.reply_text(reply)
