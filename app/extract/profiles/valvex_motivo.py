"""VALVEX MOTIVO brochure (English). Article numbers but NO prices.

Layout: spreads (839 x 595 pt; the cover and back are single pages). Each page half has one column of products,
the right half sometimes a lifestyle photo instead. A product cell: a 9 pt title, then a 7 pt "FINISH  CODE"
header and one row per finish ("Brushed Gold  2457390-BAPV", with a small colour swatch picture in front).
The product photo sits to the right of that table, followed by line drawings (dimensions only, not read).
The collection name is printed in the page footer ("4 | MOTIVO"). Prices are left empty (None).
Not picked automatically (the main VALVEX catalogue reader owns the brand name): choose it in the Reader list.
Sample: tests/samples/MOTIVO Valvex.pdf
"""
import re
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_raw
from PIL import Image

from ..pdf_parser import Profile, crop_image, rows

PROFILE = Profile(name="valvex_motivo", label="VALVEX MOTIVO brochure (no prices)", brands=[])

# titles the keyword rules would file wrongly: the "bidet mixer" is a concealed mixer with a hand spray (health faucet set)
TYPE_RULES = {"wall mounted bidet mixer": ("bidet_spray", "Wall mounted bidet mixer with hand spray")}

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
        # a cell is anchored by its "FINISH  CODE" header row
        heads = [w for w in words if w["text"].lower() == "finish" and 6.5 <= w["size"] <= 7.5]
        if not heads:
            continue
        series = _series(page, default_series)
        half = page.width / 2 if page.width > 600 else page.width
        for h in heads:
            left, right = (0, half) if h["x0"] < half else (half, page.width)
            same = sorted(o["top"] for o in heads if left <= o["x0"] < right)
            below = [t for t in same if t > h["top"]]
            end = min(below) - 30 if below else 570          # the next title starts about 29 pt above its header
            inside = [w for w in words if left <= w["x0"] < right]
            title_rows = rows([w for w in inside if 8.5 <= w["size"] <= 9.5 and h["top"] - 45 < w["top"] < h["top"]])
            title = " ".join(" ".join(w["text"] for w in r) for r in title_rows)
            top = min((w["top"] for r in title_rows for w in r), default=h["top"] - 30)
            variants = []
            for r in rows([w for w in inside if 6.5 <= w["size"] <= 7.5 and h["top"] + 4 < w["top"] < end]):
                if CODE.match(r[-1]["text"]):
                    variants.append({"art": r[-1]["text"], "finish": " ".join(w["text"] for w in r[:-1]).strip(), "width_mm": None, "price": None})
            if not variants:
                continue
            # the photo is the first picture right of the table; line drawings follow it, swatches are tiny
            ims = [im for im in page.images if left <= im["x0"] and im["x1"] <= right + 2 and im["x0"] > h["x0"] + 80
                   and top - 15 <= (im["top"] + im["bottom"]) / 2 <= end + 15
                   and 40 < (im["x1"] - im["x0"]) < 300 and (im["bottom"] - im["top"]) > 40]
            ims.sort(key=lambda im: im["x0"])
            image = None
            if ims:
                im = ims[0]
                name = f"{img_prefix}_p{pi + 1}_{int(left)}_{int(h['top'])}.jpg"
                image = _raw_photo(doc, pi, page, im, img_dir, name) or crop_image(doc, pi, page, (im["x0"], im["top"], im["x1"], im["bottom"]), img_dir, name, log)
            prod = {"series": series, "line": "", "page": pi + 1, "title": title or "Untitled product", "specs": [], "variants": variants, "image": image}
            if title.lower() in TYPE_RULES:
                prod["type"], prod["name"] = TYPE_RULES[title.lower()]
            products.append(prod)
        log(f"Page {pi + 1}: {sum(1 for p in products if p['page'] == pi + 1)} products")
    return products
