# handlers/eps_core/__init__.py

# Browser module
from .browser import (
    setup_browser,
    setup_simple_browser,
    setup_fast_browser,
    close_browser_stack,
    safe_goto,
    wait_for_selectors,
)

# Auth module
from .auth import (
    login_with,
    verifikasi_tanggal_lahir,
    normalize_birthday,
    quick_auth_check,
    full_auth_flow,
    check_auth_state,
    safe_navigation_and_auth,
    login_with_retry,
    verifikasi_tanggal_lahir_retry,
)

# Scraper module
from .scraper import (
    akses_progress,
    akses_progress_with_retry,
    quick_progress_check,
    get_page_snapshot,
    safe_scrape_progress,
)

# Formatter module
from .formatter import format_data

# Session Manager module
from .session_manager import (
    with_session_fast,
    with_session_async,
    with_session_sync_wrapper,
    ensure_session_fast,
    cleanup_idle_fast,
    cleanup_old_sessions,
    close_all_sessions,
    get_session_stats,
    health_check_session,
    health_check_all_sessions,
    cleanup_idle_sessions,
    force_cleanup_all,
)

# Navigator module
from .navigator import (
    _try_select_row2,
    _switch_to_ref,
    navigate_to_roster,
    get_available_rosters,
    get_current_roster_info,
    wait_for_page_update,
    safe_navigation,
    refresh_page_safe,
)

# Parsers module
from .parsers import (
    parse_pengiriman_table,
    parse_riwayat_table,
    extract_mediasi_from_riwayat,
    pick_latest,
)

# Link Extractor module
from .link_extractor import extract_job_links

# Utils module
from .utils import (
    normalize_birthday,
    to_int,
    roster_key,
    pick_latest as utils_pick_latest,
)

__all__ = [
    # ===== BROWSER =====
    "setup_browser",
    "setup_simple_browser",
    "setup_fast_browser",
    "close_browser_stack",
    "safe_goto",
    "wait_for_selectors",
    # ===== AUTH =====
    "login_with",
    "verifikasi_tanggal_lahir",
    "normalize_birthday",
    "quick_auth_check",
    "full_auth_flow",
    "check_auth_state",
    "safe_navigation_and_auth",
    "login_with_retry",
    "verifikasi_tanggal_lahir_retry",
    # ===== SCRAPER =====
    "akses_progress",
    "akses_progress_with_retry",
    "quick_progress_check",
    "get_page_snapshot",
    "safe_scrape_progress",
    # ===== FORMATTER =====
    "format_data",
    # ===== SESSION MANAGER =====
    "with_session_fast",
    "with_session_async",
    "with_session_sync_wrapper",
    "ensure_session_fast",
    "cleanup_idle_fast",
    "cleanup_old_sessions",
    "close_all_sessions",
    "get_session_stats",
    "health_check_session",
    "health_check_all_sessions",
    "cleanup_idle_sessions",
    "force_cleanup_all",
    # ===== NAVIGATOR =====
    "_try_select_row2",
    "_switch_to_ref",
    "navigate_to_roster",
    "get_available_rosters",
    "get_current_roster_info",
    "wait_for_page_update",
    "safe_navigation",
    "refresh_page_safe",
    # ===== PARSERS =====
    "parse_pengiriman_table",
    "parse_riwayat_table",
    "extract_mediasi_from_riwayat",
    "pick_latest",
    # ===== LINK EXTRACTOR =====
    "extract_job_links",
    # ===== UTILS =====
    "normalize_birthday",
    "to_int",
    "roster_key",
    "utils_pick_latest",
]

# ===== COMPATIBILITY ALIASES =====
# Untuk backward compatibility dengan code yang masih menggunakan nama lama
setup_driver = setup_browser
