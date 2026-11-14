"""KEUCO Price List 2026 (export, RRP excl. VAT), the full catalogue: fittings, accessories,
mirror cabinets, bathroom furniture. Picked automatically for KEUCO uploads; the 2025 project
series list still reads with "KEUCO price list" if you choose it in the Reader list.

Layout (A4, 496 pages):
- Page header (20 pt): bold collection ("EDITION 11", "IXMO", "COLLECTION MOLL") then the line
  ("Fittings", "Accessories", "Bathroom furniture"). A rotated chapter tab sits at the right edge.
- Products are boxes separated by long horizontal rules. Each box: bold 11 pt title, bullet specs
  (bold 7 pt lines start a spec group, e.g. "Equipment", "Stop and diverter valve (...)"), a photo,
  a drawing, and one or more tables that start with a bold "Art.-No." caption row.
- Main table: one row per article. Article number = bold 5 digits + 6 characters
  ("51104" "010000" -> 511 04 01 00 00; furniture uses letters, "WW0801"). Columns vary
  (PUW, Width, Height, Depth, Rosette, Hinge, Illumination...); "Surface" or "Colour No." is the
  finish; "€" is the price (right-aligned, "1,483.00").
- Description tables ("Required accessories", "Optional accessories", "Spare part"): article,
  description, price. These are kept as spec lines on the product, not as variants. A box with only
  a description table (spare-part boxes) uses its rows as the product's variants.
Sample: tests/samples/keuco_2026.pdf
"""
import re

import pdfplumber
import pypdfium2 as pdfium

from ...taxonomy import finish_key
from ..pdf_parser import Profile, crop_image, parse_price, rows


def format_art(code):
    c = re.sub(r"\s", "", code)
    return f"{c[:3]} {c[3:5]} {c[5:7]} {c[7:9]} {c[9:]}" if len(c) == 11 else code


# Several products put two article families in one table (e.g. 595 56 / 595 57 diverter valves),
# so the "first groups differ" misprint check would flag hundreds of correct rows.
PROFILE = Profile(name="keuco_2026", label="KEUCO price list 2026 (full catalogue)", brands=["KEUCO"],
                  format_art=format_art, check_article_prefix=False)

# Titles the general keyword rules in taxonomy.classify() get wrong for this catalogue.
# Checked in order; "other" keeps parts and add-ons out of the solution builder's picks.
TYPE_RULES = [
    (r"^shower shelf", "shower_shelf"),
    (r"^rough part|^extension|adapter|decorative disc|cover cap|cover plate|luminaire|diverter valve|stop valve"
     r"|curtain|grab|seat|soap dispenser|glue set|mounting set|mounting rail|fixing bracket|hookable|drain cover", "other"),
    (r"^arm for shower head.*ceiling", "arm_ceiling"),
    (r"^arm for shower head", "arm_wall"),
    (r"^shower set .*mixer", "other"),
    (r"^thermostatic shower mixer concealed", "thermo_2f"),
    (r"shower mixer (set )?concealed", "conc_1f"),
    (r"^hygienic shower", "bidet_spray"),
    (r"^pillar tap", "basin_std"),
]


# Whole chapters that hold no fittings or bathroom accessories the solution builder uses.
NON_FITTING_LINES = ("bathroom furniture", "mirror cabinets", "care")


def _type_for(title):
    t = title.lower()
    for pat, typ in TYPE_RULES:
        if re.search(pat, t):
            return typ
    return None

RIGHT_EDGE = 545          # rotated chapter tab lives to the right of this
TOP, BOTTOM = 50, 800     # page header above, page number below
CODE_A = re.compile(r"^\d{5}$")
CODE_B = re.compile(r"^[0-9A-Z]{6}$|^\d{8}$")
BULLETS = ("•", "·", "▪")
CAPTIONS = ("Art.-No.", "Art.-Nr.", "Art.No.")  # one table on page 282 is captioned "Art.-Nr."
FINISH_COLS = ("surface", "colour no.", "colour", "finish")
DESC_TABLES = ("required accessories", "optional accessories", "spare part", "spare parts")
OPTION_WORDS = {"puw": ("with pop-up waste", "without pop-up waste")}


def _bold(w):
    return "bold" in w["fontname"].lower()


def _text(ws):
    return " ".join(w["text"] for w in ws)


def _header(page):
    ws = sorted([w for w in page.extract_words(extra_attrs=["fontname", "size"]) if w["top"] < 45 and w["size"] >= 15 and w["x0"] < 470],
                key=lambda w: w["x0"])
    series = re.sub(r"^COLLECTION\s+", "", _text([w for w in ws if _bold(w)]), flags=re.I).strip()
    line = _text([w for w in ws if not _bold(w)]).strip()
    return series, line


