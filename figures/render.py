#!/usr/bin/env python3
"""Regenerate figure SVGs, 1-bit-style PNGs, and the figure HTML pages.

The site does not run this file. Pages use the committed PNGs.
Requires Pillow. From the repo root:

    python3 figures/render.py
"""

from __future__ import print_function

import math
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
IMG = os.path.join(ROOT, "img")
SIZE = 600
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# Picture-book order. Previous/Next wrap around this list.
FIGURES = [
    ("star", "Star", "তারা"),
    ("eye", "Eye", "চোখ"),
    ("hand", "Hand", "হাত"),
    ("heart", "Heart", "হৃদয়"),
    ("circle", "Circle", "বৃত্ত"),
    ("moon", "Moon", "চাঁদ"),
    ("sun", "Sun", "সূর্য"),
    ("house", "House", "বাড়ি"),
    ("tree", "Tree", "গাছ"),
    ("fish", "Fish", "মাছ"),
    ("ball", "Ball", "বল"),
]


class Drawer(object):
    def __init__(self):
        self.im = Image.new("RGB", (SIZE, SIZE), WHITE)
        self.draw = ImageDraw.Draw(self.im)
        self.parts = []

    def _hex(self, color):
        return "#000000" if color == BLACK else "#ffffff"

    def polygon(self, pts, color):
        self.draw.polygon(pts, fill=color)
        coords = " ".join("%.1f,%.1f" % (x, y) for x, y in pts)
        self.parts.append(
            '<polygon fill="%s" points="%s"/>' % (self._hex(color), coords)
        )

    def ellipse(self, box, color):
        self.draw.ellipse(box, fill=color)
        x0, y0, x1, y1 = box
        self.parts.append(
            '<ellipse fill="%s" cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f"/>'
            % (
                self._hex(color),
                (x0 + x1) / 2.0,
                (y0 + y1) / 2.0,
                (x1 - x0) / 2.0,
                (y1 - y0) / 2.0,
            )
        )

    def rect(self, box, color):
        self.draw.rectangle(box, fill=color)
        x0, y0, x1, y1 = box
        self.parts.append(
            '<rect fill="%s" x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>'
            % (self._hex(color), x0, y0, x1 - x0, y1 - y0)
        )

    def svg(self):
        body = "\n  ".join(self.parts)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600" viewBox="0 0 600 600">\n'
            '  <rect fill="#ffffff" width="600" height="600"/>\n'
            "  %s\n"
            "</svg>\n"
        ) % body


def star_points(cx, cy, outer):
    # Regular five-point star, one point up. Inner radius is the
    # pentagram intersection, which matches a plain solid star.
    inner = outer * (math.cos(math.radians(72)) / math.cos(math.radians(36)))
    pts = []
    for i in range(10):
        ang = -math.pi / 2.0 + i * (math.pi / 5.0)
        rad = outer if i % 2 == 0 else inner
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return pts


def sine_lens(cx, cy, rx, ry, steps=80):
    pts = []
    for i in range(steps + 1):
        t = i / float(steps)
        x = cx - rx + 2.0 * rx * t
        y = cy - ry * math.sin(math.pi * t)
        pts.append((x, y))
    for i in range(steps, -1, -1):
        t = i / float(steps)
        x = cx - rx + 2.0 * rx * t
        y = cy + ry * math.sin(math.pi * t)
        pts.append((x, y))
    return pts


def heart_points(cx, cy, scale, steps=180):
    pts = []
    for i in range(steps):
        a = 2.0 * math.pi * i / float(steps)
        x = 16.0 * math.sin(a) ** 3
        y = (
            13.0 * math.cos(a)
            - 5.0 * math.cos(2.0 * a)
            - 2.0 * math.cos(3.0 * a)
            - math.cos(4.0 * a)
        )
        pts.append((cx + x * scale, cy - y * scale))
    return pts


def finger(d, x, top, bottom, width):
    # Shaft plus a round tip. Overlaps the palm so there is no gap.
    d.rect((x, top + width / 2.0, x + width, bottom), BLACK)
    d.ellipse((x, top, x + width, top + width), BLACK)


