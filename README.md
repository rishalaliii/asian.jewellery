# Asian Jewellery — Python version

This version replaces the Node.js/Express backend and `better-sqlite3` with Python Flask and Python built-in SQLite. No Node.js, npm, or Visual Studio C++ tools are required. The existing HTML/CSS/browser JavaScript UI and logo are retained.

## Windows setup
1. Install Python 3.10+ from https://www.python.org/downloads/ (enable Add Python to PATH).
2. Extract this ZIP. Open PowerShell in this folder.
3. Run `py -m pip install -r requirements.txt`.
4. The `run.bat` launcher copies `.env.example` to `.env` if missing. Before public hosting, edit `.env` and set `ADMIN_USER`, a unique `ADMIN_PASS`, and a random `SESSION_SECRET` of at least 32 characters.
5. Run `py app.py`.
6. Open http://127.0.0.1:9000 on this PC. To test from a phone on the same Wi-Fi, use http://YOUR-PC-LAN-IP:9000 (find the IPv4 address with `ipconfig`). Allow Python through Windows Firewall only on Private networks. Do not expose this development server directly to the public internet.

You can also double-click `run.bat`; it installs dependencies, creates `.env` from the example if needed, and starts the site. Edit `.env` before the first run to configure the initial admin account. The initial admin is created once; password changes are available from the dashboard. Do not publish `.env`.

## Features preserved
Public pages and rates, single-admin login, manual gold/silver rate management and history, bill creation, drafts, bill history, payment recording, shop settings, print and browser Save as PDF, TXT download, and logo watermark. The backend persists data in `data.db` beside `app.py`.

## Rate source
No authorized automatic KGSMA/AKGSMA feed is connected in the supplied project. Rates remain manual until a legitimate supported feed is verified.

## Security note
For public internet deployment, use HTTPS, a strong unique admin password and secret, a production WSGI server, and secure persistent storage. The development server binds to localhost by default and is intended for local testing.

## Automatic gold & silver rates
**Sources (free, no API key):** 1) AKGSMA home page `akgsma.com` (publishes 22K/916, 18K/750, silver per gram) and 2) `livegoldkerala.com/kozhikode`, which republishes the AKGSMA Kerala board rate. The source with the newest rate date wins; AKGSMA wins ties. Neither offers an official API, so pages are read as HTML. Check each site's terms before commercial use.
**Labels:** *Quoted* = published by the source. *Calculated estimate* = derived (24K = 22K×24/22, 995, 585, silver 800, and 925 when not published); never official quotes.
**Schedule:** APScheduler runs daily at `SYNC_TIMES` (default `10:30`, Asia/Kolkata, comma-separated for more). A catch-up runs 10 s after start if no sync succeeded in 20 h. A database claim prevents duplicate runs across workers/restarts (2-minute minimum gap, also limits "Update now").
**Safety:** values outside plausible ranges or >15% from the last rate are rejected; if all sources fail the last rate is kept and shown as *stale* with its original date. A manual correction is recorded (old/new/time) and pauses auto-updates for that metal until "Resume automatic updates".
**Not running continuously?** Set `SYNC_SCHEDULER=0` and use Windows Task Scheduler: Create Basic Task → Daily 10:30 → Start a program → `run_sync.bat` (in the project folder). Log: `sync.log`.
**Tests:** `python -m unittest discover tests` (mocked responses).
**Upgrade:** `pip install -r requirements.txt` (adds APScheduler). Existing databases migrate automatically.

## GST on bills
Per item you choose the GST basis. Gold defaults to **3% on metal value (incl. wastage) + 5% on making/extra charges**; silver defaults to **3% on the total value**. Both rates are editable per item, and a discount is shared proportionally across metal and making. Old bills without a basis keep the single-rate calculation. Sources disagree on whether retail jewellery making charges attract 3% (composite supply) or 5%: confirm with your CA and use the "3% on total value" basis if that is your advice.

## Quick start
Copy `.env.example` to `.env` and set a unique `ADMIN_PASS` and a random `SESSION_SECRET` (at least 32 characters) before first run. Double-click `run.bat` or use `py -m pip install -r requirements.txt` then `py app.py`. If you omit `ADMIN_PASS` on a brand-new database, the app generates a random initial admin password and prints it once in the server console; save it immediately. Never use a known/default password on a public site.


