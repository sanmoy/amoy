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
index.html              Home. Title, then a list of sections.
style.css               Shared stylesheet. Linked relatively from every page.
.nojekyll               Disables Jekyll.
poems/index.html        One flat list of poems. English and Bengali titles together. No subsections.
poems/khai-khai.html    Sukumar Ray, খাই খাই.
figures/index.html      Placeholder. Figures are coming soon.
fonts/                  Noto Sans Bengali Regular (OFL), TTF and WOFF, plus OFL.txt.
debug/                  Kindle shaping tests. Not linked from the home page. See below.
tools/                  preshape.py and build_debug.py. Not used by the live pages.
AGENTS.md               This file.
README.md               Short intro.
```

Home links to section indexes. A section index links back to `../index.html`. A poem links back to `poems/index.html` (the file `index.html` next to it). Long poems repeat that back link at the bottom.

The stylesheet path is `style.css` from the home page and `../style.css` from any page one directory down. `url(...)` inside `style.css` is relative to the CSS file, so font paths stay `fonts/...` on every page.

## Font

Noto Sans Bengali Regular, version 2.001 (Copyright 2017 Google Inc.), SIL Open Font License 1.1. See `fonts/OFL.txt`. The files are the full font, not a per-poem subset: 679 glyphs, Unicode cmap for the Bengali block in use, and OpenType layout for both the `beng` and `bng2` scripts (`akhn`, `rphf`, `blwf`, `half`, `cjct`, `pres`, and the rest). Conjuncts are shaped from those tables. Do not subset unless a check with a real shaper (HarfBuzz or a current browser) shows the conjuncts in the poems still form. Dropping GSUB/GPOS, or keeping only the codepoints of one poem, will break later poems and can break conjuncts.

`@font-face` lists a bare TTF `src` first, then a second `src` with WOFF and TTF `format()` hints. Keep that order. Old WebKit that does not understand `format()` uses the first declaration. Browsers that understand it use the second.

Fallback list, after the embedded family: `"Nirmala UI", "Vrinda", "Bangla MN", "Kohinoor Bangla", sans-serif`.

English UI text uses `font-family: sans-serif` so the Kindle's own font draws it.

There is no bold face. Headings use a larger size and `font-weight: normal` so the browser does not synthesize a fake bold, which distorts Bengali matras.

## How to add a poem

1. Transcribe the poem yourself into Unicode. Preserve its line breaks and stanza breaks. Keep zero-width non-joiners (U+200C) where the source uses them to stop a conjunct, and keep danda (U+0964), em dashes, and the quotation marks the source uses. Do not "clean up" spelling.
2. Create `poems/<ascii-slug>.html`. Copy the head from `poems/khai-khai.html` (both charset metas, viewport, relative `../style.css`). Set `<html lang="bn">` when the poem is Bengali, or `lang="en"` when it is English.
3. Put a back link first: `<p class="nav"><a lang="en" href="index.html">Poems</a></p>`.
4. Use an `h1` for the title. For Bengali, add `class="bn"` and `lang="bn"`. Credit the poet in a paragraph. For a Bengali name, use `class="bn"` and `lang="bn"`. A Latin-script credit next to it is useful when shaping fails.
5. Put the poem in `<div class="poem bn" lang="bn">` (drop `bn` and `lang="bn"` for an English poem). One `<p>` per stanza. Inside the stanza, join lines with `<br>` and do not put spaces or newlines between the end of a line and the `<br>` that follows, or a space appears at the start of the next line. Separate stanzas by closing the `</p>` and opening another. Repeat the back link after the poem.
6. Add one `<li>` to the single list in `poems/index.html`. Bengali titles need `class="bn"` and `lang="bn"` on the `<a>`. Do not add subsections.
7. Check the new page in a browser: conjuncts look joined, the back link returns to the list, and the stylesheet loads. Relative links only.

Sukumar Ray died in 1923, so his poems are in the public domain. Credit him on the page anyway. `poems/khai-khai.html` follows the line and stanza breaks on https://www.bangla-kobita.com/sukumarray/khai-khai/ (three stanzas, split where that page has a blank line).

## How to add a top-level section

1. Create a new directory with an `index.html`, for example `songs/index.html`.
2. Use the same head as `figures/index.html`: both charset metas, viewport, `href="../style.css"`.
3. Start with `<p class="nav"><a href="../index.html">Home</a></p>`, then an `h1` with the section name.
4. On the home page, add one `<li>` to the `ul.menu` in `index.html`, linking to `songs/index.html` with a relative URL.
5. Reuse `style.css`. Do not start a second stylesheet unless the shared one cannot express the page. Keep new rules on the same blacklist: no flex, grid, variables, animation, or hover-only behavior.

## Kindle compatibility

A Kindle Touch (4th generation) has loaded these pages. `@font-face` works: Noto Sans Bengali glyphs appear. Shaping does not. Pre-base vowels sit after the consonant, o-kar is split, and conjuncts keep a visible hasant. Reph and ya-phala are wrong. The same pages shape correctly on a current phone or desktop browser. The font is not the limit. The browser has no Indic shaper. `debug/` is the comparison bench for that. See Debug pages.

- TTF is what this device accepted. Keep a bare TTF `src` ahead of any `format()` hint. Do not switch to WOFF2 only.
- The viewport meta helps phones. If the Kindle draws the type tiny or huge, try removing `<meta name="viewport" content="width=device-width">` before changing font sizes.
- Poem pages use no JavaScript. The debug index has one ES3 script that prints `navigator.userAgent`. That page still works with JavaScript off. Flexbox, grid, and CSS variables are not used.

## Debug pages

`debug/index.html` is not linked from the home page, the poems, or the figures. It is published with the rest of the site, so the Kindle can open https://nascentsoftware.com/amoy/debug/ directly. The same rules apply there: both charset metas, relative links, no flex, grid, or CSS variables, no CDN, TTF ahead of any `format()` hint, English in `sans-serif`.

Every numbered page shows the same sample: the first stanza of `poems/khai-khai.html`, then the line `কি কে কো কৌ ক্ষ ত্র স্ত ন্দ র্ক ক্য ঙ্গ শ্চ ঁ ং ৎ`. The English title is how a phone photo of the device identifies the test.

Tests 1–4 are Unicode text in Noto, Lohit Bengali, Hind Siliguri, and a static Baloo Da 2. They still need a shaper. Tests 5 and 6 are pre-shaped: `tools/preshape.py` runs HarfBuzz on Noto Sans Bengali and writes a TTF whose Private Use Area cmap points at composite glyphs with those positions baked in. GSUB and GPOS are removed. Test 5 is one character per syllable. Test 6 is one character per glyph. Test 7 is a black-and-white PNG of the sample, drawn with HarfBuzz, for comparison.

Licenses for the extra fonts, and the OFL notice for the modified Noto files, are in `debug/fonts/README.txt`. Do not point the poem pages at these fonts. Rebuild with `python3 tools/build_debug.py` after changing the sample or the script. Dependencies are listed in `tools/requirements.txt`. The pages themselves stay static.

## Future option: pre-rendered poem images

Do not build this until a Kindle test shows that live Bengali text is wrong.

If shaping fails on the device, add an alternate view that is a picture of the poem instead of relying on the browser to shape it. Render that picture on a current machine with HarfBuzz and this same Noto Sans Bengali file, black on white, large type, no antialiasing tricks that turn gray. One PNG per stanza is easier to read on a small screen than one tall image. Link it from the poem page as a plain relative image or a "picture version" link. Keep the Unicode text page as the primary version so the poem stays searchable and editable. Images are a fallback, not a replacement, and they cost more bytes, so add them only for poems that fail on the device.
