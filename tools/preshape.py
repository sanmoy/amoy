#!/usr/bin/env python3
"""Shape text with HarfBuzz and emit a TrueType font that needs no shaper.

Old WebKit (the Kindle Touch experimental browser) will load an embedded
Bengali font and paint glyphs left to right, but it has no Indic shaper.
Pre-base vowels stay after the consonant, o-kar is not split, and conjuncts
keep a visible hasant. This script does the shaping ahead of time.

Each shaped cluster (``--mode cluster``) or each shaped glyph
(``--mode glyph``) becomes one Private Use Area character. GPOS offsets are
baked into a composite glyph. GSUB and GPOS are removed. The page then
contains those PUA characters in visual order, plus real U+0020 spaces so
the browser can still wrap a line.

The pen model matches HarfBuzz. For each glyph, draw at
``(pen_x + x_offset, pen_y + y_offset)``, then add ``(x_advance, y_advance)``
to the pen. A mark with advance 0 and a negative x offset hangs back over
the previous glyph. Cluster mode folds that into one character so a browser
that drops zero-advance glyphs still draws the mark.

Examples:

  python3 tools/preshape.py src/poems/khai-khai.html \\
      --font fonts/NotoSansBengali-Regular.ttf \\
      --mode cluster \\
      --out-font /tmp/AmoyPreshapeCluster.ttf \\
      --out-html /tmp/sample-cluster.html \\
      --font-url AmoyPreshapeCluster.ttf \\
      --check

  python3 tools/preshape.py src/poems/khai-khai.html \\
      --font fonts/NotoSansBengali-Regular.ttf \\
      --mode cluster \\
      --out-font /tmp/khai-khai-preshape.ttf \\
      --out-html /tmp/khai-khai-preshape.html \\
      --font-url khai-khai-preshape.ttf

  python3 tools/preshape.py --site

``--site`` reads every HTML file under ``src/``, shapes all Bengali text
into one cluster font, drops unused glyphs and hinting, and writes
``fonts/AmoyBengali.ttf``, ``fonts/AmoyBengali.woff``, and the served
pages (the ``src/`` prefix stripped). ``<title>`` is left as Unicode.

Text input: UTF-8, one forced line per line, a blank line between paragraphs.
HTML input: tags are kept. ``<br>`` is the line break. A newline in a text
node is HTML source whitespace, not a line break. Bengali text nodes are
replaced with PUA characters. English text is left alone.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

PUA_START = 0xE000
PUA_END = 0xF8FF
BENGALI_RE = re.compile(r"[\u0980-\u09FF]")
DROP_TABLES = ("GSUB", "GPOS", "GDEF", "BASE", "JSTF", "DSIG", "MATH")
OVERLAP_COMPOUND = 0x0400


@dataclass
class ShapedGlyph:
    glyph_name: str
    glyph_id: int
    cluster: int
    x_advance: int
    y_advance: int
    x_offset: int
    y_offset: int


@dataclass(frozen=True)
class GlyphSpec:
    """One output glyph: component origins in font units, plus the advance."""

    components: tuple
    advance: int


@dataclass
class Converted:
    paragraphs: list
    family: str
    mode: str
    pua_count: int
    warnings: list = field(default_factory=list)
    font_path: str = ""


def _require(module_name, pip_name):
    import importlib

    try:
        return importlib.import_module(module_name)
    except ImportError:
        sys.stderr.write(
            "Missing Python package %s. Install tools/requirements.txt "
            "(pip install %s).\n" % (module_name, pip_name)
        )
        raise


def shape_line(hb, hb_font, text):
    """Return HarfBuzz glyphs for one LTR Bengali line, in visual order."""
    buf = hb.Buffer()
    buf.add_str(text)
    buf.direction = "ltr"
    buf.script = "Beng"
    buf.language = "bn"
    buf.cluster_level = hb.BufferClusterLevel.MONOTONE_GRAPHEMES
    hb.shape(hb_font, buf)
    glyphs = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = hb_font.get_glyph_name(info.codepoint)
        glyphs.append(
            ShapedGlyph(
                glyph_name=name,
                glyph_id=info.codepoint,
                cluster=info.cluster,
                x_advance=int(pos.x_advance),
                y_advance=int(pos.y_advance),
                x_offset=int(pos.x_offset),
                y_offset=int(pos.y_offset),
            )
        )
    return glyphs


def group_clusters(glyphs):
    """Group a monotone cluster stream into contiguous runs."""
    groups = []
    current = []
    current_id = None
    for glyph in glyphs:
        if current_id is None or glyph.cluster != current_id:
            if current:
                groups.append(current)
            current = [glyph]
            current_id = glyph.cluster
        else:
            current.append(glyph)
    if current:
        groups.append(current)
    return groups


def placements_for(glyphs):
    """Component origins for a glyph run, plus the run's x advance."""
    pen_x = 0
    pen_y = 0
    parts = []
    for glyph in glyphs:
        parts.append((glyph.glyph_name, pen_x + glyph.x_offset, pen_y + glyph.y_offset))
        pen_x += glyph.x_advance
        pen_y += glyph.y_advance
    return parts, pen_x


