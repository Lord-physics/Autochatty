"""Validacion opcional de senales locales escritas por un agente con acceso al PC.

No lee mensajes de ChatGPT. El archivo nunca basta si falta un entregable exigido.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from uuid import UUID

from completion import TOKEN_RE, missing_files
from storage import APP_DIR

SIGNAL_DIR = APP_DIR / 'senales'
STATUSES = {'TERMINADO': 'done', 'PENDIENTE': 'pending', 'BLOQUEADO': 'blocked'}


def signal_path(chat: dict) -> Path:
    uid = str(UUID(chat['id']))  # No permitir desplazamiento de rutas por JSON alterado
    return SIGNAL_DIR / f'{uid}.json'


def check(chat: dict) -> tuple[str, str] | None:
    token = chat.get('pending_token', '')
    if not TOKEN_RE.fullmatch(token):
        return None
    try:
        path = signal_path(chat)
        if not path.exists():
            return None
        if path.stat().st_size > 8192:
            return 'review', 'Senal local demasiado grande'
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('chat_id') != chat['id'] or data.get('token') != token:
            return None  # Senal vieja o de otro intento; no clasificar
        label = data.get('estado', '')
        if label not in STATUSES:
            return 'review', 'Estado de senal local invalido'
        state = STATUSES[label]
        if state == 'done':
            missing = missing_files(chat.get('expected_files', ''))
            if missing:
                return 'review', 'Senal TERMINADO pero faltan archivos locales: ' + ', '.join(missing)[:300]
        note = str(data.get('detalle', '')).strip()[:250]
        return state, (note or f'Senal local verificada: {label}')
    except (ValueError, OSError, json.JSONDecodeError, TypeError, KeyError):
        return 'review', 'No se pudo validar la senal local'


def write_signal(chat_id: str, token: str, estado: str, detalle: str = '') -> Path:
    """Para agentes locales: escribe atomica y explícitamente la prueba de estado."""
    cid = str(UUID(chat_id))
    if not TOKEN_RE.fullmatch(token) or estado not in STATUSES:
        raise ValueError('Token o estado incorrecto')
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    destination = SIGNAL_DIR / f'{cid}.json'
    data = {'chat_id': cid, 'token': token, 'estado': estado, 'detalle': detalle[:250]}
    fd, temp_path = tempfile.mkstemp(prefix='senal_', suffix='.tmp', dir=SIGNAL_DIR)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, destination)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return destination
