# AGENTS.md

Notes for the next person or agent who edits this repo. Read this before adding pages or changing the styles.

## Purpose

This site is for Amoy, a 15-month-old, and is meant to be read on a very old Amazon Kindle e-paper device with its old experimental WebKit browser. A parent reads the page aloud. Pages must stay simple, high contrast, and light.

## Hard constraints

- Plain HTML and CSS. JavaScript only if it is truly needed, and then only plain ES3: no `let` or `const`, no arrow functions, no template strings, no `fetch`, no modules. Pages must work fully with JavaScript disabled. The current site has no JavaScript.
- No frameworks, no build step, no npm, no bundler.
- Do not rely on flexbox, grid, or CSS variables. Stick to CSS that old WebKit understands: blocks, margins, padding, borders, font sizes.
- E-paper: black (`#000000`) on white (`#ffffff`), high contrast, large text, big tap targets. No animation, no video, no hover-dependent UI, as few images as possible. Pages should load quickly.
- Bengali must be real Unicode text, not pictures, unless the Kindle fallback described at the bottom of this file is being added on purpose.
- Every HTML file starts with both of these, in the first kilobyte:

  ```html
  <meta charset="utf-8">
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  ```

- Put `lang="bn"` on Bengali content. Put `class="bn"` on the same elements so the embedded font is used. The font file has no Latin letters A–Z. If the webfont is applied to English text, those letters can turn into missing-glyph boxes on browsers that do not fall back per character.
- Self-host the Bengali font. Do not call Google Fonts or any other CDN from the pages. Keep TTF and WOFF. Do not switch the site to WOFF2 only; old WebKit often cannot read WOFF2.
- Use relative links only (`poems/index.html`, `../style.css`, `fonts/...` from CSS). The site is served under `/amoy/`. A root path such as `/style.css` would leave this project and hit the parent site.
- Keep an empty `.nojekyll` file at the repo root so GitHub Pages does not run Jekyll.

## Deployment

GitHub Pages serves this repo from the `main` branch, root directory.

The custom domain `nascentsoftware.com` is owned by the user's `sanmoy.github.io` site, not by this repo. Do not add a `CNAME` file here. Project pages are then available at:

- https://nascentsoftware.com/amoy/
- https://sanmoy.github.io/amoy/

Pushing to `main` publishes the site. There is no build. What is in the repo root is what gets served.

## Site structure

```
index.html              Home. Title, then a list of sections. English.
style.css               Shared stylesheet. Linked relatively from every page.
.nojekyll               Disables Jekyll.
src/poems/              Unicode sources. Edit these, not the served poem pages.
poems/index.html        Generated list of poems. English and pre-shaped titles.
poems/khai-khai.html    Generated. Sukumar Ray, খাই খাই, pre-shaped.
figures/index.html      Placeholder. Figures are coming soon. English, not generated.
fonts/AmoyBengali.ttf   Site font. Pre-shaped clusters, subset, no hinting.
fonts/AmoyBengali.woff  Same font for browsers that understand format().
fonts/NotoSansBengali-* Unmodified Noto. Shaping source and debug test 1 only.
fonts/OFL.txt           SIL OFL for Noto and for Amoy Bengali, which is derived from it.
debug/                  Kindle shaping tests. Not linked from the home page. See below.
tools/preshape.py       Builds Amoy Bengali and the served pages (--site).
AGENTS.md               This file.
README.md               Short intro.
```

Home links to section indexes. A section index links back to `../index.html`. A poem links back to `poems/index.html` (the file `index.html` next to it). Long poems repeat that back link at the bottom.

The stylesheet path is `style.css` from the home page and `../style.css` from any page one directory down. `url(...)` inside `style.css` is relative to the CSS file, so font paths stay `fonts/...` on every page.

## Font

The pages load `fonts/AmoyBengali.ttf` (and `.woff` where `format()` is understood). It is a modified Noto Sans Bengali Regular 2.001, SIL Open Font License 1.1. See `fonts/OFL.txt` and `fonts/README.txt`. The family name is `Amoy Bengali`. It is not named Noto. Noto is a trademark of Google Inc.

`tools/preshape.py --site` shapes every Bengali string under `src/` with HarfBuzz, bakes each cluster into one composite glyph, and maps it to a Private Use Area character. GSUB and GPOS are removed. Unused Noto glyphs are dropped and hinting is removed, which is what keeps the file small. The served poem body is those Private Use characters in visual order, plus ordinary spaces so a line can still wrap. The Kindle draws them left to right and does not need a shaper. A current browser does the same, because a shaper has nothing to reorder.

Do not point poem pages at `fonts/NotoSansBengali-Regular.ttf`. That file stays in the repo as the shaping source and as debug test 1. It is about 200 KB and the Kindle would download it.

`@font-face` lists a bare TTF `src` first, then a second `src` with WOFF and TTF `format()` hints. Keep that order. Old WebKit that does not understand `format()` uses the first declaration and downloads only the TTF. Browsers that understand it use the second and download the WOFF.

`.bn` is `font-family: "Amoy Bengali", sans-serif`. System Bengali fonts do not contain these Private Use glyphs, so the old Nirmala UI / Vrinda fallback list does not belong here. English UI text uses `font-family: sans-serif`.

There is no bold face. Headings use a larger size and `font-weight: normal` so the browser does not synthesize a fake bold, which distorts Bengali matras.

## How to add a poem

Bengali pages are Unicode in `src/` and pre-shaped in the served tree. Do not edit `poems/*.html` by hand. A new poem reassigns Private Use codes across the whole site, so the tool rewrites every generated page and both font files together. Commit the source, the generated pages, and `fonts/AmoyBengali.ttf` and `.woff` in one change.

