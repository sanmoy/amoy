#!/usr/bin/env python3
"""Regenerate the Kindle debug pages from the poem and tools/preshape.py.

Reads the first stanza of poems/khai-khai.html, writes debug/sample.txt,
builds the two pre-shaped fonts, and writes debug/index.html plus tests
01 through 07. Source fonts for tests 2-4 already live in debug/fonts/.

    python3 tools/build_debug.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import preshape  # noqa: E402

DEBUG = ROOT / "debug"
FONTS = DEBUG / "fonts"
NOTO = ROOT / "fonts" / "NotoSansBengali-Regular.ttf"
POEM = ROOT / "poems" / "khai-khai.html"
ARTIFACT = Path("/opt/cursor/artifacts/preshape-vs-reference.png")

# The hard-case line, checked against codepoints so a lookalike cannot slip in.
HARD = "কি কে কো কৌ ক্ষ ত্র স্ত ন্দ র্ক ক্য ঙ্গ শ্চ ঁ ং ৎ"
HARD_CODES = [
    0x0995, 0x09BF, 0x20,
    0x0995, 0x09C7, 0x20,
    0x0995, 0x09CB, 0x20,
    0x0995, 0x09CC, 0x20,
    0x0995, 0x09CD, 0x09B7, 0x20,
    0x09A4, 0x09CD, 0x09B0, 0x20,
    0x09B8, 0x09CD, 0x09A4, 0x20,
    0x09A8, 0x09CD, 0x09A6, 0x20,
    0x09B0, 0x09CD, 0x0995, 0x20,
    0x0995, 0x09CD, 0x09AF, 0x20,
    0x0999, 0x09CD, 0x0997, 0x20,
    0x09B6, 0x09CD, 0x099A, 0x20,
    0x0981, 0x20,
    0x0982, 0x20,
    0x09CE,
]

DEBUG_CSS = """\
/* Debug pages only. Same limits as the rest of the site:
   no flex, no grid, no variables, no animation. */

html {
  background: #ffffff;
  color: #000000;
}

body {
  margin: 16px;
  padding: 0;
  background: #ffffff;
  color: #000000;
  font-family: sans-serif;
  font-size: 28px;
  font-weight: normal;
  line-height: 1.45;
}

h1 {
  margin: 0 0 12px 0;
  padding: 0;
  font-size: 36px;
  font-weight: normal;
  line-height: 1.3;
}

h2 {
  margin: 28px 0 12px 0;
  padding: 0;
  font-size: 32px;
  font-weight: normal;
  line-height: 1.3;
}

p {
  margin: 0 0 16px 0;
}

a {
  color: #000000;
}

.menu {
  list-style: none;
  margin: 0;
  padding: 0;
}

.menu li {
  margin: 0 0 14px 0;
  padding: 0;
}

.menu a {
  display: block;
  padding: 18px 16px;
  border: 4px solid #000000;
  background: #ffffff;
  color: #000000;
  font-size: 28px;
  line-height: 1.35;
  text-decoration: underline;
}

.nav {
  margin: 0 0 18px 0;
}

.nav a {
  display: block;
  padding: 16px;
  border: 4px solid #000000;
  background: #ffffff;
  color: #000000;
  font-size: 26px;
  line-height: 1.3;
  text-decoration: underline;
}

.label {
  font-family: sans-serif;
  font-size: 26px;
  font-weight: normal;
  line-height: 1.4;
  margin: 0 0 12px 0;
}

.sample {
  font-size: 40px;
  font-weight: normal;
  line-height: 1.85;
  margin: 0 0 18px 0;
}

img.picture {
  display: block;
  width: 100%;
  height: auto;
  border: 4px solid #000000;
  margin: 0 0 18px 0;
}

