"""Brand readers. Each .py file here (not starting with "_") is one reader.

A reader module must define PROFILE (a pdf_parser.Profile). It may also define
    parse(pdf_path, img_dir, img_prefix, default_series, log) -> list[product dict]
to read a layout the default block reader can't handle. See _template.py.

New files are picked up automatically after the app restarts.
"""
import importlib
import pkgutil

_REG = None


def _load():
    global _REG
    if _REG is None:
        reg = {}
        for m in pkgutil.iter_modules(__path__):
            if m.name.startswith("_"):
                continue
            mod = importlib.import_module(f"{__name__}.{m.name}")
            if hasattr(mod, "PROFILE"):
                reg[mod.PROFILE.name] = mod
        _REG = reg
    return _REG


def get(name):
    reg = _load()
    return reg.get(name) or reg["generic"]


def all_readers():
    reg = _load()
    order = sorted(reg.values(), key=lambda m: (m.PROFILE.name != "generic", m.PROFILE.label.lower()))
    return [{"key": m.PROFILE.name, "label": m.PROFILE.label, "brands": m.PROFILE.brands} for m in order]


def for_brand(brand):
    """Reader to use when the admin leaves 'Automatic' selected."""
    b = (brand or "").strip().lower()
    for m in _load().values():
        if any(x.lower() == b or x.lower() in b for x in m.PROFILE.brands):
            return m.PROFILE.name
    return "generic"