1. Transcribe the poem yourself into Unicode. Preserve its line breaks and stanza breaks. Keep zero-width non-joiners (U+200C) where the source uses them to stop a conjunct, and keep danda (U+0964), em dashes, and the quotation marks the source uses. Do not "clean up" spelling.
2. Create `src/poems/<ascii-slug>.html`. Copy the head from `src/poems/khai-khai.html` (both charset metas, viewport, relative `../style.css`). Set `<html lang="bn">` when the poem is Bengali, or `lang="en"` when it is English. The `<title>` stays Unicode on the served page. The tool does not pre-shape it, so a phone tab can show the name with a system font.
3. Put a back link first: `<p class="nav"><a lang="en" href="index.html">Poems</a></p>`.
4. Use an `h1` for the title. For Bengali, add `class="bn"` and `lang="bn"`. Credit the poet in a paragraph. For a Bengali name, use `class="bn"` and `lang="bn"`. A Latin-script credit next to it is useful on a device that never loads the font.
5. Put the poem in `<div class="poem bn" lang="bn">` (drop `bn` and `lang="bn"` for an English poem). One `<p>` per stanza. Inside the stanza, join lines with `<br>` and do not put spaces or newlines between the end of a line and the `<br>` that follows, or a space appears at the start of the next line. Separate stanzas by closing the `</p>` and opening another. Repeat the back link after the poem.
6. Add one `<li>` to the single list in `src/poems/index.html`. Bengali titles need `class="bn"` and `lang="bn"` on the `<a>`. Do not add subsections.
7. Run `python3 tools/preshape.py --site`. Dependencies are in `tools/requirements.txt`. The command reads `src/`, writes `fonts/AmoyBengali.ttf` and `.woff`, and writes the served pages. It checks that FreeType, with no shaper, matches HarfBuzz on the Unicode source.
8. Check the new page in a browser: conjuncts look joined, the back link returns to the list, and the stylesheet loads. Relative links only. The body will look like boxes if you open the file without the font.

An English poem can be a normal page under `poems/` and does not need `src/` or a font rebuild.

Sukumar Ray died in 1923, so his poems are in the public domain. Credit him on the page anyway. `src/poems/khai-khai.html` follows the line and stanza breaks on https://www.bangla-kobita.com/sukumarray/khai-khai/ (three stanzas, split where that page has a blank line).

The served HTML does not carry a second Unicode copy of the poem. That copy would be downloaded by the Kindle. The Unicode text lives in `src/`.

## How to add a top-level section

1. Create a new directory with an `index.html`, for example `songs/index.html`.
2. Use the same head as `figures/index.html`: both charset metas, viewport, `href="../style.css"`.
3. Start with `<p class="nav"><a href="../index.html">Home</a></p>`, then an `h1` with the section name.
4. On the home page, add one `<li>` to the `ul.menu` in `index.html`, linking to `songs/index.html` with a relative URL.
5. Reuse `style.css`. Do not start a second stylesheet unless the shared one cannot express the page. Keep new rules on the same blacklist: no flex, grid, variables, animation, or hover-only behavior.

## Kindle compatibility

A Kindle Touch (4th generation) loads `@font-face` TTF and does not shape Bengali. Unicode text shows pre-base vowels after the consonant, a split o-kar, a visible hasant, and wrong reph and ya-phala. The same Unicode shapes correctly on a current phone. `debug/` is the comparison that showed this. Tests 5 and 6, pre-shaped Private Use text, matched the HarfBuzz picture. The live pages use test 5 (one character per cluster).

- TTF is what this device accepts. Keep a bare TTF `src` ahead of any `format()` hint. Do not switch to WOFF2 only.
- The viewport meta helps phones. If the Kindle draws the type tiny or huge, try removing `<meta name="viewport" content="width=device-width">` before changing font sizes.
- Poem pages use no JavaScript. The debug index has one ES3 script that prints `navigator.userAgent`. That page still works with JavaScript off. Flexbox, grid, and CSS variables are not used.

## Debug pages

`debug/index.html` is not linked from the home page, the poems, or the figures. It is published with the rest of the site, so the Kindle can open https://nascentsoftware.com/amoy/debug/ directly. The same rules apply there: both charset metas, relative links, no flex, grid, or CSS variables, no CDN, TTF ahead of any `format()` hint, English in `sans-serif`.

Every numbered page shows the same sample: the first stanza of `poems/khai-khai.html`, then the line `কি কে কো কৌ ক্ষ ত্র স্ত ন্দ র্ক ক্য ঙ্গ শ্চ ঁ ং ৎ`. The English title is how a phone photo of the device identifies the test.

Tests 1–4 are Unicode text in Noto, Lohit Bengali, Hind Siliguri, and a static Baloo Da 2. They still need a shaper. On the Kindle they fail the same way the old poem page did. Tests 5 and 6 are pre-shaped Private Use text. Both matched test 7, the HarfBuzz picture. The live site ships test 5 as `fonts/AmoyBengali`, subset to the clusters the pages use. The debug copies of the fonts are the full unsubsetted files from that test, so they stay large on purpose.

Licenses for the extra fonts, and the OFL notice for the modified Noto files, are in `debug/fonts/README.txt`. Do not point the poem pages at these fonts. Rebuild with `python3 tools/build_debug.py` after changing the sample or the script. Dependencies are listed in `tools/requirements.txt`. The pages themselves stay static.

## Pictures of poems

Not the plan. The Kindle test showed that pre-shaped cluster text matches a HarfBuzz picture, so the poems stay text. A PNG would cost more and would not be selectable. Debug test 7 is that picture, kept only as the reference from the test.