def expand_components(glyf, parts):
    """Flatten nested composites so the result is one level of simple glyphs.

    Nested composites (for example ra + nukta) still work on current
    FreeType, but a single level keeps maxComponentDepth at 1 and applies
    the baked offset to every outline piece.
    """
    flat = []

    def walk(name, x, y, depth):
        if depth > 8:
            raise RuntimeError("composite component '%s' is nested too deep" % name)
        glyph = glyf[name]
        if not glyph.isComposite():
            flat.append((name, int(x), int(y)))
            return
        for comp in glyph.components:
            flags = comp.flags
            if flags & (0x0008 | 0x0040 | 0x0080) or getattr(comp, "transform", None):
                raise RuntimeError(
                    "component '%s' uses a scale; preshape.py only bakes x/y offsets"
                    % name
                )
            walk(comp.glyphName, x + comp.x, y + comp.y, depth + 1)

    for name, x, y in parts:
        walk(name, x, y, 0)
    return tuple(flat)


class Preshaper:
    def __init__(self, font_path, mode):
        if mode not in ("cluster", "glyph"):
            raise ValueError("mode must be 'cluster' or 'glyph'")
        hb = _require("uharfbuzz", "uharfbuzz")
        ttlib = _require("fontTools.ttLib", "fonttools")
        self.hb = hb
        self.TTFont = ttlib.TTFont
        self.font_path = str(font_path)
        self.mode = mode
        self.src = self.TTFont(self.font_path, recalcTimestamp=False)
        self.glyf = self.src["glyf"]
        self.glyph_set = self.src.getGlyphSet()
        cmap = self.src.getBestCmap() or {}
        if 0x20 not in cmap:
            raise RuntimeError("source font has no U+0020 space glyph")
        self.space_name = cmap[0x20]
        self.space_advance = self.src["hmtx"].metrics[self.space_name][0]
        blob = hb.Blob.from_file_path(self.font_path)
        face = hb.Face(blob)
        self.hb_font = hb.Font(face)
        self.upem = face.upem
        if self.upem != self.src["head"].unitsPerEm:
            raise RuntimeError("HarfBuzz upem does not match the font head table")
        self.hb_font.scale = (self.upem, self.upem)
        self.specs = {}
        self.order = []
        self.warnings = []
        self._seen_space_advances = set()

    def _warn_glyphs(self, text, glyphs):
        for glyph in glyphs:
            if glyph.glyph_id == 0 or glyph.glyph_name in (".notdef", ".null"):
                self.warnings.append(
                    "missing glyph while shaping %r (got %s)"
                    % (text, glyph.glyph_name)
                )
            if glyph.y_advance:
                self.warnings.append(
                    "non-zero y_advance on %s in %r; horizontal browsers ignore it"
                    % (glyph.glyph_name, text)
                )
            if glyph.glyph_name not in self.glyf:
                raise RuntimeError(
                    "HarfBuzz glyph name %s is not in the font" % glyph.glyph_name
                )

    def _intern(self, parts, advance):
        flat = expand_components(self.glyf, parts)
        if not flat:
            raise RuntimeError("shaped cluster produced no components")
        for _name, x, y in flat:
            if not (-32768 <= int(x) <= 32767 and -32768 <= int(y) <= 32767):
                raise RuntimeError("component offset does not fit in a signed 16-bit glyf argument")
        if not (0 <= int(advance) <= 65535):
            raise RuntimeError("advance %s does not fit in hmtx" % advance)
        spec = GlyphSpec(flat, int(advance))
        if spec not in self.specs:
            if PUA_START + len(self.order) > PUA_END:
                raise RuntimeError("ran out of Private Use Area codepoints")
            self.specs[spec] = len(self.order)
            self.order.append(spec)
        return chr(PUA_START + self.specs[spec])

    def _is_plain_space(self, glyph):
        return (
            glyph.glyph_name == self.space_name
            and glyph.x_offset == 0
            and glyph.y_offset == 0
            and glyph.y_advance == 0
        )

    def convert_line(self, text):
        if text == "":
            return ""
        glyphs = shape_line(self.hb, self.hb_font, text)
        self._warn_glyphs(text, glyphs)
        out = []
        if self.mode == "glyph":
            runs = [[glyph] for glyph in glyphs]
        else:
            runs = group_clusters(glyphs)
        for run in runs:
            if (
                len(run) >= 2
                and self._is_plain_space(run[0])
            ):
                # A combining mark after a space is one cluster. Keep the
                # space as U+0020 so the line can wrap, and bake the mark
                # into the following character.
                self._seen_space_advances.add(run[0].x_advance)
                out.append(" ")
                run = run[1:]
            if len(run) == 1 and self._is_plain_space(run[0]):
                self._seen_space_advances.add(run[0].x_advance)
                out.append(" ")
                continue
            parts, advance = placements_for(run)
            out.append(self._intern(parts, advance))
        return "".join(out)

    def convert_paragraphs(self, paragraphs):
        converted = []
        for paragraph in paragraphs:
            converted.append([self.convert_line(line) for line in paragraph])
        return converted

    def save_font(self, out_path, family, subset=False, woff_path=None):
        from fontTools.pens.ttGlyphPen import TTGlyphPen

        font = self.src
        glyf = self.glyf
        pen_set = self.glyph_set
        names = []
        built = []
        max_components = 0
        max_points = 0
        max_contours = 0
        for index, spec in enumerate(self.order):
            glyph_name = "preshape%04d" % index
            names.append(glyph_name)
            pen = TTGlyphPen(pen_set)
            for comp_name, x, y in spec.components:
                pen.addComponent(comp_name, (1, 0, 0, 1, x, y))
            # No ROUND_XY_TO_GRID: offsets must survive an unhinted draw.
            glyph = pen.glyph(componentFlags=0)
            if not glyph.isComposite() or len(glyph.components) != len(spec.components):
                raise RuntimeError(
                    "failed to build composite %s (%s components)"
                    % (glyph_name, len(spec.components))
                )
            glyph.components[0].flags |= OVERLAP_COMPOUND
            glyph.recalcBounds(glyf)
            points, contours = _component_stats(glyf, spec.components)
            max_components = max(max_components, len(spec.components))
            max_points = max(max_points, points)
            max_contours = max(max_contours, contours)
            lsb = int(glyph.xMin)
            built.append((glyph_name, glyph, spec.advance, lsb))

        glyph_order = list(font.getGlyphOrder())
        for glyph_name, glyph, _advance, _lsb in built:
            glyph_order.append(glyph_name)
            glyf[glyph_name] = glyph
            font["hmtx"].metrics[glyph_name] = (_advance, _lsb)
        font.setGlyphOrder(glyph_order)

        mapping = {0x20: self.space_name}
        for index, glyph_name in enumerate(names):
            mapping[PUA_START + index] = glyph_name
        _set_bmp_cmap(font, mapping)

        maxp = font["maxp"]
        maxp.numGlyphs = len(glyph_order)
        maxp.maxComponentElements = max(maxp.maxComponentElements, max_components)
        maxp.maxCompositePoints = max(maxp.maxCompositePoints, max_points)
        maxp.maxCompositeContours = max(maxp.maxCompositeContours, max_contours)
        maxp.maxComponentDepth = max(maxp.maxComponentDepth, 1)
        font["hhea"].numberOfHMetrics = len(glyph_order)
        font["head"].indexToLocFormat = 1

        os2 = font["OS/2"]
        os2.usFirstCharIndex = min(mapping)
        os2.usLastCharIndex = max(mapping)
        os2.ulUnicodeRange1 |= (1 << 31) | (1 << 0)
        os2.achVendID = "AMOY"

        family = family or _default_family(self.mode)
        ps_name = "".join(ch for ch in family if ch.isalnum()) or "AmoyPreshape"
        full = family + " Regular"
        copyright = (
            "Copyright 2017 Google Inc. All Rights Reserved. "
            "Modified version of Noto Sans Bengali Regular 2.001. "
            "HarfBuzz positions are baked into composite glyphs so the font "
            "needs no GSUB or GPOS. "
            "Licensed under the SIL Open Font License, Version 1.1."
        )
        _replace_names(
            font,
            {
                0: copyright,
                1: family,
                2: "Regular",
                3: full + " 1.000",
                4: full,
                5: "Version 1.000",
                6: ps_name,
                13: "Licensed under the SIL Open Font License, Version 1.1.",
                14: "https://scripts.sil.org/OFL",
            },
        )
        # Fixed timestamps so two runs of the same input match byte for byte.
        font["head"].created = 3456000000
        font["head"].modified = 3456000000
        font["head"].fontRevision = 1.0
        font.recalcTimestamp = False

        for tag in DROP_TABLES:
            if tag in font:
                del font[tag]

        if subset:
            _subset_used_unicodes(font)
            font["head"].created = 3456000000
            font["head"].modified = 3456000000
            font.recalcTimestamp = False

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        font.save(str(out_path))
        _sanity_check_font(self.TTFont, out_path, mapping if not subset else None, self.mode)
        if woff_path:
            _write_woff(self.TTFont, out_path, woff_path)
        return str(out_path)


