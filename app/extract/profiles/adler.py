"""ADLER brochure (collection RELDA, English). This brochure has article numbers but NO prices.

Layout: landscape spreads, each with up to two columns of boxes (left edge about 28 and 448 pt). A box has,
top to bottom: a 9 pt product title, a "FINISH  CODE" table with one row per finish
("Brushed Gold  2417728", or "Chrome  2417898-CHR"), and beside it a product photo and a dimension drawing
(the drawing is vector art, not text, so there are no specs to read). The collection name is printed
vertically on the cover (one big letter per line: R-E-L-D-A). Prices are left empty (None).
Sample: tests/samples/ADLER ENG.pdf
"""
import re

import pdfplumber
import pypdfium2 as pdfium

from ..pdf_parser import Profile, crop_image, rows

PROFILE = Profile(name="adler", label="ADLER brochure (no prices)", brands=["ADLER"])

CODE = re.compile(r"^\d{6,8}(-[A-Z0-9]+)?$")
SPLIT_X = 420  # left and right column of a spread


def _series(page, default):
    big = sorted((w for w in page.extract_words(extra_attrs=["size"]) if w["size"] >= 20), key=lambda w: w["top"])
    name = "".join(w["text"] for w in big).strip()
    return name if len(name) >= 3 else default


def parse(pdf_path, img_dir, img_prefix, default_series, log):
    products = []
    pdf, doc = pdfplumber.open(pdf_path), pdfium.PdfDocument(pdf_path)
    series = _series(pdf.pages[0], default_series) if pdf.pages else default_series
    for pi, page in enumerate(pdf.pages):
        words = page.extract_words(extra_attrs=["size"])
        titles = [w for w in words if 8.5 <= w["size"] <= 9.5 and 10 < w["top"] < 560]
        fins = [w for w in words if 6.5 <= w["size"] <= 7.5 and w["top"] < 560]
        for side in (0, 1):
            inside = (lambda w: w["x0"] < SPLIT_X) if side == 0 else (lambda w: w["x0"] >= SPLIT_X)
            tl = rows([w for w in titles if inside(w)])
            # a title can wrap onto a second line: join rows less than 14 pt apart
            heads = []
            for r in tl:
                if heads and r[0]["top"] - heads[-1]["last"] < 14:
                    heads[-1]["text"] += " " + " ".join(w["text"] for w in r)
                    heads[-1]["last"] = r[0]["top"]
                else:
                    heads.append({"top": r[0]["top"], "last": r[0]["top"], "text": " ".join(w["text"] for w in r)})
            frows = rows([w for w in fins if inside(w)])
            for hi, h in enumerate(heads):
                end = heads[hi + 1]["top"] if hi + 1 < len(heads) else 560
                box_end = heads[hi + 1]["top"] + 3 if hi + 1 < len(heads) else page.height  # a photo must sit inside its own box
                variants = []
                for r in frows:
                    if not (h["last"] < r[0]["top"] < end) or not CODE.match(r[-1]["text"]):
                        continue
                    variants.append({"art": r[-1]["text"], "finish": " ".join(w["text"] for w in r[:-1]), "width_mm": None, "price": None})
                if not variants:
                    continue
                x0, x1 = (0, SPLIT_X) if side == 0 else (SPLIT_X, page.width)
                ims = [im for im in page.images if h["top"] - 5 <= im["top"] and im["bottom"] <= box_end and (im["x1"] - im["x0"]) > 25 and (im["bottom"] - im["top"]) > 30
                       and (im["x1"] - im["x0"]) < 300 and (im["bottom"] - im["top"]) < 330 and x0 <= (im["x0"] + im["x1"]) / 2 < x1]
                ims.sort(key=lambda im: -(im["x1"] - im["x0"]) * (im["bottom"] - im["top"]))
                image = None
                if ims:
                    im = ims[0]
                    image = crop_image(doc, pi, page, (im["x0"], im["top"], im["x1"], im["bottom"]), img_dir, f"{img_prefix}_p{pi + 1}_{side}_{int(h['top'])}.jpg", log)
                products.append({"series": series, "line": "", "page": pi + 1, "title": h["text"], "specs": [], "variants": variants, "image": image})
        log(f"Page {pi + 1}: {sum(1 for p in products if p['page'] == pi + 1)} products")
    return products
