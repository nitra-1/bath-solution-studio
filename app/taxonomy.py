"""Shared vocabulary: product categories, fitting types and finish families.

The solution builder works on these normalised types, so a product from any
brand can be used once its type is set (by the parser or by the admin).
"""
import re

CATEGORIES = ["Washbasin", "Bidet", "Shower", "Bath tub", "Hand & head showers", "Accessories", "Other"]

# key, label, category
TYPES = [
    ("basin_std", "Basin mixer, standard height", "Washbasin"),
    ("basin_mid", "Basin mixer, raised", "Washbasin"),
    ("basin_tall", "Basin mixer, tall (vessel basin)", "Washbasin"),
    ("basin_wall", "Basin mixer, wall-mounted concealed", "Washbasin"),
    ("basin_3hole", "Basin mixer, three-hole", "Washbasin"),
    ("waste", "Basin waste plug", "Washbasin"),
    ("trap", "Bottle trap", "Washbasin"),
    ("angle_valve", "Angle valve", "Washbasin"),
    ("bidet_spray", "Bidet spray set / health faucet", "Bidet"),
    ("bidet_concealed", "Bidet mixer, concealed", "Bidet"),
    ("shower_exposed", "Shower mixer, exposed", "Shower"),
    ("shower_exposed_bar", "Shower mixer, exposed (bar design)", "Shower"),
    ("shower_thermo_exposed", "Thermostatic shower mixer, exposed", "Shower"),
    ("conc_1f", "Concealed mixer, 1 function", "Shower"),
    ("conc_2f_push", "Concealed mixer, 2 functions, push diverter", "Shower"),
    ("conc_2f_rot", "Concealed mixer, 2 functions, rotating diverter", "Shower"),
    ("thermo_2f", "Thermostatic concealed, 2 functions", "Shower"),
    ("thermo_3f", "Thermostatic concealed, 3 functions", "Shower"),
    ("bath_exposed", "Bath mixer, exposed", "Bath tub"),
    ("bath_exposed_bar", "Bath mixer, exposed (bar design)", "Bath tub"),
    ("bath_exposed_set", "Bath mixer set with hand shower, exposed", "Bath tub"),
    ("bath_thermo_exposed", "Thermostatic bath mixer, exposed", "Bath tub"),
    ("bath_floor", "Bath mixer, floor-standing", "Bath tub"),
    ("bath_4hole", "Bath mixer, four-hole bath rim", "Bath tub"),
    ("bath_filler", "Bath filler / spout", "Bath tub"),
    ("bath_filler_div", "Bath filler with diverter", "Bath tub"),
    ("hand_shower", "Hand shower", "Hand & head showers"),
    ("shower_hose", "Shower hose", "Hand & head showers"),
    ("head_250", "Overhead shower, about 250 mm", "Hand & head showers"),
    ("head_300", "Overhead shower, about 300 mm", "Hand & head showers"),
    ("arm_wall", "Shower arm, wall-mounted", "Hand & head showers"),
    ("arm_ceiling", "Shower arm, ceiling-mounted", "Hand & head showers"),
    ("hose_union", "Hose union / wall outlet", "Hand & head showers"),
    ("hose_union_bracket", "Hose union with bracket", "Hand & head showers"),
    ("hose_union_set", "Hose union set with hand shower", "Hand & head showers"),
    ("hand_bracket", "Hand shower bracket", "Hand & head showers"),
    ("rail", "Hand shower sliding rail", "Hand & head showers"),
    ("rail_set", "Sliding rail set with hand shower", "Hand & head showers"),
    ("hook", "Towel hook", "Accessories"),
    ("hook_double", "Towel hook, double", "Accessories"),
    ("towel_ring", "Towel ring", "Accessories"),
    ("towel_rail", "Towel rail", "Accessories"),
    ("towel_rack", "Towel rack", "Accessories"),
    ("tp_rigid", "Toilet paper holder", "Accessories"),
    ("tp_swivel", "Toilet paper holder, swivelling", "Accessories"),
    ("tp_shelf", "Toilet paper holder with shelf", "Accessories"),
    ("tp_double_shelf", "Toilet paper holder, double, with shelf", "Accessories"),
    ("shower_shelf", "Shower shelf / basket", "Accessories"),
    ("mirror", "Cosmetic mirror", "Accessories"),
    ("other", "Other (not used by the solution builder)", "Other"),
]
TYPE_CAT = {k: c for k, _, c in TYPES}
TYPE_LABEL = {k: l for k, l, _ in TYPES}

