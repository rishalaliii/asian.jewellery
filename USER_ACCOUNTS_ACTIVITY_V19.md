# Asian Jewellery v19 — Customer account administration and activity log

## Admin sections
- **Customer Accounts** lists registered accounts with registration date, active/disabled state, order count and total order value.
- Open a customer row to edit name, email, phone, enable/disable the account, or reset its password.
- **Activity Log** lists recent customer/admin events including account registration, successful and failed customer login, logout, order creation, order status/payment changes, account edits, password reset, and order-to-bill conversion.

## Security and privacy
- Passwords remain hashed and are never returned to the admin UI or written to the activity log.
- Payment card details and credentials are not collected or logged; the activity log notes only the payment status, method, amount, and whether a reference was present.
- Failed customer login events do not store the attempted email/phone identifier.
- Disabling a customer prevents future login and customer profile/order access. An already-issued browser session is rejected on the next customer API request.
- Existing customer databases are upgraded with an additive `active` column and `activity_log` table; existing customer/order/bill records are not intentionally deleted.

## Verification
- Python compilation: passed.
- SQLite schema creation: passed.
- Existing rate-sync unit tests: 7 passed.
- JavaScript syntax check: passed.
- Full Flask/browser end-to-end tests were not run in this build environment.

## Recommended first-run checks
1. Run `run.bat` and log in as admin.
2. Open **Customer Accounts**, edit a test account, disable it, and verify it cannot log in; then re-enable it.
3. Reset the test account password and confirm login with the new password.
4. Open **Activity Log** and verify the actions are recorded.
5. Create a test order and update its status/payment to confirm those events appear.
