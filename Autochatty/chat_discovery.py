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
    'your chats', 'tus chats', 'recents', 'recent', 'chats recientes', 'conversaciones recientes', 'recent items', 'recent items',
})
WHITESPACE = re.compile(r'\s+')
PROJECT_LIST_NAMES = frozenset({'proyectos', 'projects', 'your projects', 'tus proyectos'})
# Navigational controls are never treated as conversations, even inside a sidebar.
NON_CHAT_LABELS = frozenset({
    'nuevo chat', 'new chat', 'chat nuevo', 'new conversation', 'nueva conversacion',
    'buscar', 'buscar chats', 'search', 'search chats', 'buscar conversaciones',
    'search conversations', 'biblioteca', 'library', 'gpts', 'explorar gpts',
    'explore gpts', 'explorar', 'explore', 'archivados', 'archived',
    'ajustes', 'settings', 'ayuda', 'help', 'perfil', 'profile',
    'ver mas', 'ver más', 'show more', 'see more', 'more', 'más', 'mas',
    'ocultar barra lateral', 'hide sidebar', 'close sidebar',
    'abrir barra lateral', 'open sidebar', 'mostrar barra lateral', 'show sidebar',
    'proyectos', 'projects', 'your projects', 'tus proyectos',
    'crear proyecto', 'new project', 'nuevo proyecto',
    'espacios de trabajo', 'workspaces', 'workspace', 'recientes', 'recent',
    'chats', 'tus chats', 'your chats', 'historial', 'history', 'recents', 'recent items', 'recents', 'recent items',
})
SECTION_BOUNDARIES = NON_CHAT_LABELS | PROJECT_LIST_NAMES
SIDEBAR_TOGGLE_LABELS = frozenset({
    'abrir barra lateral', 'open sidebar', 'mostrar barra lateral', 'show sidebar',
    'expand sidebar', 'expandir barra lateral',
})
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


def _sidebar_bounds(window_rect: tuple) -> tuple[float, float]:
    wl, wt, wr, wb = window_rect
    return wl + min(500.0, .55 * (wr - wl)), wt + 25


def is_candidate(title: str, role: str, rect: tuple, window_rect: tuple) -> bool:
    """Geometry and label check; structural proof is required separately.

    Hyperlinks are used by Chromium/WebView2 accessible sidebars. Generic
    Buttons and Text controls cannot qualify on their own.
    """
    if role not in {'ListItem', 'TreeItem', 'Hyperlink'} or not isinstance(title, str):
        return False
    title = clean_title(title)
    if (not 1 <= len(title) <= 160 or any(ord(c) < 32 for c in title)
            or title.casefold() in NON_CHAT_LABELS | CHAT_LIST_NAMES | PROJECT_LIST_NAMES):
        return False
    left, top, right, bottom = rect
    wl, wt, wr, wb = window_rect
    cut, upper = _sidebar_bounds(window_rect)
    return (wr - wl >= 360 and wb - wt >= 240 and
            wl <= left < right <= cut and
            upper <= top < bottom <= wb - 15 and bottom - top <= 85)


def _control_name(control) -> str:
    """Use only verbatim accessible names, never text generated from a guess."""
    try:
        name = control.window_text()
        if not name:
            name = control.element_info.name
        return clean_title(name) if isinstance(name, str) else ''
    except Exception:
        return ''


def _sidebar_headings(controls, bounds):
    """Visible genuine section headings, including Chromium's Text controls."""
    cut, upper = _sidebar_bounds(bounds)
    wl, wt, _, _ = bounds
    headings = []
    for ctrl in controls:
        try:
            if not ctrl.is_visible():
                continue
            label = _control_name(ctrl).casefold()
            if label not in CHAT_LIST_NAMES | SECTION_BOUNDARIES:
                continue
            role = ctrl.element_info.control_type
            if role not in {'Text', 'Header', 'Group', 'Pane', 'List', 'Tree', 'Button'}:
                continue
            left, top, right, bottom = _rect(ctrl)
            if wl <= left < right <= cut and top >= wt + 20 and bottom <= bounds[3]:
                headings.append((top, bottom, label))
        except Exception:
            continue
    return sorted(set(headings))


def _in_chat_heading_region(control, bounds, headings) -> bool:
    """Positive section heading + spatially following sidebar row.

    Stops at the next visible non-chat section; importantly, it never infers a
    chat from arbitrary response text or a loose left-aligned label.
    """
    try:
        left, top, right, bottom = _rect(control)
    except Exception:
        return False
    latest = None
    for heading_top, heading_bottom, label in headings:
        # A labelled pane may span the whole sidebar; only headings are boundaries.
        if heading_bottom > top or heading_bottom - heading_top > 90:
            continue
        if latest is None or heading_top > latest[0]:
            latest = (heading_top, label)
    return bool(latest and latest[1] in CHAT_LIST_NAMES)


def _clickable_ancestor(control, window):
    """A Text child can identify a chat only if nested in a real nav item."""
    cursor = control
    for _ in range(3):
        try:
            cursor = cursor.parent()
            if cursor is None or cursor == window:
                break
            if cursor.element_info.control_type in {'Hyperlink', 'ListItem', 'TreeItem', 'Button'}:
                return cursor
        except Exception:
            break
    return None


