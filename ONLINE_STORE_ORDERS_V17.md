# Online Store Orders v17

## Admin section
The admin navigation now exposes **Order History** as the online-store order management section. It displays customer details, line items, total, delivery address/instructions, order status, payment status/method/amount/reference, and whether an invoice has been created.

## Payment recording
Admins can record `Not received`, `Pending verification`, `Received`, or `Refunded`, select UPI/card/cash/bank transfer/other, enter the amount and transaction reference, and save the details. For UPI/card/bank transfer marked Received, a transaction/reference number is required. Amount recorded is capped at the order total. This is an admin record only; it does not verify payment with a bank or payment gateway.

## Create invoice
`Add to Bill / Create Invoice` creates a bill linked to the order and opens it in the existing bill editor/preview. It copies customer phone and delivery address and turns each order line into a fixed-price invoice line using the submitted order price. Review the invoice, product tax treatment and GST before issuing it; this is not a substitute for verified product pricing or tax review. Duplicate invoice creation is avoided by retaining the order's `bill_id`.

## Database migration
The app additively adds payment status, method, amount, reference and bill ID columns to existing `orders` tables. Existing order records are retained.

## Checks
- Python compilation: passed (`app.py`, `rates_sync.py`).
- Existing rate-sync unit tests: 7/7 passed.
- JavaScript syntax: passed with Node.js.
- ZIP integrity: checked after packaging.
- Full Flask endpoint/browser integration test could not be run in this environment because Flask is not installed. Run `py -m pip install -r requirements.txt` locally and test customer order creation, admin payment updates, and bill creation before production use.