def capsule_points(x0, y0, x1, y1, width, steps=18):
    """Hard-edged capsule from (x0, y0) to (x1, y1). No rotated bitmaps."""
    ang = math.atan2(y1 - y0, x1 - x0)
    hw = width / 2.0
    pts = []
    for i in range(steps + 1):
        a = ang - math.pi / 2.0 + math.pi * i / float(steps)
        pts.append((x1 + hw * math.cos(a), y1 + hw * math.sin(a)))
    for i in range(steps + 1):
        a = ang + math.pi / 2.0 + math.pi * i / float(steps)
        pts.append((x0 + hw * math.cos(a), y0 + hw * math.sin(a)))
    return pts


def draw_star(d):
    d.polygon(star_points(300, 310, 250), BLACK)


def draw_eye(d):
    d.polygon(sine_lens(300, 300, 230, 118), BLACK)
    d.ellipse((228, 228, 372, 372), WHITE)
    d.ellipse((262, 262, 338, 338), BLACK)


def draw_hand(d):
    # Palm facing the reader. Thumb on the left, four thick fingers.
    finger(d, 196, 148, 360, 72)  # index
    finger(d, 284, 108, 360, 72)  # middle
    finger(d, 372, 158, 360, 72)  # ring
    finger(d, 460, 214, 360, 72)  # pinky
    d.rect((180, 300, 548, 470), BLACK)
    # Thumb starts well inside the palm so the join stays solid.
    d.polygon(capsule_points(260, 345, 88, 408, 102), BLACK)
    # Palm heel drawn last so it covers the wedge under the thumb.
    d.ellipse((60, 400, 548, 540), BLACK)


def draw_heart(d):
    d.polygon(heart_points(300, 328, 13.2), BLACK)


def draw_circle(d):
    d.ellipse((90, 90, 510, 510), BLACK)


def draw_moon(d):
    # Fat crescent. The white disk is a cutout, not a grey shade.
    d.ellipse((70, 90, 470, 510), BLACK)
    d.ellipse((188, 70, 548, 470), WHITE)


def draw_sun(d):
    cx, cy = 300, 300
    d.ellipse((175, 175, 425, 425), BLACK)
    rays = 8
    inner = 100
    outer = 246
    half = math.radians(18)
    for i in range(rays):
        ang = -math.pi / 2.0 + i * (2.0 * math.pi / rays)
        d.polygon(
            [
                (
                    cx + inner * math.cos(ang - half),
                    cy + inner * math.sin(ang - half),
                ),
                (
                    cx + outer * math.cos(ang),
                    cy + outer * math.sin(ang),
                ),
                (
                    cx + inner * math.cos(ang + half),
                    cy + inner * math.sin(ang + half),
                ),
            ],
            BLACK,
        )


def draw_house(d):
    d.polygon([(110, 280), (300, 90), (490, 280)], BLACK)
    d.rect((150, 260, 450, 520), BLACK)
    d.rect((278, 378, 362, 520), WHITE)
    d.rect((186, 300, 252, 366), WHITE)


def draw_tree(d):
    d.ellipse((70, 50, 530, 430), BLACK)
    d.rect((255, 360, 345, 545), BLACK)


def draw_fish(d):
    d.ellipse((190, 200, 520, 410), BLACK)
    d.polygon([(240, 305), (60, 185), (60, 425)], BLACK)
    d.polygon([(340, 230), (400, 115), (455, 235)], BLACK)
    d.polygon([(350, 375), (415, 495), (480, 370)], BLACK)
    d.ellipse((430, 255, 490, 315), WHITE)


def wedge(cx, cy, radius, a0, a1, steps=12):
    pts = [(cx, cy)]
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / float(steps)
        pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return pts


def draw_ball(d):
    d.ellipse((90, 90, 510, 510), BLACK)
    # Three thick seams that stop short of the rim, like a beach ball.
    # They do not cross the outline, so this is not a "no" sign.
    for base in (-math.pi / 2.0, math.pi / 6.0, 5.0 * math.pi / 6.0):
        d.polygon(wedge(300, 300, 195, base - 0.13, base + 0.13), WHITE)


