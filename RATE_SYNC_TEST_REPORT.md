# Asian Jewellery — Rate Sync Verification

## Automated tests

Ran `python -m unittest discover -s tests -v` against `rates_sync.py`.

Result: **7/7 tests passed**.

Covered scenarios include duplicate-run protection, source failover and total failure preserving existing rates, freshest-source selection and source labels, safe failure on page-layout changes, protection of manual corrections, parsing, and plausibility validation.

## Additional checks

- Python parser accepted a representative AKGSMA-format sample and extracted its date, 22K, 18K, silver, and 925 silver values.
- `requirements.txt` includes `APScheduler>=3.10,<4.0`.
- APScheduler is not installed in this verification environment, so the background scheduler could not be started here. Install project dependencies on Windows using `py -m pip install -r requirements.txt`.

## Not verified

- Live external source fetches and current market rates were not verified.
- The daily task was not observed running on the user's Windows computer.
- Unit tests do not guarantee that third-party websites keep the same HTML layout.

## Windows verification

1. Open Command Prompt in the project folder.
2. Run `py -m pip install -r requirements.txt`.
3. Run `py -m unittest discover -s tests -v`.
4. Run `py rates_sync.py` to request a live sync and inspect the output.
5. Confirm the result says `"ok": true` and check the admin rate status for current/stale state. If a source is unavailable or its page layout changed, the sync may report notes and retain previously stored rates.