## Customer storefront redesign
The customer-facing pages now use a responsive, ZIVORA-inspired editorial layout (hero, collections, product cards, contact form, and dark footer). The existing Flask routes, admin screens, billing/invoices, database and rate-sync code were left unchanged. Storefront sample catalogue cards are presentation examples; they are not connected to a product inventory API. Product enquiry and contact form actions open WhatsApp to +91 97459 21737. Product photography is loaded from Unsplash URLs and therefore requires internet access. The newsletter form is a visual placeholder and is not connected to an email marketing service.


## Public launch status (v23)
See `PUBLIC_LAUNCH_AUDIT_V23.md`. This is a hardened pre-launch build, not certified production-ready. Public checkout is disabled in `APP_ENV=production` until server-side product and price validation exists. Deploy behind HTTPS and a reverse proxy using `run_production.py`; do not expose the Flask development server directly to the internet.


## v32 verification notes
- Windows launcher explicitly selects port 9000 and creates `.env` from `.env.example` when absent.
- Shop product-card source contains Add to Bag, Shop Now, Product Details and Enquire with Photo & Weight controls.
- Collection navigation stores the selected collection in session storage and applies the category filter after navigating to Shop.
- Static checks and rate-sync unit tests were run in the build environment. Full Flask/browser end-to-end checkout and admin workflows still require testing on the target Windows machine.


## Admin login recovery (v33)
For local testing only, the default administrator login is username `asianadmin` and password `asianadmin916`. On the first v33 startup, the app applies these credentials once to an existing local database using a versioned migration; customers, orders, bills, rates, and products are preserved. The migration does not reapply on every restart, so later password changes persist. Change this password before any public deployment. Production mode still requires explicitly configured secure secrets and rejects the known default password.

## Local administrator accounts (v34)

This build supports two administrator usernames:

- `asianadmin` — initial local password `asianadmin916`
- `asian` — initial local password `asian916`

The two accounts are seeded into the `admin_accounts` table once on first startup of this build. They are separate accounts and share the existing admin permissions. Keep the database private and change these initial passwords before public hosting. The seeding marker prevents these passwords from being reset on every restart.

### Single-device admin login (v35)

Each administrator username can have only one active login session at a time. If the same username is already signed in elsewhere, another login attempt returns: `Admin already login on another device. Please log out from that device and try again.` Logging out releases that username's session. A session lease expires after 24 hours without an authenticated request; active admin requests extend it. The two different admin usernames may still be used independently.


## Durable free-tier deployment (PostgreSQL)

The default local database is SQLite (`data.db`). A free Render web service's local filesystem is ephemeral, so do not use that default for customer records in production. To use a durable external PostgreSQL database, set `DATABASE_URL` to a PostgreSQL connection string in Render. This project uses `DATABASE_URL` automatically when it begins with `postgres://` or `postgresql://`; otherwise it uses `DB_FILE`/`data.db`. Add `DATABASE_URL` as a GitHub Actions repository secret too if you want scheduled rate refreshes and backups. Keep the repository private because backups contain customer information.

### Setup checklist

1. Create a free PostgreSQL project with a provider such as Neon and copy its PostgreSQL connection string. Free-tier limits and availability are controlled by the provider and can change.
2. In Render → your web service → Environment, set `DATABASE_URL` to that connection string. Keep `APP_ENV=production`, `ADMIN_USER`, `ADMIN_PASS`, and `SESSION_SECRET` configured with unique private values.
3. In GitHub → repository Settings → Secrets and variables → Actions, add a repository secret named `DATABASE_URL` with the same connection string. Keep the GitHub repository private.
4. Push the updated code to `main`. Render should redeploy. Test customer registration, product creation, ordering, billing, and a redeploy before accepting real orders.
5. The `.github/workflows/daily-maintenance.yml` workflow attempts a daily rate refresh and creates a JSON backup artifact. GitHub scheduled workflows may run late; backup artifacts are retained for 30 days. Download important backups regularly and keep an independent copy.
6. If you have a local `data.db` that contains records you want to keep, make a copy and use `migrate_sqlite_to_postgres.py` before switching live traffic. It requires `DATABASE_URL`, `DB_FILE` pointing to the old database, and valid production `ADMIN_USER`, `ADMIN_PASS`, and `SESSION_SECRET` values. Do not expect it to recover records already lost from Render's temporary filesystem.

### Backups

An authenticated administrator can download a JSON operational backup from `/api/admin/backup`. It excludes administrator sessions and private authentication settings. The scheduled GitHub workflow also uploads a backup artifact for 30 days. Backups contain private customer data: do not make this repository public and do not publish backup files.

### Product images

When PostgreSQL is enabled, newly uploaded product images are stored as data URLs inside the product record so they survive Render redeploys. Older image files stored only in `public/uploads` need to be copied/migrated separately if you still have them.
