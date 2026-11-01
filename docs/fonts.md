# Bengali on the Kindle

Findings from the Kindle Touch tests. The debug pages that produced them have been removed. The live site keeps the approach that worked.

## What the device does

A Kindle Touch (4th generation) experimental browser loads `@font-face` TrueType. Put a bare TTF `src` ahead of any `format()` hint. That browser uses the first declaration and does not download the WOFF. Do not ship WOFF2 only.

It paints glyphs left to right. It has no Indic shaper. The same Unicode Bengali, in the same font, shapes correctly on a current phone. The failure is the browser, not the outlines.

Unicode text on that device shows:

- pre-base vowels after the consonant
- o-kar not split around the consonant
- a visible hasant instead of a conjunct
- reph and ya-phala in the wrong place

## What failed

Four Unicode tests used different OpenType Bengali fonts and left shaping to the browser. All four failed the same way:

1. Noto Sans Bengali Regular 2.001, the shaping source still in `fonts/`
2. Lohit Bengali 2.91.5
3. Hind Siliguri Regular 1.001
4. Baloo Da 2, a static Regular instance of the variable font

A system-font fallback list (Nirmala UI, Vrinda, Bangla MN, Kohinoor Bangla) does not help. The Kindle does not have those fonts, and a font that still needs GSUB and GPOS cannot be shaped there.

## What worked

HarfBuzz shapes the Unicode first. Each shaped cluster becomes one composite glyph: the pen positions, including mark offsets, are baked in. GSUB and GPOS are then removed. Each cluster is mapped to a Private Use Area character (U+E000 and up). The page stores those characters in visual order, plus ordinary U+0020 spaces so a line can still wrap.

The Kindle draws Private Use glyphs left to right and does not reorder them. A current browser does the same, because the font no longer has tables for a shaper to apply. Cluster mode folds a zero-advance mark into the same character as its base, so a browser that drops zero-advance glyphs still draws the mark.

A second mode, one Private Use character per shaped glyph, also matched. The site uses cluster mode.

Both modes were compared with a picture of the same sample rendered by HarfBuzz. They matched that picture. A PNG of the poem is not the plan: pre-shaped text already matches, and a picture would be larger and not selectable.

## How to regenerate

Unicode sources live under `src/`. Do not edit a served page's Bengali by hand. A rebuild reassigns Private Use codes for the whole site, so every generated page and both font files change together.

```
python3 tools/preshape.py --site
```

Dependencies are in `tools/requirements.txt` (`uharfbuzz`, `fonttools`, `pillow`, `freetype-py`). The command:

1. Reads every HTML file under `src/`.
2. Shapes each Bengali text node with HarfBuzz against `fonts/NotoSansBengali-Regular.ttf`. A newline inside a text node is source whitespace, not a line break. `<br>` is the line break. `<title>` stays Unicode so a phone tab can show the name with a system font.
3. Writes `fonts/AmoyBengali.ttf` and `fonts/AmoyBengali.woff`. The family name is `Amoy Bengali`. It is not named Noto. Unused Noto glyphs and hinting are dropped. GSUB and GPOS are gone.
4. Writes the served pages at the same path with the `src/` prefix removed.
5. Checks that FreeType, with no shaper, matches the HarfBuzz render of the Unicode source.

Commit the sources, the served pages, and both `fonts/AmoyBengali` files in one change. English-only pages do not need `src/` or a rebuild.

`class="bn"` selects `font-family: "Amoy Bengali", sans-serif`. Do not put that class on English text. The font has no Latin letters A–Z.
