# Jitter GPS Desktop

Browser geolocation testing for Chrome, Edge, and Brave. Does not change OS location,
mask your IP, or guarantee that websites accept or cannot detect an override.

## Try on macOS

Open `dist/JitterGPS.app`, select a browser, and click **Launch Debug Browser**.
The browser uses an app-owned isolated profile, not your normal browser profile.
Avoid sensitive accounts in this debug profile. Keep CDP port 9222 private.

1. Open https://browserleaks.com/geo in that browser.
2. Enter center coordinates, radius, interval, and accuracy; click **Start Spoofing**.
3. Allow location when the browser asks. Refresh the website's location check if needed.
4. **Stop Spoofing** clears reachable overrides. A website's already-rendered value
   may remain stale; ask it to request location again.

Use a normal browser window for normal browsing. The debug browser stays open on app exit.
If the port is occupied, close the previously launched debug browser before relaunching.

## Paste coordinates and preview the radius

Paste a `latitude, longitude` pair, for example `-6.881776, 107.610926`,
to fill both center fields automatically. Use the map to choose a center and
preview the radius circle. Adjust the radius with the slider or meter field.
Center/radius changes are locked while spoofing; stop first to edit them.

Map imagery needs internet access. Map tiles are provided by OpenStreetMap
(© OpenStreetMap contributors); tile requests reveal your IP and the area viewed
to the tile provider. Browser spoofing still works when map tiles cannot load.

The app uses an identified JitterGPS tile loader and seven-day persistent caching
(`~/Library/Caches/JitterGPS/tiles-v1` on macOS). Only viewport tiles are requested;
upstream prefetching is disabled. Expired tiles are conditionally revalidated.
HTTP errors are not rendered or cached as map images; 403/429 responses pause
provider requests for five minutes. A provider can still deny service independently.

To verify real widget imagery on a desktop: `.venv/bin/python verify_tiles.py`.

## Install & run (bash only)

Requires Python 3.10+ with Tk support and a supported browser installed.

```bash
git clone https://github.com/byhaqii/JitterGPS.git && cd JitterGPS && python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt && .venv/bin/python main.py
```

## Live development preview

```sh
.venv/bin/python dev.py
```

Opens the app and restarts after valid Python source changes. Restart requests
normal override cleanup and resets form inputs. Close the window to stop watching.

## Build / test

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python build.py
```

Build independently on macOS and Windows; macOS build architecture follows Python.
Local builds are not Developer-ID signed/notarized. Only bypass Gatekeeper for a
build you trust. No Windows or Intel macOS support is claimed as tested until exercised.

## Behavior and limitations

- One six-decimal coordinate per tick, shared across reachable page tabs.
- Local-disc radius sampling mapped onto a sphere; rounded points checked inside radius.
- Bounded recent-history uniqueness; it is not a lifetime non-repetition guarantee.
- Page targets are polled once per tick. New tabs may read normal location until updated.
- Navigation, site permissions, site caching, and unavailable normal geolocation affect results.
- Cleanup is best effort if a browser closes or becomes unreachable.
- Optional IP lookup contacts ipapi.co only after explicit confirmation.
