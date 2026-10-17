"""Checks run on a catalog before it is published. Each finding is stored on the
variant (flags) or the product (attributes.issues) and shown on the review screen."""
from collections import Counter


def validate(products, profile=None):
    """products: list of dicts with 'variants' (art, finish, finish_key, width_mm, price). Mutates in place."""
    prices = {}
    for p in products:
        for v in p["variants"]:
            prices.setdefault(v["art"].replace(" ", ""), set()).add(v.get("price"))
    for p in products:
        issues = []
        if not p["variants"]:
            issues.append("No article numbers or prices found.")
        if not p.get("image"):
            issues.append("No product photo. Upload one on the review screen.")
        if p.get("type") == "other":
            issues.append("Type not recognised. Set the type so the solution builder can use this product.")
        vs = p["variants"]
        for v in vs:
            v["flags"] = [f for f in v.get("flags", []) if f.startswith("Admin:")]
        # prefix consistency (spaced numeric article numbers)
        spaced = [v for v in vs if " " in v["art"] and v["art"].replace(" ", "").isdigit()]
        if len(spaced) >= 3:
            pref = Counter(v["art"][:6] for v in spaced).most_common(1)[0][0]
            for v in spaced:
                if v["art"][:6] != pref:
                    v["flags"].append(f"Article number starts {v['art'][:6]}, the other finishes start {pref}. Likely misprint; confirm with the brand.")
        # finish code check (brand-specific)
        if profile and profile.finish_codes:
            for v in spaced:
                code = v["art"].split()[2] if len(v["art"].split()) > 2 else None
                if code in profile.finish_codes and profile.finish_codes[code] != v["finish"]:
                    v["flags"].append(f"Finish code {code} usually means '{profile.finish_codes[code]}', but the row says '{v['finish']}'.")
        # price checks
        for v in vs:
            if v.get("price") in (None, 0):
                v["flags"].append("Price missing.")
            if len(prices[v["art"].replace(" ", "")]) > 1:
                v["flags"].append("This article number appears again in the catalog with a different price.")
        # PVD finishes of one product are normally priced the same
        for w in set(v.get("width_mm") for v in vs):
            pvd = [v for v in vs if "pvd" in v["finish"].lower() and v.get("width_mm") == w and v.get("price")]
            if len(pvd) >= 3:
                common, n = Counter(v["price"] for v in pvd).most_common(1)[0]
                if n >= 2:
                    for v in pvd:
                        if v["price"] != common:
                            v["flags"].append(f"Price {v['price']:.2f} differs from the other PVD finishes ({common:.2f}). Check the price list.")
        for v in vs:
            v["flags"] = [f for f in v["flags"] if f not in v.get("accepted", [])]
        p.setdefault("attributes", {})["issues"] = issues
    return products
