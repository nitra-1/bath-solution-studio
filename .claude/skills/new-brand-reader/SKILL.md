---
name: new-brand-reader
description: Create or fix the PDF reader for a brand's price list in Bath Solution Studio. Use when asked to "create a reader for <pdf>", "add a new brand", or when a price list didn't read cleanly in the app.
---

# Create a brand reader

The app reads price lists without AI, using one reader per layout in
`app/extract/profiles/<name>.py`. Your job: make a new brand's PDF read correctly,
prove it with a test, and leave every existing reader passing.

The owner is not a programmer. Explain results in plain words (how many products and
prices were read, what still needs fixing by hand), not in code terms.

## Steps

1. **Find the PDF.** It should be in `tests/samples/`. If the user gave another path, copy it to
   `tests/samples/<brand>.pdf` (lowercase, no spaces). Ask for the brand name if the file name doesn't make it clear.

2. **Try the general reader first:**
   ```
   python scripts/try_reader.py tests/samples/<brand>.pdf --brand "<Brand>" --reader generic
   ```
   If the verdict is "looks usable" and the samples look right (titles, finishes, prices, collection names),
   a light profile may be enough: just `brands=[...]` plus any tweaks.

3. **Look at the layout.** Read 2–3 product pages as images (Read tool with `pages`) and dump the words:
   ```
   python scripts/try_reader.py tests/samples/<brand>.pdf --dump-page <n>
   ```
   Note: where the product name is (font size, bold), how article numbers look, where finishes and prices are,
   whether it's one row per finish or a price grid, where the collection name is printed, which pages have no text
   (photo pages are fine; if product pages have no text the PDF is scanned and can't be read without OCR: tell the
   user to use the Excel template for that brand).

4. **Write the reader** by copying `app/extract/profiles/_template.py` to `app/extract/profiles/<brand>.py`:
   - Same structure as the block reader → set `PROFILE` fields only (`code_tokens`, `series_header`, `format_art`, `finish_codes`).
   - Different structure (price grid, multi-line rows, products spanning pages) → write `parse()`; reuse `rows`,
     `parse_price`, `crop_image`, `largest_image` from `pdf_parser`.
   - Set `brands=["<Brand>"]` so the app picks it automatically, and a clear `label`.
   - Put a short docstring describing the layout, like `keuco.py` has.
   - Don't change `pdf_parser.block_reader` or other brands' readers to make this one work. If a shared helper truly
     needs a fix, run the full test suite afterwards.

5. **Check it** until the numbers match the PDF:
   ```
   python scripts/try_reader.py tests/samples/<brand>.pdf --reader <brand>
   ```
   Spot-check several products against the page images: every finish row, every price, photo cropped to the product.
   Product **types** come from `app/taxonomy.py classify()` (English keywords). If many titles show as
   "type not recognised" because the brand uses different words (or another language), add keywords to `classify()`
   or set `"type"` in the reader's output. Never guess prices.

6. **Lock it in:**
   ```
   python scripts/try_reader.py tests/samples/<brand>.pdf --reader <brand> --brand "<Brand>" --write-expected
   pytest -q
   ```
   All tests must pass, including the KEUCO sample (88 products, 514 article numbers) if its PDF is present.

7. **Hand over.** Commit `app/extract/profiles/<brand>.py`, `tests/samples/<brand>.expected.json` and any
   `taxonomy.py` change (the PDF itself stays local; it's git-ignored). Then tell the user, in plain words:
   - what was read (products, article numbers, collections) and anything still to fix on the review screen;
   - how to get it onto the office computer: copy the updated project (or `git pull`) and restart the app
     (`start.bat` / `start.sh`, or `docker compose up -d --build`);
   - then upload the PDF in **Upload & review**; with Reader on "Automatic" the new reader is used for that brand.
