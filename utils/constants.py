import os

DATA_DIR = "data"
LOG_DIR = "logs"

MODERATION_FILE = os.path.join(DATA_DIR, "moderation_keywords.json")
PENGUMUMAN_FILE = os.path.join(DATA_DIR, "get_info.json")
APPROVAL_FILE = os.path.join(DATA_DIR, "approval_status.json")
PRELIM_FILE = os.path.join(DATA_DIR, "get_prelim.json")
BANNED_FILE = os.path.join(DATA_DIR, "banned_users.json")
RESPON_FILE = os.path.join(DATA_DIR, "respon.json")
STRIKE_LOG = os.path.join(LOG_DIR, "strike.log")
EPS_DATA = os.path.join(DATA_DIR, "cache_eps.json")
EPS_PROGRESS = os.path.join(DATA_DIR, "progress_eps.json")
MONITOR_INFO = os.path.join(DATA_DIR, "cache_pengumuman.json")
MONITOR_PRELIM = os.path.join(DATA_DIR, "cache_training.json")
JADWAL_EPS = os.path.join(DATA_DIR, "cache_jadwal_eps.json")
JADWAL_REG_EPS = os.path.join(DATA_DIR, "cache_pendaftaran.json")
EPS_TAHAP1 = os.path.join(DATA_DIR, "cache_tahap1.json")
EPS_FINAL = os.path.join(DATA_DIR, "cache_tahap2.json")
LINK = os.path.join(DATA_DIR, "link.json")
TOPIK_ID = os.path.join(DATA_DIR, "topik_ids.json")
WHITELIST_LINK = os.path.join(DATA_DIR, "whitelist.json")
BLACKLIST_LINK = os.path.join(DATA_DIR, "blacklist.json")
