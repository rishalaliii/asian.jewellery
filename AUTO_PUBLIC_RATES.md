# Automatic public gold and silver rates

The public `GET /api/rates` endpoint now attempts an external rate sync when no sync has run in the last five minutes. This means loading the Home, Gold Rates, Silver Rates, or billing pages that call this endpoint can refresh the published rates without an admin manually clicking “Update rates now”.

- Existing rates remain visible if external websites are unavailable.
- The rate-sync module's shared 120-second claim prevents concurrent requests from repeatedly fetching sources.
- Manual admin corrections remain protected by the existing sync logic.
- The daily background scheduler remains enabled when its dependency (`APScheduler`) is installed.

To enable the daily scheduler on Windows, install dependencies from the project folder with `py -m pip install -r requirements.txt`. Live external fetching still depends on the configured source websites being reachable and retaining a compatible page layout.
