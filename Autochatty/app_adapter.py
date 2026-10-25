"""Adaptador CONSERVADOR para la aplicacion oficial de ChatGPT en Windows.

Solo consulta nombres/roles de controles UIA (no el cuerpo de respuestas).
Ante cualquier ambiguedad, NO escribe, pulsa ni envia en el chat.
"""
from __future__ import annotations

import ctypes
import re
import subprocess
import time

APP_EXES = {'chatgpt.exe', 'chatgptdesktop.exe', 'chatgptapp.exe', 'openai.chatgpt.exe', 'codex.exe', 'applicationframehost.exe'}
BLOCKED_EXES = {'msedge.exe', 'chrome.exe', 'firefox.exe', 'python.exe', 'pythonw.exe'}
COMPOSER = re.compile(r'^(message( chatgpt)?|send a message|ask anything|pregunta lo que quieras|pregunta algo|escribe un mensaje|mensaje( a chatgpt)?|prompt)(\b.*)?$', re.I)
SEARCH = re.compile(r'^(search|buscar|search chats|buscar chats|search conversations|buscar conversaciones)(\b.*)?$', re.I)
STOP = re.compile(r'^(stop( generating| streaming| response)?|detener( generaci[oó]n| respuesta)?)(\b.*)?$', re.I)


class UnsafeUI(RuntimeError):
    """No se puede determinar con seguridad el destino de una accion."""


def allowed_window(title: str, executable: str) -> bool:
    """El navegador y el propio controlador jamas se reconocen como la app."""
    exe = executable.casefold()
    name = title.strip().casefold()
    return (name == 'chatgpt' or name.startswith('chatgpt -')) and (exe in APP_EXES or (exe.startswith('chatgpt') and exe.endswith('.exe')))


def interactive_desktop() -> bool:
    """La sesion debe tener escritorio de entrada Default; no operar bloqueada."""
    if not hasattr(ctypes, 'windll'):
        return False
    user = ctypes.windll.user32
    user.OpenInputDesktop.restype = ctypes.c_void_p
    desk = user.OpenInputDesktop(0, False, 1)
    if not desk:
        return False
    try:
        length = ctypes.c_uint(0)
        buf = ctypes.create_unicode_buffer(80)
        # UOI_NAME = 2, DESKTOP_READOBJECTS = 0x0001
        if not user.GetUserObjectInformationW(ctypes.c_void_p(desk), 2, buf,
                                               ctypes.sizeof(buf), ctypes.byref(length)):
            return False
        return buf.value.casefold() == 'default'
    finally:
        user.CloseDesktop(ctypes.c_void_p(desk))


def locate_window():
    """Detecta una UNICA ventana oficial, sin confundir paginas de navegador."""
    from pywinauto import Desktop
    import psutil
    matches = []
    for w in Desktop(backend='uia').windows():
        try:
            if not w.is_visible():
                continue
            name = psutil.Process(w.process_id()).name()
            if allowed_window(w.window_text(), name):
                matches.append(w)
        except Exception:
            continue
    if len(matches) != 1:
        raise UnsafeUI(f'Esperaba 1 ventana de ChatGPT; encontradas {len(matches)}. '
                       'Cierra ventanas duplicadas y comprueba que la app esta abierta.')
    return matches[0]


def launch_app() -> None:
    """Abre el acceso instalado en el menu Inicio, sin iniciar ningun navegador."""
    if not interactive_desktop():
        raise UnsafeUI('Sesion Windows bloqueada o no interactiva')
    command = ('$apps = @(Get-StartApps | Where-Object { '
               "$_.Name -eq 'ChatGPT' -or $_.Name -eq 'OpenAI ChatGPT' }); "
               'if ($apps.Count -ne 1) { exit 22 }; '
               '[Console]::Write($apps[0].AppID)')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                            text=True, capture_output=True, timeout=25)
    appid = result.stdout.strip()
    if result.returncode or not appid or '\n' in appid:
        raise UnsafeUI('No se encontro un acceso unico de ChatGPT en Inicio. '
                       'Abre ChatGPT manualmente y vuelve a probar.')
    subprocess.Popen(['explorer.exe', 'shell:AppsFolder\\' + appid])


def ensure_app_window(timeout: float = 35):
    if not interactive_desktop():
        raise UnsafeUI('Escritorio bloqueado; no se pueden utilizar controles de la app')
    try:
        return locate_window()
    except UnsafeUI:
        launch_app()
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                return locate_window()
            except UnsafeUI:
                time.sleep(1.5)
    raise UnsafeUI('No se encontro la ventana oficial de ChatGPT despues de abrirla')


def focused_on_app(window) -> bool:
    """Verificacion adicional inmediatamente antes de enviar teclas globales."""
    if not interactive_desktop():
        return False
    try:
        import win32gui
        fg = win32gui.GetForegroundWindow()
        root = win32gui.GetAncestor(fg, 2)  # GA_ROOT
        return root == window.handle
    except Exception:
        return False


def _focus(window):
    window.set_focus()
    time.sleep(0.25)
    if not focused_on_app(window):
        raise UnsafeUI('ChatGPT no mantiene el foco; cancelado para evitar escribir en otra aplicacion')


