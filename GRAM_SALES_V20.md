# Gram Sales in Admin Dashboard (v20)

## Added
- Today's recorded gross grams for in-store bills, online orders, and combined total.
- Lifetime recorded gross grams for in-store bills, online orders, and combined total.
- In-store grams are calculated from each saved bill line's `gross × qty`.
- Online grams are calculated from saved order item `weight_grams × qty` (or legacy `weight × qty`).
- Online orders converted into bills are excluded from in-store gram totals to prevent double counting.
- Online order creation now preserves a supplied `weight_grams` value for future reporting.

## Important data limitation
The app does not infer jewellery weight from a product's price. Existing online orders without a saved weight are counted as 0 recorded grams, not as a guessed weight. For meaningful online gram reports, add verified weight (in grams) to each product and ensure that weight is passed with the cart item. In-store gram totals use the gross-weight values entered on bills.

## Validation
- `python -m py_compile app.py rates_sync.py`
- Existing rate-sync tests: 7 passed.
- ZIP integrity checked after packaging.
