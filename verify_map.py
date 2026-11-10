"""Real Tk smoke check: clipboard pair -> fields -> map circle -> radius slider."""
import math
import tkintermapview
import customtkinter as ctk
from ui.app_window import AppWindow
from core.jitter_engine import distance_m


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def verify():
    app = AppWindow()
    failures = []
    def check(callback):
        try:
            callback()
        except Exception as exc:
            failures.append(exc)
            app.destroy()

    def paste():
        app.clipboard_clear()
        app.clipboard_append('-6.881776, 107.610926')
        app.entries[0]._entry.event_generate('<<Paste>>')
        app.after(700, lambda: check(check_pair))

    def check_pair():
        assert tuple(float(e.get()) for e in app.entries[:2]) == (-6.881776, 107.610926)
        maps = [w for w in descendants(app) if isinstance(w, tkintermapview.TkinterMapView)]
        assert len(maps) == 1, 'Expected embedded map'
        view = maps[0]
        assert app.radius_paths, 'Expected radius outline'
        radius = float(app.entries[2].get())
        points = app.radius_paths[0].position_list
        assert len(points) >= 24
        assert all(abs(distance_m(-6.881776, 107.610926, *p) - radius) < 1 for p in points)
        app.entries[1]._entry.event_generate('<<Paste>>')
        assert tuple(float(e.get()) for e in app.entries[:2]) == (-6.881776, 107.610926)
        app.entries[2].delete(0, 'end')
        app.entries[2].insert(0, '500')
        app.entries[2]._entry.event_generate('<KeyRelease>')
        app.after(700, lambda: check(check_radius))

    def check_radius():
        view = next(w for w in descendants(app) if isinstance(w, tkintermapview.TkinterMapView))
        points = app.radius_paths[0].position_list
        assert all(abs(distance_m(-6.881776, 107.610926, *p) - 500) < 1 for p in points)
        assert any(isinstance(w, ctk.CTkSlider) for w in descendants(app)), 'Radius slider missing'
        print('PASS: actual clipboard paste in both coordinate fields; radius 150m -> 500m updates map polygon; slider present.')
        app.destroy()

    app.after(800, lambda: check(paste))
    app.after(15000, lambda: check(lambda: (_ for _ in ()).throw(TimeoutError('GUI verification timed out'))))
    app.mainloop()
    if failures:
        raise failures[0]


if __name__ == '__main__':
    verify()
