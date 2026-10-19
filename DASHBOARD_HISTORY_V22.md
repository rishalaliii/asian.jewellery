# Dashboard Historical Reports v22

## Changes
- Added a date picker to the admin Dashboard. It automatically loads today's report when the dashboard opens; selecting any earlier date and clicking **Load selected date** loads that day's report.
- Added an authenticated `/api/admin/report?date=YYYY-MM-DD` endpoint.
- The report shows date-specific in-store sales and paid amount, accepted online order sales and recorded received payments, recorded gram totals, all in-store bills, all bills linked to online orders, and every online order with customer contact/delivery data, line items, order/payment status, reference and bill ID.
- Each in-store bill can be opened directly from the report in the existing bill editor.
- Sales and grams count accepted/processed online orders only. Incoming `Received`, `Declined`, and `Cancelled` orders remain visible in the order list but do not contribute to online sales or grams. Online-linked bills are identified and excluded from in-store totals to prevent double-counting.
- Responsive, horizontally scrollable tables and high-contrast buttons are included for mobile screens.

## Validation performed
- `python -m py_compile app.py rates_sync.py`: passed.
- Existing rate-sync tests: 7/7 passed.
- Inline JavaScript extracted from `public/index.html`: `node --check` passed.
- ZIP integrity check: passed.
- A live Flask endpoint integration test could not be run in this environment because Flask is not installed. Install the project's requirements on Windows and test current/previous dates with actual records before relying on the report for accounting.

## How to use
1. Sign in to Admin and open Dashboard.
2. Today's report loads automatically.
3. Choose any previous date in the date picker and select **Load selected date**.
4. Open an in-store bill with **Open bill**. Online orders are fully listed with customer and payment details; use Order History for order actions and status changes.
