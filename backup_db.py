"""Create a JSON backup of operational data from PostgreSQL or local SQLite."""
import json, os
from datetime import datetime, timezone
from pathlib import Path
from db_compat import connect, DATABASE_URL, USE_POSTGRES

TABLES=('customers','products','orders','bills','activity_log','rates','product_enquiries','sync_log','rate_audit')
SAFE_KV={'shop','sync_cfg'}
def main():
    target=DATABASE_URL if USE_POSTGRES else os.environ.get('DB_FILE','data.db')
    out=Path(os.environ.get('BACKUP_DIR','backups')); out.mkdir(parents=True,exist_ok=True)
    snap={'created_at':datetime.now(timezone.utc).isoformat(),'format':'asian-jewellery-operational-backup-v1','tables':{}}
    with connect(target) as db:
        for table in TABLES:
            try: snap['tables'][table]=[dict(r) for r in db.execute(f'SELECT * FROM {table}').fetchall()]
            except Exception: snap['tables'][table]=[]
        try:
            snap['tables']['kv']=[dict(r) for r in db.execute('SELECT k,v FROM kv').fetchall() if r['k'] in SAFE_KV]
        except Exception: snap['tables']['kv']=[]
    path=out/f'asian-jewellery-backup-{datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")}.json'
    path.write_text(json.dumps(snap,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(f'Created backup: {path} ({path.stat().st_size} bytes)')
if __name__=='__main__': main()
