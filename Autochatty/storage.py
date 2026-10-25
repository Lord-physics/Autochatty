"""Persistencia local: sin nube y con escritura atómica."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

APP_DIR = Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'ControladorChatGPT'
CONFIG_FILE = APP_DIR / 'controlador.json'


def defaults() -> dict:
    return {
        'version': 8,
        'schedule_mode': 'ventana',
        'window_start': '02:00',
        'window_end': '06:00',
        'exact_times': '02:00, 05:00',
        'interval_minutes': 60,
        'min_memory_free_percent': 12,
        'max_cpu_percent': 65,
        'auto_send': False,
        'enabled': True,
        'last_run_key': '',
        'last_run_at': '',
        'chats': [],
    }


def load() -> dict:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    cfg = defaults()
    if CONFIG_FILE.is_file():
        try:
            saved = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
            if isinstance(saved, dict):
                cfg.update({k: v for k, v in saved.items() if k in cfg})
                if not isinstance(cfg['chats'], list):
                    cfg['chats'] = []
                if int(cfg.get('version', 2)) < 3:
                    # Nunca heredar el permiso experimental de envio desde Edge.
                    cfg['auto_send'] = False
                    for chat in cfg['chats']:
                        chat.setdefault('app_title', chat.get('name', ''))
                        if chat.get('pending_token') or chat.get('attempt_state'):
                            chat['status'] = 'revision'
                            chat['last_result'] = 'Migrado de v2: revisar el intento anterior manualmente'
                            chat['pending_token'] = ''
                            chat['attempt_state'] = ''
                    cfg['version'] = 8
                else:
                    for chat in cfg['chats']:
                        chat.setdefault('app_title', chat.get('name', ''))
                    if int(cfg.get('version', 3)) < 5:
                        cfg['auto_send'] = False  # Nuevo adaptador UIA: volver a confirmar permiso
                    cfg['version'] = 8
                for chat in cfg['chats']:
                    chat.setdefault('project', 'Sin proyecto verificado')
                    chat.setdefault('project_id', '')
                    chat.setdefault('chat_id', '')
                    chat.setdefault('source', 'manual')
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def save(cfg: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix='estado_', suffix='.tmp', dir=APP_DIR)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, CONFIG_FILE)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def new_chat(name: str, url: str, instruction: str) -> dict:
    from uuid import uuid4
    return {
        'id': str(uuid4()),
        'name': name,
        'url': url,
        'app_title': name,
        'project': 'Sin proyecto verificado',
        'project_id': '',
        'chat_id': '',
        'source': 'manual',
        'instruction': instruction,
        'selected': False,
        'status': 'pendiente',
        'last_run_at': '',
        'last_result': '',
        'cooldown_until': '',
        'done_criteria': '',
        'expected_files': '',
        'pending_token': '',
        'attempt_state': '',
    }


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')
