# constants.py

# URLs & constants
LOGIN_URL = "https://www.eps.go.kr/eo/langMain.eo?langCD=in"
PROGRESS_URL = (
    "https://www.eps.go.kr/eo/EntProgCk.eo?pgID=P_000000015&langCD=in&menuID=10008"
)
BASE = "https://www.eps.go.kr"

# Regex precompiled
import re

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2}~\d{4}-\d{2}-\d{2})")

# Normalisasi label & mapping emoji
NORMALIZE_LABELS = {
    "알선 횟수": "Jumlah pencocokan/mediasi pekerjaan",
    "고용허가제 한국어능력시험": "Ujian Bahasa Korea",
    "Korean Language Test": "Ujian Bahasa Korea",
}

MEDIASI_LABELS = {"Jumlah pencocokan/mediasi pekerjaan", "알선 횟수"}

EMOJI_MAP = {
    "Ujian Bahasa Korea": "📝",
    "Tanggal Pengiriman Daftar Pencari Kerja": "📮",
    "Tanggal Penerimaan Daftar Pencari Kerja": "📥",
    "Keadaan pencarian pekerjaan": "🏢",
    "Pengeluaran Izin Kerja": "📄",
    "Pengiriman SLC": "📤",
    "Penandatanganan SLC": "✍️",
    "Pengeluaran CCVI": "📑",
    "Tanggal Masuk Sementara": "🛬",
    "Tanggal Masuk Sesungguhnya": "🛬",
    "Penugasan kerja": "📌",
    # Korea
    "고용허가제 한국어능력시험": "📝",
    "구직자명부 전송일": "📮",
    "구직자명부 인증일": "📥",
    "구직 진행상태": "🏢",
    "고용허가서 발급": "📄",
    "표준근로계약서 전송": "📤",
    "표준근로계약 체결": "✍️",
    "사증발급인정서 발급": "📑",
    "입국예상일": "🛬",
    "실제입국일": "🛬",
    "사업장 배치": "📌",
    # baris baru:
    "Jumlah pencocokan/mediasi pekerjaan": "🔹",
    "알선 횟수": "🔹",
}

# Single unified selector map (used across navigator/scraper/parsers)
SEL = {
    "nama_ready": "table.tbl_typeA.center",
    "nama_value": "table.tbl_typeA.center td:nth-child(2)",
    "tables_purple": "table.tbl_typeA.purple.mt30",
    "row_anchor": 'a[href^="javascript:fncDetailRow("]',
    # Fallback selectors
    "any_purple_table": "table.purple",
    "any_table": "table",
    "nama_fallback": "td:nth-child(2)",
}
