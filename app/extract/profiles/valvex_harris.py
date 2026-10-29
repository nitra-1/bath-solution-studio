"""VALVEX HARRIS brochure (English). This brochure has article numbers but NO prices.

Layout: landscape spreads, the left page holding up to three columns (left edges about 28, 221 and 448 pt)
in two rows. Each cell has a product photo, a 9 pt title (usually two lines, under the photo or beside it),
a "finish  code" table and one row per finish ("satin copper  2419580"). The collection name is printed in
the page footer ("2 | HARRIS"). There is no spec text (dimensions are not given). Prices are left empty (None).
Not picked automatically (the main VALVEX catalogue reader owns the brand name): choose it in the Reader list.
Sample: tests/samples/HARRIS Valvex.pdf
"""
import re
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from PIL import Image

from ..pdf_parser import Profile, crop_image, rows

PROFILE = Profile(name="valvex_harris", label="VALVEX HARRIS brochure (no prices)", brands=[])

CODE = re.compile(r"^\d{6,8}(-[A-Z0-9]+)?$")


def _series(page, default):
    foot = [w["text"] for w in page.extract_words() if w["top"] > 565 and re.match(r"^[A-Z]{3,}$", w["text"])]
    return foot[0] if foot else default


def _raw_photo(doc, pi, page, im, img_dir, name):
    """Save the embedded picture itself (the page render would also catch title text printed over the photo)."""
    try:
        pg = doc[pi]
        height = pg.get_size()[1]
        for o in pg.get_objects(filter=[pdfium_raw.FPDF_PAGEOBJ_IMAGE]):
            l, b, r, t = o.get_bounds()
            if abs(l - im["x0"]) < 2 and abs(r - im["x1"]) < 2 and abs((height - t) - im["top"]) < 2 and abs((height - b) - im["bottom"]) < 2:
                pil = o.get_bitmap(render=True).to_pil().convert("RGBA")  # keeps the picture's transparent background
                flat = Image.new("RGB", pil.size, "white")
                flat.paste(pil, mask=pil.split()[3])
                pil = flat
                pil.thumbnail((480, 480))
                pil.save(Path(img_dir) / name, quality=82)
                return name
    except Exception:  # noqa
        pass
    return None


def parse(pdf_path, img_dir, img_prefix, default_series, log):
    products = []
    pdf, doc = pdfplumber.open(pdf_path), pdfium.PdfDocument(pdf_path)
    for pi, page in enumerate(pdf.pages):
        words = page.extract_words(extra_attrs=["size"])
        # a cell is anchored by its "finish  code" header row
        heads = sorted((w for w in words if w["text"].lower() == "finish" and 6.5 <= w["size"] <= 7.5), key=lambda w: (w["x0"], w["top"]))
        if not heads:
            continue
        series = _series(page, default_series)
        xs = []
        for w in sorted(heads, key=lambda w: w["x0"]):
            if not xs or w["x0"] - xs[-1] > 15:
                xs.append(w["x0"])
        for h in heads:
            ci = max(i for i, x in enumerate(xs) if x <= h["x0"] + 8)
            left = xs[ci] - 3
            right = xs[ci + 1] - 3 if ci + 1 < len(xs) else page.width
            above = [o["top"] for o in heads if o is not h and xs[max(i for i, x in enumerate(xs) if x <= o["x0"] + 8)] == xs[ci] and o["top"] < h["top"]]
            prev = max(above) if above else -50
            below = [o["top"] for o in heads if o is not h and xs[max(i for i, x in enumerate(xs) if x <= o["x0"] + 8)] == xs[ci] and o["top"] > h["top"]]
            end = min(below) - 60 if below else 570
            inside = [w for w in words if left <= w["x0"] < right]
            title = " ".join(" ".join(w["text"] for w in r) for r in rows([w for w in inside if 8.5 <= w["size"] <= 9.5 and h["top"] - 55 < w["top"] < h["top"]]))
            variants = []
            for r in rows([w for w in inside if 7.5 <= w["size"] <= 8.5 and h["top"] < w["top"] < end]):
                if CODE.match(r[-1]["text"]):
                    variants.append({"art": r[-1]["text"], "finish": " ".join(w["text"] for w in r[:-1]).strip(), "width_mm": None, "price": None})
            if not variants:
                continue
            ims = [im for im in page.images if left <= (im["x0"] + im["x1"]) / 2 < right and im["top"] >= prev + 10 and im["bottom"] <= h["top"] + 12
                   and 40 < (im["x1"] - im["x0"]) < 300 and (im["bottom"] - im["top"]) > 40]
            ims.sort(key=lambda im: -(im["x1"] - im["x0"]) * (im["bottom"] - im["top"]))
            image = None
            if ims:
                im = ims[0]
                name = f"{img_prefix}_p{pi + 1}_{ci}_{int(h['top'])}.jpg"
                image = _raw_photo(doc, pi, page, im, img_dir, name) or crop_image(doc, pi, page, (im["x0"], im["top"], im["x1"], im["bottom"]), img_dir, name, log)
            products.append({"series": series, "line": "", "page": pi + 1, "title": title or "Untitled product", "specs": [], "variants": variants, "image": image})
        log(f"Page {pi + 1}: {sum(1 for p in products if p['page'] == pi + 1)} products")
    return products