def _component_stats(glyf, components):
    points = 0
    contours = 0
    seen = set()

    def walk(name):
        nonlocal points, contours
        if name in seen:
            return
        seen.add(name)
        glyph = glyf[name]
        if glyph.isComposite():
            for comp in glyph.components:
                walk(comp.glyphName)
            return
        if glyph.numberOfContours > 0:
            coords, _ends, _flags = glyph.getCoordinates(glyf)
            points += len(coords)
            contours += glyph.numberOfContours

    for name, _x, _y in components:
        walk(name)
    return points, contours


def _set_bmp_cmap(font, mapping):
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

    tables = []
    for platform_id, plat_enc_id in ((3, 1), (0, 3)):
        sub = CmapSubtable.newSubtable(4)
        sub.platformID = platform_id
        sub.platEncID = plat_enc_id
        sub.language = 0
        sub.cmap = dict(mapping)
        tables.append(sub)
    font["cmap"].tables = tables


def _replace_names(font, names):
    table = font["name"]
    table.names = []
    for name_id, value in names.items():
        table.setName(value, name_id, 3, 1, 0x409)
        table.setName(value, name_id, 1, 0, 0)


def _default_family(mode):
    if mode == "cluster":
        return "Amoy Preshape Cluster"
    return "Amoy Preshape Glyph"


def _subset_used_unicodes(font):
    """Keep only cmap codepoints and the glyphs they use. Drop hinting.

    This is ``pyftsubset --unicodes='*' --no-hinting``. The Kindle font
    otherwise still carries every Noto outline.
    """
    from fontTools.subset import Options, Subsetter

    options = Options()
    options.hinting = False
    unicodes = list(font.getBestCmap().keys())
    subsetter = Subsetter(options=options)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)


def _write_woff(ttfont_cls, ttf_path, woff_path):
    font = ttfont_cls(str(ttf_path), recalcTimestamp=False)
    font.flavor = "woff"
    font["head"].created = 3456000000
    font["head"].modified = 3456000000
    Path(woff_path).parent.mkdir(parents=True, exist_ok=True)
    font.save(str(woff_path))


