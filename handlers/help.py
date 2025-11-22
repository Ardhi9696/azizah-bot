from telegram import Update
from telegram.ext import ContextTypes


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = """
<b>📖 Bantuan Bot EPS-TOPIK</b>
Semua perintah gabungan tiga bot di grup ini:

<b>🧪 Azizah-Bot (grup)</b>
/jadwal [n] – Jadwal pelaksanaan EPS-TOPIK
/reg [n] – Jadwal pendaftaran EPS-TOPIK
/pass1 [n] – Hasil Tahap 1 (CBT)
/pass2 [n] – Hasil Tahap Final (lolos ke Korea)
/get – Pengumuman terbaru G to G
/prelim – Info tahap prelim
/kurs – Kurs 1 KRW → IDR
/kursidr [n] – KRW → IDR, /kurswon [n] – IDR → KRW
/kursusd [n] – USD → IDR, /kursidrusd [n] – IDR → USD
/adminlist – Daftar admin grup, /cekstrike – Cek strike kamu

<b>🧩 Nichanan-Bot</b>
/cek &lt;nomor&gt; – Cek hasil CBT EPS-TOPIK (hanya di grup; DM khusus admin)
/tanya &lt;pertanyaan&gt; – Tanya Meta AI (hanya di grup; DM khusus admin)
/eps [USER PASS TGL] – Cek progres EPS (hanya di DM & ID yang di-whitelist)

<b>🗒️ Park-Min-Soo-Bot (catatan)</b>
/list – Daftar catatan umum
/notes – Daftar catatan Korea
#hashtag – Lihat detail catatan
👑 Admin: /add, /update, /delete, /add_korea, /update_korea, /delete_korea

⚠️ <b>Admin Grup</b>: /mute, /unmute, /ban, /unban, /restrike
🛡️ <b>Owner</b>: /resetstrikeall, /resetbanall

<b>📎 Lainnya</b>
/help – Tampilkan bantuan ini
/link – Kumpulan link belajar Korea
/cekid – Tampilkan ID chat dan thread

✨ Moderasi aktif: anti spam command, filter kata kasar/topik sensitif, strike otomatis (ban setelah 3), auto mute.

💌 Powered by: <b>LeeBot EPS-TOPIK</b> 🇰🇷🇮🇩
"""
    await update.message.reply_html(message)
