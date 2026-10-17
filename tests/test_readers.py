"""Every tests/samples/<name>.pdf with a <name>.expected.json is read and checked."""
import json
import tempfile
from pathlib import Path

import pytest

from app.extract import pdf_parser, profiles
from app.taxonomy import classify

SAMPLES = Path(__file__).parent / "samples"
CASES = [e for e in sorted(SAMPLES.glob("*.expected.json")) if e.with_name(e.name.replace(".expected.json", ".pdf")).exists()]


def test_registry_has_readers():
    keys = [r["key"] for r in profiles.all_readers()]
    assert "generic" in keys and "keuco" in keys and "template" not in keys
    assert profiles.for_brand("KEUCO") == "keuco" and profiles.for_brand("Unknown Brand") == "generic"


def test_price_formats():
    assert pdf_parser.parse_price("1,261.00") == 1261.0
    assert pdf_parser.parse_price("1.261,00") == 1261.0
    assert pdf_parser.parse_price("₹12,450.00") == 12450.0
    assert pdf_parser.parse_price("1,23,456.00") == 123456.0
    assert pdf_parser.parse_price("157.50") == 157.5
    assert pdf_parser.parse_price("2026") is None


@pytest.mark.parametrize("expected", CASES, ids=[c.name.split(".")[0] for c in CASES])
def test_sample_pdf(expected):
    exp = json.loads(expected.read_text())
    pdf = expected.with_name(expected.name.replace(".expected.json", ".pdf"))
    products, _ = pdf_parser.parse(str(pdf), Path(tempfile.mkdtemp()), "t", exp["reader"], "", log=lambda m: None)
    assert len(products) == exp["products"]
    assert sum(len(p["variants"]) for p in products) == exp["article_numbers"]
    unknown = sum(1 for p in products if (p.get("type") or classify(p["title"], p["specs"], p.get("series", ""))[0]) == "other")
    assert unknown <= exp.get("max_unrecognised", 0)


def test_template_grid_reader_example(tmp_path):
    """Keeps the worked example in profiles/_template.py runnable."""
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    from app.extract.profiles import _template

    img = tmp_path / "tap.png"
    Image.new("RGB", (60, 60), (120, 130, 140)).save(img)
    pdf = tmp_path / "grid.pdf"
    c = canvas.Canvas(str(pdf), pagesize=(595, 842))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, 760, "Code Product Chrome Black Gold")
    c.setFont("Helvetica", 9)
    for i, (code, name, prices) in enumerate([("AU101", "Basin mixer", ("4,500.00", "5,200.00", "6,100.00")),
                                              ("AU202", "Shower mixer exposed", ("7,250.00", "8,000.00", "9,400.00"))]):
        y = 700 - i * 120
        c.drawImage(ImageReader(str(img)), 300, y - 20, 50, 50)
        c.drawString(40, y, f"{code} {name} " + " ".join(prices))
    c.save()
    products = _template.parse(str(pdf), tmp_path, "t", "AURA", lambda m: None)
    assert [p["title"] for p in products] == ["Basin mixer", "Shower mixer exposed"]
    assert [v["price"] for v in products[1]["variants"]] == [7250.0, 8000.0, 9400.0]
    assert products[0]["variants"][2]["finish"] == "Gold" and products[0]["image"]
