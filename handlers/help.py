from telegram import Update
from telegram.ext import ContextTypes


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """
📖 *Bantuan Bot EPS-TOPIK*  
Semua perintah gabungan tiga bot di grup ini:

🧪 *Azizah-Bot (grup)*  
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

🧩 *Nichanan-Bot*  
/cek <nomor> – Cek hasil CBT EPS-TOPIK (hanya di grup; DM khusus admin)  
/tanya <pertanyaan> – Tanya Meta AI (hanya di grup; DM khusus admin)  
/eps [USER PASS TGL] – Cek progres EPS (hanya di DM & ID yang di-whitelist)

🗒️ *Park-Min-Soo-Bot (catatan)*  
/list – Daftar catatan umum  
/notes – Daftar catatan Korea  
#hashtag – Lihat detail catatan  
👑 Admin: /add, /update, /delete, /add_korea, /update_korea, /delete_korea

⚠️ Admin Grup: /mute, /unmute, /ban, /unban, /restrike  
🛡️ Owner: /resetstrikeall, /resetbanall

📎 *Lainnya*  
/help – Tampilkan bantuan ini  
/link – Kumpulan link belajar Korea  
/cek_id – Tampilkan ID chat dan thread

✨ Moderasi aktif: anti spam command, filter kata kasar/topik sensitif, strike otomatis (ban setelah 3), auto mute.

💌 Powered by: *LeeBot EPS-TOPIK* 🇰🇷🇮🇩
        """,
        parse_mode="Markdown",
    )
