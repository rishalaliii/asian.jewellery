"""Daily gold/silver rate sync. Sources: AKGSMA site (primary), LiveGold Kerala Kozhikode page (relays AKGSMA board rate).
Run once from the command line (Windows Task Scheduler): python rates_sync.py"""
import re, html, json, time, sqlite3, os, logging, urllib.request
from datetime import datetime, timezone, timedelta, date
log=logging.getLogger('rates_sync'); IST=timezone(timedelta(hours=5,minutes=30))
MON={m:i for i,m in enumerate('January February March April May June July August September October November December'.split(),1)}
UA='Mozilla/5.0 (compatible; AsianJewelleryRateCheck/1.0)'
def text(h):
    h=re.sub(r'<!--.*?-->|<(script|style)\b.*?</\1>',' ',h,flags=re.S|re.I); h=re.sub(r'<[^>]+>',' ',h)
    return re.sub(r'\s+',' ',html.unescape(h))
def _n(t,p):
    m=re.search(p,t); return float(m.group(1).replace(',','')) if m else None
def parse_akgsma(h):
    t=text(h); d=re.search(r"Today'?s Rate\s*\((\d{1,2})/(\d{1,2})/(\d{4})\)",t)
    if not d: raise ValueError('rate date not found (page layout changed?)')
    v=lambda lab:_n(t,lab+r'\s*[-–:]\s*(?:₹|Rs\.?)?\s*([\d,]+(?:\.\d+)?)')
    return dict(date=date(int(d[3]),int(d[2]),int(d[1])).isoformat(),g916=v(r'22K\s*916\s*\(1\s*gm\)'),g750=v(r'18K\s*750\s*\(1\s*gm\)'),
                s999=v(r'(?<!Marked )Silver\s*\(1\s*gm\)'),s925=v(r'925 Hall ?Marked Silver\s*\(1\s*gm\)'))
def parse_livegold(h):
    t=text(h)
    if 'AKGSMA' not in t: raise ValueError('AKGSMA board label missing')
    d=re.search(r'\b\w+day,\s*(\d{1,2}) ([A-Z][a-z]+) (\d{4})',t)
    if not d or d[2] not in MON: raise ValueError('rate date not found')
    return dict(date=date(int(d[3]),MON[d[2]],int(d[1])).isoformat(),g916=_n(t,r'22 Karat Gold.{0,60}?₹\s*([\d,]+)'),
                g750=_n(t,r'18 Karat\s*750.{0,40}?₹\s*([\d,]+)'),s999=_n(t,r'Ag 999.{0,60}?₹\s*([\d,]+(?:\.\d+)?)\s*/\s*g'),s925=None)
SOURCES={'akgsma':('AKGSMA board (akgsma.com)','https://akgsma.com/',parse_akgsma),
         'livegold':('LiveGold Kerala – AKGSMA board rate, Kozhikode','https://www.livegoldkerala.com/kozhikode',parse_livegold)}
def validate(d):
    g,g7,s=d.get('g916'),d.get('g750'),d.get('s999')
    if not g and not s: raise ValueError('no rates found')
    if g and not 3000<g<60000: raise ValueError(f'22K value {g} outside plausible range')
    if g and g7 and abs(g7/(g*750/916)-1)>.04: raise ValueError('18K/22K ratio implausible')
    if s and not 20<s<5000: raise ValueError(f'silver value {s} outside plausible range')
    return d
def http_get(u,tries=3):
    for i in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':UA}),timeout=10).read().decode('utf8','ignore')
        except Exception:
            if i==tries-1: raise
            time.sleep(2*(i+1))
def _db(path):
    c=sqlite3.connect(path,timeout=15); c.row_factory=sqlite3.Row; return c
