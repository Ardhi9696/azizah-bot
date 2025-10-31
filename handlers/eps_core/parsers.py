from typing import List, Dict, Tuple, Optional
import re
from bs4 import BeautifulSoup
from .constants import SEL, DATE_RE, RANGE_RE, NORMALIZE_LABELS, MEDIASI_LABELS


def _extract_first_date(text: str) -> str:
    m = DATE_RE.search(text or "")
    return m.group(0) if m else "-"


def _extract_date_range(text: str) -> Optional[str]:
    m = RANGE_RE.search(text or "")
    return m.group(1) if m else None


def parse_pengiriman_table(t1_soup: BeautifulSoup) -> List[Dict]:
    rows: List[Dict] = []
    for tr in t1_soup.select("tbody tr"):
        tds = tr.select("td")
        if len(tds) < 3:
            continue

        no_text = tds[0].get_text(strip=True)

        a_tag = tds[0].select_one(SEL["row_anchor"])
        ref_id = None
        if a_tag:
            href = a_tag.get("href") or ""
            m = re.search(r"fncDetailRow\('([^']+)'", href)
            if m:
                ref_id = m.group(1)

        tanggal_kirim = tds[1].get_text(" ", strip=True)
        penerimaan_raw = tds[2].get_text("\n", strip=True)

        rows.append(
            {
                "no": no_text,
                "ref_id": ref_id,
                "tanggal_kirim": tanggal_kirim,
                "tanggal_terima": _extract_first_date(penerimaan_raw),
                "masa_berlaku": _extract_date_range(penerimaan_raw),
                "raw": penerimaan_raw,
            }
        )
    return rows


def _clean_status_text(text: str) -> str:
    # ubah <br> jadi newline, hapus noise token tombol
    t = (text or "").replace("<br>", "\n").replace("<BR>", "\n")
    t = re.sub(r"\b(?:URL|IMG2?|ROAD VIEW)\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def _collapse_newlines(s: str) -> str:
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)  # maksimal 2 newline berturut
    return s.strip()


def parse_riwayat_table(t2_soup) -> List[Tuple[str, str, str]]:
    riwayat: List[Tuple[str, str, str]] = []
    for row in t2_soup.select("tbody tr"):
        cols = row.select("td")
        if len(cols) < 3:
            continue

        prosedur_raw = cols[0].get_text(strip=True)
        prosedur = NORMALIZE_LABELS.get(prosedur_raw, prosedur_raw)

        # ⬇️ ambil teks saja (bukan HTML), simpan <br> sebagai newline
        status_txt = cols[1].get_text("\n", strip=True)
        status_txt = _collapse_newlines(status_txt)

        tanggal = cols[2].get_text(" ", strip=True)

        if prosedur == "Jumlah pencocokan/mediasi pekerjaan" and not status_txt.strip():
            status_txt = "0"

        riwayat.append((prosedur, status_txt, tanggal))
    return riwayat


def extract_mediasi_from_riwayat(riwayat) -> str:
    for prosedur, status, _tgl in riwayat or []:
        label = (prosedur or "").strip()
        if label in MEDIASI_LABELS:
            m = re.search(r"\d+", (status or ""))
            return m.group(0) if m else (status or "-")
    return "-"


def pick_latest(pengiriman_list: List[Dict]) -> Optional[Dict]:
    """
    Ambil entry 'terbaru' berdasarkan kolom 'no' (angka roster paling besar).
    Fallback ke elemen terakhir jika parsing gagal.
    """
    if not pengiriman_list:
        return None
    try:
        import re as _re

        return max(
            pengiriman_list,
            key=lambda r: int(_re.sub(r"\D", "", r.get("no", "") or "0") or 0),
        )
    except Exception:
        return pengiriman_list[-1]
