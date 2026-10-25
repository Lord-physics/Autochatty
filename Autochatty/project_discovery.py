"""Inventory only project titles verified in the ChatGPT desktop accessibility tree.

A project and a chat are different things. This module does not treat a
project as a runnable chat and never manufactures a title or an ID.
"""
from dataclasses import dataclass
import time

from chat_discovery import (
    PROJECT_LIST_NAMES, CHAT_LIST_NAMES, NON_CHAT_LABELS,
    _all_controls, _control_name, _rect, _sidebar_bounds,
    _sidebar_headings, _clickable_ancestor, _scrollable, _scroll_percent,
    clean_title, scan_window_with_projects, discover_all_chats,
    MAX_SCROLL_STEPS, MAX_SCAN_SECONDS,
)
from app_adapter import ensure_app_window


@dataclass(frozen=True)
class DiscoveredProject:
    name: str
    source: str = 'uia'


def _project_section(control, window, bounds, headings):
    try:
        r = _rect(control)
        top = r[1]
        latest = None
        for ht, hb, label in headings:
            if hb > top or hb - ht > 90:
                continue
            if latest is None or ht > latest[0]:
                latest = (ht, label)
        if latest is not None and latest[1] in PROJECT_LIST_NAMES:
            return True
        ancestor = control
        for _ in range(12):
            ancestor = ancestor.parent()
            if ancestor is None or ancestor == window:
                break
            if (ancestor.element_info.control_type in {'Tree', 'List', 'Pane', 'Group'}
                    and _control_name(ancestor).casefold() in PROJECT_LIST_NAMES):
                return True
    except Exception:
        return False
    return False


def _verified_project_rows(window, controls):
    bounds = _rect(window)
    wl, wt, wr, wb = bounds
    cut, _ = _sidebar_bounds(bounds)
    headings = _sidebar_headings(controls, bounds)
    rows = []
    seen = set()
    for ctrl in controls:
        try:
            if not ctrl.is_visible():
                continue
            role = ctrl.element_info.control_type
            if role not in {'Button', 'Hyperlink', 'TreeItem', 'ListItem', 'Text'}:
                continue
            title = _control_name(ctrl)
            if not title or not 1 <= len(title) <= 160:
                continue
            if title.casefold() in NON_CHAT_LABELS | PROJECT_LIST_NAMES | CHAT_LIST_NAMES:
                continue
            x1, y1, x2, y2 = _rect(ctrl)
            if not (wl <= x1 < x2 <= cut and wt + 25 <= y1 < y2 <= wb - 15 and y2-y1 <= 90):
                continue
            nav = _clickable_ancestor(ctrl, window) if role == 'Text' else ctrl
            if nav is None or not _project_section(ctrl, window, bounds, headings):
                continue
            # Ignore subordinate links within an already verified project item.
            parent = nav
            nested = False
            for _ in range(8):
                parent = parent.parent()
                if parent is None or parent == window:
                    break
                if parent.element_info.control_type in {'TreeItem', 'ListItem', 'Hyperlink', 'Button'}:
                    # A child of a project is not another project.
                    nested = True
                    break
            if nested:
                continue
            identity = (title.casefold(), int((y1+y2)/24))
            if identity in seen:
                continue
            seen.add(identity)
            rows.append((ctrl, title))
        except Exception:
            continue
    return rows


def scan_visible_projects(window):
    try:
        controls = window.descendants()
        return [DiscoveredProject(name) for _, name in _verified_project_rows(window, controls)]
    except Exception:
        return []


def _project_scroll_containers(window):
    controls = _all_controls(window)
    targets = [control for control, _ in _verified_project_rows(window, controls)]
    for control in controls:
        try:
            if (control.element_info.control_type in {'List', 'Tree', 'Group', 'Pane'}
                    and _control_name(control).casefold() in PROJECT_LIST_NAMES):
                targets.append(control)
        except Exception:
            pass
    containers, seen = [], set()
    for target in targets:
        parent = target
        for _ in range(12):
            try:
                scroll = _scrollable(parent)
                if scroll is not None:
                    key = (getattr(parent,'handle',id(parent)), _rect(parent))
                    if key not in seen:
                        seen.add(key)
                        containers.append(scroll)
                    break
                parent = parent.parent()
                if parent is None or parent == window:
                    break
            except Exception:
                break
    # A Projects section can be below the initial viewport. Include only
    # scrollable sidebar panes, never the right-hand conversation pane.
    bounds = _rect(window)
    cut, _ = _sidebar_bounds(bounds)
    for candidate in controls:
        try:
            if not candidate.is_visible():
                continue
            if candidate.element_info.control_type not in {'Pane', 'Group', 'List', 'Tree'}:
                continue
            left, top, right, bottom = _rect(candidate)
            if right > cut + 35 or bottom - top < 180:
                continue
            scroll = _scrollable(candidate)
            if scroll is None:
                continue
            key = (getattr(candidate,'handle',id(candidate)), _rect(candidate))
            if key not in seen:
                seen.add(key)
                containers.append(scroll)
        except Exception:
            continue
    return containers


def discover_projects(window, deadline, limit=500):
    """Scroll accessible project navigation; never inspect conversation bodies."""
    seen = {}
    def collect():
        for item in scan_visible_projects(window):
            seen[item.name.casefold()] = item
    collect()
    for scroll in _project_scroll_containers(window):
        if time.monotonic() >= deadline or len(seen) >= limit:
            break
        original = _scroll_percent(scroll)
        try:
            if original is not None and original > 0:
                scroll.SetScrollPercent(-1.0, 0.0)
                time.sleep(.1)
            prev = None
            for _ in range(MAX_SCROLL_STEPS):
                if time.monotonic() >= deadline or len(seen) >= limit:
                    break
                collect()
                pos = _scroll_percent(scroll)
                if pos is None or pos >= 99.9 or (prev is not None and pos <= prev):
                    break
                prev = pos
                try:
                    scroll.ScrollVertical(3)
                except Exception:
                    break
                time.sleep(.12)
            collect()
        finally:
            if original is not None:
                try:
                    scroll.SetScrollPercent(-1.0, original)
                except Exception:
                    pass
    return list(seen.values())


def discover_inventory(seconds=MAX_SCAN_SECONDS):
    """Return (verified chats, verified projects), not an account-wide inventory.

    Project names can be visible without their chats being exposed. These projects
    must not be silently omitted or converted to fake chat entries.
    """
    window = ensure_app_window()
    deadline = time.monotonic() + max(2, min(float(seconds), 90))
    chats = discover_all_chats(seconds=max(1, deadline-time.monotonic()), window=window)
    projects = discover_projects(window, deadline)
    for chat in chats:
        if chat.project and chat.project != 'Sin proyecto verificado':
            projects.append(DiscoveredProject(chat.project))
    unique = {x.name.casefold(): x for x in projects}
    return chats, sorted(unique.values(), key=lambda x: x.name.casefold())
