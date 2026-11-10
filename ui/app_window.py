"""Thread-safe, compact desktop controls for browser geolocation testing."""
import math
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
import requests
from PIL import Image, ImageDraw, ImageTk
from ui import theme as T

from core.browser_finder import launch_browser_with_cdp
from core.cdp_client import CDPClient
from core.jitter_engine import JitterEngine, distance_m
from ui.coordinate_input import parse_coordinate_pair, radius_polygon, validate_center

try:
    from ui.tile_loader import PolicyMapView as TkinterMapView
except ImportError:
    TkinterMapView = None


def validate_settings(values):
    lat, lng, radius, interval, accuracy = map(float, values)
    if not all(math.isfinite(x) for x in (lat, lng, radius, interval, accuracy)):
        raise ValueError('All values must be finite numbers.')
    for value, low, high, label in (
        (lat, -90, 90, 'Latitude'), (lng, -180, 180, 'Longitude'),
        (radius, 5, 50000, 'Radius'), (interval, 1, 300, 'Interval'),
        (accuracy, 0, 50000, 'Accuracy'),
    ):
        if not low <= value <= high:
            raise ValueError(f'{label} must be between {low} and {high}.')
    return lat, lng, radius, interval, accuracy


class AppWindow(ctk.CTk):
    def __init__(self, *, map_offline=False):
        ctk.set_appearance_mode('dark')
        super().__init__()
        self.title('Jitter GPS')
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f'{min(1200, screen_w)}x{min(820, screen_h - 60)}')
        self.minsize(min(1000, screen_w), min(740, screen_h - 60))
        self.configure(fg_color=T.CANVAS)
        self.fonts = {name: ctk.CTkFont(family=T.SANS, size=size, weight=weight)
                      for name, size, weight in [('small', T.SMALL, 'normal'),
                       ('body', T.BODY, 'normal'), ('section', T.SECTION, 'bold'),
                       ('title', T.TITLE, 'bold')]}
        self.mono_font = ctk.CTkFont(family=T.MONO, size=T.SMALL)
        self.inputs_locked = False
        self._preview_job = None
        self._syncing = False
        self.applied_point = None
        self.center_marker = self.point_marker = None
        self.radius_paths = []
        self.map_view = None
        self.tile_error = ""
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.closing = False
        self.launching = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.label(self, 'Jitter GPS', 'title').grid(row=0, column=0, padx=16, pady=(12, 0), sticky='w')
        self.label(self, 'Browser geolocation testing · isolated profile · no IP masking', 'small', T.SECONDARY).grid(row=1, column=0, padx=16, pady=(0, 10), sticky='w')
        content = ctk.CTkFrame(self, fg_color=T.CANVAS, corner_radius=0)
        content.grid(row=2, column=0, padx=16, sticky='nsew')
        content.grid_columnconfigure(0, weight=0, minsize=T.RAIL_WIDTH)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)
        self.rail = form = ctk.CTkFrame(content, width=T.RAIL_WIDTH, fg_color=T.PANEL, corner_radius=0,
                                        border_width=1, border_color=T.DIVIDER)
        form.grid(row=0, column=0, sticky='nsew')
        form.grid_propagate(False)
        form.grid_columnconfigure((0, 1), weight=1, uniform='rail')
        form.grid_rowconfigure(15, weight=1)
        self.entries = []
        fields = [('Center latitude', '-6.2088'), ('Center longitude', '106.8456'), ('Radius (meters)', '150'), ('Interval (seconds)', '5'), ('Accuracy (meters)', '10')]
        for index, (label, default) in enumerate(fields):
            row, col = ((index * 2, 0) if index < 2 else ((4, index - 2) if index < 4 else (6, 0)))
            self.label(form, label, 'small', T.SECONDARY).grid(row=row, column=col, columnspan=2 if index < 2 or index == 4 else 1, padx=(16, 8) if index == 2 else (8, 16) if index == 3 else 16, pady=(6 if index else 10, 0), sticky='w')
            entry = ctk.CTkEntry(form, height=T.CONTROL_HEIGHT, corner_radius=T.RADIUS,
                                 fg_color=T.FIELD, border_color=T.EDGE, text_color=T.TEXT,
                                 font=self.fonts['body'])
            entry.insert(0, default)
            entry.grid(row=row + 1, column=col, columnspan=2 if index < 2 or index == 4 else 1,
                       padx=(16, 8) if index == 2 else (8, 16) if index == 3 else 16, sticky='ew')
            entry._entry.configure(disabledforeground=T.DISABLED, insertbackground=T.TEXT)
            self.entries.append(entry)
        self.radius_slider = ctk.CTkSlider(form, from_=0, to=1, command=self.on_radius_slider,
                                          height=20, fg_color=T.EDGE, progress_color=T.SECONDARY,
                                          button_color=T.SECONDARY, button_hover_color=T.FOCUS)
        self.radius_slider.grid(row=10, column=0, columnspan=2, padx=16, pady=(10, 0), sticky='ew')
        self.label(form, 'Radius: 5 m to 50 km (log scale)', 'small', T.SECONDARY).grid(row=11, column=0, columnspan=2, padx=16, sticky='w')
        self.input_message = self.label(form, 'Paste latitude, longitude into either field.\nClick the map to choose a center.', 'small', T.SECONDARY,
                                        justify='left', wraplength=268, anchor='w')
        self.input_message.grid(row=12, column=0, columnspan=2, padx=16, pady=(4, 0), sticky='ew')
        self.label(form, 'Debug browser', 'small', T.SECONDARY).grid(row=13, column=0, columnspan=2, padx=16, pady=(6, 0), sticky='w')
        self.browser = ctk.CTkOptionMenu(form, values=['chrome', 'edge', 'brave'],
                                       height=T.CONTROL_HEIGHT, corner_radius=T.RADIUS,
                                       fg_color=T.HOVER, button_color=T.HOVER, button_hover_color=T.DIVIDER,
                                       text_color=T.TEXT, text_color_disabled=T.DISABLED,
                                       dropdown_fg_color=T.PANEL, dropdown_hover_color=T.HOVER,
                                       dropdown_text_color=T.TEXT, font=self.fonts['body'], dropdown_font=self.fonts['body'])
        self.browser.grid(row=14, column=0, columnspan=2, padx=16, sticky='ew')
        self.browser._canvas.configure(highlightthickness=1, highlightbackground=T.EDGE)
        self.launch_button = self.button(form, 'Launch Debug Browser', self.launch_browser)
        self.launch_button.grid(row=16, column=0, columnspan=2, padx=16, pady=(8, 4), sticky='ew')
        self.ip_button = self.button(form, 'Get IP Location', self.fetch_ip)
        self.ip_button.grid(row=17, column=0, columnspan=2, padx=16, pady=(0, 8), sticky='ew')
        self.toggle = self.button(form, 'Start Spoofing', self.toggle_run, primary=True)
        self.toggle.grid(row=18, column=0, columnspan=2, padx=16, pady=(0, 16), sticky='ew')
        self.map_frame = ctk.CTkFrame(content, fg_color=T.CANVAS, corner_radius=0)
        self.map_frame.grid(row=0, column=1, padx=(12, 0), sticky='nsew')
        self.map_frame.grid_columnconfigure(0, weight=1)
        self.map_frame.grid_rowconfigure(1, weight=1)
        self.label(self.map_frame, 'Center & radius preview', 'section').grid(row=0, column=0, pady=(0, 6), sticky='w')
        self.label(self.map_frame, 'Drag to pan / scroll to zoom', 'small', T.SECONDARY).grid(row=0, column=0, sticky='e')
        self.center_icon = self.marker_icon(T.ACCENT, hollow=True)
        self.applied_icon = self.marker_icon(T.APPLIED)
        self.circle_canvas = tk.Canvas(self.map_frame, height=112, background=T.PANEL, highlightthickness=0)
        self.circle_canvas.bind('<Configure>', lambda event: self.draw_circle_preview())
        if TkinterMapView is not None:
            try:
                self.map_view = TkinterMapView(self.map_frame, width=560, height=330, corner_radius=0, use_database_only=map_offline, database_path=':memory:' if map_offline else None, on_tile_error=lambda message: self.events.put(('tile_error', message)))
                self.map_view.grid(row=1, column=0, sticky='nsew')
                self.map_view.add_left_click_map_command(self.on_map_click)
                self.map_view.set_zoom(15)
            except Exception as exc:
                self.map_view = None
                self.tile_error = f'Map unavailable. Use coordinate fields.\n{exc}'
        else:
            self.tile_error = 'Map unavailable. Coordinate fields and radius preview work offline.'
        self.map_message = self.label(self.map_frame, '', 'small', T.APPLIED, wraplength=620, anchor='w')
        self.map_message.grid(row=2, column=0, sticky='ew')
        legend = ctk.CTkFrame(self.map_frame, fg_color=T.CANVAS, corner_radius=0)
        legend.grid(row=3, column=0, sticky='ew')
        self.label(legend, '○ Center', 'small', T.ACCENT).pack(side='left')
        self.label(legend, '● Applied', 'small', T.APPLIED).pack(side='left', padx=16)
        self.latest_applied = ctk.CTkLabel(legend, text='', font=self.mono_font, text_color=T.TEXT)
        self.latest_applied.pack(side='right')
        self.label(self.map_frame, '© OpenStreetMap contributors · openstreetmap.org/copyright\nTiles need internet; OSM receives your IP and viewed area.\nNo tiles? Fields and circle preview still work offline.', 'small', T.SECONDARY, justify='left').grid(row=4, column=0, pady=(2, 8), sticky='w')
        self.update_fallback(map_offline or self.map_view is None)
        self.input_vars = []
        for index, entry in enumerate(self.entries[:3]):
            variable = tk.StringVar(value=entry.get())
            entry.configure(textvariable=variable)
            variable.trace_add('write', lambda *_: self.schedule_preview())
            self.input_vars.append(variable)
            if index < 2:
                entry._entry.bind('<Return>', lambda event: self.refresh_preview(recenter=True))
                # CTkEntry bindings alone miss the native macOS Cmd+V path.
                entry._entry.bind('<<Paste>>', self.on_coordinate_paste)
                entry._entry.bind('<Command-v>', self.on_coordinate_paste)
                entry._entry.bind('<Command-V>', self.on_coordinate_paste)
        self.refresh_preview(recenter=True)
        if self.map_view is not None and not self.map_view.use_database_only and not self.tile_error:
            self.map_message.configure(text='Loading map tiles…')
        self.status = self.label(self.map_frame, 'Idle · CDP port 9222', 'small', T.SECONDARY, anchor='w')
        self.status.grid(row=5, column=0, sticky='ew')
        self.log = ctk.CTkTextbox(self.map_frame, height=T.ACTIVITY_HEIGHT, font=self.mono_font,
                                 fg_color=T.PANEL, text_color=T.TEXT, corner_radius=0,
                                 scrollbar_button_color=T.EDGE, scrollbar_button_hover_color=T.SECONDARY, state='disabled')
        self.log.grid(row=6, column=0, pady=(4, 0), sticky='ew')
        self.label(self, 'Open browserleaks.com/geo in the debug browser and allow location.\nStop clears reachable overrides; closing this app leaves the browser open.', 'small', T.SECONDARY, justify='left').grid(row=3, column=0, padx=16, pady=(8, 12), sticky='w')
        self.wire_keyboard()
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.after(100, self.drain_events)
        self.append_log('Ready. Launch an isolated browser, then start. Do not sign into sensitive accounts in the debug profile.')

    def label(self, parent, text, role='body', color=T.TEXT, **kwargs):
        return ctk.CTkLabel(parent, text=text, font=self.fonts[role], text_color=color,
                            height=18 if role == 'small' else 24, **kwargs)

    def button(self, parent, text, command, *, primary=False):
        return ctk.CTkButton(parent, text=text, command=command, height=T.ACTION_HEIGHT,
                             corner_radius=T.RADIUS, font=self.fonts['body'], border_width=1,
                             border_color=T.ACCENT if primary else T.EDGE,
                             fg_color=T.ACCENT if primary else T.PANEL,
                             hover_color=T.FOCUS if primary else T.HOVER,
                             text_color=T.INK if primary else T.TEXT, text_color_disabled=T.DISABLED)

    def marker_icon(self, color, *, hollow=False):
        image = Image.new('RGBA', (64, 64))
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 56, 56), outline=T.INK, width=8)
        draw.ellipse((12, 12, 52, 52), outline=color, width=8,
                     fill=None if hollow else color)
        return ImageTk.PhotoImage(image.resize((16, 16), Image.Resampling.LANCZOS), master=self)

    def update_fallback(self, visible):
        if visible:
            self.circle_canvas.grid(row=1, column=0, sticky='nsew')
            self.tk.call('raise', self.circle_canvas._w)
        else:
            self.circle_canvas.grid_remove()

    def wire_keyboard(self):
        self.focus_controls = self.entries + [self.radius_slider, self.browser,
                                               self.launch_button, self.ip_button, self.toggle]
        self.focus_targets = [e._entry for e in self.entries] + [self.radius_slider._canvas] + [c._text_label for c in self.focus_controls[6:]]
        for control, target in zip(self.focus_controls, self.focus_targets):
            target.configure(takefocus=1)
            tk.Misc.bind(target, '<Tab>', lambda event, c=control: self.move_focus(c, 1))
            tk.Misc.bind(target, '<Shift-Tab>', lambda event, c=control: self.move_focus(c, -1))
            tk.Misc.bind(target, '<ISO_Left_Tab>', lambda event, c=control: self.move_focus(c, -1))
            tk.Misc.bind(target, '<FocusIn>', lambda event, c=control: self.focus_style(c, True), add='+')
            tk.Misc.bind(target, '<FocusOut>', lambda event, c=control: self.focus_style(c, False), add='+')
        for button in (self.launch_button, self.ip_button, self.toggle):
            for key in ('<Return>', '<space>'):
                tk.Misc.bind(button._text_label, key, lambda event, b=button: self.activate_button(b))
        for key, delta in (('<Left>', -.01), ('<Down>', -.01), ('<Right>', .01), ('<Up>', .01)):
            tk.Misc.bind(self.radius_slider._canvas, key, lambda event, d=delta: self.step_radius(d))
        for key, delta in (('<Up>', -1), ('<Left>', -1), ('<Down>', 1), ('<Right>', 1)):
            tk.Misc.bind(self.browser._text_label, key, lambda event, d=delta: self.step_browser(d))

    def focus_style(self, control, focused):
        if control in self.entries or control in (self.launch_button, self.ip_button, self.toggle):
            control.configure(border_color=T.FOCUS if focused else
                              T.ACCENT if control is self.toggle else T.EDGE,
                              border_width=2 if focused else 1)
        else:
            control._canvas.configure(highlightthickness=2 if focused else 1 if control is self.browser else 0,
                                      highlightbackground=T.FOCUS if focused else T.EDGE, highlightcolor=T.FOCUS)

    def move_focus(self, control, delta):
        index = self.focus_controls.index(control)
        for step in range(1, len(self.focus_controls) + 1):
            next_index = (index + delta * step) % len(self.focus_controls)
            candidate = self.focus_controls[next_index]
            if candidate.cget('state') != 'disabled':
                self.focus_targets[next_index].focus_set()
                break
        return 'break'

    def activate_button(self, button):
        if button.cget('state') != 'disabled':
            button.invoke()
        return 'break'

    def step_radius(self, delta):
        if not self.inputs_locked:
            value = min(1, max(0, self.radius_slider.get() + delta))
            self.radius_slider.set(value)
            self.on_radius_slider(value)
        return 'break'

    def step_browser(self, delta):
        values = self.browser.cget('values')
        self.browser.set(values[(values.index(self.browser.get()) + delta) % len(values)])
        return 'break'

    def on_coordinate_paste(self, event):
        if self.inputs_locked:
            return 'break'
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return 'break'
        if ',' in text:
            try:
                self.set_center(*parse_coordinate_pair(text), recenter=True)
            except ValueError as exc:
                self.input_message.configure(text=str(exc), text_color=T.ERROR)
        else:
            # Keep ordinary one-value paste, including native selection replacement.
            widget = event.widget
            try:
                widget.delete('sel.first', 'sel.last')
            except tk.TclError:
                pass
            widget.insert('insert', text)
        return 'break'

    def set_center(self, lat, lng, *, recenter=False):
        if self.inputs_locked:
            return
        lat, lng = validate_center(lat, lng)
        self._syncing = True
        try:
            for variable, coord in zip(self.input_vars[:2], (lat, lng)):
                variable.set(f'{coord:.8f}'.rstrip('0').rstrip('.'))
        finally:
            self._syncing = False
        self.refresh_preview(recenter=recenter)

    def on_map_click(self, coordinates):
        if not self.inputs_locked:
            self.set_center(*coordinates, recenter=False)

    def on_radius_slider(self, fraction):
        if self.inputs_locked:
            return
        radius = round(5 * (10000 ** float(fraction)))
        self.input_vars[2].set(str(radius))

    def schedule_preview(self):
        if self._syncing or self.inputs_locked:
            return
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(220, self.refresh_preview)

    def refresh_preview(self, *, recenter=False):
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
            self._preview_job = None
        try:
            lat, lng = validate_center(*(entry.get() for entry in self.entries[:2]))
            radius = float(self.entries[2].get())
            outline = radius_polygon(lat, lng, radius)
        except (ValueError, TypeError) as exc:
            self.input_message.configure(text=f'Invalid preview: {exc}', text_color=T.ERROR)
            return
        self.preview_center, self.preview_radius = (lat, lng), radius
        self.radius_slider.set(math.log(radius / 5, 10000))
        self.input_message.configure(text='Paste latitude, longitude into either field.\nClick the map to choose a center.', text_color=T.SECONDARY)
        self.draw_circle_preview()
        # Mercator cannot represent the poles; never clamp the worker's center.
        mercator_limit = 85.05112878
        polar = any(abs(p[0]) >= mercator_limit for p in outline) or abs(lat) >= mercator_limit
        self.update_fallback(polar or self.map_view is None or self.map_view.use_database_only or bool(self.tile_error))
        self.map_message.configure(text='Polar area: Web Mercator cannot show this circle accurately.\nOriginal coordinates retained; use the circle preview.' if polar else self.tile_error)
        if self.map_view is None:
            return
        try:
            if self.center_marker is not None:
                self.center_marker.delete()
                self.center_marker = None
            for path in self.radius_paths:
                path.delete()
            self.radius_paths = []
            if recenter:
                self.map_view.set_position(max(-mercator_limit, min(mercator_limit, lat)), lng)
            if not polar:
                self.center_marker = self.map_view.set_marker(lat, lng, icon=self.center_icon, icon_anchor='center')
                # Split at the date line to avoid an erroneous world-spanning edge.
                segment = []
                for point in outline:
                    if segment and abs(point[1] - segment[-1][1]) > 180:
                        if len(segment) > 1:
                            self.radius_paths.append(self.map_view.set_path(segment, color=T.MAP_OUTLINE, width=3))
                        segment = []
                    segment.append(point)
                if len(segment) > 1:
                    self.radius_paths.append(self.map_view.set_path(segment, color=T.MAP_OUTLINE, width=3))
        except Exception as exc:
            self.map_message.configure(text=f'Map preview unavailable; form and circle still work. {exc}')

    def draw_circle_preview(self):
        if not hasattr(self, 'preview_radius'):
            return
        canvas = self.circle_canvas
        canvas.delete('all')
        width, height = max(canvas.winfo_width(), 180), max(canvas.winfo_height(), 100)
        x, y, r = width / 2, height / 2 - 8, min(36, height / 2 - 20)
        canvas.create_oval(x-r, y-r, x+r, y+r, outline=T.ACCENT, width=2)
        canvas.create_oval(x-3, y-3, x+3, y+3, fill=T.ACCENT, outline='')
        canvas.create_text(x, height-12, text=f'Offline radius preview · {self.preview_radius:g} m', fill=T.SECONDARY, font=self.fonts['small'])
        if self.applied_point is not None:
            lat, lng = self.preview_center
            plat, plng = self.applied_point
            offset = distance_m(lat, lng, plat, plng)
            phi, pphi = math.radians(lat), math.radians(plat)
            dlng = math.radians(plng-lng)
            bearing = math.atan2(math.sin(dlng) * math.cos(pphi),
                                 math.cos(phi) * math.sin(pphi) - math.sin(phi) * math.cos(pphi) * math.cos(dlng))
            scale = min(1.2, offset / self.preview_radius) * r
            px, py = x + scale * math.sin(bearing), y - scale * math.cos(bearing)
            canvas.create_oval(px-3, py-3, px+3, py+3, fill=T.APPLIED, outline='')

    def show_applied_point(self, point):
        self.applied_point = validate_center(*point)
        self.latest_applied.configure(text=f'{point[0]:.6f}, {point[1]:.6f}')
        self.draw_circle_preview()
        if self.map_view is not None:
            if self.point_marker is not None:
                self.point_marker.delete()
                self.point_marker = None
            if abs(point[0]) < 85.05112878:
                self.point_marker = self.map_view.set_marker(*point, icon=self.applied_icon, icon_anchor='center')

    def set_inputs_locked(self, locked):
        self.inputs_locked = locked
        for entry in self.entries:
            entry.configure(state='disabled' if locked else 'normal')
        self.radius_slider.configure(state='disabled' if locked else 'normal')
        self.ip_button.configure(state='disabled' if locked else 'normal')

    def append_log(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', f'[{time.strftime("%H:%M:%S")}] {text}\n')
        if int(self.log.index('end-1c').split('.')[0]) > 500:
            self.log.delete('1.0', '100.0')
        self.log.see('end')
        self.log.configure(state='disabled')

    def drain_events(self):
        if (self.map_view is not None and self.map_view.loaded_tile_count > 0
                and self.map_message.cget('text') == 'Loading map tiles…'):
            self.map_message.configure(text=self.tile_error)
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'log':
                self.append_log(value)
            elif kind == 'tile_error':
                self.tile_error = value
                self.map_message.configure(text=value)
                self.update_fallback(True)
                self.append_log(value)
            elif kind == 'ip':
                if not self.inputs_locked:
                    self.set_center(*value, recenter=True)
            elif kind == 'point':
                self.show_applied_point(value)
            elif kind == 'ip_done':
                self.ip_button.configure(state='disabled' if self.inputs_locked else 'normal')
            elif kind == 'launch_done':
                self.launching = False
                self.launch_button.configure(state='normal')
                self.status.configure(text='Running · same coordinate shared across page tabs'
                                           if self.worker is not None else 'Idle · CDP port 9222')
            elif kind == 'stopped':
                self.worker = None
                self.applied_point = None
                if self.point_marker is not None:
                    self.point_marker.delete()
                    self.point_marker = None
                self.latest_applied.configure(text='')
                self.draw_circle_preview()
                self.toggle.configure(text='Start Spoofing', state='normal', fg_color=T.ACCENT, hover_color=T.FOCUS, text_color=T.INK, border_color=T.ACCENT)
                self.status.configure(text='Idle · CDP port 9222')
                self.set_inputs_locked(False)
                if self.closing:
                    self.destroy()
                    return
        self.after(100, self.drain_events)

    def launch_browser(self):
        browser = self.browser.get()
        self.launching = True
        self.launch_button.configure(state='disabled')
        self.status.configure(text=f'Launching {browser}…')
        def work():
            try:
                launch_browser_with_cdp(browser_type=browser)
                self.events.put(('log', 'Debug browser ready on port 9222. Open https://browserleaks.com/geo and allow location.'))
            except Exception as exc:
                self.events.put(('log', f'Browser: {exc}'))
            finally:
                self.events.put(('launch_done', None))
        threading.Thread(target=work, daemon=True).start()

    def fetch_ip(self):
        if not messagebox.askokcancel('Approximate IP location', 'This sends a request to ipapi.co, which sees your public IP. Continue?'):
            return
        self.ip_button.configure(state='disabled')
        def work():
            try:
                response = requests.get('https://ipapi.co/json/', timeout=8)
                response.raise_for_status()
                data = response.json()
                lat, lng, *_ = validate_settings([data['latitude'], data['longitude'], 5, 1, 10])
                self.events.put(('ip', (lat, lng)))
                self.events.put(('log', 'Approximate IP center loaded (not GPS).'))
            except Exception as exc:
                self.events.put(('log', f'IP lookup failed; inputs unchanged: {exc}'))
            finally:
                self.events.put(('ip_done', None))
        threading.Thread(target=work, daemon=True).start()

    def toggle_run(self):
        if self.worker is not None:
            self.stop_event.set()
            self.toggle.configure(text='Stopping…', state='normal')
            self.status.configure(text='Stopping · clearing overrides…')
            return
        try:
            settings = validate_settings([e.get() for e in self.entries])
        except (ValueError, TypeError) as exc:
            self.input_message.configure(text=f'Invalid settings: {exc}', text_color=T.ERROR)
            return
        self.refresh_preview(recenter=False)
        self.stop_event.clear()
        self.set_inputs_locked(True)
        self.toggle.configure(text='Stop Spoofing', fg_color=T.ERROR, hover_color=T.ERROR, text_color=T.ERROR_INK, border_color=T.ERROR)
        self.status.configure(text='Running · same coordinate shared across page tabs')
        self.worker = threading.Thread(target=self.run_loop, args=(settings,), daemon=True)
        self.worker.start()

    def run_loop(self, settings):
        lat, lng, radius, interval, accuracy = settings
        engine = JitterEngine()
        client = CDPClient(port=9222)
        try:
            while not self.stop_event.is_set():
                point = engine.generate_unique_coord(lat, lng, radius)
                count, errors = client.apply(*point, accuracy=accuracy)
                if count:
                    self.events.put(('point', point))
                    offset = distance_m(lat, lng, *point)
                    self.events.put(('log', f'Applied → {point[0]:.6f}, {point[1]:.6f} · {offset:.1f}m · {count} tab(s)'))
                elif not errors:
                    self.events.put(('log', 'No page tabs found. Open a page in the debug browser.'))
                for error in errors:
                    self.events.put(('log', f'CDP: {error}'))
                if self.stop_event.wait(interval):
                    break
        except Exception as exc:
            self.events.put(('log', f'Stopped after error: {exc}'))
        finally:
            try:
                count, errors = client.clear_geolocation_override()
                self.events.put(('log', f'Cleared overrides on {count} tab(s).'))
                for error in errors:
                    self.events.put(('log', f'Cleanup warning: {error}'))
            except Exception as exc:
                self.events.put(('log', f'Cleanup warning: {exc}'))
            finally:
                client.close()
                self.events.put(('stopped', None))

    def destroy(self):
        # The map owns daemon tile loaders. Stop new work while Tk is still
        # servicing queued PhotoImage calls, then release widgets on this thread.
        if getattr(self, '_destroy_pending', False):
            return
        self._destroy_pending = True
        if self.map_view is not None:
            self.map_view.running = False
        self.after(300, self._finish_destroy)

    def _finish_destroy(self):
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
            self._preview_job = None
        super().destroy()

    def on_close(self):
        if self.worker is not None:
            self.closing = True
            self.stop_event.set()
            self.toggle.configure(state='disabled', text='Clearing…')
            self.status.configure(text='Closing after cleanup…')
        else:
            self.destroy()
