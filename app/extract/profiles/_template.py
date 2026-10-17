r"""Template for a new brand reader. Copy to <brand>.py (lowercase, no spaces) and edit.

Two ways to write a reader:

1. Tune the default block reader (most price lists): set PROFILE fields only.
   - brands:        brand names that should pick this reader automatically
   - code_tokens:   regex(es) for the article number, e.g. [r"^\d{5}-\d{3}$"] or [r"^[A-Z]{2}\d{6}$"]
   - series_header: regex on the page header text; group 1 = collection name
   - format_art:    function to display article numbers consistently
   - finish_codes:  {code: finish text} if the article number encodes the finish

2. Write parse() yourself when the layout is different, for example a price grid
   with one row per product and one column per finish. Use the helpers in
   pdf_parser (rows, parse_price, crop_image, largest_image) and return product
   dicts in the shape described at the top of pdf_parser.py.

Check your reader with:
    python scripts/try_reader.py tests/samples/<brand>.pdf --reader <name>
then add tests/samples/<brand>.expected.json and run pytest.
"""
import pdfplumber
import pypdfium2 as pdfium

from ..pdf_parser import Profile, crop_image, largest_image, parse_price, rows  # noqa: F401

PROFILE = Profile(name="template", label="Template (not used)", brands=[])


def parse(pdf_path, img_dir, img_prefix, default_series, log):
    """Example of a price-grid reader: header row lists finishes, each product row has a price per finish."""
    products = []
    pdf, doc = pdfplumber.open(pdf_path), pdfium.PdfDocument(pdf_path)
    for pi, page in enumerate(pdf.pages):
        lines = rows(page.extract_words(extra_attrs=["fontname", "size"]))
        finishes = None
        for ln in lines:
            texts = [w["text"] for w in ln]
            if texts and texts[0].lower() in ("code", "art.no.", "article"):
                finishes = texts[2:]  # e.g. ["Chrome", "Black", "Gold"]
                continue
            if finishes and len(texts) >= 2 + len(finishes) and all(parse_price(t) is not None for t in texts[-len(finishes):]):
                code, name = texts[0], " ".join(texts[1:-len(finishes)])
                prices = [parse_price(t) for t in texts[-len(finishes):]]
                y0 = ln[0]["top"] - 40
                bbox = largest_image(page, y0, ln[0]["bottom"] + 40)
                products.append({
                    "series": default_series, "line": "", "page": pi + 1, "title": name, "specs": [],
                    "variants": [{"art": f"{code}-{i + 1:02d}", "finish": f, "width_mm": None, "price": pr} for i, (f, pr) in enumerate(zip(finishes, prices))],
                    "image": crop_image(doc, pi, page, bbox, img_dir, f"{img_prefix}_p{pi + 1}_{int(y0)}.jpg", log) if bbox else None,
                })
        log(f"Page {pi + 1}: {sum(1 for p in products if p['page'] == pi + 1)} products")
    return products
