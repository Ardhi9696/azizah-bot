# Thin wrapper untuk kompatibilitas setelah pemecahan auth menjadi beberapa berkas.
# Modul implementasi dipecah ke auth_core.py, auth_fast.py, auth_state.py.
from .auth_core import *  # noqa: F401,F403
from .auth_fast import *  # noqa: F401,F403
from .auth_state import *  # noqa: F401,F403

# Ekspos __all__ gabungan
from .auth_core import __all__ as _core_all  # noqa: E402
from .auth_fast import __all__ as _fast_all  # noqa: E402
from .auth_state import __all__ as _state_all  # noqa: E402

__all__ = list(_core_all) + list(_fast_all) + list(_state_all)