def _sanity_check_font(ttfont_cls, path, mapping, mode):
    font = ttfont_cls(str(path))
    for tag in ("GSUB", "GPOS", "GDEF"):
        if tag in font:
            raise RuntimeError("preshape font still has a %s table" % tag)
    cmap = font.getBestCmap()
    if mapping is not None and cmap != mapping:
        raise RuntimeError("saved cmap does not match the PUA map")
    if mapping is None:
        if not cmap or 0x20 not in cmap:
            raise RuntimeError("subset font lost the space glyph")
        if not any(code >= PUA_START for code in cmap):
            raise RuntimeError("subset font has no Private Use characters")
    for sub in font["cmap"].tables:
        if sub.format != 4:
            raise RuntimeError("cmap is not format 4; old WebKit may ignore it")
    order = font.getGlyphOrder()
    if len(order) != font["maxp"].numGlyphs:
        raise RuntimeError("maxp.numGlyphs does not match the glyph order")
    if len(order) != font["hhea"].numberOfHMetrics:
        raise RuntimeError("hhea.numberOfHMetrics does not cover every glyph")
    if mode not in ("cluster", "glyph"):
        raise RuntimeError(mode)


def read_paragraphs(path):
    """Read a UTF-8 text file. A blank line separates paragraphs."""
    text = Path(path).read_text(encoding="utf-8")
    if text.startswith("\ufeff"):
        text = text[1:]
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = []
    current = []
    for line in text.split("\n"):
        if line.strip() == "":
            if current:
                paragraphs.append(current)
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(current)
    if not paragraphs:
        raise RuntimeError("input text is empty: %s" % path)
    return paragraphs


def convert_paragraphs(font_path, paragraphs, mode, out_font, family=None):
    shaper = Preshaper(font_path, mode)
    converted = shaper.convert_paragraphs(paragraphs)
    family = family or _default_family(mode)
    saved = shaper.save_font(out_font, family)
    if shaper._seen_space_advances and shaper._seen_space_advances != {shaper.space_advance}:
        shaper.warnings.append(
            "shaped space advances %s differ from the font space advance %s"
            % (sorted(shaper._seen_space_advances), shaper.space_advance)
        )
    return Converted(
        paragraphs=converted,
        family=family,
        mode=mode,
        pua_count=len(shaper.order),
        warnings=shaper.warnings,
        font_path=saved,
    )


def _needs_shape(data):
    return BENGALI_RE.search(data) is not None


def _html_source_line(data):
    """Drop HTML source newlines. ``<br>`` is the real line break."""
    text = data.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    return text


