# v31 — Shop controls, collection filtering, and port 9000

- `run.bat` sets `PORT=9000` and opens `http://127.0.0.1:9000`.
- Flask defaults to port 9000 when PORT is not provided.
- Product image-overlay quick-add is hidden so it cannot be mistaken for the only purchase action.
- Product cards force visible, high-contrast ADD TO BAG, SHOP NOW, PRODUCT DETAILS, and ENQUIRE WITH PHOTO & WEIGHT controls beneath product details.
- Collection click handling stores the selected collection before navigating to Shop and applies the filter after render.
- Collection filtering supports category aliases for necklaces, chains, bangles/kadas, earrings, rings, anklets, diamonds, gemstones, silver jewellery, and silver articles.

## Run
1. Stop older server windows.
2. Run `run.bat` from this folder.
3. Open `http://127.0.0.1:9000`.
4. From a phone on the same Wi-Fi, use `http://YOUR-PC-IP:9000`.
5. Hard-refresh with Ctrl+Shift+R.
