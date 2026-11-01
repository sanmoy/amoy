# AGENTS.md

Notes for the next person or agent who edits this repo. Read this before adding pages or changing the styles.

## Purpose

This site is for Amoy, a 15-month-old, and is meant to be read on a very old Amazon Kindle e-paper device with its old experimental WebKit browser. A parent reads the page aloud. Pages must stay simple, high contrast, and light.

## Hard constraints

- Plain HTML and CSS. JavaScript only if it is truly needed, and then only plain ES3: no `let` or `const`, no arrow functions, no template strings, no `fetch`, no modules. Pages must work fully with JavaScript disabled. The current site has no JavaScript.
- No frameworks, no build step, no npm, no bundler.
- Do not rely on flexbox, grid, or CSS variables. Stick to CSS that old WebKit understands: blocks, margins, padding, borders, font sizes.
- E-paper: black (`#000000`) on white (`#ffffff`), high contrast, large text, big tap targets. No animation, no video, no hover-dependent UI. Keep poem pages free of images. Figure pages are the exception: one black-and-white PNG each, as described below. Pages should load quickly.
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
index.html              Home. Title, then Poems, Figures, and Songs. English.
style.css               Shared stylesheet. Linked relatively from every page.
.nojekyll               Disables Jekyll.
src/poems/              Unicode poem sources. Edit these, not the served poem pages.
poems/index.html        Generated list of poems. English and pre-shaped titles.
poems/khai-khai.html    Generated. Sukumar Ray, খাই খাই, pre-shaped.
src/figures/            Unicode figure pages. Bengali names live here.
figures/index.html      Generated picture-book index. Two columns, big tap targets.
figures/<name>.html     Generated. Large PNG, English name, pre-shaped Bengali name, Previous and Next.
figures/img/*.png       The images the pages show. 600×600, black and white only.
figures/src/*.svg       Vector sources. Not linked from pages. Hand, eye, and apple are traced from flash cards.
figures/render.py       Regenerates SVGs, PNGs, and src/figures. Not used at serve time.
songs/index.html        Song list. Empty until songs are added. English for now.
fonts/AmoyBengali.ttf   Site font. Pre-shaped clusters, subset, no hinting.
fonts/AmoyBengali.woff  Same font for browsers that understand format().
fonts/NotoSansBengali-* Unmodified Noto. Shaping source only. Pages do not load it.
fonts/OFL.txt           SIL OFL for Noto and for Amoy Bengali, which is derived from it.
tools/preshape.py       Builds Amoy Bengali and the served pages (--site).
docs/fonts.md           Kindle Bengali findings and how to regenerate the font.
AGENTS.md               This file.
README.md               Short intro.
```

Home links to section indexes. A section index links back to `../index.html`. A poem links back to `poems/index.html` (the file `index.html` next to it). Long poems repeat that back link at the bottom.

The stylesheet path is `style.css` from the home page and `../style.css` from any page one directory down. `url(...)` inside `style.css` is relative to the CSS file, so font paths stay `fonts/...` on every page.

## Font

The pages load `fonts/AmoyBengali.ttf` (and `.woff` where `format()` is understood). It is a modified Noto Sans Bengali Regular 2.001, SIL Open Font License 1.1. See `fonts/OFL.txt` and `fonts/README.txt`. The family name is `Amoy Bengali`. It is not named Noto. Noto is a trademark of Google Inc.

`tools/preshape.py --site` shapes every Bengali string under `src/` with HarfBuzz, bakes each cluster into one composite glyph, and maps it to a Private Use Area character. GSUB and GPOS are removed. Unused Noto glyphs are dropped and hinting is removed, which is what keeps the file small. The served poem body is those Private Use characters in visual order, plus ordinary spaces so a line can still wrap. The Kindle draws them left to right and does not need a shaper. A current browser does the same, because a shaper has nothing to reorder.

Do not point pages at `fonts/NotoSansBengali-Regular.ttf`. That file stays in the repo as the shaping source. It is about 200 KB and the Kindle would download it. Why the served font is built this way is in `docs/fonts.md`.

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

## How to add a figure

Figures are solid black shapes on white, in the same style as a filled five-pointed star: one bold silhouette, no grey, no text inside the picture. Pages must point at the PNG. Old Kindle WebKit is unreliable with SVG.

The picture-book order is the `FIGURES` list in `figures/render.py`. Previous and Next wrap around that list. Bengali names are Unicode in `src/figures/` and pre-shaped in `figures/`. Do not edit `figures/*.html` by hand.

1. Add a draw function in `figures/render.py` that paints only pure black `(0, 0, 0)` and pure white `(255, 255, 255)` through `Drawer` (`polygon`, `ellipse`, `rect`). Do not rotate or resize a bitmap; Pillow's rotate adds grey pixels. Keep the shape inside the 600×600 canvas with a margin, and make it something a toddler recognises at a glance.
2. Add one tuple to `FIGURES`: `("slug", "English name", "বাংলা নাম")`. The slug is ASCII. Put `class="bn"` and `lang="bn"` only on the Bengali name. The webfont has no Latin letters, so the English name must not use `class="bn"`.
3. From the repo root run `python3 figures/render.py`, then `python3 tools/preshape.py --site`. `render.py` needs Pillow. It writes `figures/src/<slug>.svg`, `figures/img/<slug>.png`, and the Unicode pages under `src/figures/`. It refuses to save a PNG that contains any colour other than black and white. PNGs are an 8-bit palette of those two colours, not interlaced, with no alpha. `preshape.py` then rebuilds `fonts/AmoyBengali` and writes the served `figures/*.html`. Slugs in `TRACED` (`hand`, `eye`, `apple`) are traced from Amoy's flash cards. The script only rasterizes those SVGs. Do not replace them with a procedural drawing.
4. Do not link the SVG from HTML. The figure page uses `img/<slug>.png`. The index uses the same file, shown smaller.
5. Check the new shape on its page, then Previous and Next, including the wrap from the last figure back to the first. The Bengali name should render with Amoy Bengali. Links stay relative. The name will look like boxes if the font file is missing.

To add a figure without the script, draw `figures/src/<slug>.svg`, export a 600×600 PNG with every pixel forced to `#000000` or `#ffffff`, and copy `src/figures/star.html` to `src/figures/<slug>.html`. Point Previous and Next at the neighbours, update those neighbours, and add a cell to `src/figures/index.html`. Then run `python3 tools/preshape.py --site`.

## How to add a song

`songs/index.html` is the list. It is English and empty until songs arrive, so it is not under `src/` and it does not use the Bengali font. The home-page link is the English word Songs.

When a song is added:

1. Create `songs/<ascii-slug>.html`. Copy the head from `songs/index.html`. Start with `<p class="nav"><a href="index.html">Songs</a></p>`, then an `h1` for the title, then the words. Repeat the back link after a long song.
2. Add one `<li>` to the `ul.menu` on the list page. If the list is still the placeholder paragraph, replace that paragraph with `<ul class="menu">` and one `<li>`, in the same shape as `src/poems/index.html`.
3. If the title or the words contain Bengali, do not leave that Unicode in the served file. Move the list to `src/songs/index.html` and the song to `src/songs/<ascii-slug>.html`, with `class="bn"` and `lang="bn"` on the Bengali parts only. Relative links in those sources must be the served-page links (`../style.css`, `index.html`), the same way `src/poems/` works.
4. Run `python3 tools/preshape.py --site`. That rebuilds the font and writes `songs/`. Commit the sources, the served pages, and both `fonts/AmoyBengali` files together.
5. An English-only song stays a normal page under `songs/` and does not need a font rebuild.

## How to add a top-level section

1. Create a new directory with an `index.html`, for example `stories/index.html`.
2. Use the same head as `figures/index.html`: both charset metas, viewport, `href="../style.css"`.
3. Start with `<p class="nav"><a href="../index.html">Home</a></p>`, then an `h1` with the section name.
4. On the home page, add one `<li>` to the `ul.menu` in `index.html`, linking to `stories/index.html` with a relative URL. If that label is Bengali, it has to be pre-shaped: put the home page under `src/` or keep the label English. The Songs link is the English word Songs.
5. Reuse `style.css`. Do not start a second stylesheet unless the shared one cannot express the page. Keep new rules on the same blacklist: no flex, grid, variables, animation, or hover-only behavior.

## Kindle compatibility

A Kindle Touch (4th generation) loads `@font-face` TTF and does not shape Bengali. The live pages use pre-shaped cluster text in `fonts/AmoyBengali`. What was tried, what failed, and how to rebuild the font is in `docs/fonts.md`.

- TTF is what this device accepts. Keep a bare TTF `src` ahead of any `format()` hint. Do not switch to WOFF2 only.
- The viewport meta helps phones. If the Kindle draws the type tiny or huge, try removing `<meta name="viewport" content="width=device-width">` before changing font sizes.
- Pages use no JavaScript. Flexbox, grid, and CSS variables are not used.

## Pictures of poems

Not the plan. The Kindle test showed that pre-shaped cluster text matches a HarfBuzz picture, so the poems stay text. A PNG would cost more and would not be selectable. Figure pages are pictures on purpose: they are shapes, not text.
