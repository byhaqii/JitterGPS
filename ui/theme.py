"""Precision workbench tokens. Native system type keeps desktop controls familiar."""
# Glass-inspired layering: darker canvas, lifted frosted panels, lightest fields.
# Flat tone steps only — Tk has no backdrop blur, so depth is simulated, never drawn.
# 2026-11-08: owner swapped green for an ice-blue accent to match the glass direction.
CANVAS = '#0e1319'
PANEL = '#1b2530'
FIELD = '#202b38'
HOVER = '#29394a'
TEXT = '#edf1f4'
SECONDARY = '#a7b4c0'
DISABLED = '#98aab8'
EDGE = '#7d90a0'
DIVIDER = '#3a4a5c'
ACCENT = '#8ecdf1'
MAP_OUTLINE = '#2e6a94'
INK = '#10161c'
FOCUS = '#b8e2f9'
APPLIED = '#f2c06b'
ERROR = '#e6a29d'
ERROR_INK = '#261715'
TRANSPARENT = 'transparent'
SANS = 'TkDefaultFont'
MONO = 'Menlo'
SMALL = 12
BODY = 14
SECTION = 16
TITLE = 20
RAIL_WIDTH = 300
CONTROL_HEIGHT = 40
ACTION_HEIGHT = 44
ACTIVITY_HEIGHT = 120
RADIUS = 10
TEXT_PAIRS = [(TEXT, CANVAS), (TEXT, PANEL), (SECONDARY, CANVAS),
              (SECONDARY, PANEL), (DISABLED, FIELD), (DISABLED, HOVER),
              (INK, ACCENT), (INK, FOCUS), (ERROR_INK, ERROR),
              (APPLIED, PANEL), (APPLIED, CANVAS), (ERROR, PANEL)]
EDGE_PAIRS = [(EDGE, FIELD), (EDGE, PANEL), (FOCUS, FIELD), (FOCUS, HOVER)]


def contrast(a, b):
    def luminance(color):
        rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        rgb = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
        return sum(v * w for v, w in zip(rgb, (.2126, .7152, .0722)))
    light, dark = sorted((luminance(a), luminance(b)), reverse=True)
    return (light + .05) / (dark + .05)
