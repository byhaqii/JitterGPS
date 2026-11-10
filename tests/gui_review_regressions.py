"""Native UI regressions identified by the independent finish review."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui.app_window import AppWindow


def main():
    app = AppWindow(map_offline=True)
    failures = []
    def check():
        app.update_fallback(False)
        app.set_center(90, 180, recenter=True)
        if app.circle_canvas.winfo_manager() != 'grid':
            failures.append('Polar fallback remains hidden')
        app.set_center(-6.881776, 107.610926, recenter=True)
        app.show_applied_point((-6.881780, 107.610930))
        app.events.put(('stopped', None))
        app.drain_events()
        if app.applied_point is not None or app.point_marker is not None or app.latest_applied.cget('text'):
            failures.append('Stopped state still presents an applied position')
        app.on_close()
    app.after(500, check)
    app.mainloop()
    assert not failures, '; '.join(failures)
    print('PASS: polar fallback shown; stopped state clears applied marker and readout.')


if __name__ == '__main__':
    main()
