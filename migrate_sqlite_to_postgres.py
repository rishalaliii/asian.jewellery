"""One-time migration for an existing local data.db into DATABASE_URL PostgreSQL.
Set APP_ENV=production and strong ADMIN_USER/ADMIN_PASS/SESSION_SECRET before running.
"""
import os, sqlite3, sys
from pathlib import Path
from db_compat import connect, DATABASE_URL, USE_POSTGRES

def main():
    if not USE_POSTGRES or not DATABASE_URL:
        raise SystemExit('Set DATABASE_URL to the target PostgreSQL connection string first.')
    source=Path(os.environ.get('DB_FILE','data.db'))
    if not source.exists(): raise SystemExit(f'SQLite source database not found: {source}')
    # Import app once to create/upgrade the destination schema. Production secrets must be set.
    import app  # noqa: F401
    src=sqlite3.connect(source); src.row_factory=sqlite3.Row
    tables=['customers','products','orders','bills','activity_log','rates','product_enquiries','sync_log','rate_audit']
    with connect(DATABASE_URL) as dst:
        for table in tables:
            exists=src.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
            if not exists: continue
            cols=[r['name'] for r in src.execute(f'PRAGMA table_info({table})')]
            if not cols: continue
            count=0
            for row in src.execute(f'SELECT * FROM {table}'):
                values=[row[c] for c in cols]
                marks=','.join('?' for _ in cols)
                cur=dst.execute(f'INSERT INTO {table} ({",".join(cols)}) VALUES ({marks}) ON CONFLICT DO NOTHING',values)
                count += 1
            print(f'{table}: copied/checked {count} rows')
        # Keep non-secret shop and sync settings only; do not migrate admin session tokens.
        if src.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='kv'").fetchone():
            for row in src.execute("SELECT k,v FROM kv WHERE k IN ('shop','sync_cfg')"):
                dst.execute('INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT (k) DO UPDATE SET v=EXCLUDED.v',(row['k'],row['v']))
        for table in tables:
            try: dst.execute(f"SELECT setval(pg_get_serial_sequence('{table}','id'), GREATEST(COALESCE((SELECT MAX(id) FROM {table}),1),1), EXISTS(SELECT 1 FROM {table}))")
            except Exception: pass
    src.close(); print('Migration finished. Verify record counts before changing production traffic.')
if __name__=='__main__': main()
