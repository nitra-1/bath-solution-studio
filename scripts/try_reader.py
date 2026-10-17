"""Try a brand reader on a PDF without the app. Used when creating or fixing a reader.

    python scripts/try_reader.py tests/samples/brand.pdf                 # automatic reader
    python scripts/try_reader.py tests/samples/brand.pdf --reader generic
    python scripts/try_reader.py tests/samples/brand.pdf --dump-page 7   # every word with font, size, position
    python scripts/try_reader.py tests/samples/brand.pdf --json out.json # full output
    python scripts/try_reader.py tests/samples/brand.pdf --write-expected  # save counts for the test suite
"""
import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.extract import pdf_parser, profiles  # noqa: E402
from app.extract.ingest import _attributes, _looks_poor  # noqa: E402
from app.extract.validate import validate  # noqa: E402
from app.taxonomy import TYPE_CAT, classify, finish_key  # noqa: E402


def dump_page(pdf, n):
    import pdfplumber
    page = pdfplumber.open(pdf).pages[n - 1]
    print(f"Page {n}: {page.width:.0f} x {page.height:.0f} pt, {len(page.images)} images")
    for im in page.images:
        print(f"  IMAGE x={im['x0']:.0f}-{im['x1']:.0f} y={im['top']:.0f}-{im['bottom']:.0f}")
    for r in pdf_parser.rows(page.extract_words(extra_attrs=["fontname", "size"])):
        print(f"  y={r[0]['top']:6.1f} " + " | ".join(f"{w['text']}[x{w['x0']:.0f} {w['size']:.1f}{' B' if 'bold' in w['fontname'].lower() else ''}]" for w in r))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--reader", default="auto")
    ap.add_argument("--brand", default="")
    ap.add_argument("--series", default="")
    ap.add_argument("--dump-page", type=int)
    ap.add_argument("--json")
    ap.add_argument("--write-expected", action="store_true")
    ap.add_argument("--show", type=int, default=5, help="how many sample products to print")
    a = ap.parse_args()
    if a.dump_page:
        return dump_page(a.pdf, a.dump_page)
    reader = a.reader if a.reader != "auto" else profiles.for_brand(a.brand or Path(a.pdf).stem)
    img_dir = Path(tempfile.mkdtemp(prefix="reader-imgs-"))
    logs = []
    products, prof = pdf_parser.parse(a.pdf, img_dir, "t", reader, a.series, log=logs.append)
    for p in products:
        if not p.get("type"):
            p["type"], p["name"] = classify(p["title"], p["specs"], p.get("series", ""))
        p["category"] = p.get("category") or TYPE_CAT.get(p["type"], "Other")
        for v in p["variants"]:
            v["finish_key"] = finish_key(v["finish"])
        p["attributes"] = _attributes(p["specs"])
    validate(products, prof)
    n_v = sum(len(p["variants"]) for p in products)
    print(f"Reader: {reader}   Products: {len(products)}   Article numbers: {n_v}   Photos cropped to: {img_dir}")
    print("Pages with products:", len({p['page'] for p in products}), " Collections:", dict(Counter(p['series'] for p in products)))
    checks = {
        "untitled products": sum(1 for p in products if p["title"] == "Untitled product"),
        "type not recognised": sum(1 for p in products if p["type"] == "other"),
        "no photo": sum(1 for p in products if not p.get("image")),
        "no article numbers": sum(1 for p in products if not p["variants"]),
        "rows without finish text": sum(1 for p in products for v in p["variants"] if not v["finish"]),
        "rows without price": sum(1 for p in products for v in p["variants"] if v["price"] is None),
        "rows with review flags": sum(1 for p in products for v in p["variants"] if v["flags"]),
        "finish family 'other'": sum(1 for p in products for v in p["variants"] if v["finish_key"] == "other"),
    }
    for k, v in checks.items():
        print(f"  {k:28s} {v}")
    print("VERDICT:", "looks poor, needs work" if _looks_poor(products) else "looks usable, check the samples below")
    no_text = [l for l in logs if "no text" in l]
    if no_text:
        print(f"  {len(no_text)} pages have no text (photo pages, or scans this reader can't read).")
    if checks["type not recognised"]:
        print("  Unrecognised titles:", [p["title"] for p in products if p["type"] == "other"][:15])
    for p in products[: a.show]:
        print(f"\n- p{p['page']} [{p['series']}] {p['title']!r} -> {p['type']}")
        for g in p["specs"]:
            print(f"    {g['group'] or ''} {g['items'][:4]}")
        for v in p["variants"][:6]:
            print(f"    {v['art']:22s} {v['finish']:30s} {v['price']}  {v['flags'] or ''}")
    if a.json:
        Path(a.json).write_text(json.dumps(products, indent=1, ensure_ascii=False))
        print("\nWrote", a.json)
    if a.write_expected:
        exp = Path(a.pdf).with_suffix(".expected.json")
        exp.write_text(json.dumps({"reader": reader, "brand": a.brand or Path(a.pdf).stem, "products": len(products),
                                   "article_numbers": n_v, "max_unrecognised": checks["type not recognised"]}, indent=1))
        print("\nWrote", exp)


if __name__ == "__main__":
    main()
