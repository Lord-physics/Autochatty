"""Reglas de planificación puras, comprobables sin interfaz gráfica."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from urllib.parse import urlparse

ACTIVE = {'pendiente', 'en_curso', 'error'}


def parse_clock(s: str) -> time:
    try:
        hour, minute = map(int, s.strip().split(':'))
        assert 0 <= hour <= 23 and 0 <= minute <= 59
        return time(hour, minute)
    except (ValueError, AssertionError) as exc:
        raise ValueError('Utiliza horas HH:MM, por ejemplo 03:30.') from exc


def parse_times(s: str) -> list[time]:
    times = sorted(set(parse_clock(v) for v in s.split(',') if v.strip()))
    if not times:
        raise ValueError('Indica al menos una hora.')
    return times


def valid_chat_url(value: str) -> bool:
    try:
        p = urlparse(value.strip())
        return p.scheme == 'https' and p.hostname in {'chatgpt.com', 'chat.openai.com'} and p.path.startswith('/c/') and bool(p.path[3:].strip('/')) and not p.username and not p.password
    except ValueError:
        return False


def window_active(now: datetime, start: str, end: str) -> bool:
    a, b = parse_clock(start), parse_clock(end)
    t = now.time().replace(second=0, microsecond=0)
    if a == b:
        return True
    if a < b:
        return a <= t < b
    return t >= a or t < b  # cruza medianoche


def schedule_key(now: datetime, cfg: dict) -> str | None:
    mode = cfg.get('schedule_mode', 'ventana')
    if mode == 'ventana':
        if not window_active(now, cfg['window_start'], cfg['window_end']):
            return None
        # La comprobación temporal fina se realiza con last_run_at.
        return f'ventana:{now.date()}'
    if mode == 'horas':
        # 10 minutos de tolerancia cuando el equipo arranca tarde.
        for moment in parse_times(cfg['exact_times']):
            scheduled = now.replace(hour=moment.hour, minute=moment.minute, second=0, microsecond=0)
            if timedelta(0) <= now - scheduled < timedelta(minutes=10):
                return scheduled.strftime('hora:%Y-%m-%d:%H:%M')
    return None


def due(now: datetime, cfg: dict) -> tuple[bool, str]:
    if not cfg.get('enabled', True):
        return False, 'Programación pausada'
    key = schedule_key(now, cfg)
    if key is None:
        return False, 'Fuera del horario programado'
    if cfg.get('schedule_mode') == 'horas':
        if cfg.get('last_run_key') == key:
            return False, 'Esta hora ya se ha ejecutado'
    else:
        last = cfg.get('last_run_at', '')
        if last:
            try:
                previous = datetime.fromisoformat(last)
                if now - previous < timedelta(minutes=max(5, int(cfg.get('interval_minutes', 60)))):
                    return False, 'En espera del siguiente intervalo'
            except ValueError:
                pass
    return True, key


def candidate(chats: list[dict], now: datetime) -> dict | None:
    active = [c for c in chats if c.get('status', 'pendiente') in ACTIVE]
    selected = [c for c in active if c.get('selected')]
    possibilities = selected if selected else active
    def eligible(c: dict) -> bool:
        until = c.get('cooldown_until', '')
        if until:
            try:
                return datetime.fromisoformat(until) <= now
            except ValueError:
                return True
        return True
    possibilities = [c for c in possibilities if eligible(c)]
    # Se alterna entre los chats incompletos sin privilegiar siempre el primero.
    possibilities.sort(key=lambda c: (c.get('last_run_at', ''), c.get('name', '')))
    return possibilities[0] if possibilities else None