def _separators(page):
    ys = sorted({round(l["top"]) for l in page.lines + page.rects
                 if l["x1"] - l["x0"] > 440 and l["bottom"] - l["top"] < 2 and TOP < l["top"] < BOTTOM})  # box rules span the page; table underlines are shorter
    out = []
    for y in ys:
        if not out or y - out[-1] > 6:
            out.append(y)
    return out


def _is_code_row(r):
    return len(r) > 1 and _bold(r[0]) and CODE_A.match(r[0]["text"]) and CODE_B.match(r[1]["text"])


def _columns(head):
    """Header row -> list of (label, x0, x1). Words closer than 6 pt form one label ("Colour No.")."""
    cols = []
    for w in head[1:]:
        if cols and w["x0"] - cols[-1][2] < 6:
            cols[-1] = (cols[-1][0] + " " + w["text"], cols[-1][1], w["x1"])
        else:
            cols.append((w["text"], w["x0"], w["x1"]))
    return cols


def _cells(ws):
    cells = []
    for w in ws:
        if cells and w["x0"] - cells[-1][2] < 4.5:
            cells[-1] = (cells[-1][0] + " " + w["text"], cells[-1][1], w["x1"])
        else:
            cells.append((w["text"], w["x0"], w["x1"]))
    return cells


def _assign(cells, cols):
    """Each cell goes to the column whose header it lines up with (right- or left-aligned)."""
    out = {}
    for text, x0, x1 in cells:
        best = min(cols, key=lambda c: min(abs(x1 - c[2]), abs(x0 - c[1])))
        out[best[0]] = (out[best[0]] + " " + text) if best[0] in out else text
    return out


def _variant(r, cols):
    code = r[0]["text"] + r[1]["text"]
    vals = _assign(_cells(r[2:]), cols)
    price = None
    finish, opts, width = "", [], None
    for label, val in vals.items():
        lab = label.lower()
        if label == "€":
            price = parse_price(val.split()[-1]) if val else None
        elif lab in FINISH_COLS:
            finish = f"Colour No. {val}" if lab == "colour no." and re.match(r"^[\d, ]+$", val) else val
        elif lab in OPTION_WORDS and val.lower() in ("yes", "no"):
            opts.append(OPTION_WORDS[lab][0 if val.lower() == "yes" else 1])
        elif lab == "width" and re.match(r"^\d+ mm$", val) and width is None:
            width = int(val.split()[0])
        else:
            opts.append(f"{label}: {val}")
    return {"art": format_art(code), "finish": ", ".join([finish] + opts) if finish else ", ".join(opts),
            "finish_key": finish_key(finish) if finish else "other", "width_mm": width, "price": price}


def _desc_line(r):
    code = format_art(r[0]["text"] + r[1]["text"])
    rest = r[2:]
    price = parse_price(rest[-1]["text"]) if rest else None
    desc = _text(rest[:-1] if price is not None else rest)
    return code, desc, price


def _specs(ws):
    groups = [{"group": None, "items": []}]
    for r in rows(ws):
        t = _text(r)
        if r[0]["text"] in BULLETS or r[0]["text"].startswith(BULLETS):
            groups[-1]["items"].append(t.lstrip("".join(BULLETS)).strip())
        elif _bold(r[0]) and r[0]["size"] < 9:
            if groups[-1]["group"] and not groups[-1]["items"]:   # a bold heading over several lines
                groups[-1]["group"] += " " + t
            else:
                groups.append({"group": t, "items": []})
        elif groups[-1]["items"] and r[0]["x0"] > 60.5:   # wrapped bullet line (indented)
            groups[-1]["items"][-1] += " " + t
        else:
            groups[-1]["items"].append(t)
    # bold lines with nothing under them are notes ("Not available in special finishes.")
    notes = [g["group"] for g in groups if g["group"] and not g["items"]]
    groups = [g for g in groups if g["items"]]
    if notes:
        groups.append({"group": "Notes", "items": notes})
    return groups


