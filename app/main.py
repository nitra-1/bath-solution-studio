"""Bath Solution Studio: web server and API."""
import io
import json
import re
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, db
from .extract import ingest, profiles
from .taxonomy import CATEGORIES, FINISHES, GROUPS, TYPE_CAT, TYPES, finish_key, sync_categories

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
VERSION = "1.0.0"

@asynccontextmanager
async def lifespan(_app):
    db.init()
    with db.connect() as c:
        sync_categories(c)
    with db.connect() as c:  # catalogs interrupted by a restart
        c.execute("UPDATE catalogs SET status='failed', log=coalesce(log,'')||'Stopped: the server restarted during processing. Upload again.\n' WHERE status='processing'")
    yield


app = FastAPI(title="Bath Solution Studio", version=VERSION, docs_url=None, redoc_url=None, lifespan=lifespan)


@app.exception_handler(HTTPException)
async def _http_err(_, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


# ---------- setup & login ----------
class Creds(BaseModel):
    email: str
    password: str
    name: str = ""


_fails: dict = {}


@app.get("/api/status")
def status():
    with db.connect() as c:
        n = db.row(c, "SELECT count(*) n FROM users")["n"]
        dealer = db.get_setting(c, "dealer")
    return {"needs_setup": n == 0, "dealer": dealer, "version": VERSION}


@app.post("/api/setup")
def setup(body: Creds, response: Response):
    with db.connect() as c:
        if db.row(c, "SELECT count(*) n FROM users")["n"]:
            raise HTTPException(400, "Setup is already done. Sign in instead.")
        _check_pw(body.password)
        uid = c.execute("INSERT INTO users(email,name,password_hash,role) VALUES(?,?,?, 'admin')",
                        (body.email.strip().lower(), body.name.strip() or "Admin", auth.hash_pw(body.password))).lastrowid
        _set_cookie(response, auth.new_session(c, uid))
    return {"ok": True}


def _check_pw(pw):
    if len(pw) < 8:
        raise HTTPException(400, "Use at least 8 characters for the password.")


def _set_cookie(response, token):
    response.set_cookie(auth.COOKIE, token, httponly=True, samesite="lax", max_age=auth.SESSION_DAYS * 86400)


@app.post("/api/login")
def login(body: Creds, response: Response):
    email = body.email.strip().lower()
    recent = [t for t in _fails.get(email, []) if t > time.time() - 300]
    if len(recent) >= 8:
        raise HTTPException(429, "Too many attempts. Wait 5 minutes and try again.")
    with db.connect() as c:
        u = db.row(c, "SELECT * FROM users WHERE email=?", email)
        if not u or not u["active"] or not auth.check_pw(body.password, u["password_hash"]):
            _fails[email] = recent + [time.time()]
            raise HTTPException(401, "Email or password is wrong.")
        _fails.pop(email, None)
        _set_cookie(response, auth.new_session(c, u["id"]))
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    with db.connect() as c:
        c.execute("DELETE FROM sessions WHERE token=?", (request.cookies.get(auth.COOKIE, ""),))
    response.delete_cookie(auth.COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(u=Depends(auth.current_user)):
    with db.connect() as c:
        s = {k: db.get_setting(c, k) for k in ("dealer", "contact")}
    return {**u, "settings": s}


class PwChange(BaseModel):
    current: str
    new: str


@app.post("/api/me/password")
def change_pw(body: PwChange, u=Depends(auth.current_user)):
    _check_pw(body.new)
    with db.connect() as c:
        h = db.row(c, "SELECT password_hash FROM users WHERE id=?", u["id"])["password_hash"]
        if not auth.check_pw(body.current, h):
            raise HTTPException(400, "Current password is wrong.")
        c.execute("UPDATE users SET password_hash=? WHERE id=?", (auth.hash_pw(body.new), u["id"]))
    return {"ok": True}


# ---------- users (admin) ----------
class UserIn(BaseModel):
    email: str
    name: str
    role: str = "sales"
    password: str


class UserPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    active: bool | None = None
    password: str | None = None


@app.get("/api/users")
def list_users(_=Depends(auth.require_admin)):
    with db.connect() as c:
        return db.rows(c, "SELECT id,email,name,role,active,created_at FROM users ORDER BY active DESC, name")


@app.post("/api/users")
def create_user(body: UserIn, _=Depends(auth.require_admin)):
    if body.role not in ("admin", "sales"):
        raise HTTPException(400, "Role must be admin or sales.")
    if not re.match(r"^[^@\s]+@[^@\s]+$", body.email.strip()):
        raise HTTPException(400, "Enter a valid email address.")
    _check_pw(body.password)
    with db.connect() as c:
        if db.row(c, "SELECT id FROM users WHERE email=?", body.email.strip().lower()):
            raise HTTPException(400, "Someone already uses that email.")
        uid = c.execute("INSERT INTO users(email,name,password_hash,role) VALUES(?,?,?,?)",
                        (body.email.strip().lower(), body.name.strip(), auth.hash_pw(body.password), body.role)).lastrowid
    return {"id": uid}


@app.patch("/api/users/{uid}")
def patch_user(uid: int, body: UserPatch, me_=Depends(auth.require_admin)):
    with db.connect() as c:
        if not db.row(c, "SELECT id FROM users WHERE id=?", uid):
            raise HTTPException(404, "User not found.")
        if uid == me_["id"] and (body.active is False or body.role == "sales"):
            raise HTTPException(400, "You can't remove your own admin access.")
        if body.name is not None:
            c.execute("UPDATE users SET name=? WHERE id=?", (body.name.strip(), uid))
        if body.role in ("admin", "sales"):
            c.execute("UPDATE users SET role=? WHERE id=?", (body.role, uid))
        if body.active is not None:
            c.execute("UPDATE users SET active=? WHERE id=?", (1 if body.active else 0, uid))
            if not body.active:
                c.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
        if body.password:
            _check_pw(body.password)
            c.execute("UPDATE users SET password_hash=? WHERE id=?", (auth.hash_pw(body.password), uid))
            c.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    return {"ok": True}


# ---------- settings ----------
class SettingsIn(BaseModel):
    dealer: str = ""
    contact: str = ""


@app.put("/api/settings")
def put_settings(body: SettingsIn, _=Depends(auth.require_admin)):
    with db.connect() as c:
        db.set_setting(c, "dealer", body.dealer.strip())
        db.set_setting(c, "contact", body.contact.strip())
    return {"ok": True}


# ---------- reference data ----------
@app.get("/api/meta")
def meta(_=Depends(auth.current_user)):
    return {"categories": CATEGORIES, "groups": [{"name": g, "categories": cats} for g, cats in GROUPS], "types": [{"key": k, "label": l, "category": c} for k, l, c in TYPES],
            "finishes": [{"key": k, "label": l, "color": col} for k, l, col in FINISHES],
            "readers": profiles.all_readers()}


# ---------- published catalog (sales) ----------
@app.get("/api/catalog")
def catalog(_=Depends(auth.current_user)):
    with db.connect() as c:
        prods = db.products_for(c, "c.status='published'")
        cats = db.rows(c, "SELECT c.id, c.name, b.name brand, b.currency, b.price_basis FROM catalogs c JOIN brands b ON b.id=c.brand_id WHERE c.status='published'")
        series = db.rows(c, "SELECT s.name, s.style, b.name brand FROM series s JOIN brands b ON b.id=s.brand_id")
    by_cat = {x["id"]: x for x in cats}
    brands = {}
    for p in prods:
        cat = by_cat[p["catalog_id"]]
        p["brand"] = cat["brand"]
        p["currency"] = cat["currency"]
        p["id"] = f"p{p['id']}"
        p["image"] = f"/images/{p['image']}" if p["image"] else None
        b = brands.setdefault(cat["brand"], {"name": cat["brand"], "currency": cat["currency"], "price_basis": cat["price_basis"], "catalogs": set(), "series": []})
        b["catalogs"].add(cat["name"])
        if p["series"] not in [s["name"] for s in b["series"]]:
            st = next((s["style"] for s in series if s["brand"] == cat["brand"] and s["name"] == p["series"]), "")
            b["series"].append({"name": p["series"], "style": st})
    out = []
    for b in brands.values():
        b["catalog"] = ", ".join(sorted(b["catalogs"]))
        del b["catalogs"]
        out.append(b)
    return {"brands": sorted(out, key=lambda b: b["name"]), "products": prods}


@app.get("/images/{name}")
def image(name: str, _=Depends(auth.current_user)):
    p = (db.IMG_DIR / name).resolve()
    if p.parent != db.IMG_DIR.resolve() or not p.exists():
        raise HTTPException(404, "Image not found.")
    return FileResponse(p, headers={"Cache-Control": "private, max-age=86400"})


# ---------- catalogs (admin) ----------
@app.get("/api/catalogs")
def list_catalogs(_=Depends(auth.require_admin)):
    with db.connect() as c:
        cs = db.rows(c, """SELECT c.id,c.name,c.filename,c.parser,c.status,c.uploaded_at,c.published_at,b.name brand,b.currency,b.price_basis,
                           u.name uploaded_by,(SELECT count(*) FROM products p WHERE p.catalog_id=c.id) products,
                           (SELECT count(*) FROM variants v JOIN products p ON p.id=v.product_id WHERE p.catalog_id=c.id) skus,
                           (SELECT count(*) FROM variants v JOIN products p ON p.id=v.product_id WHERE p.catalog_id=c.id AND v.flags!='[]') flagged,
                           (SELECT count(*) FROM products p WHERE p.catalog_id=c.id AND p.attributes LIKE '%"issues": ["%') product_issues
                           FROM catalogs c JOIN brands b ON b.id=c.brand_id LEFT JOIN users u ON u.id=c.uploaded_by ORDER BY c.id DESC""")
    return cs


@app.post("/api/catalogs")
async def upload_catalog(file: UploadFile = File(...), brand: str = Form(...), name: str = Form(""), currency: str = Form("EUR"),
                         price_basis: str = Form("RRP excl. VAT"), parser: str = Form("auto"), series: str = Form(""),
                         u=Depends(auth.require_admin)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".pdf", ".xlsx", ".xlsm"):
        raise HTTPException(400, "Upload a PDF price list or the Excel template (.xlsx).")
    if not brand.strip():
        raise HTTPException(400, "Enter the brand name.")
    stored = f"{uuid.uuid4().hex}{ext}"
    dest = db.UPLOAD_DIR / stored
    size = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > 200 * 1024 * 1024:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(400, "The file is larger than 200 MB.")
            f.write(chunk)
    if parser == "auto":
        parser = profiles.for_brand(brand)
    elif parser not in [r["key"] for r in profiles.all_readers()]:
        raise HTTPException(400, "Unknown reader.")
    with db.connect() as c:
        bid = db.brand_id(c, brand.strip(), currency.strip() or "EUR", price_basis.strip() or "RRP excl. VAT")
        cid = c.execute("INSERT INTO catalogs(brand_id,name,filename,stored_file,parser,uploaded_by) VALUES(?,?,?,?,?,?)",
                        (bid, name.strip() or Path(file.filename).stem, file.filename, stored, parser if ext == ".pdf" else "excel", u["id"])).lastrowid
    ingest.start(cid, dest, parser, series.strip())
    return {"id": cid}


@app.get("/api/catalogs/{cid}")
def get_catalog(cid: int, _=Depends(auth.require_admin)):
    with db.connect() as c:
        cat = db.row(c, "SELECT c.*, b.name brand, b.currency, b.price_basis FROM catalogs c JOIN brands b ON b.id=c.brand_id WHERE c.id=?", cid)
        if not cat:
            raise HTTPException(404, "Catalog not found.")
        prods = db.products_for(c, "p.catalog_id=?", cid)
        series = db.rows(c, "SELECT id,name,style FROM series WHERE brand_id=? ORDER BY name", cat["brand_id"])
    for p in prods:
        p["image"] = f"/images/{p['image']}" if p["image"] else None
    return {"catalog": cat, "products": prods, "series": series}


class CatalogPatch(BaseModel):
    name: str | None = None
    currency: str | None = None
    price_basis: str | None = None


@app.patch("/api/catalogs/{cid}")
def patch_catalog(cid: int, body: CatalogPatch, _=Depends(auth.require_admin)):
    with db.connect() as c:
        cat = db.row(c, "SELECT * FROM catalogs WHERE id=?", cid)
        if not cat:
            raise HTTPException(404, "Catalog not found.")
        if body.name:
            c.execute("UPDATE catalogs SET name=? WHERE id=?", (body.name.strip(), cid))
        if body.currency:
            c.execute("UPDATE brands SET currency=? WHERE id=?", (body.currency.strip(), cat["brand_id"]))
        if body.price_basis:
            c.execute("UPDATE brands SET price_basis=? WHERE id=?", (body.price_basis.strip(), cat["brand_id"]))
    return {"ok": True}


class SeriesPatch(BaseModel):
    style: str


@app.patch("/api/series/{sid}")
def patch_series(sid: int, body: SeriesPatch, _=Depends(auth.require_admin)):
    with db.connect() as c:
        c.execute("UPDATE series SET style=? WHERE id=?", (body.style.strip(), sid))
    return {"ok": True}


class PublishIn(BaseModel):
    replace_previous: bool = True


@app.post("/api/catalogs/{cid}/publish")
def publish(cid: int, body: PublishIn, _=Depends(auth.require_admin)):
    with db.connect() as c:
        cat = db.row(c, "SELECT * FROM catalogs WHERE id=?", cid)
        if not cat or cat["status"] not in ("review", "archived"):
            raise HTTPException(400, "Only catalogs that finished processing can be published.")
        if body.replace_previous:
            c.execute("UPDATE catalogs SET status='archived' WHERE brand_id=? AND status='published' AND id!=?", (cat["brand_id"], cid))
        c.execute("UPDATE catalogs SET status='published', published_at=CURRENT_TIMESTAMP WHERE id=?", (cid,))
    return {"ok": True}


@app.post("/api/catalogs/{cid}/unpublish")
def unpublish(cid: int, _=Depends(auth.require_admin)):
    with db.connect() as c:
        c.execute("UPDATE catalogs SET status='review' WHERE id=? AND status='published'", (cid,))
    return {"ok": True}


@app.post("/api/catalogs/{cid}/revalidate")
def reval(cid: int, _=Depends(auth.require_admin)):
    ingest.revalidate(cid)
    return {"ok": True}


@app.delete("/api/catalogs/{cid}")
def delete_catalog(cid: int, _=Depends(auth.require_admin)):
    with db.connect() as c:
        cat = db.row(c, "SELECT * FROM catalogs WHERE id=?", cid)
        if not cat:
            raise HTTPException(404, "Catalog not found.")
        if cat["status"] == "processing":
            raise HTTPException(400, "Wait for processing to finish.")
        imgs = [r["image"] for r in db.rows(c, "SELECT image FROM products WHERE catalog_id=? AND image IS NOT NULL", cid)]
        c.execute("DELETE FROM catalogs WHERE id=?", (cid,))
    for name in imgs:
        (db.IMG_DIR / name).unlink(missing_ok=True)
    if cat["stored_file"]:
        (db.UPLOAD_DIR / cat["stored_file"]).unlink(missing_ok=True)
    return {"ok": True}


@app.get("/api/catalogs/{cid}/file")
def catalog_file(cid: int, _=Depends(auth.require_admin)):
    with db.connect() as c:
        cat = db.row(c, "SELECT * FROM catalogs WHERE id=?", cid)
    if not cat or not cat["stored_file"] or not (db.UPLOAD_DIR / cat["stored_file"]).exists():
        raise HTTPException(404, "The original file is not available.")
    return FileResponse(db.UPLOAD_DIR / cat["stored_file"], filename=cat["filename"])


@app.get("/api/template.xlsx")
def template(_=Depends(auth.require_admin)):
    buf = io.BytesIO()
    ingest.write_template(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": 'attachment; filename="product-template.xlsx"'})


# ---------- product editing (admin) ----------
class VariantIn(BaseModel):
    id: int | None = None
    art: str
    finish: str = ""
    finish_key: str | None = None
    width_mm: int | None = None
    price: float | None = None


class ProductIn(BaseModel):
    series: str = ""
    category: str = "Other"
    type: str = "other"
    name: str
    specs: list = Field(default_factory=list)
    note: str | None = None
    variants: list[VariantIn] = Field(default_factory=list)


def _save_product(c, pid, body: ProductIn):
    if body.type not in TYPE_CAT:
        raise HTTPException(400, "Unknown product type.")
    cat = TYPE_CAT[body.type]  # category always follows the type
    c.execute("UPDATE products SET series=?,category=?,type=?,name=?,specs=?,note=? WHERE id=?",
              (body.series.strip(), cat, body.type, body.name.strip(), json.dumps(body.specs), body.note, pid))
    keep = []
    for k, v in enumerate(body.variants):
        fk = v.finish_key or finish_key(v.finish)
        if v.id:
            c.execute("UPDATE variants SET art=?,finish=?,finish_key=?,width_mm=?,price=?,sort=? WHERE id=? AND product_id=?",
                      (v.art.strip(), v.finish.strip(), fk, v.width_mm, v.price, k, v.id, pid))
            keep.append(v.id)
        else:
            keep.append(c.execute("INSERT INTO variants(product_id,art,finish,finish_key,width_mm,price,sort) VALUES(?,?,?,?,?,?,?)",
                                  (pid, v.art.strip(), v.finish.strip(), fk, v.width_mm, v.price, k)).lastrowid)
    c.execute(f"DELETE FROM variants WHERE product_id=? AND id NOT IN ({','.join('?' * len(keep)) or 'NULL'})", (pid, *keep))
    p = db.row(c, "SELECT catalog_id FROM products WHERE id=?", pid)
    s = db.row(c, "SELECT brand_id FROM catalogs WHERE id=?", p["catalog_id"])
    if body.series.strip():
        db.ensure_series(c, s["brand_id"], body.series.strip())
    return p["catalog_id"]


@app.put("/api/products/{pid}")
def put_product(pid: int, body: ProductIn, _=Depends(auth.require_admin)):
    with db.connect() as c:
        if not db.row(c, "SELECT id FROM products WHERE id=?", pid):
            raise HTTPException(404, "Product not found.")
        cid = _save_product(c, pid, body)
    ingest.revalidate(cid)
    with db.connect() as c:
        p = db.products_for(c, "p.id=?", pid)[0]
    p["image"] = f"/images/{p['image']}" if p["image"] else None
    return p


@app.post("/api/catalogs/{cid}/products")
def add_product(cid: int, body: ProductIn, _=Depends(auth.require_admin)):
    with db.connect() as c:
        if not db.row(c, "SELECT id FROM catalogs WHERE id=?", cid):
            raise HTTPException(404, "Catalog not found.")
        pid = c.execute("INSERT INTO products(catalog_id,name,sort) VALUES(?,?,9999)", (cid, body.name)).lastrowid
        _save_product(c, pid, body)
    ingest.revalidate(cid)
    return {"id": pid}


@app.delete("/api/products/{pid}")
def delete_product(pid: int, _=Depends(auth.require_admin)):
    with db.connect() as c:
        p = db.row(c, "SELECT * FROM products WHERE id=?", pid)
        if not p:
            raise HTTPException(404, "Product not found.")
        c.execute("DELETE FROM products WHERE id=?", (pid,))
    return {"ok": True}


@app.post("/api/variants/{vid}/accept")
def accept_flags(vid: int, _=Depends(auth.require_admin)):
    """Admin confirms the flagged values are correct; the warnings stop showing."""
    with db.connect() as c:
        v = db.row(c, "SELECT v.*, p.catalog_id FROM variants v JOIN products p ON p.id=v.product_id WHERE v.id=?", vid)
        if not v:
            raise HTTPException(404, "Article not found.")
        acc = list(dict.fromkeys(json.loads(v["accepted"]) + json.loads(v["flags"])))
        c.execute("UPDATE variants SET accepted=?, flags='[]' WHERE id=?", (json.dumps(acc), vid))
    return {"ok": True}


@app.post("/api/products/{pid}/image")
async def product_image(pid: int, file: UploadFile = File(...), _=Depends(auth.require_admin)):
    from PIL import Image
    data = await file.read()
    try:
        im = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:  # noqa
        raise HTTPException(400, "That file is not an image (use JPG or PNG).")
    im.thumbnail((480, 480))
    name = f"u{pid}_{uuid.uuid4().hex[:8]}.jpg"
    im.save(db.IMG_DIR / name, quality=82)
    with db.connect() as c:
        old = db.row(c, "SELECT image, catalog_id FROM products WHERE id=?", pid)
        if not old:
            raise HTTPException(404, "Product not found.")
        c.execute("UPDATE products SET image=? WHERE id=?", (name, pid))
    ingest.revalidate(old["catalog_id"])
    return {"image": f"/images/{name}"}


# ---------- projects ----------
class ProjectIn(BaseModel):
    title: str = "Untitled project"
    customer: str = ""
    data: dict = Field(default_factory=dict)


@app.get("/api/projects")
def list_projects(u=Depends(auth.current_user)):
    with db.connect() as c:
        q = """SELECT p.id,p.title,p.customer,p.updated_at,p.created_at,u.name owner,p.owner_id,
               json_array_length(json_extract(p.data,'$.rooms')) rooms FROM projects p JOIN users u ON u.id=p.owner_id"""
        if u["role"] == "admin":
            return db.rows(c, q + " ORDER BY p.updated_at DESC")
        return db.rows(c, q + " WHERE p.owner_id=? ORDER BY p.updated_at DESC", u["id"])


def _own(c, pid, u):
    p = db.row(c, "SELECT * FROM projects WHERE id=?", pid)
    if not p or (p["owner_id"] != u["id"] and u["role"] != "admin"):
        raise HTTPException(404, "Project not found.")
    return p


@app.post("/api/projects")
def create_project(body: ProjectIn, u=Depends(auth.current_user)):
    with db.connect() as c:
        pid = c.execute("INSERT INTO projects(owner_id,title,customer,data) VALUES(?,?,?,?)",
                        (u["id"], body.title, body.customer, json.dumps(body.data))).lastrowid
    return {"id": pid}


@app.get("/api/projects/{pid}")
def get_project(pid: int, u=Depends(auth.current_user)):
    with db.connect() as c:
        p = _own(c, pid, u)
    p["data"] = json.loads(p["data"])
    return p


@app.put("/api/projects/{pid}")
def put_project(pid: int, body: ProjectIn, u=Depends(auth.current_user)):
    with db.connect() as c:
        _own(c, pid, u)
        c.execute("UPDATE projects SET title=?,customer=?,data=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (body.title, body.customer, json.dumps(body.data), pid))
    return {"ok": True}


@app.delete("/api/projects/{pid}")
def delete_project(pid: int, u=Depends(auth.current_user)):
    with db.connect() as c:
        _own(c, pid, u)
        c.execute("DELETE FROM projects WHERE id=?", (pid,))
    return {"ok": True}


# ---------- backup (admin) ----------
@app.get("/api/backup")
def backup(_=Depends(auth.require_admin)):
    import sqlite3
    import tempfile
    tmp = Path(tempfile.mkdtemp()) / "studio.db"
    src = sqlite3.connect(db.DB_PATH)
    dst = sqlite3.connect(tmp)
    src.backup(dst)
    src.close()
    dst.close()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tmp, "studio.db")
        for f in db.IMG_DIR.iterdir():
            z.write(f, f"images/{f.name}")
    buf.seek(0)
    stamp = time.strftime("%Y-%m-%d")
    return StreamingResponse(buf, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="bath-studio-backup-{stamp}.zip"'})


# ---------- front end ----------
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})
