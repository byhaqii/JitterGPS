import os
import signal
import sys
import tkinter as tk
from pathlib import Path

# Source-preview restarts request the same cleanup as closing the window.
from ui.app_window import AppWindow


if __name__ == '__main__':
    app = AppWindow()
    resources = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    app._icon_photo = tk.PhotoImage(file=str(resources / 'assets/JitterGPS.png'))
    app.iconphoto(True, app._icon_photo)
    closing = False
    if os.environ.get('JITTER_LIVE_PREVIEW'):
        app.title('Jitter GPS · Live Preview')

    def request_close(*_):
        global closing
        closing = True

    def check_close():
        if closing:
            app.on_close()
        else:
            app.after(150, check_close)

    signal.signal(signal.SIGTERM, request_close)
    signal.signal(signal.SIGINT, request_close)
    app.after(150, check_close)
    app.mainloop()