def _escape_text(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(text):
    return _escape_text(text).replace('"', "&quot;")


class _Rewriter(HTMLParser):
    def __init__(self, convert_line):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.convert_line = convert_line
        self.parts = []
        self.skip = 0
        self.raw_text = 0

    def handle_decl(self, decl):
        self.parts.append("<!%s>" % decl)

    def handle_starttag(self, tag, attrs):
        self.parts.append(self._tag(tag, attrs, False))
        if tag.lower() in ("script", "style"):
            self.skip += 1
        if tag.lower() == "title":
            # The browser chrome does not use the page webfont. Leave the
            # Unicode title so a phone tab can still show the poem name.
            self.raw_text += 1

    def handle_endtag(self, tag):
        if tag.lower() in ("script", "style") and self.skip:
            self.skip -= 1
        if tag.lower() == "title" and self.raw_text:
            self.raw_text -= 1
        self.parts.append("</%s>" % tag)

    def handle_startendtag(self, tag, attrs):
        self.parts.append(self._tag(tag, attrs, True))

    def handle_data(self, data):
        if self.skip or self.raw_text or not _needs_shape(data):
            self.parts.append(_escape_text(data))
            return
        self.parts.append(self.convert_line(_html_source_line(data)))

    def handle_comment(self, data):
        self.parts.append("<!--%s-->" % data)

    def _tag(self, tag, attrs, close):
        chunks = ["<", tag]
        for key, value in attrs:
            if value is None:
                chunks.append(" " + key)
            else:
                chunks.append(' %s="%s"' % (key, _escape_attr(value)))
        chunks.append(" />" if close else ">")
        return "".join(chunks)


def _font_face_css(family, font_url):
    # First src has no format() hint: old WebKit that rejects format() uses it.
    return (
        "@font-face {\n"
        "  font-family: \"%s\";\n"
        "  font-style: normal;\n"
        "  font-weight: normal;\n"
        "  src: url(\"%s\");\n"
        "  src: url(\"%s\") format(\"truetype\");\n"
        "}\n"
        ".bn, .preshape, .sample {\n"
        "  font-family: \"%s\", sans-serif;\n"
        "  font-weight: normal;\n"
        "}\n"
    ) % (family, font_url, font_url, family)


def rewrite_html(html, convert_line, family=None, font_url=None, inject_style=True):
    parser = _Rewriter(convert_line)
    parser.feed(html)
    parser.close()
    text = "".join(parser.parts)
    if inject_style:
        if not family or not font_url:
            raise RuntimeError("inject_style needs a family and a font URL")
        style = "<style>\n%s</style>\n" % _font_face_css(family, font_url)
        if "</head>" in text:
            text = text.replace("</head>", style + "</head>", 1)
        else:
            text = style + text
    return text


def _section_slugs(index_html):
    """Slugs in the order of the section list. Skips the Home link."""
    slugs = []
    for href in re.findall(r'href="([^"]+)"', index_html):
        if href.endswith(".html") and "/" not in href:
            slugs.append(href[:-5])
    return slugs


def _section_bar(label, prev_slug, next_slug):
    """Same Previous / Next words and pager table as the figure pages.
    The first item has no Previous and the last has no Next. The list
    link stays in the middle cell."""
    def cell(slug, word):
        if not slug:
            return "<td></td>"
        return '<td><a lang="en" href="%s.html">%s</a></td>' % (slug, word)
    return (
        '<table class="pager section-pager">\n<tr>\n%s\n'
        '<td><a lang="en" href="index.html">%s</a></td>\n%s\n'
        "</tr>\n</table>"
    ) % (cell(prev_slug, "Previous"), label, cell(next_slug, "Next"))


_SECTION_NAV = re.compile(
    r'<p class="nav"><a lang="en" href="index.html">(Poems|Songs)</a></p>'
)


def _add_section_pagers(html, rel, orders):
    """Replace the back-link bars on a poem or song page. Index pages
    and figure pages are left alone."""
    if rel.parts[0] not in ("poems", "songs") or rel.name == "index.html":
        return html
    slugs = orders[rel.parts[0]]
    slug = rel.stem
    if slug not in slugs:
        raise SystemExit("%s is not in src/%s/index.html" % (rel.as_posix(), rel.parts[0]))
    index = slugs.index(slug)
    label = "Poems" if rel.parts[0] == "poems" else "Songs"
    prev_slug = slugs[index - 1] if index else None
    next_slug = slugs[index + 1] if index + 1 < len(slugs) else None
    bar = _section_bar(label, prev_slug, next_slug)
    converted, count = _SECTION_NAV.subn(bar, html)
    if count != 2:
        raise SystemExit("%s should have two list links, found %s" % (rel.as_posix(), count))
    return converted


def build_site(root=None):
    """Build fonts/AmoyBengali from every HTML file under src/ and write the served pages."""
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    src_root = root / "src"
    sources = sorted(path for path in src_root.rglob("*.html") if path.is_file())
    if not sources:
        raise SystemExit("no HTML files under %s" % src_root)
    noto = root / "fonts" / "NotoSansBengali-Regular.ttf"
    if not noto.is_file():
        raise SystemExit("missing shaping source %s" % noto)

    orders = {}
    for section in ("poems", "songs"):
        index_path = src_root / section / "index.html"
        orders[section] = _section_slugs(index_path.read_text(encoding="utf-8"))

    shaper = Preshaper(str(noto), "cluster")
    unicode_lines = []
    pua_lines = []

    def convert_line(text):
        unicode_lines.append(text)
        shaped = shaper.convert_line(text)
        pua_lines.append(shaped)
        return shaped

    pages = []
    for src in sources:
        rel = src.relative_to(src_root)
        html = src.read_text(encoding="utf-8")
        converted = rewrite_html(html, convert_line, inject_style=False)
        # After the charset metas, not before the doctype. A comment in
        # front of the doctype can push an old WebKit into quirks mode.
        banner = (
            "<!-- Generated from src/%s. Edit that file, then run python3 tools/preshape.py --site. -->\n"
            % rel.as_posix()
        )
        marker = '<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
        if marker in converted:
            converted = converted.replace(marker, marker + banner, 1)
        else:
            converted = banner + converted
        converted = _add_section_pagers(converted, rel, orders)
        pages.append((root / rel, converted))

    if shaper.warnings:
        for warning in shaper.warnings:
            sys.stderr.write("warning: %s\n" % warning)
        raise SystemExit("site build stopped because shaping reported a missing glyph")

    out_ttf = root / "fonts" / "AmoyBengali.ttf"
    out_woff = root / "fonts" / "AmoyBengali.woff"
    shaper.save_font(out_ttf, "Amoy Bengali", subset=True, woff_path=out_woff)

    reference = render_shaped_image(str(noto), [unicode_lines], 32, pad=12)
    plain = render_unshaped_image(str(out_ttf), [pua_lines], 32, pad=12)
    stats = diff_stats(plain, reference)
    sys.stdout.write(
        "site check mean_abs=%.4f frac_gt_40=%.5f clusters=%s glyphs=%s\n"
        % (
            stats["mean_abs"],
            stats["frac_gt_40"],
            len(shaper.order),
            _require("fontTools.ttLib", "fonttools").TTFont(str(out_ttf))["maxp"].numGlyphs,
        )
    )
    if stats["frac_gt_40"] > 0.04 or stats["mean_abs"] > 8:
        raise SystemExit("subset font does not match HarfBuzz when the shaper is off")
    _assert_shaper_passthrough(out_ttf, pua_lines)

    for path, html in pages:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        visible = re.sub(r"<title>.*?</title>", "", html, flags=re.S)
        visible = re.sub(r"<!--.*?-->", "", visible, flags=re.S)
        if BENGALI_RE.search(visible):
            raise SystemExit("Bengali Unicode left in the body of %s" % path)
    sys.stdout.write(
        "wrote %s (%s bytes) and %s (%s bytes), %s clusters, %s pages\n"
        % (
            out_ttf,
            out_ttf.stat().st_size,
            out_woff,
            out_woff.stat().st_size,
            len(shaper.order),
            len(pages),
        )
    )
    return 0


def _assert_shaper_passthrough(font_path, lines):
    """A real shaper must not reorder Private Use text or apply GPOS."""
    hb = _require("uharfbuzz", "uharfbuzz")
    tt = _require("fontTools.ttLib", "fonttools").TTFont(str(font_path))
    cmap = tt.getBestCmap()
    order = tt.getGlyphOrder()
    nominal = {}
    for code, name in cmap.items():
        nominal[code] = order.index(name)
    blob = hb.Blob.from_file_path(str(font_path))
    face = hb.Face(blob)
    font = hb.Font(face)
    font.scale = (face.upem, face.upem)
    for line in lines:
        if not line:
            continue
        buf = hb.Buffer()
        buf.add_str(line)
        buf.direction = "ltr"
        buf.script = "Beng"
        buf.language = "bn"
        hb.shape(font, buf)
        if len(buf.glyph_infos) != len(line):
            raise RuntimeError("shaper changed the length of a PUA line")
        for ch, info, pos in zip(line, buf.glyph_infos, buf.glyph_positions):
            expected = nominal.get(ord(ch))
            if info.codepoint != expected or pos.x_offset or pos.y_offset:
                raise RuntimeError(
                    "shaper moved U+%04X (glyph %s, expected %s, offset %s,%s)"
                    % (ord(ch), info.codepoint, expected, pos.x_offset, pos.y_offset)
                )


def simple_html_page(paragraphs, family, font_url, title, label):
    """A Kindle-safe page for converted plain text."""
    title = title or family
    body = []
    if label:
        body.append("<p class=\"label\">%s</p>" % _escape_text(label))
    body.append("<h1>%s</h1>" % _escape_text(title))
    for paragraph in paragraphs:
        body.append("<p class=\"sample preshape\">")
        for index, line in enumerate(paragraph):
            if index:
                body.append("<br\n>")
            body.append(line)
        body.append("</p>\n")
    css = (
        "html { background: #ffffff; color: #000000; }\n"
        "body {\n"
        "  margin: 16px;\n"
        "  background: #ffffff;\n"
        "  color: #000000;\n"
        "  font-family: sans-serif;\n"
        "  font-size: 28px;\n"
        "  font-weight: normal;\n"
        "  line-height: 1.45;\n"
        "}\n"
        "h1 { font-size: 36px; font-weight: normal; margin: 0 0 12px 0; }\n"
        ".label { font-family: sans-serif; font-size: 26px; }\n"
        ".sample { font-size: 40px; font-weight: normal; line-height: 1.85; }\n"
        + _font_face_css(family, font_url)
    )
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta http-equiv=\"Content-Type\" content=\"text/html; charset=utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width\">\n"
        "<meta name=\"color-scheme\" content=\"light\">\n"
        "<title>%s</title>\n"
        "<style>\n%s</style>\n"
        "</head>\n"
        "<body>\n%s</body>\n"
        "</html>\n"
    ) % (_escape_text(title), css, "".join(body))


