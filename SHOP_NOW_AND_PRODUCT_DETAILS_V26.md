# Shop Now and Product Details — v26

## Customer storefront
- Added **SHOP NOW** beside **ADD TO BAG** on both built-in catalogue products and admin-managed products.
- SHOP NOW adds the selected item to the cart and navigates directly to the Shopping Bag (`#Cart`) so the customer can review quantity, delivery details and checkout.
- Added **PRODUCT DETAILS** toggles on product cards. These show the description, material/purity, approximate weight and any administrator-entered product features.
- On mobile, action buttons use a responsive two-column layout with a full-width details action.

## Admin product catalogue
- Added a **Product details & peculiarities** textarea to the Products form.
- Details are stored in the `products.features` field and displayed on the public product card details panel.
- Existing databases are migrated additively; existing product records are preserved and receive an empty features value.
- Existing create/update handlers save this field, and the edit form loads it.

## Checks
- Python compilation: passed.
- Inline JavaScript syntax (`node --check`): passed.
- Existing rate-sync tests: 7/7 passed.
- ZIP integrity: checked after packaging.
- Full Flask endpoint/browser tests could not be run in this environment because Flask is not installed. Run `py -m pip install -r requirements.txt` on Windows, then test product create/edit, details display, Add to Bag, and Shop Now.

## Price and inventory note
Displayed built-in catalogue prices remain estimates; actual sale prices, weights, stock and product characteristics should be confirmed against the admin-managed catalogue before accepting orders.
