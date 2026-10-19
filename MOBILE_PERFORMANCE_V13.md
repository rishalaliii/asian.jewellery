# Asian Jewellery v13 — Mobile and performance improvements

## Changes
- Reworked mobile header into a compact logo/icons row and horizontally scrollable navigation.
- Added mobile layouts for hero, category/product grids, filters, cart rows, forms, contact section and footer.
- Increased touch target sizes and added visible keyboard-focus styles.
- Added reduced-motion support and horizontal overflow safeguards.
- Removed the external Google Fonts CSS import so first paint does not wait for that stylesheet; system font stacks are used for speed and offline resilience.
- Kept local jewellery image assets and verified the main hero/product/collection image paths exist.
- Stopped re-rendering the Home page every minute just to refresh the rate ticker; the ticker still refreshes, and the Gold/Silver Rates pages refresh as before.
- Corrected the phone number shown in the scrolling rate ticker to +91 97459 21737.

## Checks performed
- Python compilation: passed (`app.py`, `rates_sync.py`).
- Existing rate-sync unit tests: 7 passed.
- JavaScript syntax: passed (inline storefront script and `calc.js`).
- HTML parser: completed.
- Key local image paths: present.
- Old `shipzivora@gmail.com` address: not found in `public/index.html`.

## Not claimed as verified
No live browser/device matrix, real external rate-source fetch, checkout transaction, or production deployment test was performed here. Please test on a phone and desktop before deploying. This update does not guarantee every possible bug is removed.
