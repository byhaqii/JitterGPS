"""Regenerate the map-pin app icon using the existing Pillow dependency."""
from pathlib import Path
from PIL import Image, ImageDraw


if __name__ == '__main__':
    scale = 4
    image = Image.new('RGBA', (1024 * scale, 1024 * scale))
    draw = ImageDraw.Draw(image)
    def box(values):
        return tuple(int(v * scale) for v in values)
    draw.rounded_rectangle(box((64, 64, 960, 960)), radius=208 * scale,
                           fill='#223b30', outline='#3e5d46', width=3 * scale)
    draw.arc(box((208, 208, 816, 816)), 22, 338, fill='#668168', width=14 * scale)
    curves = [((512, 748), (480, 690), (350, 560), (350, 430)),
              ((350, 430), (350, 340), (422, 268), (512, 268)),
              ((512, 268), (602, 268), (674, 340), (674, 430)),
              ((674, 430), (674, 560), (544, 690), (512, 748))]
    points = []
    for start, a, b, end in curves:
        for step in range(65):
            t = step / 64
            points.append(tuple(scale * ((1-t)**3 * start[i] + 3*(1-t)**2*t*a[i]
                                        + 3*(1-t)*t*t*b[i] + t**3*end[i]) for i in (0, 1)))
    draw.polygon(points, fill='#c9e2cb')
    draw.ellipse(box((450, 368, 574, 492)), fill='#223b30')
    draw.ellipse(box((744, 596, 820, 672)), fill='#223b30')
    draw.ellipse(box((754, 606, 810, 662)), fill='#f2c06b')
    image = image.resize((1024, 1024), Image.Resampling.LANCZOS)
    root = Path(__file__).resolve().parent
    image.save(root / 'JitterGPS.png')
    image.save(root / 'JitterGPS.icns')
    image.save(root / 'JitterGPS.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print('Generated PNG, macOS ICNS and Windows ICO.')