#device-ua {
  font-family: sans-serif;
  font-size: 22px;
  line-height: 1.45;
  border: 4px solid #000000;
  padding: 12px;
  margin: 0 0 16px 0;
}
"""

DEVICE_SCRIPT = """\
<script type="text/javascript">
var el = document.getElementById("device-ua");
if (el && navigator && navigator.userAgent) {
  var text = "User agent: " + navigator.userAgent;
  while (el.firstChild) {
    el.removeChild(el.firstChild);
  }
  el.appendChild(document.createTextNode(text));
}
</script>
"""

TESTS = [
    (
        "01-noto.html",
        "Test 1. Noto Sans Bengali",
        "Unicode text. Same Noto Sans Bengali files as the poems. Shaping is left to the browser.",
        "noto",
    ),
    (
        "02-lohit.html",
        "Test 2. Lohit Bengali",
        "Unicode text. Lohit Bengali 2.91.5, SIL Open Font License.",
        "lohit",
    ),
    (
        "03-hind-siliguri.html",
        "Test 3. Hind Siliguri",
        "Unicode text. Hind Siliguri Regular, Indian Type Foundry, SIL Open Font License.",
        "hind",
    ),
    (
        "04-baloo-da-2.html",
        "Test 4. Baloo Da 2",
        "Unicode text. Baloo Da 2 Regular, a static instance of the OFL variable font.",
        "baloo",
    ),
    (
        "05-preshape-cluster.html",
        "Test 5. Pre-shaped clusters",
        "One Private Use character per syllable. Positions are baked into the glyph. The font has no GSUB or GPOS.",
        "cluster",
    ),
    (
        "06-preshape-glyph.html",
        "Test 6. Pre-shaped glyphs",
        "One Private Use character per glyph, in visual order. Mark offsets are baked in. The font has no GSUB or GPOS.",
        "glyph",
    ),
    (
        "07-image.html",
        "Test 7. Picture",
        "A picture of the sample, drawn with HarfBuzz and Noto Sans Bengali. Black on white.",
        "image",
    ),
]


def extract_stanza():
    html = POEM.read_text(encoding="utf-8")
    match = re.search(r'<div class="poem bn" lang="bn">(.*?)</div>', html, re.S)
    if not match:
        raise SystemExit("could not find the poem body")
    paras = re.findall(r"<p>(.*?)</p>", match.group(1), re.S)
    if not paras:
        raise SystemExit("could not find a stanza")
    lines = [line.strip() for line in re.split(r"<br\s*>", paras[0])]
    lines = [line for line in lines if line]
    if len(lines) != 14:
        raise SystemExit("expected 14 lines in the first stanza, got %s" % len(lines))
    if not lines[0].startswith("খাই খাই"):
        raise SystemExit("first line is not the Khai Khai stanza")
    return lines


def check_hard_line():
    codes = [ord(ch) for ch in HARD]
    if codes != HARD_CODES:
        raise SystemExit("hard-case line codepoints do not match the locked list")


def escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def comment(text):
    return "<!-- %s -->" % text.replace("--", "-")


def sample_paragraph(lines, lang):
    lang_attr = ' lang="%s"' % lang if lang else ""
    parts = ['<p class="sample"%s>' % lang_attr]
    for index, line in enumerate(lines):
        if index:
            parts.append("<br\n>")
        parts.append(escape(line))
    parts.append("</p>")
    return "".join(parts)


def page_head(title, extra_css):
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
        '<meta name="viewport" content="width=device-width">\n'
        '<meta name="color-scheme" content="light">\n'
        "<title>%s</title>\n"
        '<link rel="stylesheet" href="debug.css">\n'
        "%s"
        "</head>\n"
    ) % (escape(title), extra_css)


def font_face(family, urls):
    """urls is a list of (href, format or None). The bare TTF src comes first."""
    lines = [
        "<style>",
        "@font-face {",
        '  font-family: "%s";' % family,
        "  font-style: normal;",
        "  font-weight: normal;",
    ]
    bare = urls[0][0]
    lines.append('  src: url("%s");' % bare)
    hinted = []
    for href, fmt in urls:
        if fmt:
            hinted.append('url("%s") format("%s")' % (href, fmt))
    if not hinted:
        hinted.append('url("%s") format("truetype")' % bare)
    lines.append("  src: %s;" % ",\n       ".join(hinted))
    lines.append("}")
    return "\n".join(lines)


def sample_rule(family, fallbacks):
    stack = ", ".join(['"%s"' % family] + fallbacks)
    return (
        ".sample {\n"
        "  font-family: %s;\n"
        "  font-weight: normal;\n"
        "}\n"
        "</style>\n"
    ) % stack


def unicode_css(kind):
    if kind == "noto":
        css = font_face(
            "Noto Sans Bengali",
            [
                ("../fonts/NotoSansBengali-Regular.ttf", None),
                ("../fonts/NotoSansBengali-Regular.woff", "woff"),
                ("../fonts/NotoSansBengali-Regular.ttf", "truetype"),
            ],
        )
        css += "\n" + sample_rule(
            "Noto Sans Bengali",
            ['"Nirmala UI"', '"Vrinda"', '"Bangla MN"', '"Kohinoor Bangla"', "sans-serif"],
        )
        return css
    if kind == "lohit":
        family, href = "Lohit Bengali", "fonts/Lohit-Bengali.ttf"
    elif kind == "hind":
        family, href = "Hind Siliguri", "fonts/HindSiliguri-Regular.ttf"
    elif kind == "baloo":
        family, href = "Baloo Da 2", "fonts/BalooDa2-Regular.ttf"
    else:
        raise SystemExit(kind)
    css = font_face(family, [(href, None), (href, "truetype")])
    css += "\n" + sample_rule(family, ["sans-serif"])
    return css


def preshape_css(family, href):
    css = font_face(family, [(href, None), (href, "truetype")])
    css += "\n" + sample_rule(family, ["sans-serif"])
    return css


def test_page(title, label, body_html):
    return (
        page_head(title, "")
        + "<body>\n"
        + '<p class="nav"><a href="index.html">All tests</a></p>\n'
        + "<h1>%s</h1>\n" % escape(title)
        + '<p class="label">%s</p>\n' % escape(label)
        + body_html
        + '<p class="nav"><a href="index.html">All tests</a></p>\n'
        + "</body>\n</html>\n"
    )


def sample_block(lines, hard_line, lang):
    hard_label = (
        "Hard cases. A lone chandrabindu or anusvara has no consonant, "
        "so it sits on a dotted circle."
    )
    return (
        sample_paragraph(lines, lang)
        + "\n"
        + '<p class="label">%s</p>\n' % hard_label
        + sample_paragraph([hard_line], lang)
        + "\n"
    )


def index_page():
    items = []
    for filename, title, _label, _kind in TESTS:
        items.append('<li><a href="%s">%s</a></li>' % (filename, escape(title)))
    body = (
        "<h1>Debug</h1>\n"
        "<p>Shaping tests for the Kindle browser. These pages are not part of the book. "
        "Open a test and photograph the screen. The English title at the top names the test.</p>\n"
        "<p>Every test shows the same words: the first stanza of Khai Khai, then one line of hard cases.</p>\n"
        '<ul class="menu">\n%s\n</ul>\n' % "\n".join(items)
        + "<h2>This browser</h2>\n"
        + "<p>The line below is filled in by JavaScript when the browser runs it. "
        "The test links work with JavaScript off.</p>\n"
        + '<p id="device-ua">User agent: (not available, JavaScript is off)</p>\n'
        + DEVICE_SCRIPT
        + "<noscript><p>JavaScript is off. The user agent stays hidden, and the tests above still open.</p></noscript>\n"
    )
    return page_head("Debug", "") + "<body>\n" + body + "</body>\n</html>\n"


def write_font_readme():
    text = """\
