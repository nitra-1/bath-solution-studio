"""VALVEX "Sanitary Collection" catalogue (2026). This catalogue has article numbers but NO prices.

Layout: up to three product columns per page (left edge about 54, 227 and 400 pt). Each column has,
top to bottom: photo, collection name (e.g. ALLORA), the product name in six languages (EN / DE / CZ /
SK / RO / SR; we keep the English one), one row per finish "Chrome 2413000-CHR", then a spec table
("type standing", "installation one-hole" ...), then small dimension drawings (tiny fonts, ignored).
A page can hold two such blocks (accessory pages). Prices are left empty (None); the review screen
flags them so they can be filled in from the Excel template or by hand.
Sample: tests/samples/Sanitary-Collection-2026-1.pdf
"""
import re

import pdfplumber
import pypdfium2 as pdfium

from ..pdf_parser import Profile, crop_image, rows

PROFILE = Profile(name="valvex", label="VALVEX Sanitary Collection (no prices)", brands=["VALVEX"])

COL_WIDTH = 173
CODE = re.compile(r"^\d{6,8}[A-Z]?(-[A-Z0-9]+)?$")
SPEC_X = 38  # spec values start this far right of the column's left edge


def _in_col(w, colx, right):
    return colx - 3 <= w["x0"] < right


def _blocks(words):
    """Find (en_top, [column x]) for each product block on the page. EN rows start 12 pt right of the column edge."""
    ens = sorted((w["top"], round(w["x0"] - 12)) for w in words if w["text"] == "EN" and w["x0"] > 55 and w["top"] > 60)
    blocks = []
    for top, x in ens:
        if blocks and abs(blocks[-1]["top"] - top) < 6:
            if x not in blocks[-1]["cols"]:
                blocks[-1]["cols"].append(x)
        else:
            blocks.append({"top": top, "cols": [x]})
    return blocks


def _spec_items(rws, colx):
    items = []
    for r in rws:
        label = " ".join(w["text"] for w in r if w["x0"] < colx + SPEC_X)
        value = " ".join(w["text"] for w in r if w["x0"] >= colx + SPEC_X)
        if value and label:
            items.append([label, value])
        elif label and items:  # wrapped label, e.g. "connection" under "hoses /"
            items[-1][0] += " " + label
        elif value and items:
            items[-1][1] += " " + value
    return [f"{a}: {b}" for a, b in items]


def parse(pdf_path, img_dir, img_prefix, default_series, log):
    products = []
    pdf, doc = pdfplumber.open(pdf_path), pdfium.PdfDocument(pdf_path)
    for pi, page in enumerate(pdf.pages):
        words = [w for w in page.extract_words(extra_attrs=["size"]) if 6.9 <= w["size"] <= 7.1 and 48 < w["top"] < 800]
        blocks = _blocks(words)
        for bi, blk in enumerate(blocks):
            end = blocks[bi + 1]["top"] - 24 if bi + 1 < len(blocks) else 800
            prev_title = blocks[bi - 1]["top"] if bi else -50
            cols = sorted(blk["cols"])
            for ci, colx in enumerate(cols):
                right = cols[ci + 1] - 3 if ci + 1 < len(cols) else 600  # a wide column runs up to the next one
                colw = [w for w in words if _in_col(w, colx, right)]
                series = " ".join(w["text"] for w in rows([w for w in colw if blk["top"] - 24 < w["top"] < blk["top"] - 8])[0:1][0]) if any(
                    blk["top"] - 24 < w["top"] < blk["top"] - 8 for w in colw) else default_series
                rws = rows([w for w in colw if blk["top"] - 5 <= w["top"] < end])
                # English name: from the EN row until the DE row
                title = []
                i = 0
                while i < len(rws) and not (rws[i][0]["text"] == "DE" and i > 0):
                    title.append(" ".join(w["text"] for w in rws[i] if w["text"] != "EN" or w is not rws[i][0]))
                    i += 1
                while i < len(rws) and rws[i][0]["text"] in ("DE", "CZ", "SK", "RO", "SR", "PL", "HU", "EN") or (
                        i < len(rws) and rws[i][0]["x0"] > colx + 8 and not CODE.match(rws[i][-1]["text"])):
                    i += 1
                variants = []
                while i < len(rws) and CODE.match(rws[i][-1]["text"]):
                    variants.append({"art": rws[i][-1]["text"], "finish": " ".join(w["text"] for w in rws[i][:-1]),
                                     "width_mm": None, "price": None})
                    i += 1
                specs = _spec_items(rws[i:], colx)
                # photo: biggest picture in this column above the collection name, below the previous block
                cx0, cx1 = colx - 5, min(right, colx + COL_WIDTH + 60)
                cands = [im for im in page.images if im["top"] > prev_title and im["bottom"] < blk["top"]
                         and (im["x1"] - im["x0"]) > 25 and (im["bottom"] - im["top"]) > 30
                         and cx0 <= (im["x0"] + im["x1"]) / 2 < cx1 and (im["x1"] - im["x0"]) < 300 and (im["bottom"] - im["top"]) < 330]
                cands.sort(key=lambda im: -(im["x1"] - im["x0"]) * (im["bottom"] - im["top"]))
                image = None
                if cands:
                    im = cands[0]
                    image = crop_image(doc, pi, page, (im["x0"], im["top"], im["x1"], im["bottom"]), img_dir,
                                       f"{img_prefix}_p{pi + 1}_{int(blk['top'])}_{colx}.jpg", log)
                products.append({"series": series or default_series, "line": "", "page": pi + 1,
                                 "title": " ".join(title).strip() or "Untitled product",
                                 "specs": [{"group": None, "items": specs}] if specs else [],
                                 "variants": variants, "image": image})
        log(f"Page {pi + 1}: {sum(1 for p in products if p['page'] == pi + 1)} products")
    return products
