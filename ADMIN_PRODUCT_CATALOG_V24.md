# Admin Product Catalogue v24

## Manage products
1. Start the app and sign in as the administrator.
2. Open **Products** in the admin navigation.
3. Enter a unique SKU, product name, category, product type, metal/purity, weight, making charge, stone/diamond allowance, stock, description and optional image.
4. Choose **Rate + weight + making + stone** for gold/silver items priced from the saved metal rate, or **Fixed approved price** for manually approved prices (especially diamonds/gemstones).
5. Choose Published to show the product on the public Home, Shop and Collections catalogue, or Hidden to keep it out of the public catalogue.
6. Use Edit to update a product and Hide to remove it from the storefront without deleting historical references.

## Images
- JPG/JPEG, PNG and WebP accepted, maximum 4 MB each.
- Images are saved in `public/uploads/` with random generated filenames; do not upload confidential images.
- A product can be saved without a photo; a storefront fallback image is shown.

## Price behaviour
- Rate mode calculates from the latest saved server rate for the selected metal/purity, weight in grams, making charge per gram and stone/diamond charge. Displayed prices exclude GST.
- Fixed mode uses the admin-entered approved price. Diamond pricing must be manually verified; metal rates do not value diamonds.
- These values are shop-maintained catalogue data. Confirm purity, net/gross weight, making charges, stone details, tax treatment and actual stock before publishing real products.

## Orders and stock
- The public catalogue exposes active products only.
- For managed catalogue products, the server recalculates the price and checks stock when the order is submitted; browser-supplied price is not trusted.
- Stock is deducted when an order moves from an unaccepted state to Accepted/Confirmed/Processing/Ready for pickup/Shipped/Completed, and restored if it moves back to Declined/Cancelled/Received. Test this lifecycle with test products before taking real orders.
- Legacy/demo storefront products do not have server-managed inventory. In production, these cannot be ordered through checkout unless `ALLOW_CLIENT_PRICED_ORDERS=1` is deliberately enabled. Do not enable that setting for public production use.

## Deployment notes
- Keep the SQLite database persistent and back it up before upgrades.
- Configure `APP_ENV=production`, a unique `SESSION_SECRET` of at least 32 characters, and a strong `ADMIN_PASS` through environment configuration.
- The project still needs full live browser, payment-provider and hosting verification before public launch. No payment gateway is included; admin payment status remains manual.
