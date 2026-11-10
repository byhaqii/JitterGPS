# Jitter GPS design system

## Direction
Precision workbench, approved by the user. Desktop geolocation testing, not a marketing page.
Hallmark app-screen scope with Anti Slop applied during the redesign.
Dial: ENERGY 1 / RHYTHM 2 / MOTION 1.

## Composition
The map is the primary object. A fixed-width, compact control rail sets its center,
radius and timing. Start/stop is the only filled primary action. Browser launch and
IP lookup remain secondary. A short activity region holds real events below the map,
not a terminal-shaped hero. No navigation destinations, metrics, photos or logos added.
Preserve all five fields, coordinate-paste handlers, radius slider, browser selector,
launch/start/stop/IP callbacks, status, real activity log and map attribution.
Keep the offline circle as a fallback, not a competing duplicate map.

## Tokens
Native Python theme tokens, not CSS: `ui/theme.py`.
2026-11-07 owner-approved amendment: glass-inspired layered surfaces. Tk has no
backdrop blur, so depth is simulated with flat tone steps only: deeper canvas,
lifted frosted panels with a hairline divider edge, fields one step lighter than
panels. No real glassmorphism, gradients, glow or texture is drawn.
2026-11-08 owner-approved amendment: green replaced by an ice-blue accent to match
the glass direction. The blue is a deliberate owner choice for this identity (not a
default), sits far from the amber applied marker and salmon error tone, and carries
the surfaces to cool slate so the map stays the warmest object on screen.
Surfaces: canvas #0e1319, panel #1b2530, field #202b38, hover #29394a.
Text: primary #edf1f4, secondary #a7b4c0, disabled #98aab8.
Edges: field #7d90a0 (visible field boundary), divider #3a4a5c.
Signal: accent #8ecdf1, accent ink #10161c, focus #b8e2f9.
Applied point: #f2c06b. Error/stop: #e6a29d with ink #261715.
Sans: native system face for familiar desktop controls. Monospace only for exact
coordinates and real log records. Sizes: 12, 14, 16, 20. No decorative display font.
Spacing: 4, 8, 12, 16, 24. Control height 40, action height 44. Radius 10 for controls,
zero for layout regions; no nested decorative cards, gradients, glow or texture.

## Reasons
Dark control surfaces reduce glare beside map imagery during repeated test sessions.
Layered tone steps (canvas → panel → field) give the depth the owner asked for in the
glass theme without fake blur, gradients or contrast loss over map imagery.
Ice blue marks the one primary action and geographic center; amber marks actual applied position.
Neutral secondary actions do not compete with the map or Start/Stop.
The map earns most screen area because users choose and inspect a real location there.
Short event history stays visible without dominating center selection.
No animation beyond hover/focus/state changes; periodic point movement is actual data.

## Native scope
Desktop macOS/Windows only. Mobile web, CSS, ARIA, URL-state and Hallmark browser-render
linting do not apply to Tk. Verify native bounds, keyboard operation, contrast, actual
map imagery, state handling and the packaged executable instead. Do not claim browser
lint scores or full screen-reader accessibility from these checks.
