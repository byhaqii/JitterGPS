"""Real-Tk smoke: .venv/bin/python tests/gui_map_smoke.py (desktop required)."""
import pathlib
import sys
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from ui.app_window import AppWindow


def main():
    app = AppWindow(map_offline='--online' not in sys.argv)
    failures = []
    app.report_callback_exception = lambda *exc: failures.append(''.join(traceback.format_exception(*exc)))

    def check():
        try:
            for entry in app.entries[:2]:
                app.clipboard_clear()
                app.clipboard_append('-6.881776, 107.610926')
                entry._entry.event_generate('<<Paste>>')
                assert tuple(float(e.get()) for e in app.entries[:2]) == (-6.881776, 107.610926)
            before = tuple(e.get() for e in app.entries[:2])
            app.clipboard_clear()
            app.clipboard_append('107.610926, -6.881776')
            app.entries[0]._entry.event_generate('<<Paste>>')
            assert tuple(e.get() for e in app.entries[:2]) == before
            assert 'Invalid' in app.input_message.cget('text')
            app.on_radius_slider(1.0)
            assert float(app.entries[2].get()) == 50000
            app.on_map_click((-6.9, 107.7))
            assert tuple(float(e.get()) for e in app.entries[:2]) == (-6.9, 107.7)
            app.refresh_preview(recenter=False)
            assert app.preview_radius == 50000
            assert app.preview_center == (-6.9, 107.7)
            app.set_inputs_locked(True)
            app.on_map_click((1, 2))
            app.on_radius_slider(0)
            app.clipboard_clear()
            app.clipboard_append('1, 2')
            app.entries[1]._entry.event_generate('<<Paste>>')
            assert tuple(float(e.get()) for e in app.entries[:2]) == (-6.9, 107.7)
            assert float(app.entries[2].get()) == 50000
            app.events.put(('ip', (3, 4)))
            app.events.put(('point', (-6.9001, 107.7001)))
            app.drain_events()
            assert app.preview_center == (-6.9, 107.7)
            assert app.applied_point == (-6.9001, 107.7001)
            app.set_inputs_locked(False)
            app.events.put(('ip', (-6.8, 107.6)))
            app.drain_events()
            assert app.preview_center == (-6.8, 107.6)
            app.set_center(90, 180, recenter=True)
            assert float(app.entries[0].get()) == 90
            assert 'Polar' in app.map_message.cget('text')
            app.set_center(0, 179.9999, recenter=True)
            assert len(app.radius_paths) >= 2
            if app.map_view is not None:
                app.map_view.set_position(-6.8, 107.6)
                position = app.map_view.get_position()
                app.refresh_preview(recenter=False)
                assert app.map_view.get_position() == position
            app.input_vars[2].set('250')
            app.after(350, check_debounce)
        except Exception:
            failures.append(traceback.format_exc())
            app.after(200, app.destroy)

    def check_debounce():
        try:
            assert app.preview_radius == 250
            assert abs(app.radius_slider.get() - __import__('math').log(50, 10000)) < 1e-6
            print('PASS: real Tk paste in either field, invalid paste, slider, map click, locking, queued IP/point, offline preview, poles/date line, debounce/pan')
        except Exception:
            failures.append(traceback.format_exc())
        finally:
            app.after(200, app.destroy)

    app.after(700, check)
    app.mainloop()
    if failures:
        print('\n'.join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
