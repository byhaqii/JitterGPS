"""Capture real Tk before/after evidence on macOS. No fabricated application data."""
import sys
from pathlib import Path

from ui.app_window import AppWindow


def main():
    scratch = Path.home() / '.hermes/profiles/builder/cache/scratch'
    from tests.native_capture import capture
    output = Path(sys.argv[1] if len(sys.argv) > 1 else scratch / 'jitter-redesign.png')
    output.parent.mkdir(parents=True, exist_ok=True)
    app = AppWindow()
    errors = []
    app.report_callback_exception = lambda *exc: errors.append(str(exc[1]))
    if len(sys.argv) > 2:
        app.geometry(sys.argv[2])
    def save():
        try:
            print(capture(output))
            print('Window:', app.winfo_width(), app.winfo_height())
            if app.map_view is not None:
                print('Map:', app.map_view.winfo_width(), app.map_view.winfo_height())
        except Exception as exc:
            errors.append(str(exc))
        finally:
            app.on_close()
    app.after(2500, save)
    app.mainloop()
    if errors:
        raise RuntimeError('; '.join(errors))


if __name__ == '__main__':
    main()
