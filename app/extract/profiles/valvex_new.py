"""VALVEX "New products" flyer (e.g. AVOLA, ENKO, VARSO, ALIBI, ASSO). This flyer has article numbers but NO prices.

Layout: one product per page. 20 pt heading "<SERIES> mixer series", the product name in 12 pt under it, a wide
lifestyle photo, the product photo (lower left), a dimension drawing (vector art, no specs to read) and at the
bottom right a "FINISH  CODE" table, one row per finish ("Brushed Gold  2417670"). Some rows hold two article
numbers separated by "/" ("2417600 / 2417180-CHR"): each becomes its own article number with the same finish.
Prices are left empty (None). Not picked automatically (the main VALVEX catalogue reader owns the brand name):
choose it in the Reader list.
Sample: tests/samples/ENKO VARSO ALIBI ASSO.pdf
"""
import re

import pdfplumber
import pypdfium2 as pdfium

from ..pdf_parser import Profile, crop_image, rows

PROFILE = Profile(name="valvex_new", label="VALVEX new products flyer (no prices)", brands=[])

CODE = re.compile(r"^\d{6,8}(-[A-Z0-9]+)?$")


def parse(pdf_path, img_dir, img_prefix, default_series, log):
    products = []
    pdf, doc = pdfplumber.open(pdf_path), pdfium.PdfDocument(pdf_path)
    for pi, page in enumerate(pdf.pages):
        words = page.extract_words(extra_attrs=["size"])
        variants = []
        for r in rows([w for w in words if 7.5 <= w["size"] <= 8.5 and w["top"] > 500]):
            codes = [w["text"] for w in r if CODE.match(w["text"])]
            if not codes:
                continue
            finish = " ".join(w["text"] for w in r if not CODE.match(w["text"]) and w["text"] != "/")
            variants += [{"art": c, "finish": finish, "width_mm": None, "price": None} for c in codes]
        if not variants:
            continue
        head = " ".join(w["text"] for w in sorted((w for w in words if w["size"] >= 19 and w["top"] < 70), key=lambda w: w["x0"]) if not set(w["text"]) <= {"_"})
        series = re.sub(r"\s*mixer series$", "", head, flags=re.I).strip() or default_series
        title = " ".join(" ".join(w["text"] for w in r) for r in rows([w for w in words if 11.5 <= w["size"] <= 12.5 and 75 < w["top"] < 135])) or "Untitled product"
        # the product photo sits lower left, below the lifestyle photos (top of page) and left of the dimension drawing
        ims = [im for im in page.images if im["top"] >= 480 and (im["x0"] + im["x1"]) / 2 < 300 and (im["x1"] - im["x0"]) > 60 and (im["bottom"] - im["top"]) > 60]
        ims.sort(key=lambda im: -(im["x1"] - im["x0"]) * (im["bottom"] - im["top"]))
        image = None
        if ims:
            im = ims[0]
            image = crop_image(doc, pi, page, (im["x0"], im["top"], im["x1"], im["bottom"]), img_dir, f"{img_prefix}_p{pi + 1}.jpg", log)
        products.append({"series": series, "line": "", "page": pi + 1, "title": title, "specs": [], "variants": variants, "image": image})
        log(f"Page {pi + 1}: {series} · {title}")
    return products