def _load_flags(freetype):
    return (
        freetype.FT_LOAD_RENDER
        | freetype.FT_LOAD_NO_HINTING
        | freetype.FT_LOAD_NO_AUTOHINT
        | freetype.FT_LOAD_NO_BITMAP
    )


def _blit(pixels, width, height, bitmap, dest_x, dest_y):
    if bitmap.pixel_mode != 2:
        raise RuntimeError("expected a FreeType gray bitmap, got mode %s" % bitmap.pixel_mode)
    pitch = bitmap.pitch
    buf = bitmap.buffer
    for row in range(bitmap.rows):
        y = dest_y + row
        if y < 0 or y >= height:
            continue
        row_off = row * pitch
        for col in range(bitmap.width):
            x = dest_x + col
            if x < 0 or x >= width:
                continue
            cov = buf[row_off + col]
            if not cov:
                continue
            index = y * width + x
            pixels[index] = pixels[index] * (255 - cov) // 255


def _new_canvas(width, height):
    return bytearray([255]) * (width * height)


def max_line_advance(font_path, paragraphs):
    """Widest line in font units, and the font's units per em."""
    hb = _require("uharfbuzz", "uharfbuzz")
    tt = _require("fontTools.ttLib", "fonttools").TTFont(str(font_path))
    upem = tt["head"].unitsPerEm
    blob = hb.Blob.from_file_path(str(font_path))
    face = hb.Face(blob)
    hb_font = hb.Font(face)
    hb_font.scale = (upem, upem)
    widest = 0
    for paragraph in paragraphs:
        for line in paragraph:
            glyphs = shape_line(hb, hb_font, line)
            widest = max(widest, sum(glyph.x_advance for glyph in glyphs))
    return widest, upem


