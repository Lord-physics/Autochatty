"""Impide dos controladores con la misma cola, incluso tras el despertar."""
from __future__ import annotations

import os
from pathlib import Path

from storage import APP_DIR

_LOCK = None


def acquire() -> bool:
    global _LOCK
    if os.name != 'nt':
        return True
    import msvcrt
    APP_DIR.mkdir(parents=True, exist_ok=True)
    path = APP_DIR / 'controlador.lock'
    file = open(path, 'a+b')
    file.seek(0, os.SEEK_END)
    if file.tell() == 0:
        file.write(b'0')
        file.flush()
    try:
        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        file.close()
        return False
    _LOCK = file
    return True
