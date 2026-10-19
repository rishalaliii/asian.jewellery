# Checkout delivery details — v10

## Changes
- Added required delivery address, city/town, state, and six-digit PIN code fields to checkout.
- Added optional delivery instructions.
- Customer orders persist delivery details in SQLite.
- Existing databases are upgraded safely with additive columns; existing orders are retained.
- Admin order history displays the saved delivery address and notes.
- WhatsApp order message includes the order reference, cart, estimated total and delivery details.
- Checkout requires customer sign-in and server-side validation of delivery fields.

## Verification performed
- `python -m py_compile app.py` passed.
- `node --check` passed for the storefront script.
- All 7 existing rate-sync unit tests passed.
- ZIP integrity checked after packaging.

## Important limitations
- A full Flask/browser end-to-end test was not run in this environment because Flask is not installed here.
- Catalogue products and prices are still the existing sample storefront catalogue; this change does not connect the product grid to an inventory-management system.
- The displayed total is an estimate and the shop must confirm availability, final price and delivery before the order is accepted.
