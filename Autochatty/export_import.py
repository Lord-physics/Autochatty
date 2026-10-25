"""Importar nombres e IDs de conversaciones desde una exportación oficial de ChatGPT.

Este módulo NO inventa títulos, ni infiere proyectos por palabras clave. Solo
acepta evidencia estructurada. El archivo ZIP se procesa localmente, no se sube.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import zipfile

MAX_JSON_SIZE = 60 * 1024 * 1024
MAX_CHATS = 30000
UNKNOWN_PROJECT = 'Sin proyecto verificado'


@dataclass(frozen=True)
class ExportedChat:
    title: str
    chat_id: str
    project: str = UNKNOWN_PROJECT
    project_id: str = ''
    source: str = 'exportacion'
    duplicates: int = 1


class InvalidExport(ValueError):
    pass


def _text(value, limit: int = 180) -> str:
    if not isinstance(value, str):
        return ''
    result = value.strip()
    return result if 1 <= len(result) <= limit and all(ord(c) >= 32 for c in result) else ''


def _json_member(zf: zipfile.ZipFile, basename: str):
    matches = [a for a in zf.infolist() if not a.is_dir() and a.filename.rsplit('/', 1)[-1] == basename]
    if len(matches) > 1:
        raise InvalidExport(f'Hay varios archivos {basename}; importación ambigua')
    if not matches:
        return None
    member = matches[0]
    if member.file_size > MAX_JSON_SIZE:
        raise InvalidExport(f'{basename} supera el tamaño permitido')
    with zf.open(member) as fh:
        raw = fh.read(MAX_JSON_SIZE + 1)
    if len(raw) > MAX_JSON_SIZE:
        raise InvalidExport(f'{basename} demasiado grande')
    try:
        return json.loads(raw.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidExport(f'{basename} no contiene JSON válido') from exc


def _projects(data) -> dict[str, str]:
    """Solo IDs que apuntan explícitamente a un nombre de proyecto."""
    if isinstance(data, dict):
        data = data.get('projects', [])
    if not isinstance(data, list):
        return {}
    out = {}
    for obj in data:
        if not isinstance(obj, dict):
            continue
        pid = _text(obj.get('id') or obj.get('project_id'), 180)
        name = _text(obj.get('name') or obj.get('title'), 160)
        if pid and name:
            out[pid] = name
    return out


def import_export(path: str | Path) -> list[ExportedChat]:
    """Lee conversations.json y, si existe, projects.json del ZIP oficial.

    Puede haber exportaciones sin projects.json, sin project_id o sin chats de
    proyecto; se presentan sin proyecto verificado y nunca se adivina.
    """
    try:
        with zipfile.ZipFile(path) as zf:
            data = _json_member(zf, 'conversations.json')
            if not isinstance(data, list):
                raise InvalidExport('No se encontró conversations.json con una lista de conversaciones')
            if len(data) > MAX_CHATS:
                raise InvalidExport('Demasiadas conversaciones en la exportación')
            projects = _projects(_json_member(zf, 'projects.json'))
    except (OSError, zipfile.BadZipFile) as exc:
        raise InvalidExport('Selecciona un ZIP de exportación válido de ChatGPT') from exc

    results: list[ExportedChat] = []
    seen_ids: set[str] = set()
    for row in data:
        if not isinstance(row, dict):
            continue
        title = _text(row.get('title'), 160)
        chat_id = _text(row.get('id') or row.get('conversation_id'), 180)
        if not title or not chat_id or chat_id in seen_ids:
            continue
        seen_ids.add(chat_id)
        pid = _text(row.get('project_id'), 180)
        project = projects.get(pid, UNKNOWN_PROJECT) if pid else UNKNOWN_PROJECT
        # Exportaciones futuras pueden incluir objeto relacional explícito.
        p = row.get('project')
        if isinstance(p, dict):
            structured_id = _text(p.get('id'), 180)
            structured_name = _text(p.get('name'), 160)
            if structured_id and structured_name and (not pid or structured_id == pid):
                pid, project = structured_id, structured_name
        results.append(ExportedChat(title, chat_id, project, pid))

    title_counts = {}
    for r in results:
        title_counts[r.title.casefold()] = title_counts.get(r.title.casefold(), 0) + 1
    return [ExportedChat(r.title, r.chat_id, r.project, r.project_id, r.source,
                         title_counts[r.title.casefold()]) for r in results]
