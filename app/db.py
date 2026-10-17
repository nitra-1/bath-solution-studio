"""SQLite storage. One file (data/studio.db) holds everything except images and uploaded PDFs."""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

DATA_DIR = Path(os.environ.get("BSS_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DB_PATH = DATA_DIR / "studio.db"
IMG_DIR = DATA_DIR / "images"
UPLOAD_DIR = DATA_DIR / "uploads"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('admin','sales')),
  active INTEGER NOT NULL DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS brands (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, currency TEXT NOT NULL DEFAULT 'EUR',
  price_basis TEXT NOT NULL DEFAULT 'RRP excl. VAT'
);
CREATE TABLE IF NOT EXISTS series (
  id INTEGER PRIMARY KEY, brand_id INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
  name TEXT NOT NULL, style TEXT NOT NULL DEFAULT '', UNIQUE (brand_id, name)
);
CREATE TABLE IF NOT EXISTS catalogs (
  id INTEGER PRIMARY KEY, brand_id INTEGER NOT NULL REFERENCES brands(id),
  name TEXT NOT NULL, filename TEXT, stored_file TEXT, parser TEXT,
  status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing','review','published','archived','failed')),
  log TEXT DEFAULT '', uploaded_by INTEGER REFERENCES users(id),
  uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP, published_at TEXT
);
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY, catalog_id INTEGER NOT NULL REFERENCES catalogs(id) ON DELETE CASCADE,
  series TEXT NOT NULL DEFAULT '', line TEXT DEFAULT '', category TEXT NOT NULL DEFAULT 'Other',
  type TEXT NOT NULL DEFAULT 'other', name TEXT NOT NULL, specs TEXT NOT NULL DEFAULT '[]',
  attributes TEXT NOT NULL DEFAULT '{}', image TEXT, source_page INTEGER, note TEXT, sort INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS variants (
  id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  art TEXT NOT NULL, finish TEXT NOT NULL DEFAULT '', finish_key TEXT NOT NULL DEFAULT 'other',
  width_mm INTEGER, price REAL, flags TEXT NOT NULL DEFAULT '[]', accepted TEXT NOT NULL DEFAULT '[]', sort INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY, owner_id INTEGER NOT NULL REFERENCES users(id),
  title TEXT NOT NULL, customer TEXT DEFAULT '', data TEXT NOT NULL DEFAULT '{}',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS ix_products_catalog ON products(catalog_id);
CREATE INDEX IF NOT EXISTS ix_variants_product ON variants(product_id);
"""

_lock = threading.Lock()


def init():
    for d in (DATA_DIR, IMG_DIR, UPLOAD_DIR):
        d.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.executescript(SCHEMA)
        cols = [r["name"] for r in c.execute("PRAGMA table_info(variants)")]
        if "accepted" not in cols:  # databases created by an earlier version
            c.execute("ALTER TABLE variants ADD COLUMN accepted TEXT NOT NULL DEFAULT '[]'")


@contextmanager
def connect():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def rows(con, sql, *args):
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def row(con, sql, *args):
    r = con.execute(sql, args).fetchone()
    return dict(r) if r else None


def get_setting(con, key, default=""):
    r = row(con, "SELECT value FROM settings WHERE key=?", key)
    return r["value"] if r else default


def set_setting(con, key, value):
    con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def brand_id(con, name, currency="EUR", price_basis="RRP excl. VAT"):
    r = row(con, "SELECT id FROM brands WHERE lower(name)=lower(?)", name)
    if r:
        con.execute("UPDATE brands SET currency=?, price_basis=? WHERE id=?", (currency, price_basis, r["id"]))
        return r["id"]
    return con.execute("INSERT INTO brands(name,currency,price_basis) VALUES(?,?,?)", (name, currency, price_basis)).lastrowid


def ensure_series(con, bid, name, style=""):
    r = row(con, "SELECT id, style FROM series WHERE brand_id=? AND name=?", bid, name)
    if r:
        if style and not r["style"]:
            con.execute("UPDATE series SET style=? WHERE id=?", (style, r["id"]))
        return r["id"]
    return con.execute("INSERT INTO series(brand_id,name,style) VALUES(?,?,?)", (bid, name, style)).lastrowid


def product_dict(p, variants):
    return {
        "id": p["id"], "catalog_id": p["catalog_id"], "series": p["series"], "line": p["line"],
        "category": p["category"], "type": p["type"], "name": p["name"],
        "specs": json.loads(p["specs"]), "attributes": json.loads(p["attributes"]),
        "image": p["image"], "source_page": p["source_page"], "note": p["note"],
        "variants": [{"id": v["id"], "art": v["art"], "finish": v["finish"], "finish_key": v["finish_key"],
                      "width_mm": v["width_mm"], "price": v["price"], "flags": json.loads(v["flags"]),
                      "accepted": json.loads(v.get("accepted") or "[]")} for v in variants],
    }


def products_for(con, where, *args):
    ps = rows(con, f"SELECT p.* FROM products p JOIN catalogs c ON c.id=p.catalog_id WHERE {where} ORDER BY p.catalog_id, p.sort, p.id", *args)
    if not ps:
        return []
    ids = [p["id"] for p in ps]
    vs = {}
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        for v in rows(con, f"SELECT * FROM variants WHERE product_id IN ({','.join('?' * len(chunk))}) ORDER BY sort, id", *chunk):
            vs.setdefault(v["product_id"], []).append(v)
    return [product_dict(p, vs.get(p["id"], [])) for p in ps]
