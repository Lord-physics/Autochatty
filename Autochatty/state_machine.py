"""Transiciones de estado puras para evitar declarar éxito sin una prueba válida."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

from completion import new_token


def prepare_attempt(chat: dict, auto_send: bool,
                    token_factory: Callable[[], str] = new_token) -> None:
    if auto_send and not chat.get('pending_token'):
        chat['pending_token'] = token_factory()
        chat['attempt_state'] = 'prepared'


def mark_submitted(chat: dict) -> None:
    chat['attempt_state'] = 'submitted'
    chat['status'] = 'en_curso'


def reset_attempt(chat: dict, status: str) -> None:
    chat['status'] = status
    chat['pending_token'] = ''
    chat['attempt_state'] = ''
    chat['cooldown_until'] = ''


def apply_result(chat: dict, state: str, summary: str, now: datetime) -> None:
    chat['last_result'] = summary
    if state in ('done', 'pending', 'blocked'):
        reset_attempt(chat, {
            'done': 'terminado', 'pending': 'pendiente', 'blocked': 'bloqueado',
        }[state])
    elif state == 'review':
        chat['status'] = 'revision'
        # La señal del intento se conserva para revisión forense manual.
    elif state == 'timeout':
        chat['status'] = 'en_curso'
        chat['cooldown_until'] = (now + timedelta(minutes=30)).isoformat()
    elif state == 'error':
        chat['status'] = 'error'
        chat['cooldown_until'] = (now + timedelta(hours=2)).isoformat()
    elif state == 'memory':
        chat['cooldown_until'] = (now + timedelta(minutes=30)).isoformat()
