from telegram import Update
from telegram.ext import ContextTypes


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "*📖 Bantuan Bot EPS-TOPIK*\n"
        "Semua perintah gabungan tiga bot di grup ini:\n\n"
        "*🧪 Azizah-Bot (grup)*\n"
        "`/jadwal [jumlah]` – Jadwal pelaksanaan EPS-TOPIK\n"
        "`/reg [jumlah]` – Jadwal pendaftaran EPS-TOPIK\n"
        "`/pass1 [jumlah]` – Hasil Tahap 1 (CBT/UBT)\n"
        "`/pass2 [jumlah]` – Hasil Tahap Final\n"
        "`/get` – Pengumuman terbaru G to G\n"
        "`/prelim` – Info tahap prelim\n"
        "`/kurs` – Kurs 1 KRW → IDR\n"
        "`/kursidr [jumlah]` – KRW → IDR, `/kurswon [jumlah]` – IDR → KRW\n"
        "`/kursusd [jumlah]` – USD → IDR, `/kursidrusd [jumlah]` – IDR → USD\n"
        "`/adminlist` – Daftar admin grup, `/cekstrike` – Cek strike kamu\n\n"
        "*🧩 Nichanan-Bot*\n"
        "`/cek <nomor>` – Cek hasil CBT EPS-TOPIK (hanya di grup; DM khusus admin)\n"
        "`/tanya <pertanyaan>` – Tanya Meta AI (hanya di grup; DM khusus admin)\n"
        "`/eps [USER PASS TGL]` – Progres EPS (hanya di DM & ID yang di-whitelist)\n\n"
        "*🗒️ Park-Min-Soo-Bot (catatan)*\n"
        "`/list` – Daftar catatan umum\n"
        "`/notes` – Daftar catatan Korea\n"
        "`#hashtag` – Lihat detail catatan\n"
        "👑 Admin: `/add`, `/update`, `/delete`, `/add_korea`, `/update_korea`, `/delete_korea`\n\n"
        "⚠️ *Admin Grup*: `/mute`, `/unmute`, `/ban`, `/unban`, `/restrike`\n"
        "🛡️ *Owner*: `/resetstrikeall`, `/resetbanall`\n\n"
        "*📎 Lainnya*\n"
        "`/help` – Tampilkan bantuan ini\n"
        "`/link` – Kumpulan link belajar Korea\n"
        "`/cekid` – Tampilkan ID chat dan thread\n\n"
        "✨ Moderasi aktif: anti spam command, filter kata kasar/topik sensitif, "
        "strike otomatis (ban setelah 3), auto mute.\n\n"
        "💌 Powered by: *LeeBot EPS-TOPIK* 🇰🇷🇮🇩"
    )
    await update.message.reply_text(message, parse_mode="Markdown")
