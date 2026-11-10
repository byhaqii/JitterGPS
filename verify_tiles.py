"""Verify imagery through the actual map widget, not a separate HTTP request."""
import sys
import time
from pathlib import Path
from PIL import ImageTk

from ui.app_window import AppWindow


def verify():
    app = AppWindow()
    failures = []
    app.report_callback_exception = lambda *exc: failures.append(str(exc[1]))
    started = time.monotonic()
    app.set_center(-6.881776, 107.610926, recenter=True)
    def check():
        view = app.map_view
        if view is None:
            failures.append('Map widget did not initialize')
            app.destroy()
            return
        tiles = [tile for column in view.canvas_tile_array for tile in column
                 if tile.canvas_object is not None and tile.image not in
                 (view.empty_tile_image, view.not_loaded_tile_image)]
        if tiles:
            # A real, visible CanvasTile backed by a decoded provider image.
            output = Path.home() / '.hermes/profiles/builder/cache/scratch/jitter-widget-tile.png'
            output.parent.mkdir(parents=True, exist_ok=True)
            ImageTk.getimage(tiles[0].image).save(output)
            print(f'PASS: actual widget displays {len(tiles)} map tile(s); '
                  f'network requests={view.tile_cache.network_count}, disk hits={view.tile_cache.hit_count}')
            print('Visible widget tile saved:', output)
            if app.tile_error:
                failures.append(app.tile_error)
            app.destroy()
        elif time.monotonic() - started > 35:
            failures.append(app.tile_error or 'No actual map imagery loaded in 35 seconds')
            app.destroy()
        else:
            app.after(250, check)
    app.after(250, check)
    app.mainloop()
    if failures:
        raise RuntimeError('; '.join(failures))


if __name__ == '__main__':
    verify()
