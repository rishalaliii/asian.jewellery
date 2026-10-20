# Asian Jewellery v38 — free-tier deployment checklist

This version supports local SQLite for development and external PostgreSQL for a hosted deployment. A free Render web service's local filesystem is not durable; use a PostgreSQL `DATABASE_URL` for live records.

## 1. Create the database

Create a free PostgreSQL project with a provider such as Neon (subject to that provider's current free-tier limits). Copy the connection string that starts with `postgresql://` or `postgres://`. Keep it private.

## 2. Configure Render

In Render → `asian-jewellery` → Environment, set:

- `DATABASE_URL` = your PostgreSQL connection string
- `APP_ENV` = `production`
- `ADMIN_USER` = your own admin username
- `ADMIN_PASS` = a new strong password
- `SESSION_SECRET` = a random secret of at least 32 characters

Build command: `pip install -r requirements.txt`

Start command: `python run_production.py`

Push the updated code to the same GitHub repository. Render should deploy the new commit. The app creates its tables at startup.

## 3. Enable daily rate refresh and backup

Keep the GitHub repository **Private**. Go to repository Settings → Secrets and variables → Actions → New repository secret. Add:

- Name: `DATABASE_URL`
- Value: the same PostgreSQL connection string

The workflow in `.github/workflows/daily-maintenance.yml` runs daily (GitHub may delay scheduled runs), refreshes rates, and creates a JSON backup artifact retained for 30 days. In GitHub → Actions, run it manually once and check the run. Download backup artifacts regularly and keep a separate copy. A backup is not a restore until you've tested recovery.

## 4. Existing data

Do not expect this migration to recover data already lost from Render's temporary filesystem. If you still have a local `data.db`, back it up first, then use `migrate_sqlite_to_postgres.py` with `DB_FILE` pointing at the local file and the destination `DATABASE_URL` set. The migration imports customer, product, order, bill, activity, rate and enquiry records while avoiding overwriting existing IDs. Check the counts afterward. Old product image files under `public/uploads` may need to be copied separately; new uploaded images are stored in PostgreSQL-backed product records when PostgreSQL is enabled.

## 5. Smoke-test after deployment

- Register a test customer and sign out/in again.
- Create a published test product in Admin → Products and check `/api/products` plus the Shop page.
- Place a test order using that managed product; confirm it appears in Admin → Orders and opens WhatsApp with the order details ready to send.
- Create a test bill and check the invoice/history.
- Redeploy or restart the service and verify the test records remain.
- Delete the test records when done.

## 6. Backup endpoint

An authenticated admin can download an operational JSON snapshot at `/api/admin/backup`. It excludes administrator sessions and private authentication settings. Treat all backups as confidential because they include customer data.