def render_shaped_image(font_path, paragraphs, px, pad=24):
    """Reference picture: HarfBuzz positions, FreeType draw, no hinting."""
    hb = _require("uharfbuzz", "uharfbuzz")
    freetype = _require("freetype", "freetype-py")
    tt = _require("fontTools.ttLib", "fonttools").TTFont(str(font_path))
    upem = tt["head"].unitsPerEm
    ascent = tt["hhea"].ascent
    descent = -tt["hhea"].descent
    scale = px / float(upem)
    step = int(round((ascent + descent) * scale + px * 0.28))
    gap = int(round(px * 0.55))

    blob = hb.Blob.from_file_path(str(font_path))
    face_hb = hb.Face(blob)
    hb_font = hb.Font(face_hb)
    hb_font.scale = (upem, upem)
    face = freetype.Face(str(font_path))
    face.set_pixel_sizes(0, px)
    flags = _load_flags(freetype)

    line_runs = []
    max_width = 1
    for paragraph in paragraphs:
        for line in paragraph:
            glyphs = shape_line(hb, hb_font, line)
            width = sum(g.x_advance for g in glyphs) * scale
            max_width = max(max_width, int(round(width)))
            line_runs.append(glyphs)
        line_runs.append(None)
    if line_runs and line_runs[-1] is None:
        line_runs.pop()

    line_count = sum(1 for item in line_runs if item is not None)
    blanks = sum(1 for item in line_runs if item is None)
    width = max_width + pad * 2
    height = pad * 2 + line_count * step + blanks * gap
    pixels = _new_canvas(width, height)
    y = pad + int(round(ascent * scale))
    for glyphs in line_runs:
        if glyphs is None:
            y += gap
            continue
        pen = float(pad)
        for glyph in glyphs:
            face.load_glyph(glyph.glyph_id, flags)
            ft = face.glyph
            draw_x = int(round(pen + glyph.x_offset * scale)) + ft.bitmap_left
            draw_y = int(round(y - glyph.y_offset * scale)) - ft.bitmap_top
            _blit(pixels, width, height, ft.bitmap, draw_x, draw_y)
            pen += glyph.x_advance * scale
        y += step
    Image = _require("PIL.Image", "pillow")
    return Image.frombytes("L", (width, height), bytes(pixels))


def render_unshaped_image(font_path, paragraphs, px, pad=24):
    """Draw PUA text with FreeType cmap lookups only. No HarfBuzz, no GPOS."""
    freetype = _require("freetype", "freetype-py")
    tt = _require("fontTools.ttLib", "fonttools").TTFont(str(font_path))
    upem = tt["head"].unitsPerEm
    ascent = tt["hhea"].ascent
    descent = -tt["hhea"].descent
    hmtx = tt["hmtx"].metrics
    cmap = tt.getBestCmap()
    scale = px / float(upem)
    step = int(round((ascent + descent) * scale + px * 0.28))
    gap = int(round(px * 0.55))

    face = freetype.Face(str(font_path))
    face.set_pixel_sizes(0, px)
    if face.charmap is None or face.charmap.encoding_name != "unicode":
        face.select_charmap(freetype.FT_ENCODING_UNICODE)
    flags = _load_flags(freetype)

    flat = []
    max_width = 1
    for paragraph in paragraphs:
        for line in paragraph:
            width = 0
            for ch in line:
                name = cmap.get(ord(ch))
                if name is None:
                    raise RuntimeError("preshape font has no glyph for U+%04X" % ord(ch))
                width += hmtx[name][0]
            max_width = max(max_width, int(round(width * scale)))
            flat.append(line)
        flat.append(None)
    if flat and flat[-1] is None:
        flat.pop()

    line_count = sum(1 for item in flat if item is not None)
    blanks = sum(1 for item in flat if item is None)
    width = max_width + pad * 2
    height = pad * 2 + line_count * step + blanks * gap
    pixels = _new_canvas(width, height)
    y = pad + int(round(ascent * scale))
    for line in flat:
        if line is None:
            y += gap
            continue
        pen = float(pad)
        for ch in line:
            index = face.get_char_index(ord(ch))
            if index == 0 and ord(ch) != 0:
                raise RuntimeError("FreeType cmap miss for U+%04X" % ord(ch))
            face.load_glyph(index, flags)
            ft = face.glyph
            _blit(pixels, width, height, ft.bitmap, int(round(pen)) + ft.bitmap_left, y - ft.bitmap_top)
            pen += ft.advance.x / 64.0
        y += step
    Image = _require("PIL.Image", "pillow")
    return Image.frombytes("L", (width, height), bytes(pixels))


def render_pil_basic(font_path, paragraphs, px, pad=24):
    """PIL basic layout. This must not be raqm, even if raqm is installed."""
    ImageFont = _require("PIL.ImageFont", "pillow")
    ImageDraw = _require("PIL.ImageDraw", "pillow")
    Image = _require("PIL.Image", "pillow")
    font = ImageFont.truetype(
        str(font_path), px, layout_engine=ImageFont.Layout.BASIC
    )
    tt = _require("fontTools.ttLib", "fonttools").TTFont(str(font_path))
    upem = tt["head"].unitsPerEm
    ascent = tt["hhea"].ascent
    descent = -tt["hhea"].descent
    scale = px / float(upem)
    step = int(round((ascent + descent) * scale + px * 0.28))
    gap = int(round(px * 0.55))
    flat = []
    max_width = 1
    for paragraph in paragraphs:
        for line in paragraph:
            length = font.getlength(line)
            max_width = max(max_width, int(round(length)))
            flat.append(line)
        flat.append(None)
    if flat and flat[-1] is None:
        flat.pop()
    line_count = sum(1 for item in flat if item is not None)
    blanks = sum(1 for item in flat if item is None)
    width = max_width + pad * 2
    height = pad * 2 + line_count * step + blanks * gap
    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)
    y = pad + int(round(ascent * scale))
    for line in flat:
        if line is None:
            y += gap
            continue
        draw.text((pad, y), line, font=font, fill=0, anchor="ls")
        y += step
    return image