Debug fonts
===========

These files are only for the pages in debug/. The poems keep using
fonts/NotoSansBengali-Regular.ttf.

Lohit-Bengali.ttf
  Lohit Bengali, version 2.91.5.
  Copyright 2011-15 Lohit Fonts Project contributors.
  License: SIL Open Font License 1.1. See OFL-Lohit-Bengali.txt.
  Unmodified. No Reserved Font Name is declared in that license.
  Source package: fonts-lohit-beng-bengali 2.91.5 (upstream OFL build).

HindSiliguri-Regular.ttf
  Hind Siliguri Regular, version 1.001.
  Copyright (c) 2015 Indian Type Foundry (info@indiantypefoundry.com).
  License: SIL Open Font License 1.1. See OFL-Hind-Siliguri.txt.
  Unmodified. No Reserved Font Name is declared in that license.
  Source: https://github.com/google/fonts/tree/main/ofl/hindsiliguri

BalooDa2-Regular.ttf
  Baloo Da 2 Regular, version 1.700.
  Copyright 2019 The Baloo 2 Project Authors (https://github.com/EkType/Baloo2).
  License: SIL Open Font License 1.1. See OFL-Baloo-Da-2.txt.
  No Reserved Font Name is declared.
  The file published upstream is the variable font BalooDa2[wght].ttf
  (weight axis 400 to 800, default 400). This copy is a static TrueType
  instance at weight 400, made with fontTools.varLib.instancer, and the
  STAT table was removed so an old WebKit reader sees a plain TTF.
  Outlines and the Bengali GSUB/GPOS tables are that Regular instance.

AmoyPreshapeCluster.ttf
AmoyPreshapeGlyph.ttf
  Modified versions of Noto Sans Bengali Regular 2.001
  (Copyright 2017 Google Inc.), built by tools/preshape.py.
  License: SIL Open Font License 1.1. See OFL-Amoy-Preshape.txt
  and ../../fonts/OFL.txt.
  The family names are "Amoy Preshape Cluster" and "Amoy Preshape Glyph".
  They are not named Noto. Noto is a trademark of Google Inc.
  GSUB and GPOS are removed. Private Use Area characters point at
  composite glyphs whose positions were baked in with HarfBuzz.
  Cluster mode is one character per syllable. Glyph mode is one
  character per shaped glyph, in visual order.
"""
    (FONTS / "README.txt").write_text(text, encoding="utf-8")
    ofl = (ROOT / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    notice = (
        "Amoy Preshape Cluster and Amoy Preshape Glyph\n"
        "Copyright 2017 Google Inc. All Rights Reserved.\n"
        "\n"
        "Modified version of Noto Sans Bengali Regular 2.001.\n"
        "The modification bakes HarfBuzz glyph positions into composite\n"
        "glyphs and removes GSUB and GPOS. Built by tools/preshape.py.\n"
        "Family names do not use the name Noto.\n"
        "\n"
        "This Font Software is licensed under the SIL Open Font License,\n"
        "Version 1.1. The license is copied below.\n"
        "\n"
    )
    (FONTS / "OFL-Amoy-Preshape.txt").write_text(notice + ofl, encoding="utf-8")


def check_pages():
    html_paths = [DEBUG / "index.html"] + [DEBUG / name for name, _t, _l, _k in TESTS]
    bad_js = re.compile(r"\b(let|const)\b|=>|`")
    link_re = re.compile(r'(?:href|src)="([^"]+)"')
    url_re = re.compile(r'url\("([^"]+)"\)')
    for path in html_paths:
        text = path.read_text(encoding="utf-8")
        head = text[:1024]
        if '<meta charset="utf-8">' not in head or "charset=utf-8" not in head:
            raise SystemExit("%s is missing a charset meta in the first kilobyte" % path.name)
        for token in ("display:flex", "display: flex", "display:grid", "display: grid", "var(--"):
            if token in text:
                raise SystemExit("%s uses %s" % (path.name, token))
        for target in link_re.findall(text) + url_re.findall(text):
            if target.startswith("/") or target.startswith("http:") or target.startswith("https:"):
                raise SystemExit("%s has a non-relative URL %s" % (path.name, target))
        if bad_js.search(text):
            raise SystemExit("%s has JavaScript newer than ES3" % path.name)
        if "navigator.userAgent" in text and path.name != "index.html":
            raise SystemExit("user-agent script leaked into %s" % path.name)
    index = (DEBUG / "index.html").read_text(encoding="utf-8")
    if "navigator.userAgent" not in index:
        raise SystemExit("index is missing the user-agent script")
    if 'id="device-ua"' not in index:
        raise SystemExit("index is missing the noscript-safe user-agent element")


def main():
    check_hard_line()
    for path in (
        NOTO,
        FONTS / "Lohit-Bengali.ttf",
        FONTS / "HindSiliguri-Regular.ttf",
        FONTS / "BalooDa2-Regular.ttf",
    ):
        if not path.is_file():
            raise SystemExit("missing font %s" % path)
    lines = extract_stanza()
    paragraphs = [lines, [HARD]]
    sample = "\n".join(lines) + "\n\n" + HARD + "\n"
    (DEBUG / "sample.txt").write_text(sample, encoding="utf-8")
    (DEBUG / "debug.css").write_text(DEBUG_CSS, encoding="utf-8")

    cluster = preshape.convert_paragraphs(
        NOTO,
        paragraphs,
        "cluster",
        FONTS / "AmoyPreshapeCluster.ttf",
        "Amoy Preshape Cluster",
    )
    glyph = preshape.convert_paragraphs(
        NOTO,
        paragraphs,
        "glyph",
        FONTS / "AmoyPreshapeGlyph.ttf",
        "Amoy Preshape Glyph",
    )
    for result in (cluster, glyph):
        for warning in result.warnings:
            sys.stderr.write("warning: %s\n" % warning)
        if result.warnings:
            raise SystemExit("preshape reported warnings")
        sys.stdout.write(
            "%s: %s private-use glyphs\n" % (result.family, result.pua_count)
        )

    # FreeType, no shaper, no hinting, compared with the HarfBuzz reference.
    reference = preshape.render_shaped_image(NOTO, paragraphs, 36, pad=18)
    plain = preshape.render_unshaped_image(
        cluster.font_path, cluster.paragraphs, 36, pad=18
    )
    stats = preshape.diff_stats(plain, reference)
    sys.stdout.write(
        "cluster check mean_abs=%.4f frac_gt_40=%.5f\n"
        % (stats["mean_abs"], stats["frac_gt_40"])
    )
    # Edge pixels differ where a composite overlaps a base. A real miss
    # (vowel on the wrong side, a visible hasant) moves a much larger share.
    if stats["frac_gt_40"] > 0.04 or stats["mean_abs"] > 8:
        raise SystemExit("cluster font does not match HarfBuzz when the shaper is off")
    glyph_plain = preshape.render_unshaped_image(
        glyph.font_path, glyph.paragraphs, 36, pad=18
    )
    glyph_stats = preshape.diff_stats(glyph_plain, reference)
    sys.stdout.write(
        "glyph check mean_abs=%.4f frac_gt_40=%.5f\n"
        % (glyph_stats["mean_abs"], glyph_stats["frac_gt_40"])
    )
    if glyph_stats["frac_gt_40"] > 0.04 or glyph_stats["mean_abs"] > 8:
        raise SystemExit("glyph font does not match HarfBuzz when the shaper is off")

    preshape.side_by_side(
        plain,
        reference,
        "Test 5. Clusters, FreeType, no shaper",
        "Test 7. HarfBuzz and Noto reference",
        ARTIFACT,
    )

    widest, upem = preshape.max_line_advance(NOTO, paragraphs)
    # Fit the longest line on a Kindle Touch screen, about 600px wide.
    image_px = 30
    while image_px < 48 and (widest * (image_px + 1) / float(upem)) <= 540:
        image_px += 1
    sys.stdout.write("picture font size %s px\n" % image_px)
    # Draw large, then average down so the 1-bit picture keeps thin marks.
    scale = 2
    big = preshape.render_shaped_image(NOTO, paragraphs, image_px * scale, pad=12 * scale)
    from PIL import Image

    small = big.resize((big.size[0] // scale, big.size[1] // scale), Image.Resampling.BOX)
    bilevel = preshape.to_bilevel(small, 150)
    bilevel.save(DEBUG / "sample.png", format="PNG", optimize=True)
    sys.stdout.write("sample.png %sx%s\n" % (bilevel.size[0], bilevel.size[1]))

    for filename, title, label, kind in TESTS:
        if kind in ("noto", "lohit", "hind", "baloo"):
            css = unicode_css(kind)
            body = sample_block(lines, HARD, "bn")
            html = page_head(title, css) + (
                "<body>\n"
                '<p class="nav"><a href="index.html">All tests</a></p>\n'
                "<h1>%s</h1>\n" % escape(title)
                + '<p class="label">%s</p>\n' % escape(label)
                + body
                + '<p class="nav"><a href="index.html">All tests</a></p>\n'
                "</body>\n</html>\n"
            )
        elif kind == "cluster":
            css = preshape_css("Amoy Preshape Cluster", "fonts/AmoyPreshapeCluster.ttf")
            body = (
                comment(" ".join(lines))
                + "\n"
                + sample_block(cluster.paragraphs[0], cluster.paragraphs[1][0], None)
            )
            html = page_head(title, css) + (
                "<body>\n"
                '<p class="nav"><a href="index.html">All tests</a></p>\n'
                "<h1>%s</h1>\n" % escape(title)
                + '<p class="label">%s</p>\n' % escape(label)
                + body
                + '<p class="nav"><a href="index.html">All tests</a></p>\n'
                "</body>\n</html>\n"
            )
        elif kind == "glyph":
            css = preshape_css("Amoy Preshape Glyph", "fonts/AmoyPreshapeGlyph.ttf")
            body = (
                comment(" ".join(lines))
                + "\n"
                + sample_block(glyph.paragraphs[0], glyph.paragraphs[1][0], None)
            )
            html = page_head(title, css) + (
                "<body>\n"
                '<p class="nav"><a href="index.html">All tests</a></p>\n'
                "<h1>%s</h1>\n" % escape(title)
                + '<p class="label">%s</p>\n' % escape(label)
                + body
                + '<p class="nav"><a href="index.html">All tests</a></p>\n'
                "</body>\n</html>\n"
            )
        elif kind == "image":
            body = (
                '<img class="picture" src="sample.png" '
                'alt="First stanza of Khai Khai, then the hard-case line, '
                'drawn in Noto Sans Bengali">\n'
            )
            html = page_head(title, "") + (
                "<body>\n"
                '<p class="nav"><a href="index.html">All tests</a></p>\n'
                "<h1>%s</h1>\n" % escape(title)
                + '<p class="label">%s</p>\n' % escape(label)
                + '<p class="label">Hard cases are the last line of the picture. '
                "A lone chandrabindu or anusvara has no consonant, so it sits on a dotted circle.</p>\n"
                + body
                + '<p class="nav"><a href="index.html">All tests</a></p>\n'
                "</body>\n</html>\n"
            )
        else:
            raise SystemExit(kind)
        (DEBUG / filename).write_text(html, encoding="utf-8")

    (DEBUG / "index.html").write_text(index_page(), encoding="utf-8")
    write_font_readme()
    check_pages()

    # The visible sample on the pre-shaped pages must not be Bengali Unicode.
    for filename in ("05-preshape-cluster.html", "06-preshape-glyph.html"):
        text = (DEBUG / filename).read_text(encoding="utf-8")
        visible = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        if re.search(r"[\u0980-\u09FF]", visible):
            raise SystemExit("%s still contains Bengali Unicode" % filename)
        if not re.search(r"[\uE000-\uF8FF]", visible):
            raise SystemExit("%s has no Private Use characters" % filename)
    noto = (DEBUG / "01-noto.html").read_text(encoding="utf-8")
    if lines[0] not in noto or HARD not in noto:
        raise SystemExit("test 1 does not contain the Unicode sample")
    sys.stdout.write("debug pages written\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
