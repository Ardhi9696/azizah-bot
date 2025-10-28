import os
from typing import Set


def load_admin_ids_from_env() -> Set[int]:
    raw = os.getenv("ADMIN_LIST", "") or ""
    ids: Set[int] = set()
    for part in [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]:
        try:
            ids.add(int(part))
        except ValueError:
            pass
    return ids


def load_protected_threads_from_env() -> Set[int]:
    """
    Daftar thread yang hanya boleh diisi admin.
    Contoh di .env:
      ADMIN_ONLY_THREADS=1336,1400,2001
    """
    raw = os.getenv("ADMIN_ONLY_THREADS", "") or ""
    threads: Set[int] = set()
    for part in [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]:
        try:
            threads.add(int(part))
        except ValueError:
            pass
    return threads
