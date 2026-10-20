"""Run from GitHub Actions to refresh metal rates even while Render sleeps."""
import json, os, sys
from db_compat import DATABASE_URL, USE_POSTGRES
import rates_sync
if not DATABASE_URL or not USE_POSTGRES:
    print('DATABASE_URL must be set to a PostgreSQL connection string.', file=sys.stderr)
    raise SystemExit(2)
result = rates_sync.run_sync(DATABASE_URL, 'github-actions-daily')
print(json.dumps(result, indent=2))
if not result.get('ok') and not result.get('skipped'):
    raise SystemExit(1)
