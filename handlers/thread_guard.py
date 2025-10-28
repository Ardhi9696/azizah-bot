import logging
from telegram import Update
from telegram.ext import ContextTypes
from utils.admin_guard import load_admin_ids_from_env, load_protected_threads_from_env

logger = logging.getLogger(__name__)

ADMIN_IDS = load_admin_ids_from_env()
PROTECTED_THREADS = load_protected_threads_from_env()


async def auto_delete_non_admin_in_threads(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """
    Hapus semua pesan dari NON-ADMIN di thread tertentu (forum sub-topic).
    Berlaku untuk semua jenis pesan (teks/media), kecuali:
      - pesan dari admin
      - pesan di luar supergroup
      - pesan di thread yang tidak diproteksi
    """
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    # hanya supergroup + punya message_thread_id
    if chat.type != "supergroup":
        return
    thread_id = getattr(msg, "message_thread_id", None)
    if thread_id is None:
        return

    # kalau thread ini tidak diproteksi, abaikan
    if thread_id not in PROTECTED_THREADS:
        return

    # admin selalu lolos
    if user and user.id in ADMIN_IDS:
        return

    # non-admin: hapus
    try:
        await context.bot.delete_message(chat_id=chat.id, message_id=msg.message_id)
        logger.info(f"🧹 Hapus pesan non-admin uid={user.id} di thread={thread_id}")
    except Exception as e:
        logger.warning(
            f"❌ Gagal hapus pesan uid={getattr(user,'id',None)} di thread={thread_id}: {e}"
        )
