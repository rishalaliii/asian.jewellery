"""Small SQLite/PostgreSQL compatibility layer for Asian Jewellery.
Use DATABASE_URL (e.g. a free managed PostgreSQL URL) for durable hosted storage.
"""
import os, re, sqlite3
from pathlib import Path

# Support local .env files as well as host-provided environment variables.
_env_file=Path(__file__).resolve().parent/'.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        _line=_line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _key,_value=_line.split('=',1); os.environ.setdefault(_key.strip(),_value.strip().strip('\"').strip("'"))
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
USE_POSTGRES = DATABASE_URL.startswith(('postgres://', 'postgresql://'))

class Row(dict):
    def __init__(self, values=(), names=()):
        if isinstance(values, dict): super().__init__(values)
        else: super().__init__(zip(names, values))
        self._names=list(self.keys())
    def __getitem__(self, key):
        if isinstance(key, int): key=self._names[key]
        return super().__getitem__(key)

def _row_factory(cur):
    names=[d.name for d in cur.description] if cur.description else []
    return Row(cur.fetchone(), names) if False else None

class Cursor:
    def __init__(self, cur, lastrowid=None, inserted=False): self._cur=cur; self.lastrowid=lastrowid; self._inserted=inserted; self.rowcount=cur.rowcount
    def fetchone(self):
        if self._inserted: self._inserted=False; return None
        row=self._cur.fetchone()
        if row is None: return None
        if isinstance(row, dict): return Row(row)
        names=[d.name if hasattr(d,'name') else d[0] for d in (self._cur.description or [])]
        return Row(row,names)
    def fetchall(self):
        rows=self._cur.fetchall(); names=[d.name if hasattr(d,'name') else d[0] for d in (self._cur.description or [])]
        return [Row(r) if isinstance(r,dict) else Row(r,names) for r in rows]
    def __iter__(self): return self
    def __next__(self):
        row=self.fetchone()
        if row is None: raise StopIteration
        return row

class PGConnection:
    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self._c=psycopg.connect(url, row_factory=dict_row, connect_timeout=15)
    def __enter__(self): return self
    def __exit__(self, typ, val, tb):
        if typ: self._c.rollback()
        else: self._c.commit()
        self._c.close()
    def close(self): self._c.close()
    def commit(self): self._c.commit()
    def rollback(self): self._c.rollback()
    def executescript(self, script):
        script=script.replace('INTEGER PRIMARY KEY AUTOINCREMENT','BIGSERIAL PRIMARY KEY')
        for stmt in script.split(';'):
            if stmt.strip(): self.execute(stmt)
    def execute(self, sql, args=()):
        original=sql.strip(); q=original
        # SQLite metadata query compatibility.
        m=re.fullmatch(r"PRAGMA table_info\((\w+)\)", q, re.I)
        if m:
            table=m.group(1)
            cur=self._c.execute("SELECT ordinal_position-1 AS cid,column_name AS name,data_type AS type,CASE WHEN is_nullable='NO' THEN 1 ELSE 0 END AS notnull, column_default AS dflt_value,CASE WHEN column_name='id' THEN 1 ELSE 0 END AS pk FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,))
            return Cursor(cur)
        q=re.sub(r'\?', '%s', q)
        q=q.replace('SELECT last_insert_rowid()', "SELECT currval(pg_get_serial_sequence('products','id'))")
        # SQLite INSERT OR IGNORE -> PostgreSQL ON CONFLICT DO NOTHING.
        if re.match(r'INSERT\s+OR\s+IGNORE\s+INTO', q, re.I):
            q=re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO','INSERT INTO',q,flags=re.I)
            if ' ON CONFLICT ' not in q.upper(): q += ' ON CONFLICT DO NOTHING'
        # SQLite INSERT OR REPLACE uses known unique keys in this application.
        if re.match(r'INSERT\s+OR\s+REPLACE\s+INTO', q, re.I):
            q=re.sub(r'INSERT\s+OR\s+REPLACE\s+INTO','INSERT INTO',q,flags=re.I)
            table_match=re.match(r'INSERT INTO\s+(\w+)\s*\(([^)]+)\)',q,re.I)
            if table_match:
                table=table_match.group(1).lower(); cols=[x.strip().strip('"') for x in table_match.group(2).split(',')]
                key={'kv':'k','admin_accounts':'username','admin_sessions':'username'}.get(table)
                if key and key in cols:
                    updates=[f'{c}=EXCLUDED.{c}' for c in cols if c!=key]
                    q += f' ON CONFLICT ({key}) DO '+('UPDATE SET '+','.join(updates) if updates else 'NOTHING')
        inserted=bool(re.match(r'INSERT\s+INTO\s+(rates|bills|customers|activity_log|products|orders|product_enquiries|sync_log|rate_audit)\b',q,re.I)) and 'RETURNING' not in q.upper()
        if inserted: q += ' RETURNING id'
        cur=self._c.cursor(); cur.execute(q,args or None)
        lastrowid=None
        if inserted:
            try:
                rec=cur.fetchone(); lastrowid=rec.get('id') if rec else None
            except Exception: pass
        return Cursor(cur,lastrowid,inserted)

def connect(target=None, timeout=15):
    target = str(target or '')
    if target.startswith(('postgres://','postgresql://')):
        return PGConnection(target)
    if USE_POSTGRES:
        return PGConnection(DATABASE_URL)
    path=target or os.environ.get('DB_FILE','data.db')
    c=sqlite3.connect(path, timeout=timeout); c.row_factory=sqlite3.Row
    return c

INTEGRITY_ERRORS=(sqlite3.IntegrityError,)
DB_ERRORS=(sqlite3.Error,)
if USE_POSTGRES:
    try:
        import psycopg
        INTEGRITY_ERRORS += (psycopg.IntegrityError,)
        DB_ERRORS += (psycopg.Error,)
    except ImportError: pass