def _candidate_row(control, window, bounds, headings):
    try:
        if not control.is_visible():
            return None
        role = control.element_info.control_type
        title = _control_name(control)
        # WebView2 may expose chat navigation as a Button. A button is only
        # accepted AFTER an observed chat section heading or named chat list.
        navigation = control
        if role == 'Text':
            navigation = _clickable_ancestor(control, window)
            if navigation is None:
                return None  # plain sidebar labels aren't clickable conversations
        elif role not in {'Button', 'ListItem', 'TreeItem', 'Hyperlink'}:
            return None
        if not is_candidate(title, 'Hyperlink', _rect(control), bounds):
            return None
        if not (_within_explicit_chat_list(navigation, window)
                or _in_chat_heading_region(control, bounds, headings)):
            return None
        # Do not mistake an actual section heading for a chat even if clickable.
        if title.casefold() in SECTION_BOUNDARIES:
            return None
        return title
    except Exception:
        return None


def _chat_rows(window, controls, bounds):
    headings = _sidebar_headings(controls, bounds)
    rows = []
    for ctrl in controls:
        title = _candidate_row(ctrl, window, bounds, headings)
        if title:
            rows.append((ctrl, title))
    return rows

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
    for ctrl, title in _chat_rows(window, controls, bounds):
        rect = _rect(ctrl)
        key = (title.casefold(), int((rect[1] + rect[3]) / 24))
        if key in seen_rows:
            continue
        seen_rows.add(key)
        titles.append(title)
        if len(titles) >= limit:
            break
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
        return _control_name(project)
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
    """Real UIA navigation names and only hierarchy-verified projects."""
    try:
        controls = window.descendants()
        bounds = _rect(window)
    except Exception as exc:
        raise UnsafeUI('No se pudo leer la jerarquía de accesibilidad') from exc
    counts = {}
    seen = set()
    for ctrl, title in _chat_rows(window, controls, bounds):
        rect = _rect(ctrl)
        project = _project_for_chat(ctrl, window)
        key = (project.casefold(), title.casefold())
        # The same row may be exposed by several accessibility wrappers.
        identity = (*key, int((rect[1] + rect[3]) / 24))
        if identity in seen:
            continue
        seen.add(identity)
        if key not in counts:
            counts[key] = [title, project, 0]
        counts[key][2] += 1
        if len(counts) >= limit:
            break
    return [DiscoveredChat(name, count, project) for name, project, count in counts.values()]


def _scroll_containers(window):
    """Find scroll parents of VERIFIED chat rows, even if their UIA name is empty."""
    controls = _all_controls(window)
    try:
        bounds = _rect(window)
    except Exception:
        return []
    accepted = [c for c, _ in _chat_rows(window, controls, bounds)]
    cut, _ = _sidebar_bounds(bounds)
    unique, seen = [], set()
    for ctrl in accepted:
        parent = ctrl
        for _ in range(12):
            try:
                parent = parent.parent()
                if parent is None or parent == window:
                    break
                rect = _rect(parent)
                if rect[0] >= cut or rect[2] > cut + 35:
                    continue
                scroll = _scrollable(parent)
                if scroll is not None and id(parent) not in seen:
                    seen.add(id(parent))
                    unique.append((parent, scroll))
                    break
            except Exception:
                break
    # Also retain the original explicitly named chat list scanning strategy.
    for ctrl in controls:
        if _is_named_list(ctrl, CHAT_LIST_NAMES):
            scroll = _scrollable(ctrl)
            if scroll is not None and id(ctrl) not in seen:
                unique.append((ctrl, scroll))
                seen.add(id(ctrl))
    return unique


def _expand_sidebar_if_closed(window):
    """Open only a UIA button explicitly labelled 'Open sidebar' (safe fallback)."""
    try:
        bounds = _rect(window)
        wl, wt, _, _ = bounds
        candidates = []
        for ctrl in _all_controls(window):
            if ctrl.element_info.control_type != 'Button' or not ctrl.is_visible():
                continue
            if _control_name(ctrl).casefold() not in SIDEBAR_TOGGLE_LABELS:
                continue
            x1, y1, x2, y2 = _rect(ctrl)
            if wl <= x1 < x2 <= wl + 175 and wt <= y1 < y2 <= wt + 160:
                candidates.append(ctrl)
        if len(candidates) != 1:
            return False
        from app_adapter import _focus
        _focus(window)
        candidates[0].click_input()
        time.sleep(.45)
        return True
    except Exception:
        return False

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


def discover_all_chats(limit: int = 2000, seconds: float = MAX_SCAN_SECONDS, window=None) -> list[DiscoveredChat]:
    """Best-effort passive inventory of sidebar, including UIA scroll ranges.

    Does not open messages, scrape network requests, read cookies or local caches,
    or pretend that a virtualized sidebar is the complete account history.
    Restores original scroll position when UIA permits it.
    """
    if not 1 <= limit <= 5000:
        raise ValueError('Límite fuera de rango')
    window = window if window is not None else ensure_app_window()
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
    if not records and _expand_sidebar_if_closed(window):
        collect()
    # WebView may paint before its accessibility navigation tree exists.
    # A bounded warm-up avoids reporting zero chats just after launching ChatGPT.
    retry_deadline = min(deadline, time.monotonic() + 4.0)
    while not records and time.monotonic() < retry_deadline:
        time.sleep(.55)
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
