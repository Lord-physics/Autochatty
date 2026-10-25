"""Lectura conservadora de nombres de chats en UIA de la aplicación Windows.

No se leen mensajes, no se inventan títulos y NO se asume que el historial visible
es completo. Una fila de UIA no equivale por sí sola a una conversación confirmada:
solo se consideran filas pertenecientes a una lista explícita de chats.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import time
from app_adapter import UnsafeUI, ensure_app_window

UNKNOWN_PROJECT = 'Sin proyecto verificado'
CHAT_LIST_NAMES = frozenset({
    'chats', 'conversaciones', 'recent chats', 'recent conversations',
    'recientes', 'historial de chats', 'chat history', 'history', 'historial',
    'your chats', 'tus chats',
})
WHITESPACE = re.compile(r'\s+')
PROJECT_LIST_NAMES = frozenset({'proyectos', 'projects', 'your projects', 'tus proyectos'})
MAX_SCAN_SECONDS = 24
MAX_SCROLL_STEPS = 36



@dataclass(frozen=True)
class DiscoveredChat:
    title: str
    duplicates: int = 1
    project: str = UNKNOWN_PROJECT
    chat_id: str = ''
    source: str = 'uia'


def clean_title(s: str) -> str:
    return WHITESPACE.sub(' ', s).strip()


def is_candidate(title: str, role: str, rect: tuple, window_rect: tuple) -> bool:
    if role not in {'ListItem', 'TreeItem'} or not isinstance(title, str):
        return False
    title = clean_title(title)
    if not 1 <= len(title) <= 160 or any(ord(c) < 32 for c in title):
        return False
    if title.casefold() in CHAT_LIST_NAMES:
        return False
    left, top, right, bottom = rect
    wl, wt, wr, wb = window_rect
    width, height = wr - wl, wb - wt
    return (width >= 460 and height >= 300 and
            wl <= left < right <= wl + .45 * width and
            wt + 35 <= top < bottom <= wb - 35 and bottom - top <= 65)


def consolidate_titles(titles: list[str]) -> list[DiscoveredChat]:
    grouped = {}
    for value in titles:
        title = clean_title(value)
        key = title.casefold()
        name, count = grouped.get(key, (title, 0))
        grouped[key] = name, count + 1
    return [DiscoveredChat(title, count) for title, count in grouped.values()]


def _rect(ctrl):
    r = ctrl.rectangle()
    return (r.left, r.top, r.right, r.bottom)


def _project_ancestor(control, window):
    """Return verified project TreeItem only if it belongs to a Projects list.

    This uses hierarchy, never similarity of names. The project heading itself
    is not counted as a chat. A plain project label is not enough.
    """
    child = control
    for _ in range(12):
        try:
            parent = child.parent()
            if parent is None or parent == window:
                return None
            if parent.element_info.control_type in {'TreeItem','Group'}:
                grand = parent.parent()
                while grand is not None and grand != window:
                    if _is_named_list(grand, PROJECT_LIST_NAMES):
                        if child != parent and clean_title(parent.window_text()):
                            return parent
                        break
                    grand = grand.parent()
            child = parent
        except Exception:
            break
    return None


def _within_explicit_chat_list(ctrl, window) -> bool:
    """Require a verified Chats list OR a nested chat in an explicit Projects tree."""
    cursor = ctrl
    for _ in range(12):
        try:
            cursor = cursor.parent()
            if cursor is None or cursor == window:
                break
            label = clean_title(cursor.window_text()).casefold()
            kind = cursor.element_info.control_type
            if kind in {'List', 'Tree', 'Group', 'Pane'} and label in CHAT_LIST_NAMES:
                return True
        except Exception:
            return False
    return _project_ancestor(ctrl,window) is not None


def scan_window(window, limit: int = 500) -> list[DiscoveredChat]:
    if not 1 <= limit <= 2000:
        raise ValueError('Límite fuera de rango')
    try:
        controls = window.descendants()
        bounds = _rect(window)
    except Exception as exc:
        raise UnsafeUI('Windows no expone controles de la aplicación') from exc
    seen_rows: set[tuple] = set()
    titles = []
    for ctrl in controls:
        try:
            if not ctrl.is_visible():
                continue
            title = clean_title(ctrl.window_text())
            if not is_candidate(title, ctrl.element_info.control_type, _rect(ctrl), bounds):
                continue
            if not _within_explicit_chat_list(ctrl, window):
                continue
            rect = _rect(ctrl)
            key = (title.casefold(), int((rect[1] + rect[3]) / 24))
            if key in seen_rows:
                continue
            seen_rows.add(key)
            titles.append(title)
            if len(titles) >= limit:
                break
        except Exception:
            continue
    return consolidate_titles(titles)


def _all_controls(window):
    try:
        return window.descendants()
    except Exception:
        return []


def _is_named_list(control, names: frozenset[str]):
    try:
        return (control.element_info.control_type in {'List', 'Tree', 'Group', 'Pane'}
                and clean_title(control.window_text()).casefold() in names
                and control.is_visible())
    except Exception:
        return False


def _scrollable(control):
    try:
        scroll = control.iface_scroll
        if scroll.CurrentVerticallyScrollable:
            return scroll
    except Exception:
        pass
    return None


def _scroll_percent(scroll):
    try:
        return float(scroll.CurrentVerticalScrollPercent)
    except Exception:
        return None


def _project_for_chat(control, window) -> str:
    """Project only from verified UIA hierarchy; otherwise unverified."""
    project=_project_ancestor(control,window)
    if project is not None:
        return clean_title(project.window_text())
    child=control
    for _ in range(12):
        try:
            parent=child.parent()
            if parent is None or parent == window:
                break
            if _is_named_list(parent,CHAT_LIST_NAMES):
                project_control=parent.parent()
                if project_control and project_control!=window:
                    label=clean_title(project_control.window_text())
                    kind=project_control.element_info.control_type
                    if (kind in {'TreeItem','Group'} and label and
                        label.casefold() not in CHAT_LIST_NAMES | PROJECT_LIST_NAMES and
                        len(label)<=160):
                        return label
            child=parent
        except Exception:
            break
    return UNKNOWN_PROJECT


def scan_window_with_projects(window, limit: int = 500) -> list[DiscoveredChat]:
    """Returns ONLY actual accessible chat rows, with verified UIA project parents."""
    results = scan_window(window, limit)
    if not results:
        return results
    mapping = {}
    for ctrl in _all_controls(window):
        try:
            title = clean_title(ctrl.window_text())
            if not title or ctrl.element_info.control_type not in {'ListItem', 'TreeItem'}:
                continue
            if not ctrl.is_visible() or not _within_explicit_chat_list(ctrl, window):
                continue
            project = _project_for_chat(ctrl, window)
            if project != UNKNOWN_PROJECT:
                mapping.setdefault(title.casefold(), set()).add(project)
        except Exception:
            continue
    return [DiscoveredChat(c.title, c.duplicates,
            next(iter(mapping[c.title.casefold()])) if len(mapping.get(c.title.casefold(), ())) == 1 else UNKNOWN_PROJECT,
            c.chat_id, c.source) for c in results]


def _scroll_containers(window):
    """Only scan explicitly labelled CHAT lists (never conversation body)."""
    unique = []
    for ctrl in _all_controls(window):
        if _is_named_list(ctrl, CHAT_LIST_NAMES):
            scroll = _scrollable(ctrl)
            if scroll is not None:
                unique.append((ctrl, scroll))
    return unique


def _project_expanders(window):
    """Only expand verified project rows, restore collapsed states later."""
    items=[]
    for ctrl in _all_controls(window):
        try:
            if ctrl.element_info.control_type not in {'TreeItem','Group'} or not ctrl.is_visible():
                continue
            ancestor=ctrl.parent()
            verified=False
            while ancestor is not None and ancestor!=window:
                if _is_named_list(ancestor,PROJECT_LIST_NAMES):
                    verified=True
                    break
                ancestor=ancestor.parent()
            if not verified:
                continue
            # ExpandCollapseState_Collapsed = 0
            exp=ctrl.iface_expand_collapse
            if exp.CurrentExpandCollapseState==0:
                items.append((ctrl,exp))
        except Exception:
            continue
    return items


def discover_all_chats(limit: int = 2000, seconds: float = MAX_SCAN_SECONDS) -> list[DiscoveredChat]:
    """Best-effort passive inventory of sidebar, including UIA scroll ranges.

    Does not open messages, scrape network requests, read cookies or local caches,
    or pretend that a virtualized sidebar is the complete account history.
    Restores original scroll position when UIA permits it.
    """
    if not 1 <= limit <= 5000:
        raise ValueError('Límite fuera de rango')
    window = ensure_app_window()
    deadline = time.monotonic() + max(1, min(float(seconds), 75))
    records: dict[tuple[str, str], DiscoveredChat] = {}
    ambiguous: set[str] = set()

    def collect():
        for c in scan_window_with_projects(window, min(limit, 2000)):
            key = (c.project.casefold(), c.title.casefold())
            if key not in records:
                records[key] = c
            if c.duplicates > 1:
                ambiguous.add(c.title.casefold())

    collect()
    # Expand any clearly identified project group, not random navigation items.
    expanded=[]
    try:
        for ctrl, exp in _project_expanders(window):
            if time.monotonic()>=deadline:
                break
            try:
                exp.Expand()
                expanded.append(exp)
                time.sleep(.10)
                collect()
            except Exception:
                continue
    finally:
        # Keep restored state after scanning the resulting lists below.
        pass
    for ctrl, scroll in _scroll_containers(window):
        if time.monotonic() >= deadline or len(records) >= limit:
            break
        original = _scroll_percent(scroll)
        try:
            # Begin at top to find older rows beyond initial viewport.
            if original is not None and original > 0:
                scroll.SetScrollPercent(-1.0, 0.0)
                time.sleep(.15)
            last = None
            for _ in range(MAX_SCROLL_STEPS):
                if time.monotonic() >= deadline or len(records) >= limit:
                    break
                collect()
                position = _scroll_percent(scroll)
                if position is None or position >= 99.9 or (last is not None and position <= last):
                    break
                last = position
                try:
                    # UIA ScrollAmount_LargeIncrement=3
                    scroll.ScrollVertical(3)
                except Exception:
                    break
                time.sleep(.12)
            collect()
        except Exception:
            pass
        finally:
            if original is not None:
                try:
                    scroll.SetScrollPercent(-1.0, original)
                except Exception:
                    pass
    for exp in reversed(expanded):
        try:
            exp.Collapse()
        except Exception:
            pass
    # Treat duplicates with same title across distinct visible project groups as
    # ambiguous too: selection in the app is by title only.
    counts = {}
    for c in records.values():
        counts[c.title.casefold()] = counts.get(c.title.casefold(), 0) + 1
    return [DiscoveredChat(c.title,
                           max(c.duplicates, 2 if c.title.casefold() in ambiguous or counts[c.title.casefold()] > 1 else 1),
                           c.project, c.chat_id, c.source) for c in records.values()]


def discover_visible_chats() -> list[DiscoveredChat]:
    return discover_all_chats()
