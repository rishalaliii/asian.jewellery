# Customer accounts

This version adds server-side customer registration and login using the existing SQLite database (`customers` table). Passwords are stored as Werkzeug password hashes, never as plaintext. Customer sessions are separate from the existing admin session; logging in as either role clears the previous session.

## Customer features
- Register with name, email, phone and password (minimum 8 characters).
- Sign in using email or phone number and password.
- View basic account details and log out.
- Email and phone are unique per customer.

## API routes
- `POST /api/customer/register` — `{ "name", "email", "phone", "password" }`
- `POST /api/customer/login` — `{ "identity", "password" }`
- `GET /api/customer/profile` — requires a customer session
- `POST /api/customer/logout`
- `GET /api/me` — reports current admin/customer session

## Important limitations
Cart and wishlist still use browser-local storage and do not sync between devices. Orders are not stored in the database yet. Configure a stable `SESSION_SECRET` in `.env` before deploying, use HTTPS, change the default admin password, and back up `data.db` regularly. This project has not undergone a professional security audit.

## Customer orders (added in this version)

- Signed-in customers can submit their cart to the server using `POST /api/customer/orders`.
- Customers can view their own orders at `GET /api/customer/orders` and in the Account page.
- Admins can review orders at `GET /api/admin/orders` and change their status using `PATCH /api/admin/orders/<id>`.
- Supported statuses: Received, Confirmed, Processing, Ready for pickup, Shipped, Completed, Cancelled.
- When a customer checks out, the order is saved in SQLite first; WhatsApp then opens with an order reference. The customer must still send the WhatsApp message and the shop must confirm availability/payment/delivery.
- The checkout price is the displayed catalogue price sent by the browser; this project still uses sample storefront product data, so confirm product pricing and availability before accepting payment.
