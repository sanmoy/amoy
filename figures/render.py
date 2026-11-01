#!/usr/bin/env python3
"""Regenerate figure SVGs, 1-bit-style PNGs, and the figure HTML pages.

The site does not run this file. Pages use the committed PNGs.
Requires Pillow. From the repo root:

    python3 figures/render.py
"""

from __future__ import print_function

import math
import os
import re

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
    ("apple", "Apple", "আপেল"),
]

# These SVGs are traced from Amoy's flash cards. render.py rasterizes
# them and does not redraw them.
TRACED = set(["hand", "eye", "apple"])


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


def draw_star(d):
    d.polygon(star_points(300, 310, 250), BLACK)


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
    "heart": draw_heart,
    "circle": draw_circle,
    "moon": draw_moon,
    "sun": draw_sun,
    "house": draw_house,
    "tree": draw_tree,
    "fish": draw_fish,
    "ball": draw_ball,
}


_SVG_TOKEN = re.compile(
    r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?"
)


def _flatten_cubic(p0, p1, p2, p3, n=12):
    pts = []
    for i in range(1, n + 1):
        t = i / float(n)
        u = 1.0 - t
        x = (u * u * u) * p0[0] + 3 * (u * u) * t * p1[0] + 3 * u * (t * t) * p2[0] + (t * t * t) * p3[0]
        y = (u * u * u) * p0[1] + 3 * (u * u) * t * p1[1] + 3 * u * (t * t) * p2[1] + (t * t * t) * p3[1]
        pts.append((x, y))
    return pts


def _svg_subpaths(d):
    tokens = _SVG_TOKEN.findall(d)
    i = 0
    cmd = None
    cx = cy = 0.0
    sx = sy = 0.0
    sub = []
    subs = []

    def num():
        v = float(tokens[i])
        return v

    while i < len(tokens):
        if re.match(r"[A-Za-z]", tokens[i]):
            cmd = tokens[i]
            i += 1
        if cmd in ("M", "m"):
            x = float(tokens[i]); i += 1
            y = float(tokens[i]); i += 1
            if cmd == "m":
                x += cx
                y += cy
            if sub:
                subs.append(sub)
            sub = [(x, y)]
            cx, cy = x, y
            sx, sy = x, y
            cmd = "L" if cmd == "M" else "l"
            continue
        if cmd in ("L", "l"):
            x = float(tokens[i]); i += 1
            y = float(tokens[i]); i += 1
            if cmd == "l":
                x += cx
                y += cy
            sub.append((x, y))
            cx, cy = x, y
            continue
        if cmd in ("C", "c"):
            nums = []
            for _k in range(6):
                nums.append(float(tokens[i])); i += 1
            x1, y1, x2, y2, x, y = nums
            if cmd == "c":
                x1 += cx; y1 += cy
                x2 += cx; y2 += cy
                x += cx; y += cy
            sub.extend(_flatten_cubic((cx, cy), (x1, y1), (x2, y2), (x, y)))
            cx, cy = x, y
            continue
        if cmd in ("Z", "z"):
            if sub and sub[0] != sub[-1]:
                sub.append(sub[0])
            subs.append(sub)
            sub = []
            cx, cy = sx, sy
            continue
        raise SystemExit("unsupported SVG path command: %s" % cmd)
    if sub:
        subs.append(sub)
    return subs


def rasterize_svg(path):
    """Even-odd fill of an SVG path onto a 600x600 black-and-white image.

    Edges are stair-stepped, same as the Pillow polygons used for the
    other figures, so the PNG has no grey antialias halo.
    """
    text = open(path, encoding="utf-8").read()
    chunks = re.findall(r'<path\b[^>]*\bd="([^"]+)"', text, re.S)
    if not chunks:
        raise SystemExit("no path in " + path)
    subs = []
    for d in chunks:
        subs.extend(_svg_subpaths(re.sub(r"\s+", " ", d)))
    edges = []
    for sub in subs:
        for i in range(len(sub) - 1):
            edges.append((sub[i], sub[i + 1]))
    buf = bytearray(SIZE * SIZE)
    for y in range(SIZE):
        ys = y + 0.5
        xs = []
        for (x0, y0), (x1, y1) in edges:
            if (y0 <= ys < y1) or (y1 <= ys < y0):
                t = (ys - y0) / (y1 - y0)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        k = 0
        row = y * SIZE
        while k + 1 < len(xs):
            a = int(math.ceil(xs[k] - 1e-6))
            b = int(math.floor(xs[k + 1] + 1e-6))
            if b >= a:
                if a < 0:
                    a = 0
                if b >= SIZE:
                    b = SIZE - 1
                if a <= b:
                    for x in range(a, b + 1):
                        buf[row + x] = 255
            k += 2
    # buf is 255 where the shape is black. Build an RGB image.
    im = Image.new("RGB", (SIZE, SIZE), WHITE)
    pix = im.load()
    for y in range(SIZE):
        row = y * SIZE
        for x in range(SIZE):
            if buf[row + x]:
                pix[x, y] = BLACK
    return im


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
    known = set(DRAW) | TRACED
    wanted = set(slug for slug, _e, _b in FIGURES)
    if known != wanted:
        raise SystemExit("DRAW/TRACED and FIGURES are out of sync")
    os.makedirs(SRC, exist_ok=True)
    os.makedirs(IMG, exist_ok=True)
    n = len(FIGURES)
    for i, (slug, english, bengali) in enumerate(FIGURES):
        png_path = os.path.join(IMG, slug + ".png")
        svg_path = os.path.join(SRC, slug + ".svg")
        if slug in TRACED:
            save_png(rasterize_svg(svg_path), png_path)
        else:
            d = Drawer()
            DRAW[slug](d)
            save_png(d.im, png_path)
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(d.svg())
        audit(png_path)
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