FINISHES = [
    ("chrome", "Chrome", "C9CED3"), ("black", "Matt black", "232323"), ("nickel", "Brushed nickel", "A9A498"),
    ("gold", "Gold", "C8A96B"), ("rosegold", "Rose gold", "B97E6B"), ("gunmetal", "Gunmetal", "5B5E61"),
    ("steel", "Stainless steel", "B4B8BB"), ("brass", "Brass / bronze", "9C7A3C"), ("white", "White", "F2F2F2"),
    ("other", "Other", "9AA3A8"),
]


def finish_key(text: str) -> str:
    t = (text or "").lower()
    rules = [("rose", "rosegold"), ("gunmetal", "gunmetal"), ("graphite", "gunmetal"), ("anthracite", "gunmetal"),
             ("black", "black"), ("nickel", "nickel"), ("gold", "gold"), ("champagne", "gold"), ("brass", "brass"),
             ("bronze", "brass"), ("copper", "rosegold"), ("stainless", "steel"), ("steel", "steel"), ("inox", "steel"),
             ("white", "white"), ("chrom", "chrome")]
    for needle, key in rules:
        if needle in t:
            return key
    return "other"


def _has(specs, s):
    s = s.lower()
    return any(s in i.lower() for g in specs for i in g["items"])


def _num(specs, label):
    for g in specs:
        for i in g["items"]:
            m = re.match(label + r"[^:]*:\s*([\d\-\s.,]+)", i, re.I)
            if m:
                try:
                    return float(m.group(1).split("-")[0].strip().replace(",", "."))
                except ValueError:
                    pass
    return None


