# Asian Jewellery — final pre-launch audit (v23)

## Changes in this release
- Added basic same-origin checks for state-changing `/api/` requests when `Origin`/`Referer` is supplied.
- Added a per-process login failure throttle (10 failures per IP per 10 minutes) for admin and customer login.
- Added response security headers, request-size limit, secure-cookie setting in `APP_ENV=production`, and production startup guards for a missing/short `SESSION_SECRET` or the known default admin password.
- New installations receive a randomly generated admin password printed once in the server console if `ADMIN_PASS` is not configured. Save it immediately.
- Added a Waitress WSGI entry point and updated Windows launcher to use a virtual environment.
- In production, customer checkout is disabled by default because storefront prices and weights are currently submitted by the browser and are not validated against a server-owned product catalogue. This avoids treating user-modified client prices as authoritative. Do not enable `ALLOW_CLIENT_PRICED_ORDERS=1` for real sales.

## Checks actually performed here
- `python -m py_compile app.py rates_sync.py run_production.py`: passed.
- `python -m unittest discover -s tests -v`: 7/7 existing rate-sync unit tests passed.
- JavaScript syntax check: see test report generated with this package; static checks only.
- ZIP integrity check: performed after packaging.

## Not performed / production blockers
This environment did not have Flask/Waitress installed and network access was unavailable, so the app could not be launched for live HTTP/browser testing. The following are still required before public launch:
1. Install requirements on the deployment machine and run browser/end-to-end tests for customer login, account disable/reset, admin sessions, bill calculations, order state changes, payments, report dates, and WhatsApp.
2. Implement a server-managed product catalogue (SKU, metal/purity, actual gross/net weight, stock, current approved price/making charge, image) and calculate/validate order totals on the server. Until then public checkout intentionally returns HTTP 503 in production.
3. Integrate a payment gateway before representing card/UPI as automatically paid. Current payment status is manually entered by admin; never collect card numbers or UPI PINs in this app.
4. Confirm real business identity, GSTIN, tax treatment, refund/shipping/privacy terms and product certifications. Placeholder GSTIN/shop settings must be replaced.
5. Deploy behind HTTPS/reverse proxy, persistent storage and backups; configure firewall, monitoring, and a recovery procedure. Do not expose Flask's built-in development server directly to the public internet.
6. Review privacy/consent and retention for customer contact/address data and activity logs.

## Deployment configuration
- Copy `.env.example` to `.env`, use a strong unique `ADMIN_PASS`, and generate `SESSION_SECRET` with at least 32 random characters. Never upload `.env`.
- For local testing: `py -m pip install -r requirements.txt`, then `py app.py`.
- For a production process: set `APP_ENV=production` and run `py run_production.py` behind a TLS reverse proxy. Waitress listens on 127.0.0.1 by design.
- Keep `ALLOW_CLIENT_PRICED_ORDERS=0` until server-side pricing validation exists.
- Back up `data.db` before replacing the project. Do not overwrite it during deployment.

## Scope statement
This is a hardened pre-launch build, not a certification that the site is production-ready. Static checks and rate-sync unit tests are not a substitute for live integration, security review, payment testing, or jewellery-business compliance review.