def diff_stats(left, right):
    if left.size != right.size:
        width = max(left.size[0], right.size[0])
        height = max(left.size[1], right.size[1])
        Image = _require("PIL.Image", "pillow")
        canvas_l = Image.new("L", (width, height), 255)
        canvas_r = Image.new("L", (width, height), 255)
        canvas_l.paste(left, (0, 0))
        canvas_r.paste(right, (0, 0))
        left, right = canvas_l, canvas_r
    a = left.tobytes()
    b = right.tobytes()
    total = len(a)
    mad = 0
    big = 0
    for x, y in zip(a, b):
        delta = x - y
        if delta < 0:
            delta = -delta
        mad += delta
        if delta > 40:
            big += 1
    return {
        "mean_abs": mad / float(total),
        "frac_gt_40": big / float(total),
        "width": left.size[0],
        "height": left.size[1],
    }


def side_by_side(left, right, left_caption, right_caption, out_path):
    Image = _require("PIL.Image", "pillow")
    ImageDraw = _require("PIL.ImageDraw", "pillow")
    ImageFont = _require("PIL.ImageFont", "pillow")
    label_font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22
    )
    caption_h = 64
    gap = 24
    width = left.size[0] + right.size[0] + gap
    height = caption_h + max(left.size[1], right.size[1])
    image = Image.new("L", (width, height), 255)
    draw = ImageDraw.Draw(image)
    draw.text((8, 8), left_caption, font=label_font, fill=0)
    draw.text((left.size[0] + gap + 8, 8), right_caption, font=label_font, fill=0)
    image.paste(left, (0, caption_h))
    image.paste(right, (left.size[0] + gap, caption_h))
    # A black rule between the two pictures.
    for y in range(caption_h, height):
        image.putpixel((left.size[0] + gap // 2, y), 0)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(out_path), format="PNG", optimize=True)
    return image


def to_bilevel(image, threshold=160):
    """Pure black or white, for e-paper. Light gray fringes become white."""
    return image.point(lambda value: 0 if value < threshold else 255).convert("1")


def main(argv):
    if "--site" in argv:
        root = None
        if "--root" in argv:
            root = argv[argv.index("--root") + 1]
        return build_site(root)

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("input", help="UTF-8 text file, or an HTML file")
    parser.add_argument("--font", required=True, help="source TTF, shaped with HarfBuzz")
    parser.add_argument("--mode", required=True, choices=("cluster", "glyph"))
    parser.add_argument("--out-font", required=True)
    parser.add_argument("--out-html")
    parser.add_argument("--out-text", help="write converted paragraphs as UTF-8 text")
    parser.add_argument("--font-url", help="relative URL of the font from the HTML file")
    parser.add_argument("--family")
    parser.add_argument("--title")
    parser.add_argument("--label")
    parser.add_argument(
        "--check",
        action="store_true",
        help="render the PUA font with FreeType and no shaper, and compare to HarfBuzz",
    )
    parser.add_argument("--check-png", help="side-by-side PNG written when --check is set")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    raw = input_path.read_text(encoding="utf-8")
    is_html = input_path.suffix.lower() in (".html", ".htm") or raw.lstrip().lower().startswith("<!doctype") or raw.lstrip().lower().startswith("<html")
    family = args.family or _default_family(args.mode)

    if is_html:
        if not args.out_html:
            parser.error("HTML input needs --out-html")
        if not args.font_url:
            parser.error("HTML input needs --font-url")
        shaper = Preshaper(args.font, args.mode)

        def convert_line(text):
            return shaper.convert_line(text)

        html_out = rewrite_html(raw, convert_line, family, args.font_url)
        shaper.save_font(args.out_font, family)
        Path(args.out_html).write_text(html_out, encoding="utf-8")
        paragraphs = None
        converted = None
        warnings = shaper.warnings
        pua_count = len(shaper.order)
    else:
        paragraphs = read_paragraphs(input_path)
        converted = convert_paragraphs(
            args.font, paragraphs, args.mode, args.out_font, family
        )
        warnings = converted.warnings
        pua_count = converted.pua_count
        if args.out_text:
            chunks = []
            for paragraph in converted.paragraphs:
                chunks.append("\n".join(paragraph))
            Path(args.out_text).write_text("\n\n".join(chunks) + "\n", encoding="utf-8")
        if args.out_html:
            if not args.font_url:
                parser.error("--out-html needs --font-url")
            page = simple_html_page(
                converted.paragraphs, family, args.font_url, args.title, args.label
            )
            Path(args.out_html).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out_html).write_text(page, encoding="utf-8")

    for warning in warnings:
        sys.stderr.write("warning: %s\n" % warning)
    sys.stdout.write(
        "wrote %s (%s mode, %s PUA glyphs)\n" % (args.out_font, args.mode, pua_count)
    )

    if args.check:
        if is_html:
            parser.error("--check currently compares plain-text input")
        reference = render_shaped_image(args.font, paragraphs, 40)
        plain = render_unshaped_image(args.out_font, converted.paragraphs, 40)
        stats = diff_stats(plain, reference)
        sys.stdout.write(
            "check mean_abs=%.4f frac_gt_40=%.5f size=%sx%s\n"
            % (stats["mean_abs"], stats["frac_gt_40"], stats["width"], stats["height"])
        )
        if args.check_png:
            side_by_side(
                plain,
                reference,
                "Test, FreeType, no shaper",
                "HarfBuzz reference",
                args.check_png,
            )
        # Overlapping marks (u-kar, reph) disagree by a pixel at the edge.
        # A vowel on the wrong side, or a visible hasant, is a much larger share.
        if stats["frac_gt_40"] > 0.04 or stats["mean_abs"] > 8:
            sys.stderr.write("preshape check failed: the unshaped render does not match HarfBuzz\n")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
