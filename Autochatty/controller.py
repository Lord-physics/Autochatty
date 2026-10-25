"""Interfaz Windows para programar y serializar chats de ChatGPT."""
from __future__ import annotations

import ctypes
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import runner
import signals
import completion
import state_machine
import scheduler
import storage
import chat_discovery
import export_import

HERE = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
DEFAULT_INSTRUCTION = (
    'Continúa el trabajo pendiente de este chat sin repetir acciones terminadas. '
    'Avanza lo máximo posible. Si hay una limitación de uso o necesitas autorización, '
    'detente sin inventar resultados. Indica lo que queda por hacer.'
)


def python_gui() -> str:
    p = Path(sys.executable)
    if p.name.lower() == 'python.exe' and p.with_name('pythonw.exe').exists():
        return str(p.with_name('pythonw.exe'))
    return str(p)


class ChatDialog(tk.Toplevel):
    def __init__(self, parent, chat=None):
        super().__init__(parent)
        self.title('Editar chat' if chat else 'Añadir chat')
        self.geometry('745x615')
        self.minsize(635, 565)
        self.result = None
        self.transient(parent)
        self.grab_set()
        self.columnconfigure(1, weight=1)
        self.name = tk.StringVar(value=(chat or {}).get('name', ''))
        self.url = tk.StringVar(value=(chat or {}).get('url', ''))
        self.app_title = tk.StringVar(value=(chat or {}).get('app_title', (chat or {}).get('name', '')))
        ttk.Label(self, text='Nombre:').grid(row=0, column=0, padx=12, pady=12, sticky='w')
        ttk.Entry(self, textvariable=self.name).grid(row=0, column=1, padx=12, pady=12, sticky='ew')
        ttk.Label(self, text='Titulo exacto en la app:').grid(row=1, column=0, padx=12, pady=8, sticky='w')
        ttk.Entry(self, textvariable=self.app_title).grid(row=1, column=1, padx=12, pady=8, sticky='ew')
        ttk.Label(self, text='Instrucción al continuar:').grid(row=2, column=0, columnspan=2, padx=12, pady=(12, 0), sticky='w')
        self.prompt = tk.Text(self, height=6, wrap='word')
        self.prompt.insert('1.0', (chat or {}).get('instruction', DEFAULT_INSTRUCTION))
        self.prompt.grid(row=3, column=0, columnspan=2, padx=12, pady=6, sticky='nsew')
        ttk.Label(self, text='Criterios de terminación (recomendado: qué debe haberse completado):').grid(
            row=4, column=0, columnspan=2, padx=12, sticky='w')
        self.criteria = tk.Text(self, height=4, wrap='word')
        self.criteria.insert('1.0', (chat or {}).get('done_criteria', ''))
        self.criteria.grid(row=5, column=0, columnspan=2, padx=12, pady=6, sticky='nsew')
        ttk.Label(self, text='Archivos locales exigidos (opcional; ruta completa, uno por línea):').grid(
            row=6, column=0, columnspan=2, padx=12, sticky='w')
        self.files = tk.Text(self, height=3, wrap='word')
        self.files.insert('1.0', (chat or {}).get('expected_files', ''))
        self.files.grid(row=7, column=0, columnspan=2, padx=12, pady=6, sticky='nsew')
        self.rowconfigure(3, weight=1)
        self.rowconfigure(5, weight=1)
        self.rowconfigure(7, weight=1)
        ttk.Label(self, text='URL del chat (opcional, solo referencia; no se abre navegador):',
                  foreground='#526070').grid(row=8, column=0, padx=12, sticky='w')
        ttk.Entry(self, textvariable=self.url).grid(row=8, column=1, padx=12, pady=3, sticky='ew')
        controls = ttk.Frame(self)
        controls.grid(row=9, column=0, columnspan=2, pady=8)
        ttk.Button(controls, text='Guardar', command=self.accept).pack(side='left', padx=10)
        ttk.Button(controls, text='Cancelar', command=self.destroy).pack(side='left', padx=10)
        self.bind('<Escape>', lambda _: self.destroy())
        self.wait_visibility()
        self.focus_set()

    def accept(self):
        if not self.name.get().strip():
            messagebox.showerror('Nombre', 'Introduce un nombre.', parent=self)
            return
        if not self.app_title.get().strip():
            messagebox.showerror('Titulo', 'Escribe el titulo exacto del chat en ChatGPT.', parent=self)
            return
        if self.url.get().strip() and not scheduler.valid_chat_url(self.url.get()):
            messagebox.showerror('URL', 'La URL es opcional; si la indicas ha de ser https://chatgpt.com/c/...', parent=self)
            return
        instruction = self.prompt.get('1.0', 'end').strip()
        if not instruction:
            messagebox.showerror('Instrucción', 'Escribe qué debe hacer el chat al continuar.', parent=self)
            return
        self.result = (self.name.get().strip(), self.url.get().strip(), self.app_title.get().strip(), instruction,
                       self.criteria.get('1.0', 'end').strip(), self.files.get('1.0', 'end').strip())
        self.destroy()


