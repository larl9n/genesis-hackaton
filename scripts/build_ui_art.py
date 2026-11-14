"""Generate the ordered diamond ribbon illustration; no downloaded artwork."""

import math
from pathlib import Path


if __name__ == "__main__":
    points = []
    for row, y in enumerate(range(10, 465, 7)):
        for x in range(-20, 1520, 7):
            xx = x + 3.5 * (row % 2)
            u = abs(xx - 749)
            if not 42 < u < 825:
                continue
            center = 218 + 63 * math.sin(u / 205) - .09 * u
            half = 38 + 83 * (1 - math.exp(-u / 210))
            v = (y - center) / half
            if abs(v) > 1:
                continue
            wave = .5 + .5 * math.cos(v * math.pi * .95 + u / 95)
            luminance = max(0, 1 - abs(v) ** 3) * (.44 + .56 * wave) * (.9 - .2 * math.cos(u / 87))
            if abs(v - .28 * math.sin(u / 170)) < .055 and u > 180:
                luminance *= .2
            radius = .45 + 2.35 * luminance
            points.append(f'<path d="M{xx:.1f} {y-radius:.2f}l{radius:.2f} {radius:.2f}-{radius:.2f} {radius:.2f}-{radius:.2f}-{radius:.2f}Z" opacity="{.23+.74*luminance:.2f}"/>')
    target = Path(__file__).resolve().parents[1] / "src/genesis_fintech/web/static/sculpture.svg"
    target.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1498 475" fill="#f3f3f3">' + ''.join(points) + '</svg>\n', encoding="utf-8")
    print(f"Generated {len(points)} ordered points: {target}")
