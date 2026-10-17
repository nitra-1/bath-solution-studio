# Bath Solution Studio

A showroom sales tool for bath and sanitary fittings. It runs on one office computer; the sales team opens it in their browser over the office network.

- **Admins** upload brand price lists (PDF, or an Excel template), check the products the system reads, and publish them.
- **Sales** build customer proposals room by room, or a brand range deck for an architect, and download both as editable PowerPoint files.

---

## What it does

| Area | Who | What happens |
|---|---|---|
| Upload & review | Admin | Upload a price list → products, specs, finishes, prices and photos are read → flagged items are listed → admin corrects, sets missing types/photos → **Publish** |
| Projects | Sales | One project per customer. Add rooms (Master bath, Guest bath, Powder room…), pick collection, finish, budget level and fixtures. The system adds the parts each fitting needs (waste plug, bottle trap, angle valves, shower arm, hand-shower set) and flags anything not made in the chosen finish. Edit, swap, add or remove items. |
| Proposal deck | Sales | Cover, rooms overview, one slide per room with photos, price summary, ordering notes. Editable `.pptx`. |
| Range deck | Sales | A brand's collections, sorted by collection and category, with all finishes and article numbers. Prices on (internal) or off (for architects). |
| Catalog | Everyone | Search every published product by name, spec or article number. |
| Users | Admin | Add salespeople, reset passwords, deactivate leavers. |
| Settings | Admin | Showroom name and contact line for the decks, one-click backup. |

Prices are shown exactly as in each price list (currency and basis are set per brand when uploading).

---

## Install on the office computer

Pick **one** of the two ways. The computer must stay on while the team uses the app.

### Option A: Python (simplest on Windows)

1. Install **Python 3.12** from https://www.python.org/downloads/ . On Windows, tick **"Add python.exe to PATH"** in the installer.
2. Download this project (green **Code** button on GitHub → **Download ZIP**) and unzip it, for example to `C:\BathStudio`.
3. Start it:
   - **Windows:** double-click `start.bat`
   - **Mac / Linux:** open Terminal in the folder and run `./start.sh`

   The first start installs what it needs (a minute or two). Later starts are instant. Keep the window open.
4. Open http://localhost:8010 on that computer and **create the admin account**.

### Option B: Docker

Install Docker Desktop, then in the project folder run:

```
docker compose up -d --build
```

It restarts automatically with the computer. Open http://localhost:8010 and create the admin account.

---

## Let the sales team in

1. Find the office computer's address:
   - **Windows:** open Command Prompt, run `ipconfig`, note the **IPv4 Address** (for example `192.168.1.25`).
   - **Mac:** System Settings → Wi-Fi → Details → IP address.
2. Salespeople open `http://192.168.1.25:8010` (your address) on any phone, tablet or laptop on the **same office network**.
3. If it doesn't open from other devices on Windows, allow it through the firewall: when Windows asks on first start, choose **Allow access** for private networks (or Windows Security → Firewall → Allow an app → Python).
4. Ask your router admin to give the office computer a **fixed IP address** so the link doesn't change.
5. In the app, go to **Users** and add each salesperson with an email and starting password. They can change it under their name (top right).

Working from outside the office is not set up. If you need it later, a tunnel service (for example Cloudflare Tunnel or Tailscale) can expose it safely; don't open the port on the router directly.

---

## Adding a price list (admin)

1. **Upload & review** → choose the PDF, type the brand name, catalog name, currency and price basis.
2. Reader: leave it on **Automatic**. It uses the brand's own reader if one exists (KEUCO has one), otherwise the general reader. The general reader expects product blocks: a bold product title, bullet specs, and rows of *article number … finish … price*.
   If a PDF doesn't read well, the review screen says so. Then either create a reader for that brand (next section), or download the **Excel template**, fill it, and upload the `.xlsx`.
3. When reading finishes, click **Review**. Tick **Needs attention only** to see:
   - possible misprints (article numbers that don't match the other finishes, PVD prices that differ),
   - products without a photo (click the photo box to add one),
   - products whose **type** wasn't recognised. Set the type so the solution builder can use them.
   Fix and **Save product**, or click **It's correct, clear warning**.
4. **Publish to sales**. By default this replaces the brand's previous price list (the old one is archived, not deleted).

Projects built on an older price list keep working. Rooms that weren't edited by hand pick up the new products and prices the next time they're opened.

---

## Adding a new brand layout (with Claude Code)

The app reads PDFs without AI and without internet. Each brand layout has a small reader file in `app/extract/profiles/`. When a brand's PDF doesn't read cleanly, create its reader once with Claude Code on your own laptop. The same brand's next price list will normally read with no further work.

1. On your laptop, open the project folder (the GitHub copy).
2. Copy the brand's PDF into `tests/samples/`, named after the brand, e.g. `tests/samples/grohe.pdf`.
3. Start Claude Code in the project folder and say:
   > Create a reader for tests/samples/grohe.pdf (brand: GROHE)

   It follows the project's `new-brand-reader` skill: tries the general reader, studies the layout, writes `app/extract/profiles/grohe.py`, checks every product and price, adds a test, and commits.
4. Update the office computer: `git pull` (or download the new ZIP and replace everything except `data`), then restart the app.
5. Upload the PDF in **Upload & review** with Reader on **Automatic**, review, publish.

Scanned PDFs (pictures of pages with no text inside) can't be read this way. Use the Excel template for those brands.

Try a reader yourself any time:

```
python scripts/try_reader.py tests/samples/grohe.pdf --brand GROHE
```

---

## Backups

**Settings → Download backup** saves the database and product photos as one zip. Do it weekly and keep the zip off the office computer (Google Drive, USB drive).

Everything lives in the `data` folder. To move the app to another computer, copy the whole project folder including `data`.

To restore: stop the app, unzip the backup into `data` (so you get `data/studio.db` and `data/images/`), start again.

## Updating

Download the new version, replace everything **except the `data` folder**, and start again. With Git: `git pull` then restart. With Docker: `docker compose up -d --build`.

---

## For developers

- Backend: Python, FastAPI, SQLite (`app/`). Frontend: plain HTML/CSS/JS without a build step (`static/`). PowerPoint files are generated in the browser with PptxGenJS (`static/vendor`).
- Run tests: `pip install -r requirements-dev.txt && pytest -q`. Sample PDFs in `tests/samples/` (git-ignored) are checked against their committed `.expected.json`.
- Data folder can be moved with the `BSS_DATA_DIR` environment variable.
- See `CLAUDE.md` for the architecture and where to change things.