def classify(title: str, specs: list, series: str = ""):
    """Return (type, display name). Works on English product names."""
    T = (title or "").lower().replace("incl. rough part", "").strip()
    name = title.replace("incl. rough part", "").strip()
    has = lambda s: _has(specs, s)
    t = None
    if "basin" in T and "waste" in T:
        t, name = "waste", "Basin waste plug"
    elif "bottle trap" in T or T == "trap" or "siphon" in T:
        t = "trap"
    elif "angle valve" in T or "angle cock" in T or "stop cock" in T:
        t = "angle_valve"
    elif "basin" in T and ("concealed" in T or "wall" in T):
        t, name = "basin_wall", "Basin mixer, wall-mounted (concealed)"
    elif "basin" in T and ("three-hole" in T or "3-hole" in T or "3 hole" in T):
        t = "basin_3hole"
    elif "basin" in T and ("mixer" in T or "tap" in T or "faucet" in T):
        h = _num(specs, "Outlet height")
        if T.endswith(" 150") and series.upper() == "TOPIA":
            t, name = "basin_3hole", "Three-hole basin mixer 150"
        elif h is None:
            t = "basin_std"
        else:
            t = "basin_tall" if h > 200 else ("basin_mid" if h > 140 else "basin_std")
    elif "bidet" in T and ("spray" in T or "health" in T or "shattaf" in T):
        t = "bidet_spray"
    elif "health faucet" in T or "hand spray" in T:
        t = "bidet_spray"
    elif "bidet" in T:
        t, name = "bidet_concealed", "Bidet mixer, concealed" if "concealed" in T else name
    elif "thermostat" in T and "bath" in T:
        t = "bath_thermo_exposed"
    elif "thermostat" in T and ("3 function" in T or "three" in T):
        t, name = "thermo_3f", "Thermostatic mixer, concealed, 3 functions"
    elif "thermostat" in T and ("concealed" in T or "2 function" in T):
        t, name = "thermo_2f", "Thermostatic mixer, concealed, 2 functions"
    elif "thermostat" in T:
        t = "shower_thermo_exposed"
    elif "bath" in T and ("floor" in T or "freestanding" in T or "free-standing" in T):
        t, name = "bath_floor", "Bath mixer, floor-standing"
    elif "bath" in T and ("four-hole" in T or "4-hole" in T or "rim" in T or "deck" in T):
        t, name = "bath_4hole", "Four-hole bath mixer, bath rim"
    elif "bath filler" in T or "spout" in T:
        t = "bath_filler_div" if "divert" in T else "bath_filler"
    elif "bath" in T and ("mixer" in T or "tap" in T):
        if "set" in T or has("Hand shower with"):
            t, name = "bath_exposed_set", "Bath mixer set, exposed"
        elif has("Rotating diverter"):
            t, name = "bath_exposed_bar", "Bath mixer, exposed (bar design)"
        else:
            t, name = "bath_exposed", "Bath mixer, exposed"
    elif ("concealed" in T or "in-wall" in T) and ("1 function" in T or "one" in T):
        t, name = "conc_1f", "Concealed mixer, 1 function"
    elif ("concealed" in T or "in-wall" in T) and ("2 function" in T or "two" in T or "diverter" in T):
        rot = has("Rotating diverter")
        t = "conc_2f_rot" if rot else "conc_2f_push"
        name = "Concealed mixer, 2 functions, " + ("rotating diverter" if rot else "push diverter")
    elif "shower mixer" in T or ("shower" in T and "exposed" in T):
        fr = _num(specs, "Flow rate")
        t = "shower_exposed_bar" if (fr == 15 and series.upper() == "TEVEO") else "shower_exposed"
        name = "Shower mixer, exposed" + (" (bar design)" if t == "shower_exposed_bar" else "")
    elif "sliding rail set" in T or "rail set" in T or "slide rail set" in T:
        t = "rail_set"
    elif "rail" in T and "shower" in T:
        t = "rail"
    elif "hose union set" in T or "outlet set" in T:
        t = "hose_union_set"
    elif ("hose union" in T or "wall outlet" in T or "wall elbow" in T) and "bracket" in T:
        t = "hose_union_bracket"
    elif "hose union" in T or "wall outlet" in T or "wall elbow" in T:
        t = "hose_union"
    elif "hand shower bracket" in T or "shower holder" in T:
        t = "hand_bracket"
    elif "hand shower" in T or "handshower" in T:
        t = "hand_shower"
    elif "hose" in T:
        t = "shower_hose"
    elif "shower head" in T or "overhead" in T or "rain shower" in T or "head shower" in T:
        d = _num(specs, "Diameter") or _num(specs, "Dimension") or _num(specs, "Size")
        t = "head_300" if (d or 250) >= 280 else "head_250"
    elif "shower arm" in T and "ceiling" in T:
        t = "arm_ceiling"
    elif "shower arm" in T:
        t = "arm_wall"
    elif "towel hook" in T and "double" in T:
        t = "hook_double"
    elif "hook" in T:
        t = "hook"
    elif "towel ring" in T:
        t = "towel_ring"
    elif "towel rack" in T or "towel shelf" in T:
        t = "towel_rack"
    elif "towel rail" in T or "towel bar" in T:
        t = "towel_rail"
    elif ("paper holder" in T or "roll holder" in T) and "double" in T:
        t = "tp_double_shelf"
    elif ("paper holder" in T or "roll holder" in T) and "shelf" in T:
        t = "tp_shelf"
    elif "paper holder" in T or "roll holder" in T:
        t = "tp_swivel" if has("Swivelling") else "tp_rigid"
    elif "shower shelf" in T or "basket" in T or "soap" in T:
        t = "shower_shelf"
    elif "mirror" in T:
        t = "mirror"
    else:
        t = "other"
    return t, name[:1].upper() + name[1:]
