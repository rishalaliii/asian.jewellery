# Product Enquiries and Live Dashboard (v28)

## Product enquiries
- Public product cards include **Enquire with photo & weight**.
- The customer is prompted for name, phone, optional email, and question.
- The enquiry stores product name, category, local or HTTPS image reference, recorded approximate weight, contact details, message, status, and timestamps.
- Admin navigation includes **Product Enquiries**. Open each enquiry to inspect the image and weight, contact the customer, and update status (New, Contacted, Quoted, Converted, Closed).
- The enquiry API is public by design; it validates required fields and size limits. Add a reverse-proxy rate limit or CAPTCHA before a public launch to reduce spam.

## Dashboard incoming orders
- Dashboard includes a direct link to **Online Order History** and **Product Enquiries**.
- Incoming online orders refresh every 15 seconds while the dashboard is open.
- Each incoming order has an **Open order** link that navigates to Order History and expands the corresponding order.

## Validation performed
- `python -m py_compile app.py rates_sync.py` passed.
- Existing rate-sync unit tests: 7/7 passed.
- Inline JavaScript syntax check with Node passed.
- Full Flask endpoint test could not run in this environment because Flask is not installed here. Run `py -m pip install -r requirements.txt` on Windows, then test enquiry submission and admin follow-up before public hosting.
