"""KEUCO price lists (e.g. Project Series 2025, RRP excl. VAT).

Layout: page header "TEVEO Fittings" / "TOPIA Accessories"; bold 11 pt product titles;
bullet specs; rows "582 04 01 01 00  chrome-plated  157.50". The 3rd group of the
article number is the finish code (01 chrome, 37 matt black, 71/75/79/83 PVD).
Sample: tests/samples/keuco.pdf → 88 products, 514 article numbers.
"""
import re

from ..pdf_parser import Profile


def format_art(code):
    c = re.sub(r"\s", "", code)
    return f"{c[:3]} {c[3:5]} {c[5:7]} {c[7:9]} {c[9:]}" if len(c) == 11 and c.isdigit() else code


PROFILE = Profile(
    name="keuco", label="KEUCO price list", brands=["KEUCO"],
    code_tokens=[r"^\d{11}$", r"^\d{5}$\s^\d{6}$"], code_min_digits=11, join_code_words=False,
    series_header=r"^([A-Z][A-Z0-9]+)\s+(Fittings|Accessories)", format_art=format_art,
    finish_codes={"01": "chrome-plated", "37": "matt black", "71": "brushed nickel PVD",
                  "75": "brushed light gold PVD", "79": "brushed rose gold PVD", "83": "brushed gunmetal grey PVD"},
)
