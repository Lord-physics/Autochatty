"""Herramienta para un agente LOCAL que pueda demostrar fin de trabajo.

Uso: py -3 crear_senal.py --chat 'Nombre' --estado TERMINADO --detalle 'Hecho'
La ruta se escribe en el perfil local; solo acepta chats con intento activo.
"""
from __future__ import annotations

import argparse
import sys

import signals
import storage
from completion import TOKEN_RE


def main(args=None) -> int:
    parser = argparse.ArgumentParser(description='Comunicar avance local al controlador ChatGPT')
    parser.add_argument('--chat', required=True, help='Nombre exacto del chat registrado')
    parser.add_argument('--estado', required=True, choices=['TERMINADO', 'PENDIENTE', 'BLOQUEADO'])
    parser.add_argument('--detalle', default='')
    opt = parser.parse_args(args)
    cfg = storage.load()
    matches = [c for c in cfg['chats'] if c['name'] == opt.chat]
    if len(matches) != 1:
        print('ERROR: debe existir exactamente un chat con ese nombre', file=sys.stderr)
        return 2
    chat = matches[0]
    if not TOKEN_RE.fullmatch(chat.get('pending_token', '')):
        print('ERROR: el chat no tiene un intento activo', file=sys.stderr)
        return 3
    if opt.estado == 'TERMINADO':
        missing = signals.missing_files(chat.get('expected_files', ''))
        if missing:
            print('ERROR: faltan entregables exigidos: ' + ', '.join(missing), file=sys.stderr)
            return 4
    dest = signals.write_signal(chat['id'], chat['pending_token'], opt.estado, opt.detalle)
    print(f'Senal creada: {dest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
