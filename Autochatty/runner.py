"""Motor de la app oficial de Windows (SIN Edge ni extraccion de respuestas).

Se puede abrir y ubicar un chat. Envio automatico: experimental, estricto y
por defecto apagado. Solo señales LOCALES pueden cerrar un intento automaticamente.
"""
from __future__ import annotations

import ctypes
import os
import time
from typing import Callable

import app_adapter
import signals
from completion import add_protocol, TOKEN_RE

MAX_WAIT_SECONDS = 60 * 45


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
        ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
        ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
        ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
        ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
    ]


def free_ram_percent() -> float:
    if os.name != 'nt':
        return 100.0
    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(status)
    return (100 * status.ullAvailPhys / max(1, status.ullTotalPhys)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else 0.0)


def cpu_percent() -> float:
    try:
        import psutil
        return float(psutil.cpu_percent(interval=0.8))
    except ImportError:
        return 100.0  # Prohibir automatizar si falta medida de recursos


def open_login_profile() -> None:
    """Compatibilidad con el boton antiguo: ahora abre la app, no Edge."""
    app_adapter.ensure_app_window()


def _observe(window, chat: dict, report: Callable[[str], None]) -> tuple[str, str]:
    """No interpreta contenido del chat; espera senal JSON local o revision."""
    start = time.monotonic()
    last_busy = start
    ever_busy = False
    while time.monotonic() - start < MAX_WAIT_SECONDS:
        status = signals.check(chat)
        if status:
            # La senal puede estar lista antes de cesar la generacion; la espera no
            # es necesaria para validar un archivo local ya escrito por un agente.
            return status
        if not app_adapter.interactive_desktop():
            return 'review', 'Windows bloqueado durante el intento; revisa el chat'
        try:
            active = app_adapter.generating(window)
        except Exception:
            return 'review', 'Se perdio la conexion con la ventana; revisa antes de reenviar'
        now = time.monotonic()
        if active:
            last_busy = now
            ever_busy = True
        if not active and now - last_busy >= (40 if ever_busy else 100):
            return 'review', 'Respuesta detenida, pero sin senal local verificada; requiere revision'
        time.sleep(3)
    return 'timeout', 'Limite de espera de observacion. No se reenvia el intento'


def run(chat: dict, auto_send: bool, minimum_free_ram: int, report=None, on_sent=None,
        *, fresh_attempt: bool = True, max_cpu: int = 65) -> tuple[str, str]:
    report = report or (lambda _msg: None)
    if os.name != 'nt':
        return 'error', 'Esta version necesita Windows 10/11'
    if free_ram_percent() < minimum_free_ram:
        return 'memory', 'Poca memoria libre. Ejecucion aplazada'
    if cpu_percent() > max_cpu:
        return 'memory', 'Procesador muy ocupado. Ejecucion aplazada'
    try:
        # Para un intento anterior, solo leer la señal externa; nunca reenviar a ciegas.
        if auto_send and not fresh_attempt:
            signal = signals.check(chat)
            return signal if signal else ('review', 'Intento anterior incierto: no se reenvia automaticamente')
        report('Abriendo la aplicacion oficial de ChatGPT...')
        window = app_adapter.ensure_app_window()
        report('Buscando la conversacion por su titulo exacto...')
        app_adapter.prepare_chat(window, chat.get('app_title') or chat['name'])
        if not auto_send:
            return 'opened', 'Chat localizado en la app. Envio desactivado; puedes continuar manualmente'
        token = chat.get('pending_token', '')
        if not TOKEN_RE.fullmatch(token):
            return 'review', 'Falta un token valido; no se enviara un intento incierto'
        # Envio protegido por el token persistido ANTES de llegar aqui.
        instruction = add_protocol(chat['instruction'], token, chat.get('done_criteria', ''))
        report('Enviando una sola continuacion a un chat identificado...')
        try:
            app_adapter.submit(window, instruction)
        except Exception as exc:
            return 'review', f'Envio incierto ({type(exc).__name__}): {str(exc)[:180]}. No se reenvia'
        if on_sent:
            on_sent()
        report('Esperando, sin inspeccionar respuestas; se comprueba señal local...')
        return _observe(window, chat, report)
    except app_adapter.UnsafeUI as exc:
        return 'review', str(exc)
    except (OSError, RuntimeError, ImportError) as exc:
        return 'error', f'No se pudo controlar la app: {str(exc)[:220]}'
