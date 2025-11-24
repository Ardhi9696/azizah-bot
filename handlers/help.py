from telegram import Update
from telegram.ext import ContextTypes


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """
📖 *Bantuan Bot EPS-TOPIK*  
Semua perintah gabungan tiga bot di grup ini:

🧪 *Azizah-Bot (Responder)*  
/jadwal – Jadwal pelaksanaan EPS-TOPIK  
/reg – Jadwal pendaftaran EPS-TOPIK  
/pass1 – Hasil Tahap 1 (UBT)  
/pass2 – Hasil Tahap Final (lolos ke Korea)  
/get – Pengumuman terbaru G to G  
/prelim – Info tahap prelim  
/kurs – Kurs 1 KRW → IDR  
/kursidr [n] – KRW → IDR, /kurswon  – IDR → KRW  
/kursusd [n] – USD → IDR, /kursidrusd – IDR → USD  
/adminlist – Daftar admin grup, /cekstrike – Cek strike kamu
/autoreply_on | /autoreply_off – Aktif/nonaktif autoreply per grup  
/autoreply_reload – Reload config autoreply (DM admin saja)

🧩 *Nichanan-Bot (Scrapper)*  
/cek <no ujian 16digit> – Cek hasil UBT EPS-TOPIK  
/eps [USER PASS TGL] – Cek progres EPS (Whitelist DM)  
/tanya <pertanyaan> – Tanya Meta AI  
*Gunakan di DM untuk keamanan kredensial.*

🗒️ *Park-Min-Soo-Bot (Monitor)*  
/list – Daftar catatan umum  
/notes – Daftar catatan Korea  
#hashtag – Lihat detail catatan  
👑 Admin: /add, /update, /delete, dll

⚠️ Admin Grup: /mute, /unmute, /ban, /unban, /restrike  
🛡️ Owner: /resetstrikeall, /resetbanall

📎 *Lainnya*  
/help – Tampilkan bantuan ini  
/link – Kumpulan link belajar Korea  
/cekid – Tampilkan ID chat dan thread

✨ Moderasi aktif: anti spam command, filter kata kasar/topik sensitif, strike otomatis (ban setelah 3), auto mute.
ℹ️ Autoreply: aktif di chat yang terdaftar di `autoreply.json` (topik bisa dibatasi; thread blacklist diabaikan). Perubahan config butuh /autoreply_reload atau restart bot.

💌 Powered by: *LeeBot EPS-TOPIK* 🇰🇷🇮🇩
        """,
        parse_mode="Markdown",
    )
