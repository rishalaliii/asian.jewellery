# Asian Jewellery v14 — Integration audit

## Fixes made during audit
- Changed Flask bind address to `0.0.0.0` so the site can be reached from a phone on the same private Wi-Fi; README warns not to expose the development server directly to the public internet.
- Corrected two malformed product image paths to use existing local image files.
- Fixed cart quantity validation so fractional quantities cannot silently become zero; zero still prompts for confirmation before removal.
- Changed public rate refresh to run in a background thread, so visitors are not held waiting for slow external rate websites. The existing sync claim still prevents concurrent source fetching.
- Changed newsletter submission from a misleading success alert to opening an email draft addressed to the shop. This is not a mailing-list service integration.
- Opened the WhatsApp checkout tab synchronously before the asynchronous order save to reduce popup-blocker failures; if popups are blocked, the order is still saved and the reference is shown.

## Checks performed in this environment
- `python -m py_compile app.py rates_sync.py`: passed.
- `python -m unittest discover -s tests -v`: 7/7 existing rate-sync tests passed.
- `node --check` on inline storefront JavaScript and `calc.js`: passed.
- HTML parser: passed.
- Local product/collection/about image assets: checked; corrected the two broken product paths.
- Old `shipzivora@gmail.com` address: not present in `public/index.html`.
- ZIP integrity: checked after packaging.

## Important limitations
- Flask is not installed in this execution environment and package installation is unavailable, so Flask API endpoints, SQLite migrations, sessions, order creation, admin billing and real external rate fetching could not be executed end-to-end here.
- A browser smoke test was attempted but local HTTP navigation was blocked by the execution environment. No claim is made that real-device browser testing passed.
- Product catalogue/prices are still hard-coded sample storefront data, and the server currently accepts the submitted product prices from the browser. Do not treat the current order total as a secure payment amount; confirm stock and final price manually. A server-managed catalogue is needed before production sales.
- Newsletter uses an email draft; no subscription database or mailing provider is connected.
- The Flask development server is not a production deployment server. For public internet use, configure a production WSGI server, HTTPS, secure secrets, firewall rules and backups.
