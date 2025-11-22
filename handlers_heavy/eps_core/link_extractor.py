import re
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
from .constants import BASE


def extract_job_links(t2_soup: BeautifulSoup) -> dict:
    """
    Deteksi baris 'Keadaan pencarian pekerjaan'/'구직 진행상태', ambil link untuk URL/IMG/IMG2/ROAD VIEW.
    """
    if not t2_soup:
        return {}

    target_tr = None
    for tr in t2_soup.select("tbody tr"):
        tds = tr.select("td")
        if len(tds) < 2:
            continue
        header = (tds[0].get_text(strip=True) or "").strip()
        if header in ("Keadaan pencarian pekerjaan", "구직 진행상태"):
            target_tr = tr
            break
    if not target_tr:
        return {}

    detail_td = target_tr.select("td")[1]
    html = str(detail_td)
    links = {}

    m = re.search(r"urlMove\('([^']*)'\)", html)
    if m:
        raw = (m.group(1) or "").strip()
        if raw:
            links["url"] = raw

    m = re.search(r"rdViewOpen\('([^']*)'\)", html)
    if m:
        addr = (m.group(1) or "").strip()
        if addr:
            links["road_view"] = urljoin(
                BASE,
                f"/comm/pop/UserRdViewPopR.eo?bplcDrAd={quote(addr)}&encType=unicode",
            )

    m = re.search(r"fncFileOpen\('([^']*)','([^']*)','([^']*)','([^']*)'\)", html)
    if m:
        attFileNo, fileNm, docId, path = m.groups()
        if any([attFileNo, fileNm, docId, path]):
            qs = f"attFileNo={quote(attFileNo)}&fileNm={quote(fileNm)}&docId={quote(docId)}&path={quote(path)}&encType=unicode"
            links["img"] = urljoin(BASE, f"/comm/pop/UserInfoImgPopR.eo?{qs}")

    m = re.search(r"fncFileOpen2\('([^']*)','([^']*)','([^']*)','([^']*)'\)", html)
    if m:
        attFileNo, fileNm, docId, path = m.groups()
        if any([attFileNo, fileNm, docId, path]):
            qs = f"attFileNo={quote(attFileNo)}&fileNm={quote(fileNm)}&docId={quote(docId)}&path={quote(path)}&encType=unicode"
            links["img2"] = urljoin(BASE, f"/comm/pop/UserInfoImgPopR.eo?{qs}")

    # fallback: kalau hidden size > 0 tapi parameter kosong, kamu bisa tambah fallback endpoint di sini bila mau
    return links