def _visible_controls(window, pattern, kinds):
    found = []
    for ctrl in window.descendants():
        try:
            if ctrl.element_info.control_type not in kinds or not ctrl.is_visible():
                continue
            if pattern.fullmatch(ctrl.window_text().strip()):
                found.append(ctrl)
        except Exception:
            continue
    return found


def _click(window, control):
    _focus(window)
    control.click_input()
    time.sleep(0.4)
    if not focused_on_app(window):
        raise UnsafeUI('Se perdio el foco tras el clic')


def _sidebar_candidates(window, label: str):
    """Solo controles activables; no botones de salida del asistente ni texto suelto."""
    exact = re.compile(re.escape(label.strip()), re.I)
    candidates = _visible_controls(window, exact, {'Button', 'ListItem', 'TreeItem', 'Hyperlink'})
    try:
        root = window.rectangle()
        cut = root.left + (root.right - root.left) * .45
        return [c for c in candidates if c.rectangle().right <= cut and
                c.rectangle().left >= root.left and c.rectangle().top >= root.top + 35]
    except Exception:
        return []  # Nunca hacer clic si no se puede verificar la zona lateral


def _verify_selected_chat(window, selected_control, title: str) -> None:
    '''Verificacion adicional: elemento seleccionado o encabezado del chat.

    Una coincidencia simple en la barra lateral NO demuestra el chat activo.
    '''
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        try:
            # Solo procede si Windows UIA expone SelectionItemPattern.
            if selected_control.element_info.control_type in ('ListItem', 'TreeItem'):
                if selected_control.iface_selection_item.CurrentIsSelected:
                    return
        except Exception:
            pass
        # Encabezado independiente: NO texto de respuestas ni titulo de barra lateral.
        headings = _visible_controls(window, re.compile(re.escape(title.strip()), re.I), {'Header'})
        try:
            root = window.rectangle()
            mid = root.left + (root.right - root.left) * .45
            headings = [h for h in headings if h.rectangle().left >= mid]
        except Exception:
            headings = []
        if len(headings) == 1:
            return
        time.sleep(0.5)
    raise UnsafeUI('El titulo coincide, pero no se pudo verificar el chat activo. '
                   'No se enviara nada automaticamente.')


def select_chat(window, title: str):
    if not title.strip():
        raise UnsafeUI('Falta titulo exacto del chat en la aplicacion')
    matches = _sidebar_candidates(window, title)
    if len(matches) == 1:
        _click(window, matches[0])
        _verify_selected_chat(window, matches[0], title)
        return
    if len(matches) > 1:
        raise UnsafeUI('Varios chats tienen el mismo titulo; utiliza un titulo unico')

    searches = _visible_controls(window, SEARCH, {'Button', 'Hyperlink'})
    if len(searches) != 1:
        raise UnsafeUI('No se localizo el chat ni una busqueda unica. Abre el chat manualmente.')
    _click(window, searches[0])
    # Buscar un campo inequívoco: no cualquier cuadro de texto de la ventana.
    fields = _visible_controls(window, SEARCH, {'Edit'})
    if len(fields) != 1:
        raise UnsafeUI('Campo de busqueda ambiguo; no se escribira nada')
    from pywinauto.keyboard import send_keys
    _click(window, fields[0])
    if not focused_on_app(window):
        raise UnsafeUI('Se perdio el foco en la busqueda')
    send_keys('^a')
    send_keys(title, with_spaces=True, pause=0.02)
    time.sleep(1.8)
    matches = _sidebar_candidates(window, title)
    if len(matches) != 1:
        raise UnsafeUI('La busqueda no encontro un unico resultado EXACTO del chat')
    _click(window, matches[0])
    _verify_selected_chat(window, matches[0], title)


def find_composer(window):
    controls = _visible_controls(window, COMPOSER, {'Edit'})
    if len(controls) != 1:
        raise UnsafeUI('No se identifico con certeza el campo de redaccion del chat')
    return controls[0]


def prepare_chat(window, chat_title: str):
    select_chat(window, chat_title)
    # Si solo se abre, no hace falta localizar el editor.
    return window


def submit(window, text: str) -> None:
    """Solo se ejecuta tras consentimiento de envio automatico.

    Evita extraer respuestas de ChatGPT. Usa portapapeles del usuario para pegar;
    se notifica este efecto en la documentacion.
    """
    import pyperclip
    from pywinauto.keyboard import send_keys
    editor = find_composer(window)
    _click(window, editor)
    if not focused_on_app(window):
        raise UnsafeUI('Se perdio el foco del editor')
    pyperclip.copy(text)
    send_keys('^v')
    time.sleep(0.3)
    if not focused_on_app(window):
        raise UnsafeUI('El foco cambio antes de enviar. Comprueba el borrador manualmente')
    send_keys('{ENTER}')


def generating(window) -> bool:
    """Señal SOLO visual. NO implica que la tarea este completa."""
    return len(_visible_controls(window, STOP, {'Button'})) > 0
