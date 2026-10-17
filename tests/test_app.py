"""Run with:  pip install -r requirements-dev.txt && pytest -q
PDF readers are tested in test_readers.py against tests/samples/."""
import io
import os
import tempfile
import time

import pytest

os.environ["BSS_DATA_DIR"] = tempfile.mkdtemp(prefix="bss-test-")

from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

from app.main import app  # noqa: E402
from app.taxonomy import classify, finish_key  # noqa: E402


@pytest.fixture(scope="module")
def admin():
    with TestClient(app) as c:
        assert c.get("/api/status").json()["needs_setup"] is True
        assert c.post("/api/setup", json={"email": "boss@shop.in", "password": "longpassword", "name": "Boss"}).status_code == 200
        yield c


def wait_ready(c, cid):
    for _ in range(120):
        st = c.get(f"/api/catalogs/{cid}").json()["catalog"]["status"]
        if st != "processing":
            return st
        time.sleep(0.5)
    raise AssertionError("catalog still processing")


def test_classify():
    assert classify("Single lever basin mixer 240", [{"group": None, "items": ["Outlet height: 238 mm"]}])[0] == "basin_tall"
    assert classify("Hose union set with hand shower bracket", [])[0] == "hose_union_set"
    assert classify("Thermostatic mixer concealed for 2 functions incl. rough part", [])[0] == "thermo_2f"
    assert classify("Toilet paper holder with shelf", [])[0] == "tp_shelf"
    assert classify("Something unusual", [])[0] == "other"
    assert finish_key("brushed rose gold PVD") == "rosegold" and finish_key("chrome-plated") == "chrome"


def test_setup_only_once(admin):
    assert admin.post("/api/setup", json={"email": "x@y.z", "password": "longpassword"}).status_code == 400


def test_excel_flow_and_roles(admin):
    # fill the template with two products
    wb = load_workbook(io.BytesIO(admin.get("/api/template.xlsx").content))
    ws = wb["Products"]
    ws.append(["AURA", "Shower", "shower_exposed", "Wall shower mixer", "Flow rate: 12 l/min", "AU-100-CH", "Chrome", "", 120, ""])
    ws.append(["AURA", "Shower", "shower_exposed", "Wall shower mixer", "", "AU-100-BK", "Matt black", "", 150, ""])
    buf = io.BytesIO()
    wb.save(buf)
    r = admin.post("/api/catalogs", data={"brand": "Aura Test", "currency": "INR"},
                   files={"file": ("aura.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    cid = r.json()["id"]
    assert wait_ready(admin, cid) == "review"
    d = admin.get(f"/api/catalogs/{cid}").json()
    names = {p["name"]: p for p in d["products"]}
    assert len(names["Wall shower mixer"]["variants"]) == 2
    assert names["Wall shower mixer"]["variants"][1]["finish_key"] == "black"

    # sales user can't see unpublished catalogs or admin endpoints
    assert admin.post("/api/users", json={"email": "sam@shop.in", "name": "Sam", "password": "salespass1"}).status_code == 200
    with TestClient(app) as sales:
        assert sales.post("/api/login", json={"email": "sam@shop.in", "password": "salespass1"}).status_code == 200
        assert all(p["brand"] != "Aura Test" for p in sales.get("/api/catalog").json()["products"])
        assert sales.get("/api/catalogs").status_code == 403
        assert admin.post(f"/api/catalogs/{cid}/publish", json={"replace_previous": True}).status_code == 200
        cat = sales.get("/api/catalog").json()
        assert any(p["brand"] == "Aura Test" for p in cat["products"])
        assert cat["brands"][0]["currency"] == "INR"
        # projects are private to their owner (admins see all)
        pid = sales.post("/api/projects", json={"title": "Villa", "data": {"rooms": []}}).json()["id"]
        assert sales.get(f"/api/projects/{pid}").json()["title"] == "Villa"
        assert sales.put(f"/api/projects/{pid}", json={"title": "Villa 2", "data": {"rooms": [{"name": "Bath"}]}}).status_code == 200
        assert admin.get(f"/api/projects/{pid}").json()["title"] == "Villa 2"
    with TestClient(app) as other:
        admin.post("/api/users", json={"email": "kim@shop.in", "name": "Kim", "password": "salespass2"})
        other.post("/api/login", json={"email": "kim@shop.in", "password": "salespass2"})
        assert other.get(f"/api/projects/{pid}").status_code == 404


def test_edit_product_and_accept_flag(admin):
    cid = admin.get("/api/catalogs").json()[0]["id"]
    p = admin.get(f"/api/catalogs/{cid}").json()["products"][0]
    body = {"name": p["name"], "series": p["series"], "type": p["type"], "category": p["category"], "specs": p["specs"],
            "variants": [{"id": v["id"], "art": v["art"], "finish": v["finish"], "price": None} for v in p["variants"]]}
    out = admin.put(f"/api/products/{p['id']}", json=body).json()
    assert "Price missing." in out["variants"][0]["flags"]
    admin.post(f"/api/variants/{out['variants'][0]['id']}/accept")
    admin.post(f"/api/catalogs/{cid}/revalidate")
    again = [x for x in admin.get(f"/api/catalogs/{cid}").json()["products"] if x["id"] == p["id"]][0]
    assert again["variants"][0]["flags"] == []


def test_deactivated_user_cannot_sign_in(admin):
    uid = [u for u in admin.get("/api/users").json() if u["email"] == "kim@shop.in"][0]["id"]
    admin.patch(f"/api/users/{uid}", json={"active": False})
    with TestClient(app) as c:
        assert c.post("/api/login", json={"email": "kim@shop.in", "password": "salespass2"}).status_code == 401
