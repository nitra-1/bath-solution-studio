"""KEUCO Project Specifier's Handbook (Pricelist 2024). This book has article numbers but NO prices.

Layout: one boxed block per product, boxes separated by long horizontal lines. The page header (20 pt)
names the edition/collection ("Edition 90", "Collection Plan"). Inside a box: photo and drawing on the left;
at x~247 a bold title, plain description lines, then one row per article:
    59016 010201   187 mm      chrome-plated
 bold 5-digit number at x~189, 6-digit number at x~215, optional size text, finish at the right.
Text after a bold "Spare part(s):" / "Note:" line is skipped (spare parts and installation notes).
Pages without article rows (overviews, ordering information) give no products.
Not picked automatically (the KEUCO price list reader owns the brand name): choose it in the Reader list.
Sample: tests/samples/KEUCO Project Specifier's Handbook.pdf
"""
import re

import pdfplumber
import pypdfium2 as pdfium

from ..pdf_parser import Profile, crop_image, rows

PROFILE = Profile(name="keuco_handbook", label="KEUCO Specifier's Handbook (no prices)", brands=[])

TEXT_X = 186  # text column starts here; photo and drawings are further left
SKIP_MARKERS = ("spare part", "note", "essential", "please order")
CODE_A = re.compile(r"^\d{5}$")
CODE_B = re.compile(r"^[0-9A-Z]{3,6}$")


def _bold(w):
    return "bold" in w["fontname"].lower()


def _separators(page):
    ys = sorted({round(l["top"]) for l in page.lines if l["x1"] - l["x0"] > 300 and 50 < l["top"] < 795})
    out = []
    for y in ys:
        if not out or y - out[-1] > 8:
            out.append(y)
    return out


def _strip_header(r):
    """Drop the column captions "No." / "Article" that sit at the top of each page."""
    return [w for w in r if not (w["fontname"] and _bold(w) and w["text"] in ("No.", "Article") and w["top"] < 60)]


def _series(page):
    ws = [w for w in page.extract_words(extra_attrs=["size"]) if w["size"] >= 15 and w["top"] < 40]
    s = " ".join(w["text"] for w in sorted(ws, key=lambda w: w["x0"]))
    return re.sub(r"^Collection\s+", "", s, flags=re.I).strip()


def parse(pdf_path, img_dir, img_prefix, default_series, log):
    products = []
    pdf, doc = pdfplumber.open(pdf_path), pdfium.PdfDocument(pdf_path)
    for pi, page in enumerate(pdf.pages):
        words = [w for w in page.extract_words(extra_attrs=["fontname", "size"])
                 if 7.5 <= w["size"] <= 8.5 and w["x0"] >= TEXT_X and 48 < w["top"] < 800]
        if not any(_bold(w) and CODE_A.match(w["text"]) and w["x0"] < 230 for w in words):
            continue
        series = _series(page) or default_series
        edges = [48] + _separators(page) + [800]
        for top, bottom in zip(edges, edges[1:]):
            rws = [r for r in (_strip_header(r) for r in rows([w for w in words if top <= w["top"] < bottom])) if r]
            title, specs, variants, extra = [], [], [], None
            skipping = False
            started = False  # a code row has been seen for the current product
            cur = None

            def close():
                nonlocal title, specs, variants
                if variants:
                    cur_products.append((title, specs, variants))
                title, specs, variants = [], [], []

            cur_products = []
            for r in rws:
                first = r[0]
                text = " ".join(w["text"] for w in r)
                is_code = _bold(first) and CODE_A.match(first["text"]) and first["x0"] < 230 and len(r) > 1 and CODE_B.match(r[1]["text"])
                if _bold(first) and not is_code and any(text.lower().startswith(m) for m in SKIP_MARKERS):
                    skipping = True
                    continue
                if skipping:
                    continue
                if is_code:
                    art = f"{first['text']} {r[1]['text']}"
                    rest = r[2:]
                    finish = " ".join(w["text"] for w in rest if w["x0"] >= 380)
                    option = " ".join(w["text"] for w in rest if w["x0"] < 380)
                    variants.append({"art": art, "finish": ", ".join(x for x in (option, finish) if x),
                                     "width_mm": None, "price": None})
                    started = True
                elif _bold(first):
                    if started:  # a second product in the same box
                        close()
                        started = False
                    title.append(text)
                elif not started:
                    specs.append(text)
            close()
            for ti, (t, sp, vs) in enumerate(cur_products):
                image = None
                ims = [im for im in page.images if top - 5 <= im["top"] < bottom and im["x1"] < 200 and (im["x1"] - im["x0"]) > 25]
                ims.sort(key=lambda im: -(im["x1"] - im["x0"]) * (im["bottom"] - im["top"]))
                if ims and ti == 0:
                    im = ims[0]
                    image = crop_image(doc, pi, page, (im["x0"], im["top"], im["x1"], im["bottom"]), img_dir,
                                       f"{img_prefix}_p{pi + 1}_{top}.jpg", log)
                products.append({"series": series, "line": "", "page": pi + 1, "title": " ".join(t).strip() or "Untitled product",
                                 "specs": [{"group": None, "items": sp}] if sp else [], "variants": vs, "image": image})
        if pi % 50 == 0:
            log(f"Page {pi + 1}: {len(products)} products so far")
    return products