def migrate(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY,v TEXT);
    CREATE TABLE IF NOT EXISTS rates(id INTEGER PRIMARY KEY AUTOINCREMENT,metal TEXT,purity TEXT,per_gram REAL,source TEXT,ts TEXT);
    CREATE TABLE IF NOT EXISTS sync_log(id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT,trigger TEXT,ok INTEGER,source TEXT,message TEXT);
    CREATE TABLE IF NOT EXISTS rate_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT,metal TEXT,purity TEXT,old REAL,new REAL,source TEXT);''')
    cols=[r[1] for r in db.execute('PRAGMA table_info(rates)')]
    for c in ('kind','rate_date'):
        if c not in cols: db.execute(f'ALTER TABLE rates ADD COLUMN {c} TEXT')
def cfg(db):
    r=db.execute("SELECT v FROM kv WHERE k='sync_cfg'").fetchone(); c=json.loads(r['v']) if r else {}
    return {'akgsma':c.get('akgsma',True),'livegold':c.get('livegold',True)}
def build_rows(d,src):
    r=lambda x:round(x); rows=[]; g,s=d.get('g916'),d.get('s999')
    if g:
        g24=g*24/22; rows+=[('gold','916',g,'quoted'),('gold','750',d.get('g750') or g*750/916,'quoted' if d.get('g750') else 'calculated'),
            ('gold','999',g24,'calculated'),('gold','995',g24*.995/.999,'calculated'),('gold','585',g*585/916,'calculated')]
    if s: rows+=[('silver','999',s,'quoted'),('silver','925',d.get('s925') or s*.925,'quoted' if d.get('s925') else 'calculated'),('silver','800',s*.8,'calculated')]
    return [(m,p,r(v) if m=='gold' else round(v,2),k) for m,p,v,k in rows]
def run_sync(path,trigger='scheduled',fetch=http_get):
    """Fetch, validate and store rates. Returns a result dict; never raises."""
    db=_db(path); migrate(db); now=time.time()
    db.execute("INSERT OR IGNORE INTO kv(k,v) VALUES('sync_claim','0')")
    if db.execute("UPDATE kv SET v=? WHERE k='sync_claim' AND CAST(v AS REAL)<?",(str(now),now-120)).rowcount!=1:
        db.commit(); return {'ok':False,'skipped':'another sync ran in the last 2 minutes'}
    db.commit(); c=cfg(db); res,errs=[],[]
    for key,(name,url,parser) in SOURCES.items():
        if not c[key]: continue
        try: d=validate(parser(fetch(url))); d['key'],d['name']=key,name; res.append(d)
        except Exception as e: errs.append(f'{name}: {type(e).__name__}: {e}'); log.warning('%s failed: %s',name,e)
    ts=datetime.now(timezone.utc).isoformat(timespec='seconds'); saved=[]; notes=list(errs)
    if res:
        top=max(d['date'] for d in res); best=next(d for d in res if d['date']==top)
        for o in res:
            if o is not best and o['date']==top and o.get('g916') and best.get('g916') and abs(o['g916']/best['g916']-1)>.02: notes.append(f"{o['name']} differs >2% from {best['name']}")
        sil=next((d for d in res if d['date']==top and d.get('s999')),None) or next((d for d in res if d.get('s999')),None)
        for metal,d in (('gold',best),('silver',sil)):
            if not d: continue
            if db.execute("SELECT 1 FROM rates r WHERE r.metal=? AND r.kind='manual' AND r.id=(SELECT MAX(id) FROM rates WHERE metal=r.metal AND purity=r.purity) LIMIT 1",(metal,)).fetchone():
                notes.append(f'{metal}: kept manual correction (not overwritten)'); continue
            prev=db.execute("SELECT per_gram FROM rates WHERE metal=? AND purity=? ORDER BY id DESC LIMIT 1",(metal,'916' if metal=='gold' else '999')).fetchone()
            rows=[x for x in build_rows(d,d['name']) if x[0]==metal]; lead=rows[0][2] if rows else 0
            if prev and lead and abs(lead/prev['per_gram']-1)>.15: notes.append(f'{metal}: rejected, change over 15% from last saved rate'); continue
            for m,p,v,k in rows:
                last=db.execute('SELECT per_gram,rate_date,kind FROM rates WHERE metal=? AND purity=? ORDER BY id DESC LIMIT 1',(m,p)).fetchone()
                if last and last['per_gram']==v and last['rate_date']==d['date']: continue
                db.execute('INSERT INTO rates(metal,purity,per_gram,source,ts,kind,rate_date) VALUES(?,?,?,?,?,?,?)',(m,p,v,d['name'][:80],ts,k,d['date'])); saved.append(f'{m}{p}')
    ok=bool(res) and not any('rejected' in n for n in notes)
    msg=json.dumps({'saved':saved,'notes':notes}); db.execute('INSERT INTO sync_log(ts,trigger,ok,source,message) VALUES(?,?,?,?,?)',(ts,trigger,int(ok),','.join(d['name'] for d in res),msg))
    db.commit(); db.close(); return {'ok':ok,'saved':saved,'notes':notes,'sources':[d['name'] for d in res]}
def status(db):
    today=datetime.now(IST).date().isoformat(); out={}
    lo=db.execute('SELECT ts FROM sync_log WHERE ok=1 ORDER BY id DESC LIMIT 1').fetchone()
    for metal in ('gold','silver'):
        r=db.execute("SELECT rate_date,source,ts,kind FROM rates WHERE metal=? ORDER BY id DESC LIMIT 1",(metal,)).fetchone()
        rd=(r['rate_date'] if r and r['rate_date'] else (r['ts'][:10] if r else None))
        out[metal]={'state':'unavailable' if not r else 'current' if rd==today else 'stale','rate_date':rd,'source':r['source'] if r else None,'last_ok':lo['ts'] if lo else None,'manual':bool(r and r['kind']=='manual')}
    return out
def start_scheduler(path):
    if os.environ.get('SYNC_SCHEDULER','1')=='0': return
    try: from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        print('WARNING: APScheduler missing, daily sync disabled. Run: py -m pip install -r requirements.txt'); return
    s=BackgroundScheduler(timezone='Asia/Kolkata')
    for t in os.environ.get('SYNC_TIMES','10:30').split(','):
        h,m=t.strip().split(':'); s.add_job(run_sync,'cron',hour=int(h),minute=int(m),args=[path,'scheduled'],id='sync'+t.strip(),misfire_grace_time=3600,coalesce=True,max_instances=1)
    def catchup():
        db=_db(path); migrate(db); r=db.execute('SELECT ts FROM sync_log WHERE ok=1 ORDER BY id DESC LIMIT 1').fetchone(); db.close()
        if not r or (datetime.now(timezone.utc)-datetime.fromisoformat(r['ts'])).total_seconds()>20*3600: run_sync(path,'startup')
    s.add_job(catchup,'date',run_date=datetime.now()+timedelta(seconds=10)); s.start(); return s
if __name__=='__main__':
    logging.basicConfig(level=logging.INFO); from app import DB_PATH; print(json.dumps(run_sync(str(DB_PATH),'task-scheduler'),indent=1,ensure_ascii=False))
