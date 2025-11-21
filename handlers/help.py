from telegram import Update
from telegram.ext import ContextTypes


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """
📖 *Bantuan Bot EPS-TOPIK*  
Berikut daftar perintah yang tersedia:

🧪 *Ujian EPS-TOPIK*  
/jadwal [jumlah] – Cek *jadwal pelaksanaan* EPS-TOPIK  
/reg [jumlah] – Cek *jadwal pendaftaran* EPS-TOPIK  
/pass1 [jumlah] – Cek *hasil Tahap 1* (CBT)  
/pass2 [jumlah] – Cek *hasil Tahap Final* (lolos ke Korea)

📝 *Pengumuman G to G Korea*  
/get – Update pengumuman terbaru G to G  
/prelim – Info tahap prelim (pra-keberangkatan)  

🗒️ *Catatan Bot*  
/list – Lihat daftar catatan  
/notes – Lihat daftar catatan Korea  
#hashtag – Lihat detail catatan (ketik di chat tanpa slash)  

🔎 *Cek Hasil CBT EPS-TOPIK*  
/cek [nomor EPS] – Cek hasil CBT berdasarkan nomor ujian  
Contoh: `/cek 012202512345678`

💬 *Tanya AI*  
/tanya [pertanyaan] – Ajukan pertanyaan ke Meta AI  
Contoh: `/tanya Siapa presiden Korea?`

💱 *Kurs Mata Uang*  
/kurs – Tampilkan kurs 1 KRW ke IDR  
/kursidr [jumlah] – Konversi KRW → IDR  
/kurswon [jumlah] – Konversi IDR → KRW  
/kursusd [jumlah] – Konversi USD → IDR (default 1 USD jika kosong)  
/kursidrusd [jumlah] – Konversi IDR → USD  
Contoh: `/kursidr 10000`, `/kurswon 50000`, `/kursusd 10`, `/kursidrusd 150000`

👥 *Fitur Grup & Moderasi*  
/adminlist – Tampilkan daftar admin grup  
/cekstrike – Cek strike kamu saat ini

⚠️ Admin Saja:  
/mute (reply) – Mute pengguna  
/unmute (reply) – Unmute pengguna  
/ban (reply) – Ban pengguna  
/unban (reply) – Unban pengguna  
/restrike (reply) – Reset strike user  

🛡️ Owner Saja:  
/resetstrikeall – Reset semua strike  
/resetbanall – Hapus semua banned user

📎 *Lainnya*  
/help – Tampilkan bantuan ini  
/link – Kumpulan link belajar Korea  
/id – Tampilkan ID Telegram

✨ Bot ini dilengkapi sistem moderasi:  
• Anti spam command  
• Filter kata kasar, topik sensitif  
• Strike otomatis (ban setelah 3 pelanggaran)  
• Auto mute jika melanggar

💌 Powered by: *LeeBot EPS-TOPIK* 🇰🇷🇮🇩
        """,
        parse_mode="Markdown",
    )
