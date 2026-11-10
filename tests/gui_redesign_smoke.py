"""Native mainloop layout/keyboard smoke, no real browser or IP requests."""
import pathlib
import sys
import traceback
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from ui.app_window import AppWindow
from ui import theme as T


def main():
    app = AppWindow(map_offline=True)
    failures = []
    app.report_callback_exception = lambda *exc: failures.append(''.join(traceback.format_exception(*exc)))

    def check(size):
        try:
            app.focus_force()
            app.update()
            assert app.rail.winfo_width() == T.RAIL_WIDTH
            assert app.map_frame.winfo_width() > app.rail.winfo_width()
            assert app.log.winfo_height() <= T.ACTIVITY_HEIGHT
            controls = app.entries + [app.radius_slider, app.browser, app.launch_button, app.ip_button, app.toggle]
            for control in controls:
                x = control.winfo_rootx() - app.winfo_rootx()
                y = control.winfo_rooty() - app.winfo_rooty()
                assert 0 <= x and x + control.winfo_width() <= app.winfo_width(), (size, control, x)
                assert 0 <= y and y + control.winfo_height() <= app.winfo_height(), (size, control, y)
            assert all(e.winfo_height() == T.CONTROL_HEIGHT for e in app.entries)
            assert not app.latest_applied.cget('text').strip()
            app.clipboard_clear()
            app.clipboard_append('-6.881776, 107.610926')
            app.entries[0]._entry.event_generate('<<Paste>>')
            assert app.preview_center == (-6.881776, 107.610926)
            app.radius_slider.focus_set()
            app.update()
            before = app.radius_slider.get()
            app.radius_slider.event_generate('<Right>')
            assert app.radius_slider.get() > before
            app.browser.focus_set()
            app.update()
            app.browser.event_generate('<Down>')
            assert app.browser.get() == 'edge'
            app.browser.set('chrome')
            app.entries[0]._entry.focus_set()
            app.update()
            assert app.entries[0].cget('border_color') == T.FOCUS
            app.entries[0]._entry.event_generate('<Tab>')
            assert app.focus_get() == app.entries[1]._entry
            for index, target in enumerate(app.focus_targets):
                target.focus_set()
                app.update()
                target.event_generate('<Tab>')
                assert app.focus_get() == app.focus_targets[(index + 1) % len(app.focus_targets)]
            with patch('ui.app_window.messagebox.askokcancel', return_value=False) as consent:
                app.ip_button.focus_set()
                app.update()
                app.ip_button.event_generate('<space>')
                consent.assert_called_once()
            def test_run(settings):
                app.stop_event.wait(2)
                app.events.put(('stopped', None))
            with patch.object(app, 'run_loop', side_effect=test_run):
                app.toggle.focus_set()
                app.update()
                app.toggle.event_generate('<Return>')
                assert app.inputs_locked
                assert app.toggle.cget('text') == 'Stop Spoofing'
                assert app.toggle.cget('state') == 'normal'
                app.toggle.event_generate('<space>')
                assert app.toggle.cget('state') == 'normal', 'Stop must stay operable during cleanup'
                app.worker.join(timeout=2)
                app.drain_events()
                assert not app.inputs_locked
                assert app.toggle.cget('text') == 'Start Spoofing'
            with patch('ui.app_window.launch_browser_with_cdp') as launch:
                app.launch_button.invoke()
                import time
                deadline = time.monotonic() + 2
                while not launch.called and time.monotonic() < deadline:
                    time.sleep(.01)
                assert launch.called
            app.set_inputs_locked(True)
            app.on_map_click((1, 2))
            assert app.preview_center == (-6.881776, 107.610926)
            assert app.toggle.cget('state') == 'normal'
            app.set_inputs_locked(False)
            app.events.put(('point', (-6.8818, 107.6109)))
            app.drain_events()
            assert '-6.881800' in app.latest_applied.cget('text')
            app.latest_applied.configure(text='')
            print(f'PASS {size}: bounds, map dominance, 40px fields, paste, keyboard slider/selector/full Tab/focus, IP consent, launch callback, Enter/Space Start/Stop, locking, queued applied readout')
            if size == '1000x740':
                app.geometry('1200x820')
                app.after(500, lambda: check('1200x820'))
            else:
                app.destroy()
        except Exception:
            failures.append(traceback.format_exc())
            app.destroy()

    app.geometry('1000x740')
    app.after(700, lambda: check('1000x740'))
    app.mainloop()
    if failures:
        print('\n'.join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