class Controller(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Autochatty v6 - Seleccion automatica de chats')
        self.geometry('1140x780')
        self.minsize(800, 580)
        self.cfg = storage.load()
        self.messages = queue.Queue()
        self.busy = False
        self.scanning = False
        self.paused_by_user = False
        self.current_id = None
        self.batch = []  # Cola en memoria: IDs de chats elegidos en este turno
        self.build_ui()
        self.draw_chats()
        self.after(1000, self.tick)
        # Descubre los chats al abrir el controlador, sin clics previos.
        self.after(1400, self.discover_chats)
        self.protocol('WM_DELETE_WINDOW', self.close)

    def build_ui(self):
        container = ttk.Frame(self, padding=14)
        container.pack(fill='both', expand=True)
        title = ttk.Frame(container)
        title.pack(fill='x')
        ttk.Label(title, text='Controlador de trabajos de ChatGPT', font=('Segoe UI', 16, 'bold')).pack(side='left')
        self.status = tk.StringVar(value='Listo')
        ttk.Label(title, textvariable=self.status, foreground='#2d6e8d').pack(side='right')

        schedule = ttk.LabelFrame(container, text='1. Programación', padding=12)
        schedule.pack(fill='x', pady=(12, 8))
        self.mode = tk.StringVar(value=self.cfg['schedule_mode'])
        self.window_start = tk.StringVar(value=self.cfg['window_start'])
        self.window_end = tk.StringVar(value=self.cfg['window_end'])
        self.exact_times = tk.StringVar(value=self.cfg['exact_times'])
        self.interval = tk.StringVar(value=str(self.cfg['interval_minutes']))
        self.ram = tk.StringVar(value=str(self.cfg['min_memory_free_percent']))
        self.cpu = tk.StringVar(value=str(self.cfg.get('max_cpu_percent', 65)))
        self.autosend = tk.BooleanVar(value=bool(self.cfg['auto_send']))
        self.enabled = tk.BooleanVar(value=bool(self.cfg['enabled']))
        a = ttk.Frame(schedule)
        a.pack(fill='x', pady=4)
        ttk.Radiobutton(a, text='Por franja', variable=self.mode, value='ventana').pack(side='left')
        ttk.Label(a, text='Desde').pack(side='left', padx=(14, 3))
        ttk.Entry(a, textvariable=self.window_start, width=7).pack(side='left')
        ttk.Label(a, text='hasta').pack(side='left', padx=(10, 3))
        ttk.Entry(a, textvariable=self.window_end, width=7).pack(side='left')
        ttk.Label(a, text='Repetir cada (min)').pack(side='left', padx=(15, 4))
        ttk.Entry(a, textvariable=self.interval, width=5).pack(side='left')
        b = ttk.Frame(schedule)
        b.pack(fill='x', pady=4)
        ttk.Radiobutton(b, text='A horas exactas', variable=self.mode, value='horas').pack(side='left')
        ttk.Label(b, text='Horas HH:MM, separadas por comas:').pack(side='left', padx=(16, 4))
        ttk.Entry(b, textvariable=self.exact_times, width=30).pack(side='left')
        c = ttk.Frame(schedule)
        c.pack(fill='x', pady=(10, 2))
        ttk.Label(c, text='RAM libre mínima (%)').pack(side='left')
        ttk.Entry(c, textvariable=self.ram, width=5).pack(side='left', padx=5)
        ttk.Label(c, text='CPU max. (%)').pack(side='left', padx=(10, 0))
        ttk.Entry(c, textvariable=self.cpu, width=5).pack(side='left', padx=5)
        ttk.Checkbutton(c, text='Enviar automaticamente en la app (EXPERIMENTAL)', variable=self.autosend).pack(side='left', padx=18)
        ttk.Checkbutton(c, text='Programación activa', variable=self.enabled).pack(side='left')

        chatsbox = ttk.LabelFrame(container, text='2. Chats: seleccionados por orden; si ninguno esta marcado, un pendiente por turno', padding=10)
        chatsbox.pack(fill='both', expand=True, pady=8)
        cols = ('mark', 'name', 'status', 'last', 'result')
        self.tree = ttk.Treeview(chatsbox, columns=cols, show='tree headings', height=10, selectmode='browse')
        for key, name, width in [
            ('mark', 'Elegido', 65), ('name', 'Chat', 215), ('status', 'Estado', 110),
            ('last', 'Última vez', 145), ('result', 'Último resultado', 460),
        ]:
            self.tree.heading(key, text=name)
            self.tree.column(key, width=width, stretch=key in ('name', 'result'))
        self.tree.heading('#0', text='Proyecto')
        self.tree.column('#0', width=125, stretch=True)
        self.tree.pack(fill='both', expand=True, side='left')
        scrollbar = ttk.Scrollbar(chatsbox, orient='vertical', command=self.tree.yview)
        scrollbar.pack(side='left', fill='y')
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind('<Double-1>', lambda _: self.toggle_selection())
        actions = ttk.Frame(container)
        actions.pack(fill='x', pady=6)
        for index, (text, fn) in enumerate([
            ('Actualizar chats detectados', self.discover_chats), ('+ Añadir chat', self.add_chat), ('Editar', self.edit_chat), ('Eliminar', self.delete_chat),
            ('Elegir/quitar', self.toggle_selection), ('Verificar respuesta', self.verify_pasted), ('Marcar terminado', self.mark_done),
            ('Reabrir pendiente', self.mark_pending), ('Pausar chat', self.mark_paused),
        ]):
            # Two compact rows prevent hidden actions on 1366x768 Windows screens.
            if index == 6:
                actions = ttk.Frame(container)
                actions.pack(fill='x', pady=3)
            ttk.Button(actions, text=text, command=fn).pack(side='left', padx=(0, 6))
        controls = ttk.Frame(container)
        controls.pack(fill='x', pady=8)
        for text, fn in [
            ('Guardar horario', self.save_config), ('Ejecutar ahora', self.run_now),
            ('Pausar/reanudar', self.toggle_pause), ('Abrir app ChatGPT', self.login),
            ('Iniciar con Windows', self.autostart), ('Configurar despertar', self.install_wake), ('Comprobar señales', self.poll_signals),
        ]:
            ttk.Button(controls, text=text, command=fn).pack(side='left', padx=(0, 6))
        self.info = tk.StringVar(value='Modo seguro: abre la app. Envio automatico solo si activas la casilla experimental.')
        ttk.Label(container, textvariable=self.info, foreground='#56677b', wraplength=1020).pack(fill='x', pady=6)
        ttk.Label(container, text='Fin: una señal LOCAL verificable o confirmacion manual. No lee respuestas ni conoce cuotas. '
                  'La app debe estar visible y Windows desbloqueado. Sin prueba, el chat queda en REVISION.',
                  foreground='#815925', wraplength=1020).pack(fill='x')

    def draw_chats(self):
        chosen = self.tree.selection()
        selected_id = chosen[0] if chosen else None
        self.tree.delete(*self.tree.get_children())
        groups = {}
        for c in self.cfg['chats']:
            project = c.get('project') or export_import.UNKNOWN_PROJECT
            if project not in groups:
                key = 'proyecto:' + str(len(groups))
                groups[project] = key
                self.tree.insert('', 'end', iid=key, text=project, open=True,
                                 values=('', '📁 ' + project, '', '', ''))
            when = (c.get('last_run_at') or '').replace('T', ' ')[:16]
            origin = c.get('source', 'manual')
            self.tree.insert(groups[project], 'end', iid=c['id'], values=(
                '✓' if c.get('selected') else '—', c['name'], c.get('status', 'pendiente'),
                when, (f'[{origin}] ' + c.get('last_result', ''))[:90],
            ))
        if selected_id and self.tree.exists(selected_id):
            self.tree.selection_set(selected_id)

    def selected_chat(self):
        selection = self.tree.selection()
        return next((c for c in self.cfg['chats'] if c['id'] == selection[0]), None) if selection else None

    def discover_chats(self):
        """Scan in a COM STA worker and show a user-reviewed import dialog."""
        if self.busy or self.scanning:
            messagebox.showinfo('Esperar', 'Espera a que termine el intento actual o la exploracion anterior.')
            return
        self.scanning = True
        self.status.set('Buscando automáticamente chats en ChatGPT…')
        self.info.set('Descubrimiento local y automático: sin exportar archivos, sin leer mensajes.')

        def worker():
            initialized = False
            try:
                import pythoncom
                pythoncom.CoInitialize()
                initialized = True
                found = chat_discovery.discover_all_chats()
                self.messages.put(('discovery', found, None))
            except Exception as exc:
                self.messages.put(('discovery', [], str(exc)))
            finally:
                if initialized:
                    pythoncom.CoUninitialize()

        threading.Thread(target=worker, daemon=True).start()

    def import_export_zip(self):
        path = filedialog.askopenfilename(
            parent=self, title='Selecciona la exportación OFICIAL de ChatGPT',
            filetypes=[('Archivo ZIP', '*.zip')])
        if not path:
            return
        try:
            found = export_import.import_export(path)
        except export_import.InvalidExport as exc:
            messagebox.showerror('Exportación no válida', str(exc), parent=self)
            return
        if not found:
            messagebox.showinfo('Sin títulos', 'La exportación no contiene conversaciones con título e ID verificables.')
            return
        self.show_discovered(found)

    def show_discovered(self, found):
        """Automatic project-grouped picker. One click registers/unregisters locally.

        No import wizard, no confirmation, no invented conversations. Windows UIA
        sometimes exposes only a subset; show that limitation in-place.
        """
        self.scanning = False
        if not found:
            self.info.set('La aplicación no expuso chats verificables. Abre la barra lateral de ChatGPT. '
                          'No se han inventado títulos ni importado datos externos.')
            return
        popup = tk.Toplevel(self)
        popup.title('Elige tus chats de ChatGPT')
        popup.geometry('965x630')
        popup.transient(self)
        ttk.Label(popup, text='Elige directamente cualquier chat de la lista. Se guarda al instante, sin importar ni confirmar.',
                  wraplength=925).pack(fill='x', padx=12, pady=(12, 4))
        ttk.Label(popup, text='Lista detectada localmente; puede no incluir todos los chats históricos o archivados. '
                  'Los proyectos sin relación verificable aparecen separados.',
                  foreground='#805122', wraplength=925).pack(fill='x', padx=12, pady=(0, 10))
        frame = ttk.Frame(popup)
        frame.pack(fill='both', expand=True, padx=12)
        tree = ttk.Treeview(frame, columns=('choose','title','note'), show='tree headings', selectmode='browse')
        tree.heading('#0', text='Proyecto')
        tree.column('#0', width=230)
        for col, label, width in [('choose','Elegido',72),('title','Nombre real del chat',460),('note','Estado',170)]:
            tree.heading(col,text=label)
            tree.column(col,width=width,stretch=col=='title')
        tree.pack(side='left',fill='both',expand=True)
        sc=ttk.Scrollbar(frame,orient='vertical',command=tree.yview)
        sc.pack(side='right',fill='y')
        tree.configure(yscrollcommand=sc.set)
        groups={}
        for i,c in enumerate(found):
            project=getattr(c,'project',export_import.UNKNOWN_PROJECT)
            if project not in groups:
                group='g'+str(len(groups))
                groups[project]=group
                tree.insert('','end',iid=group,text=project,open=True)
            match=self._find_discovered_chat(c)
            repeated=(c.duplicates>1 or self._discovery_title_ambiguous(c,found))
            tree.insert(groups[project],'end',iid='i'+str(i),values=(
                '☑' if match and match.get('selected') else '□', c.title,
                'Título duplicado: revisión' if repeated else 'En tu cola' if match else 'Disponible'))

        def choose(event=None):
            if event is not None and event.type == '4':
                row=tree.identify_row(event.y)
                if row: tree.selection_set(row)
            if event is not None and tree.identify_region(event.x,event.y) not in ('tree','cell'):
                return
            chosen=tree.selection()
            if not chosen or not chosen[0].startswith('i'):
                return
            index=int(chosen[0][1:])
            item=found[index]
            old=self._find_discovered_chat(item)
            if old:
                old['selected']=not old.get('selected',False)
            else:
                old=storage.new_chat(item.title,'',DEFAULT_INSTRUCTION)
                old['app_title']=item.title
                old['chat_id']=getattr(item,'chat_id','')
                old['project']=getattr(item,'project',export_import.UNKNOWN_PROJECT)
                old['project_id']=getattr(item,'project_id','')
                old['source']=getattr(item,'source','uia')
                old['selected']=True
                self.cfg['chats'].append(old)
            if item.duplicates>1 or self._discovery_title_ambiguous(item,found):
                # Store real title, but NEVER run ambiguous title automatically.
                old['status']='revision'
                old['last_result']='Título duplicado: no se puede seleccionar con seguridad'
                old['selected']=False
            storage.save(self.cfg)
            self.draw_chats()
            tree.set('i'+str(index),'choose','☑' if old.get('selected') else '□')
            tree.set('i'+str(index),'note','Requiere revisión' if old['status']=='revision' else
                     'Seleccionado' if old.get('selected') else 'Disponible')
            self.info.set('Selección guardada automáticamente. Los envíos siguen desactivados hasta habilitarlos expresamente.')

        # One click: selected chat is saved; no follow-up button.
        tree.bind('<ButtonRelease-1>',choose)
        footer=ttk.Frame(popup)
        footer.pack(fill='x',padx=12,pady=10)
        ttk.Label(footer,text=f'{len(found)} entradas accesibles detectadas · selección guardada en el momento').pack(side='left')
        ttk.Button(footer,text='Cerrar lista',command=popup.destroy).pack(side='right')
        self.status.set(f'{len(found)} conversaciones visibles/localizables')

    def _find_discovered_chat(self, item):
        chat_id=getattr(item,'chat_id','')
        return next((c for c in self.cfg['chats']
                     if (chat_id and c.get('chat_id')==chat_id) or
                        (not chat_id and c.get('app_title','').casefold()==item.title.casefold() and
                         (c.get('project') or export_import.UNKNOWN_PROJECT)==getattr(item,'project',export_import.UNKNOWN_PROJECT))),None)

    @staticmethod
    def _discovery_title_ambiguous(item, found):
        return sum(1 for c in found if c.title.casefold()==item.title.casefold())>1

    def add_chat(self):
        dialog = ChatDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            name, url, app_title, instruction, criteria, expected = dialog.result
            chat = storage.new_chat(name, url, instruction)
            chat['app_title'] = app_title
            chat['done_criteria'] = criteria
            chat['expected_files'] = expected
            self.cfg['chats'].append(chat)
            storage.save(self.cfg)
            self.draw_chats()

    def edit_chat(self):
        chat = self.selected_chat()
        if not chat:
            return
        dialog = ChatDialog(self, chat)
        self.wait_window(dialog)
        if dialog.result:
            name, url, app_title, instruction, criteria, expected = dialog.result
            if chat['id'] == self.current_id:
                messagebox.showwarning('En ejecución', 'No se puede editar un chat en ejecución.')
                return
            changed = (chat.get('url') != url or chat.get('app_title') != app_title or chat.get('instruction') != instruction or
                       chat.get('done_criteria', '') != criteria or chat.get('expected_files', '') != expected)
            chat.update(name=name, url=url, app_title=app_title, instruction=instruction,
                        done_criteria=criteria, expected_files=expected)
            if changed:
                chat['pending_token'] = ''
                chat['attempt_state'] = ''
                if chat['status'] != 'terminado':
                    chat['status'] = 'pendiente'
                chat['cooldown_until'] = ''
            storage.save(self.cfg)
            self.draw_chats()

    def delete_chat(self):
        chat = self.selected_chat()
        if chat and messagebox.askyesno('Eliminar', f'¿Quitar "{chat["name"]}" del controlador? No se borra el chat de ChatGPT.'):
            if self.current_id == chat['id']:
                messagebox.showwarning('En ejecución', 'No puedes eliminar la tarea que se está ejecutando.')
                return
            self.cfg['chats'] = [c for c in self.cfg['chats'] if c['id'] != chat['id']]
            storage.save(self.cfg)
            self.draw_chats()

    def toggle_selection(self):
        chat = self.selected_chat()
        if chat:
            chat['selected'] = not chat.get('selected', False)
            storage.save(self.cfg)
            self.draw_chats()

    def set_chat_status(self, state):
        chat = self.selected_chat()
        if chat:
            if chat['id'] == self.current_id:
                messagebox.showwarning('En ejecución', 'Espera a que finalice este intento.')
                return
            state_machine.reset_attempt(chat, state)
            storage.save(self.cfg)
            self.draw_chats()

    def verify_pasted(self):
        chat = self.selected_chat()
        if not chat:
            messagebox.showinfo('Seleccion', 'Selecciona un chat en la tabla.')
            return
        if not chat.get('pending_token'):
            messagebox.showinfo('Sin intento', 'Este chat no tiene un intento con identificador. Puedes marcarlo manualmente.')
            return
        dialog = tk.Toplevel(self)
        dialog.title('Verificar respuesta que tu copiaste de la app')
        dialog.geometry('690x430')
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(dialog, text='Copia y pega aqui la ultima respuesta COMPLETA. El controlador NO lee el chat.',
                  wraplength=650).pack(fill='x', padx=12, pady=10)
        entry = tk.Text(dialog, wrap='word', height=13)
        entry.pack(fill='both', expand=True, padx=12, pady=6)

        def check():
            result, why = completion.interpret(entry.get('1.0', 'end').strip(),
                                                chat['pending_token'], chat.get('expected_files', ''))
            if result not in ('done', 'pending', 'blocked'):
                messagebox.showwarning('Sin prueba suficiente', why + '. No se cambia el estado.', parent=dialog)
                return
            if not messagebox.askyesno('Confirmar', 'Estado detectado: ' + result.upper() +
                                       '\n' + why + '\n¿Aplicar al controlador?', parent=dialog):
                return
            state_machine.apply_result(chat, result, why, datetime.now().astimezone())
            storage.save(self.cfg)
            self.draw_chats()
            dialog.destroy()

        ttk.Button(dialog, text='Verificar y confirmar estado', command=check).pack(pady=10)

    def mark_done(self):
        self.set_chat_status('terminado')

    def mark_pending(self):
        self.set_chat_status('pendiente')

    def mark_paused(self):
        self.set_chat_status('pausado')

    def save_config(self, silent=False):
        try:
            scheduler.parse_clock(self.window_start.get())
            scheduler.parse_clock(self.window_end.get())
            scheduler.parse_times(self.exact_times.get())
            minutes = int(self.interval.get())
            mem = int(self.ram.get())
            cpu = int(self.cpu.get())
            if not (5 <= minutes <= 1440 and 1 <= mem <= 90 and 5 <= cpu <= 100):
                raise ValueError('Intervalo 5-1440; RAM libre minima 1-90%; CPU maxima 5-100%.')
        except ValueError as exc:
            if not silent:
                messagebox.showerror('Configuración inválida', str(exc))
            return False
        self.cfg.update(schedule_mode=self.mode.get(), window_start=self.window_start.get(),
                        window_end=self.window_end.get(), exact_times=self.exact_times.get(),
                        interval_minutes=minutes, min_memory_free_percent=mem, max_cpu_percent=cpu,
                        auto_send=self.autosend.get(), enabled=self.enabled.get())
        storage.save(self.cfg)
        if not silent:
            self.info.set('Horario y configuración guardados. Sincroniza «Configurar despertar» si cambias horas.')
        return True

    def start_run(self, manual=False):
        if self.busy or self.scanning or self.paused_by_user or self.batch:
            return
        now = datetime.now().astimezone()
        if not manual:
            ready, key = scheduler.due(now, self.cfg)
            if not ready:
                return
        else:
            key = f'manual:{now.isoformat()}'
        active = [c for c in self.cfg['chats'] if c.get('status', 'pendiente') in scheduler.ACTIVE]
        selected = [c for c in active if c.get('selected')]
        if selected:
            # Ejecutar TODOS los seleccionados, en serie, con un navegador cada vez.
            eligible = sorted(selected, key=lambda c: c.get('last_run_at', ''))
            self.batch = [c['id'] for c in eligible if self.is_eligible(c, now)]
            if not self.cfg.get('auto_send'):
                # En modo abrir, no recorrer toda la lista anulando el chat visible.
                self.batch = self.batch[:1]
        else:
            # Sin selección, solo uno de los pendientes; rota entre ellos.
            first = scheduler.candidate(active, now)
            self.batch = [first['id']] if first else []
        if not self.batch:
            if manual:
                messagebox.showinfo('Sin pendientes', 'No hay chats pendientes disponibles. Reabre el estado o espera al fin de la pausa temporal.')
            return
        self.cfg['last_run_key'] = key
        self.cfg['last_run_at'] = now.isoformat(timespec='seconds')
        storage.save(self.cfg)
        self._run_next()

    @staticmethod
    def is_eligible(chat, now):
        until = chat.get('cooldown_until', '')
        if not until:
            return True
        try:
            return datetime.fromisoformat(until) <= now
        except ValueError:
            return True

    def _run_next(self):
        if self.busy or self.paused_by_user:
            return
        while self.batch:
            cid = self.batch.pop(0)
            chat = next((c for c in self.cfg['chats'] if c['id'] == cid), None)
            if chat is None or chat.get('status', 'pendiente') not in scheduler.ACTIVE:
                continue
            if not self.is_eligible(chat, datetime.now().astimezone()):
                continue
            # La selección en la app se hace por título: duplicados son inseguros.
            if sum(1 for x in self.cfg['chats'] if x.get('app_title', '').casefold() ==
                   chat.get('app_title', '').casefold()) > 1:
                chat['status'] = 'revision'
                chat['last_result'] = 'Título repetido: selección automática insegura'
                storage.save(self.cfg)
                continue
            if not (chat.get('app_title') or chat.get('name', '')).strip():
                chat['status'] = 'revision'
                chat['last_result'] = 'Falta titulo de chat en la app'
                storage.save(self.cfg)
                continue
            now = datetime.now().astimezone()
            chat['last_run_at'] = now.isoformat(timespec='seconds')
            chat['last_result'] = 'Iniciando...'
            # Persistir el token antes de abrir el navegador para poder recuperarlo.
            fresh_attempt = not bool(chat.get('pending_token'))
            state_machine.prepare_attempt(chat, self.cfg['auto_send'])
            self.busy = True
            self.current_id = chat['id']
            self.status.set(f'Ejecutando: {chat["name"]}')
            storage.save(self.cfg)
            self.draw_chats()
            snapshot = dict(chat)
            threading.Thread(target=self.worker,
                             args=(snapshot, self.cfg['auto_send'], self.cfg['min_memory_free_percent'],
                                   fresh_attempt, self.cfg.get('max_cpu_percent', 65)),
                             daemon=True).start()
            return
        self.status.set('Cola finalizada' if not self.paused_by_user else 'Pausado')

    def worker(self, chat, auto_send, min_ram, fresh_attempt, max_cpu):
        try:
            result = runner.run(chat, auto_send, min_ram,
                                lambda msg: self.messages.put(('progress', msg)),
                                lambda: self.messages.put(('sent', chat['id'])),
                                fresh_attempt=fresh_attempt, max_cpu=max_cpu)
        except Exception as exc:
            result = ('review', 'Fallo inesperado; posible intento incierto: ' + str(exc)[:200])
        self.messages.put(('result', chat['id'], *result))

    def poll_signals(self):
        changed = False
        for chat in self.cfg['chats']:
            if chat['id'] == self.current_id:
                continue
            if chat.get('status') in ('en_curso', 'revision') and chat.get('pending_token'):
                result = signals.check(chat)
                if result and result[0] != 'review':
                    state_machine.apply_result(chat, result[0], result[1], datetime.now().astimezone())
                    changed = True
        if changed:
            storage.save(self.cfg)
            self.draw_chats()

    def tick(self):
        try:
            while True:
                item = self.messages.get_nowait()
                if item[0] == 'progress':
                    self.info.set(item[1])
                elif item[0] == 'discovery':
                    _, found, error = item
                    self.status.set('Listo')
                    if error:
                        self.scanning = False
                        self.info.set('No se pudo comprobar la app: '+error[:250])
                    else:
                        self.show_discovered(found)
                elif item[0] == 'sent':
                    cid = item[1]
                    chat = next((c for c in self.cfg['chats'] if c['id'] == cid), None)
                    if chat:
                        state_machine.mark_submitted(chat)
                        storage.save(self.cfg)
                        self.draw_chats()
                elif item[0] == 'result':
                    _, cid, state, summary = item
                    chat = next((c for c in self.cfg['chats'] if c['id'] == cid), None)
                    if chat:
                        state_machine.apply_result(chat, state, summary, datetime.now().astimezone())
                        storage.save(self.cfg)
                    self.busy = False
                    self.current_id = None
                    self.status.set('Listo' if not self.paused_by_user else 'Pausado')
                    self.info.set(summary)
                    self.draw_chats()
                    if state in ('memory', 'error', 'review', 'timeout'):
                        self.batch.clear()
                    elif self.batch:
                        self.after(4000, self._run_next)
        except queue.Empty:
            pass
        if not self.busy and not self.paused_by_user and not self.batch:
            self.start_run()
        self.poll_signals()
        self.after(3000, self.tick)

    def run_now(self):
        if self.save_config():
            self.start_run(manual=True)

    def toggle_pause(self):
        self.paused_by_user = not self.paused_by_user
        self.status.set('Pausado (no cancela el chat activo)' if self.paused_by_user else 'Listo')
        if not self.paused_by_user and self.batch:
            self.after(500, self._run_next)

    def login(self):
        try:
            runner.open_login_profile()
            self.info.set('Aplicacion de ChatGPT abierta. Inicia sesion en la app si es necesario.')
        except Exception as exc:
            messagebox.showerror('Aplicacion ChatGPT', str(exc))

    def autostart(self):
        if os.name != 'nt':
            messagebox.showerror('Windows', 'El inicio automático requiere Windows.')
            return
        try:
            import winreg
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run')
            command = (f'"{sys.executable}"' if getattr(sys, 'frozen', False) else
                       f'"{python_gui()}" "{HERE / "controller.py"}"')
            winreg.SetValueEx(key, 'ControladorChatGPT', 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
            messagebox.showinfo('Inicio automático', 'Configurado para arrancar tras iniciar sesión en Windows.')
        except Exception as exc:
            messagebox.showerror('Error', str(exc))

    def install_wake(self):
        if not self.save_config(silent=True):
            messagebox.showerror('Horario', 'Revisa el formato de las horas.')
            return
        if os.name != 'nt':
            messagebox.showerror('Windows', 'Esta función requiere Windows.')
            return
        times = self.cfg['window_start'] if self.cfg['schedule_mode'] == 'ventana' else self.cfg['exact_times']
        exe = str(Path(sys.executable).resolve()) if getattr(sys, 'frozen', False) else python_gui()
        script = '' if getattr(sys, 'frozen', False) else str(HERE / 'controller.py')
        command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(HERE / 'wake_task.ps1'),
                   '-PythonExe', exe, '-ScriptPath', script, '-Times', times]
        try:
            run = subprocess.run(command, capture_output=True, text=True, timeout=40)
            if run.returncode:
                raise RuntimeError((run.stderr or run.stdout or 'Error sin detalle')[:750])
            messagebox.showinfo('Despertar programado', 'Tarea creada en Windows. Requiere temporizadores de reactivación activados; no arranca desde apagado total.')
        except Exception as exc:
            messagebox.showerror('No se pudo programar', str(exc))

    def close(self):
        if self.busy and not messagebox.askyesno('Trabajo activo', 'Hay un intento activo. Cerrar el controlador podría interrumpirlo. ¿Cerrar de todos modos?'):
            return
        if not self.save_config(silent=True):
            if not messagebox.askyesno('Sin guardar', 'Los horarios no son válidos. ¿Salir sin guardar?'):
                return
        self.destroy()


if __name__ == '__main__':
    from single_instance import acquire
    if not acquire():
        messagebox.showinfo('Controlador ya abierto', 'Ya hay un controlador activo en esta sesion.')
        raise SystemExit(0)
    app = Controller()
    app.mainloop()
