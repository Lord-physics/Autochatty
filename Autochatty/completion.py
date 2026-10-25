"""Protocolo de cierre con identificadores de intento y validación conservadora.

El modelo *declara* finalización; esto no demuestra por sí solo que realizó el
trabajo. Solo una señal en la respuesta final del asistente permite cerrar.
"""
from __future__ import annotations

import re
import secrets
from pathlib import Path

STATES = {'TERMINADO': 'done', 'PENDIENTE': 'pending', 'BLOQUEADO': 'blocked'}
TOKEN_RE = re.compile(r'^[0-9a-f]{24}$')


def new_token() -> str:
    return secrets.token_hex(12)


def marker(token: str, state: str) -> str:
    if not TOKEN_RE.fullmatch(token) or state not in STATES:
        raise ValueError('Marcador inválido')
    return f'[[CONTROL_CHATGPT:{token}:{state}]]'


def add_protocol(instruction: str, token: str, criteria: str = '') -> str:
    """Añade contrato de salida sin cambiar los objetivos del trabajo."""
    return (
        instruction.strip() + '\n\n'
        'PROTOCOLO DE ESTADO DEL CONTROLADOR (solo para esta continuación):\n'
        'Realiza el trabajo solicitado. Al final de tu respuesta, después de un resumen '
        'breve y concreto de lo realizado y de lo que falte, escribe EXACTAMENTE una '
        'de estas tres líneas, sin comillas, sin formato Markdown y sin texto después:\n'
        f'{marker(token, "TERMINADO")} = SOLO si el trabajo completo está realmente '
        'terminado y comprobado, sin partes pendientes.\n'
        f'{marker(token, "PENDIENTE")} = si queda trabajo por hacer y puedes retomarlo más tarde.\n'
        f'{marker(token, "BLOQUEADO")} = si necesitas datos, autenticación o una '
        'autorización humana para continuar.\n'
        'No coloques marcadores en el cuerpo ni en bloques de código. No declares '
        'TERMINADO solo porque hayas terminado de redactar una respuesta. Si no puedes '
        'comprobar el resultado solicitado, utiliza PENDIENTE o BLOQUEADO.\n'
        + (f'CRITERIOS EXPLÍCITOS DE FIN (TODOS obligatorios):\n{criteria.strip()}\n'
           if criteria.strip() else '')
    )


def interpret(text: str | None, token: str, expected_files: str = '') -> tuple[str, str]:
    """Requiere marcador exacto y exclusivo en la ÚLTIMA línea del asistente.

    Ninguna salida indefinida se convierte por defecto en "terminado".
    """
    if not text or not TOKEN_RE.fullmatch(token):
        return 'unknown', 'No hay respuesta verificable del asistente'
    lines = text.strip().splitlines()
    final = lines[-1].strip() if lines else ''
    matching = [state for state in STATES if final == marker(token, state)]
    if len(matching) != 1:
        return 'unknown', 'La respuesta no termina con una señal de cierre válida'
    state = matching[0]
    if text.count(f'[[CONTROL_CHATGPT:{token}:') != 1:
        return 'unknown', 'El marcador aparece varias veces: requiere revisión'
    if not '\n'.join(lines[:-1]).strip():
        return 'unknown', 'Falta el resumen previo que justifica el estado'
    if state == 'TERMINADO' and expected_files.strip():
        missing = missing_files(expected_files)
        if missing:
            return 'unverified', 'Faltan archivos locales requeridos: ' + '; '.join(missing[:3])
    return STATES[state], {
        'TERMINADO': 'Marcador de terminación confirmado (declaración del asistente)',
        'PENDIENTE': 'El asistente declara que falta trabajo',
        'BLOQUEADO': 'El asistente solicita intervención o autorización',
    }[state]


def missing_files(paths: str) -> list[str]:
    """Verifica solo archivos explícitamente indicados por el usuario; no ejecuta nada."""
    failures = []
    for raw in paths.splitlines():
        name = raw.strip().strip('"')
        if not name:
            continue
        p = Path(name).expanduser()
        try:
            if not p.is_file() or p.stat().st_size < 1:
                failures.append(name)
        except (OSError, ValueError):
            failures.append(name)
    return failures
