"""Local, privacy-preserving sidebar accessibility diagnostics.

Does not retain chat names, project names, message text, URLs, or cookies.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from chat_discovery import (_all_controls, _control_name, _rect, _sidebar_bounds,
                            CHAT_LIST_NAMES, PROJECT_LIST_NAMES, NON_CHAT_LABELS)
from storage import APP_DIR


DIAGNOSTIC_PATH = APP_DIR / 'diagnostico_uia.json'


def describe_window(window, limit=900):
    window_bounds = _rect(window)
    cut, _ = _sidebar_bounds(window_bounds)
    known = CHAT_LIST_NAMES | PROJECT_LIST_NAMES | NON_CHAT_LABELS
    nodes = []
    for ctrl in _all_controls(window):
        try:
            rect = _rect(ctrl)
            if rect[0] >= cut or rect[2] > cut + 50:
                continue
            role = ctrl.element_info.control_type
            name = _control_name(ctrl)
            label = name.casefold() if name.casefold() in known else '[redacted]'
            if not ctrl.is_visible():
                continue
            parent_role = ''
            try:
                parent_role = ctrl.parent().element_info.control_type
            except Exception:
                pass
            nodes.append({
                'role': str(role), 'label_class': label,
                'named': bool(name), 'parent_role': str(parent_role),
                'rect': list(rect),
            })
            if len(nodes) >= limit:
                break
        except Exception:
            continue
    return {'format': 1, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'window_rect': list(window_bounds), 'sidebar_controls': nodes,
            'private_names_excluded': True,
            'note': 'Not a complete account inventory. No chat/project titles or messages stored.'}


def save_redacted_diagnostic(window, path=DIAGNOSTIC_PATH):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = describe_window(window)
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(destination)
    return destination
