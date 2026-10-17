# Bath Solution Studio — notes for coding agents

Local-network sales tool for a bath/sanitary showroom. The owner (Nitin) is not a programmer; keep changes simple, keep the no-build frontend, and keep the README's install steps working on Windows.

## Layout
- `app/main.py` — FastAPI app: auth, users, catalogs (upload/review/publish), products, projects, settings, backup. Serves `static/`.
- `app/db.py` — SQLite schema and helpers. Data dir from `BSS_DATA_DIR` (default `./data`): `studio.db`, `images/`, `uploads/`. Add schema changes as `ALTER TABLE` migrations in `init()`; never require users to delete their DB.
- `app/auth.py` — bcrypt passwords, cookie sessions (30 days), roles `admin` / `sales`.
- `app/taxonomy.py` — categories, **fitting types** (the solution builder works on these), finish families, `classify()` (English product names → type).
- `app/extract/pdf_parser.py` — reading engine: default block reader plus helpers (`rows`, `parse_price`, `crop_image`, `largest_image`).
- `app/extract/profiles/` — **one reader per brand layout**, auto-discovered (`generic.py`, `keuco.py`; `_template.py` is the starting point). A reader sets `PROFILE` and optionally its own `parse()`. To add or fix a brand, follow `.claude/skills/new-brand-reader/SKILL.md`; don't special-case brands inside `pdf_parser.py`.
- `scripts/try_reader.py` — run a reader on a PDF outside the app; `--dump-page N` shows words with font/size/position.
- `app/extract/validate.py` — review flags. Admin can accept flags (`variants.accepted`).
- `app/extract/ingest.py` — background thread: parse → classify → validate → store (status `review`). Also the Excel template writer/reader.
- `static/js/engine.js` — room → product list rules (`buildRoom`), alternatives, range deck grouping. Shared shape with the original prototype.
- `static/js/deck.js` — PptxGenJS slide builders (`buildSolution`, `buildRange`).
- `static/js/app.js` — the whole UI: hash router, sales screens, admin screens.

## Catalog lifecycle
`processing` → `review` → `published` (→ `archived` when replaced). Sales only see `published`. Product ids sent to the browser are `p<id>` strings.

## Conventions
- UI copy: plain, active voice, from the user's side ("Publish to sales", "Needs attention only").
- Keep prices exactly as in the price list; currency/basis per brand.
- Tests: `pytest -q`. `tests/test_readers.py` reads every `tests/samples/<name>.pdf` that has a `<name>.expected.json` (KEUCO: 88 products / 514 article numbers). PDFs are git-ignored; expected files are committed.
- The app must keep working offline. No network calls at runtime (fonts from Google degrade to system fonts).
