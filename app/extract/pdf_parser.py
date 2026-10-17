"""PDF reading engine (no AI). Brand-specific rules live in app/extract/profiles/.

The default "block reader" handles price lists laid out as product blocks:

    BOLD PRODUCT TITLE
    • spec bullet            Art.-No.        Finish        Price
    • spec bullet            582 04 01 01 00 chrome-plated 157.50
    [product photo]          ...

A profile tunes it (article-number format, where the collection name sits), or
replaces it entirely with its own parse() for layouts that look nothing like this.

Every reader returns a list of product dicts:
    {"series": str, "line": str, "page": int, "title": str,
     "specs": [{"group": str|None, "items": [str]}],
     "variants": [{"art": str, "finish": str, "width_mm": int|None, "price": float|None}],
     "image": str|None}          # file name inside img_dir
Optional keys: "type" (a key from app/taxonomy.py TYPES) and "category"; when absent
they are worked out from the title.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium

BULLETS = ("•", "·", "–", "-", "▪", "■", "●")


@dataclass
class Profile:
    name: str = "generic"
    label: str = "General layout"
    brands: list = field(default_factory=list)  # brand names this reader is picked for automatically (case-insensitive)
    # article number: token regexes; "a\sb" means two words glued together, e.g. KEUCO "58204" + "010100"
    code_tokens: list = field(default_factory=lambda: [r"^[A-Z0-9][A-Z0-9.\-/]{2,}$"])
    code_min_digits: int = 4
    join_code_words: bool = True  # also accept codes split over several words ("GR 3321 0001")
    series_header: str = r"^([A-Z][A-Z0-9\-]{2,})(?:\s+(.+))?$"  # on the page header; group 1 = collection, group 2 = line
    header_max_y: float = 48  # points from the top of the page that count as the header
    format_art: object = None  # function(code) -> display string
    finish_codes: dict = field(default_factory=dict)  # finish code -> finish text, used by the review checks
    keep_numbers_in_finish: tuple = ("500", "650")  # numbers allowed between article no. and price (e.g. widths)


# ---------- helpers that custom readers can reuse ----------

def rows(words, tol=3):
    """Group pdfplumber words into lines (top within tol points), each sorted left to right."""
    out = []
    for w in sorted(words, key=lambda w: w["top"]):
        if out and abs(out[-1][0]["top"] - w["top"]) < tol:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(r, key=lambda w: w["x0"]) for r in out]


def parse_price(t):
    """'1,261.00' / '1.261,00' / '€157.50' / '₹12,450.00' -> float, else None."""
    t = t.strip().lstrip("€$£₹").replace(" ", "")
    if re.match(r"^\d{1,3}(,\d{3})+(\.\d{2})?$", t) and "," in t:
        return float(t.replace(",", ""))
    if re.match(r"^\d{1,2}(,\d{2})+,\d{3}(\.\d{2})?$", t):  # Indian grouping 1,23,456.00
        return float(t.replace(",", ""))
    if re.match(r"^\d+\.\d{2}$", t):
        return float(t)
    if re.match(r"^\d{1,3}(\.\d{3})+,\d{2}$", t) or re.match(r"^\d+,\d{2}$", t):
        return float(t.replace(".", "").replace(",", "."))
    return None


def crop_image(doc, page_index, page, bbox, img_dir, name, log=print):
    """Render a region (x0, top, x1, bottom in PDF points) of a page to img_dir/name. Returns name or None."""
    x0, top, x1, bottom = bbox
    try:
        bmp = doc[page_index].render(scale=3, crop=(x0, page.height - bottom, page.width - x1, top)).to_pil().convert("RGB")
        bmp.thumbnail((480, 480))
        bmp.save(Path(img_dir) / name, quality=80)
        return name
    except Exception as e:  # noqa
        log(f"Page {page_index + 1}: could not crop image ({e})")
        return None


def largest_image(page, y0, y1, min_top=48):
    ims = [im for im in page.images if y0 - 5 < im["top"] < y1 and im["top"] > min_top and (im["x1"] - im["x0"]) > 25]
    ims.sort(key=lambda im: -(im["x1"] - im["x0"]) * (im["bottom"] - im["top"]))
    return (ims[0]["x0"], ims[0]["top"], ims[0]["x1"], ims[0]["bottom"]) if ims else None


# ---------- the default block reader ----------

def _match_code(toks, prof):
    """Return (code, n_words) if the words at the start form an article number."""
    if not toks:
        return None
    for pat in prof.code_tokens:
        parts = pat.split(r"\s")
        if len(parts) > 1 and len(toks) >= len(parts) and all(re.match(p, t) for p, t in zip(parts, toks)):
            return "".join(toks[:len(parts)]), len(parts)
        if len(parts) == 1 and re.match(parts[0], toks[0]) and sum(ch.isdigit() for ch in toks[0]) >= prof.code_min_digits:
            n = 1
            if prof.join_code_words:
                while n < len(toks) - 1 and re.match(r"^[A-Z0-9.\-/]+$", toks[n]) and any(ch.isdigit() for ch in toks[n]) and parse_price(toks[n]) is None:
                    n += 1
            return " ".join(toks[:n]), n
    if prof.join_code_words:  # spaced numeric codes: "582 04 01 01 00"
        n = 0
        while n < len(toks) and re.match(r"^\d{2,5}$", toks[n]):
            n += 1
        if n >= 3 and sum(len(t) for t in toks[:n]) >= 8:
            return " ".join(toks[:n]), n
    return None


def block_reader(pdf_path, img_dir, img_prefix, prof: Profile, default_series="", log=print):
    pdf = pdfplumber.open(pdf_path)
    doc = pdfium.PdfDocument(pdf_path)
    products = []
    for pi, page in enumerate(pdf.pages):
        words = page.extract_words(extra_attrs=["fontname", "size"])
        if not words:
            log(f"Page {pi + 1}: no text (scanned page?)")
            continue
        vrows = []
        for r in rows(words):
            toks = [w["text"] for w in r]
            for k in range(len(toks)):
                m = _match_code(toks[k:], prof)
                if m:
                    code, n = m
                    rest = toks[k + n:]
                    pk = [i for i, t in enumerate(rest) if parse_price(t) is not None]
                    if pk:
                        vrows.append({"top": r[0]["top"], "x0": r[k]["x0"], "code": code, "rest": rest[:pk[-1]], "price": parse_price(rest[pk[-1]])})
                    break
        if not vrows:
            continue
        table_x = min(v["x0"] for v in vrows)
        body = [w for w in words if w["top"] > prof.header_max_y]
        sizes = sorted(round(w["size"], 1) for w in body)
        body_size = sizes[len(sizes) // 2] if sizes else 8
        head = " ".join(w["text"] for w in sorted([w for w in words if w["top"] <= prof.header_max_y], key=lambda w: w["x0"]))
        series, line = default_series, ""
        if prof.series_header and not (prof.name == "generic" and default_series):
            m = re.search(prof.series_header, head)
            if m:
                series, line = m.group(1), (m.group(2) or "") if m.lastindex and m.lastindex > 1 else ""
        left = [w for w in body if w["x0"] < table_x - 4]
        title_rows = [r for r in rows(left) if "bold" in r[-1]["fontname"].lower() and r[-1]["size"] >= body_size + 1.5
                      and not r[0]["text"].startswith(BULLETS)]
        starts, last = [], -99
        for r in title_rows:
            t = r[0]["top"]
            if starts and t - last < 20:
                last = t
                continue
            starts.append(t - 2)
            last = t
        if not starts:
            starts = [prof.header_max_y]
        for (y0, y1) in zip(starts, starts[1:] + [page.height + 1]):
            seg_rows = [v for v in vrows if y0 < v["top"] < y1]
            if not seg_rows:
                continue
            title, specs = [], []
            for r in rows([w for w in left if y0 < w["top"] < y1]):
                t = " ".join(w["text"] for w in r)
                bold = "bold" in r[-1]["fontname"].lower()
                if bold and r[-1]["size"] >= body_size + 1.5 and not specs:
                    title.append(t)
                    continue
                if bold and not t.startswith(BULLETS):
                    specs.append({"group": t, "items": []})
                    continue
                if not specs:
                    specs.append({"group": None, "items": []})
                if t.startswith(BULLETS):
                    specs[-1]["items"].append(t.lstrip("".join(BULLETS)).strip())
                elif specs[-1]["items"]:
                    specs[-1]["items"][-1] += " " + t
            specs = [g for g in specs if g["items"]]
            variants = []
            for v in seg_rows:
                rest = [t for t in v["rest"] if not re.match(r"^[\d.,]+$", t) or t in prof.keep_numbers_in_finish]
                width = None
                if len(rest) >= 2 and rest[1] == "mm" and rest[0].isdigit():
                    width, rest = int(rest[0]), rest[2:]
                art = prof.format_art(v["code"]) if prof.format_art else v["code"]
                variants.append({"art": art, "finish": " ".join(rest), "width_mm": width, "price": v["price"]})
            bbox = largest_image(page, y0, y1, prof.header_max_y)
            image = crop_image(doc, pi, page, bbox, img_dir, f"{img_prefix}_p{pi + 1}_{int(y0)}.jpg", log) if bbox else None
            products.append({"series": series, "line": line, "page": pi + 1, "title": " ".join(title) or "Untitled product",
                             "specs": specs, "variants": variants, "image": image})
        log(f"Page {pi + 1}: {sum(1 for p in products if p['page'] == pi + 1)} products")
    return products


def parse(pdf_path, img_dir, img_prefix, profile="generic", default_series="", log=print):
    """Read a PDF with the named reader. Returns (products, Profile)."""
    from .profiles import get
    mod = get(profile)
    prof = mod.PROFILE
    custom = getattr(mod, "parse", None)
    if custom:
        products = custom(pdf_path, Path(img_dir), img_prefix, default_series, log)
    else:
        products = block_reader(pdf_path, Path(img_dir), img_prefix, prof, default_series, log)
    return products, prof


# kept for code that imported the old names
_rows, _parse_price = rows, parse_price