def _block(page, ws, top, bottom):
    """One box -> list of (title_words, spec_words, tables, y0). Usually one product per box."""
    bw = [w for w in ws if top < w["top"] < bottom]
    # tables: caption row "Art.-No." then code rows. Only words right of the caption belong to the
    # table, so spec text running down the left column doesn't break the rows apart.
    tables, used = [], set()
    for cap in sorted([w for w in bw if w["text"] in CAPTIONS and _bold(w)], key=lambda w: w["top"]):
        rws = rows([w for w in bw if w["x0"] >= cap["x0"] - 3 and w["top"] > cap["top"] - 3])
        head = rws[0]
        label = _text(head[1:]).lower()
        cur = {"kind": "desc" if any(label.startswith(d) for d in DESC_TABLES) else "main",
               "caption": re.sub(r"\s*€$", "", _text(head[1:])).strip(), "cols": _columns(head), "rows": [],
               "top": cap["top"], "x0": cap["x0"]}
        tables.append(cur)
        for w in head:
            used.add(id(w))
        for r in rws[1:]:
            t = _text(r).lower()
            if r[0]["text"] in CAPTIONS:
                break
            if _is_code_row(r):
                cur["rows"].append(r)
            elif _bold(r[0]) and any(t.startswith(d) for d in DESC_TABLES):
                # a second caption inside the same table, e.g. "Optional accessories" under "Spare part"
                cur = {"kind": "desc", "caption": _text(r).strip(), "cols": [], "rows": [], "top": r[0]["top"], "x0": cap["x0"]}
                tables.append(cur)
            elif cur["rows"] or r[0]["top"] - cap["top"] > 30:
                break
            else:
                continue
            for w in r:
                used.add(id(w))
    if not tables:
        return []
    table_left = min(t["x0"] for t in tables)
    first_table = min(t["top"] for t in tables)
    rest = [w for w in bw if id(w) not in used and 6.5 <= w["size"] <= 12]
    titles = [w for w in rest if _bold(w) and w["size"] >= 10 and w["x1"] < 300]
    title_tops = sorted({round(w["top"]) for w in titles})
    # split the box when a second title starts below an earlier product's table
    starts = []
    for t in title_tops:
        if not starts or (any(starts[-1] < tb["top"] < t for tb in tables)):
            starts.append(t)
    if not starts:
        starts = [top]
    out = []
    for k, y0 in enumerate(starts):
        y1 = starts[k + 1] if k + 1 < len(starts) else bottom
        tws = [w for w in titles if y0 - 2 <= w["top"] < y1]
        sws = [w for w in rest if y0 - 2 <= w["top"] < y1 and w not in tws and w["size"] < 10
               and (w["x1"] < table_left - 2 or (w["top"] < first_table - 2 and w["x1"] < 240))]
        tbs = [t for t in tables if y0 - 2 <= t["top"] < y1]
        out.append((tws, sws, tbs, y0, y1))
    return out


def parse(pdf_path, img_dir, img_prefix, default_series, log):
    products = []
    pdf, doc = pdfplumber.open(pdf_path), pdfium.PdfDocument(pdf_path)
    for pi, page in enumerate(pdf.pages):
        ws = [w for w in page.extract_words(extra_attrs=["fontname", "size"]) if w["x0"] < RIGHT_EDGE and TOP < w["top"] < BOTTOM]
        if not any(w["text"] in CAPTIONS for w in ws):
            continue
        series, line = _header(page)
        series = series or default_series
        edges = [TOP] + _separators(page) + [BOTTOM]
        for top, bottom in zip(edges, edges[1:]):
            for tws, sws, tbs, y0, y1 in _block(page, ws, top, bottom):
                variants, specs = [], _specs(sws)
                for t in tbs:
                    if t["kind"] == "main":
                        variants += [_variant(r, t["cols"]) for r in t["rows"]]
                for t in tbs:
                    if t["kind"] == "desc":
                        lines = [_desc_line(r) for r in t["rows"]]
                        if not variants and not any(tb["kind"] == "main" for tb in tbs):
                            variants += [{"art": c, "finish": d, "finish_key": finish_key(d), "width_mm": None, "price": p} for c, d, p in lines]
                        else:
                            specs.append({"group": t["caption"], "items": [f"{c}  {d}" + (f"  ({p:,.2f})" if p is not None else "") for c, d, p in lines]})
                if not variants:
                    continue
                title = re.sub(r"(?<=[a-z])- (?=[a-z])", "-", " ".join(_text(r) for r in rows(tws))) or "Untitled product"
                typ = _type_for(title) or ("other" if line.lower() in NON_FITTING_LINES else None)
                ims = [im for im in page.images if y0 - 5 <= im["top"] < y1 and im["top"] > TOP and (im["x1"] - im["x0"]) > 40 and im["x0"] > 150]
                ims.sort(key=lambda im: -(im["x1"] - im["x0"]) * (im["bottom"] - im["top"]))
                image = None
                if ims:
                    im = ims[0]
                    image = crop_image(doc, pi, page, (im["x0"], im["top"], im["x1"], im["bottom"]), img_dir,
                                       f"{img_prefix}_p{pi + 1}_{int(y0)}.jpg", log)
                prod = {"series": series, "line": line, "page": pi + 1, "title": title,
                        "specs": specs, "variants": variants, "image": image}
                if typ:
                    prod["type"], prod["name"] = typ, title
                    if typ == "other":  # known not to be a fitting: no "type not recognised" warning on review
                        prod["attributes"] = {"no_fitting_type": True}
                products.append(prod)
        if pi % 50 == 0:
            log(f"Page {pi + 1}: {len(products)} products so far")
    log(f"Done reading: {len(products)} products")
    return products