DRAW = {
    "star": draw_star,
    "eye": draw_eye,
    "hand": draw_hand,
    "heart": draw_heart,
    "circle": draw_circle,
    "moon": draw_moon,
    "sun": draw_sun,
    "house": draw_house,
    "tree": draw_tree,
    "fish": draw_fish,
    "ball": draw_ball,
}


def save_png(im, path):
    # Stair-step edges only. Force every pixel to pure black or pure white,
    # then store an 8-bit palette of those two colors (no alpha, no interlace).
    # 8-bit palette is safer than 1-bit for old PNG decoders, and still has no grey.
    lum = im.convert("L").point(lambda p: 255 if p >= 128 else 0)
    pal = Image.new("P", lum.size)
    pal.putpalette([0, 0, 0, 255, 255, 255] + [0, 0, 0] * 254)
    pal.paste(lum.point(lambda p: 0 if p == 0 else 1))
    pal.save(path, "PNG", optimize=True)


def page_html(slug, english, bengali, prev_slug, next_slug):
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta name="viewport" content="width=device-width">
<meta name="color-scheme" content="light">
<title>%s</title>
<link rel="stylesheet" href="../style.css">
</head>
<body class="figure-page">
<p class="nav"><a href="index.html">Figures</a></p>
<p class="figure"><img src="img/%s.png" width="600" height="600" alt="%s"></p>
<h1>%s</h1>
<p class="name-bn bn" lang="bn">%s</p>
<table class="pager">
<tr>
<td><a href="%s.html">Previous</a></td>
<td><a href="%s.html">Next</a></td>
</tr>
</table>
</body>
</html>
""" % (
        english,
        slug,
        english,
        english,
        bengali,
        prev_slug,
        next_slug,
    )


def index_html(figures):
    cells = []
    for slug, english, bengali in figures:
        cells.append(
            '<td><a href="%s.html"><img src="img/%s.png" width="150" height="150" alt="">'
            '<span class="label" lang="en">%s</span><br>'
            '<span class="bn" lang="bn">%s</span></a></td>'
            % (slug, slug, english, bengali)
        )
    rows = []
    for i in range(0, len(cells), 2):
        pair = cells[i : i + 2]
        if len(pair) == 1:
            pair.append("<td></td>")
        rows.append("<tr>\n" + "\n".join(pair) + "\n</tr>")
    body = "\n".join(rows)
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta name="viewport" content="width=device-width">
<meta name="color-scheme" content="light">
<title>Figures</title>
<link rel="stylesheet" href="../style.css">
</head>
<body>
<p class="nav"><a href="../index.html">Home</a></p>
<h1>Figures</h1>
<table class="figure-index">
%s
</table>
</body>
</html>
""" % body


def audit(path):
    im = Image.open(path)
    colors = im.convert("RGB").getcolors(maxcolors=100000)
    if not colors:
        raise SystemExit("too many colors: " + path)
    used = set(c[1] for c in colors)
    bad = used - set([BLACK, WHITE])
    if bad:
        raise SystemExit("grey or extra colors in %s: %s" % (path, sorted(bad)[:8]))
    if im.mode not in ("P", "1", "L"):
        raise SystemExit("unexpected mode %s for %s" % (im.mode, path))


def main():
    if set(DRAW) != set(slug for slug, _e, _b in FIGURES):
        raise SystemExit("DRAW and FIGURES are out of sync")
    os.makedirs(SRC, exist_ok=True)
    os.makedirs(IMG, exist_ok=True)
    n = len(FIGURES)
    for i, (slug, english, bengali) in enumerate(FIGURES):
        d = Drawer()
        DRAW[slug](d)
        png_path = os.path.join(IMG, slug + ".png")
        svg_path = os.path.join(SRC, slug + ".svg")
        save_png(d.im, png_path)
        audit(png_path)
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(d.svg())
        prev_slug = FIGURES[(i - 1) % n][0]
        next_slug = FIGURES[(i + 1) % n][0]
        page_path = os.path.join(ROOT, slug + ".html")
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(page_html(slug, english, bengali, prev_slug, next_slug))
        print("%s.png %d bytes" % (slug, os.path.getsize(png_path)))
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html(FIGURES))
    print("wrote", n, "figures")


if __name__ == "__main__":
    main()
