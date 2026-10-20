import rates_sync
import os, json, sqlite3, secrets, hashlib, hmac, time, threading
from db_compat import connect as db_connect, USE_POSTGRES, INTEGRITY_ERRORS, DB_ERRORS, DATABASE_URL
from datetime import datetime, timezone, date
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask, request, jsonify, session, send_from_directory, abort
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / 'public'

def load_env(path=ROOT/'.env'):
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v=line.split('=',1); k=k.strip(); v=v.strip().strip('"').strip("'")
            os.environ.setdefault(k,v)
load_env()
DB_PATH = Path(os.environ.get('DB_FILE', str(ROOT / 'data.db')))
DB_TARGET = DATABASE_URL if USE_POSTGRES else str(DB_PATH)
app=Flask(__name__, static_folder=None)
app.secret_key=os.environ.get('SESSION_SECRET') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict', PERMANENT_SESSION_LIFETIME=86400, MAX_CONTENT_LENGTH=6 * 1024 * 1024)
APP_ENV=os.environ.get('APP_ENV','development').strip().lower()
# Local recovery defaults: older .env files may still contain the untouched example placeholders.
# Never apply these defaults in production; production startup must use explicit secrets.
if APP_ENV != 'production':
    if os.environ.get('ADMIN_PASS','').startswith('REPLACE_WITH_'):
        os.environ.pop('ADMIN_PASS', None)
    if os.environ.get('SESSION_SECRET','').startswith('REPLACE_WITH_'):
        os.environ.pop('SESSION_SECRET', None)
    os.environ.setdefault('ADMIN_USER', 'asianadmin')
    os.environ.setdefault('ADMIN_PASS', 'asianadmin916')
if APP_ENV=='production': app.config['SESSION_COOKIE_SECURE']=True
# Small per-process brute-force guard. Use a reverse proxy/WAF for distributed production traffic.
_AUTH_ATTEMPTS={}
_AUTH_LOCK=threading.Lock()
def _auth_limited(ip):
    now_m=time.monotonic()
    with _AUTH_LOCK:
        rec=_AUTH_ATTEMPTS.get(ip,[])
        rec=[t for t in rec if now_m-t<600]
        _AUTH_ATTEMPTS[ip]=rec
        return len(rec)>=10
def _auth_failed(ip):
    now_m=time.monotonic()
    with _AUTH_LOCK:
        rec=[t for t in _AUTH_ATTEMPTS.get(ip,[]) if now_m-t<600]
        rec.append(now_m); _AUTH_ATTEMPTS[ip]=rec
def _auth_succeeded(ip):
    with _AUTH_LOCK: _AUTH_ATTEMPTS.pop(ip,None)

P={'gold':['916','999','995','750','585'],'silver':['999','925','800']}
_rate_refresh_lock=threading.Lock()
def _background_rate_refresh():
    try: rates_sync.run_sync(DB_TARGET, 'visitor_open')
    except Exception as e: app.logger.warning('Automatic visitor rate refresh failed: %s', e)
    finally: _rate_refresh_lock.release()
def conn():
    if not USE_POSTGRES: DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return db_connect(DB_TARGET if USE_POSTGRES else str(DB_PATH), timeout=15)
def init_db():
    if not USE_POSTGRES: DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    with conn() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY,v TEXT);
        CREATE TABLE IF NOT EXISTS admin_accounts(username TEXT PRIMARY KEY,password_hash TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admin_sessions(username TEXT PRIMARY KEY,token TEXT NOT NULL,expires REAL NOT NULL,created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS rates(id INTEGER PRIMARY KEY AUTOINCREMENT,metal TEXT,purity TEXT,per_gram REAL,source TEXT,ts TEXT);
        CREATE TABLE IF NOT EXISTS bills(id INTEGER PRIMARY KEY AUTOINCREMENT,no TEXT UNIQUE,date TEXT,customer TEXT,phone TEXT,status TEXT,total REAL,paid REAL,data TEXT,created TEXT);
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,phone TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,created TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS activity_log(id INTEGER PRIMARY KEY AUTOINCREMENT,actor_type TEXT NOT NULL,actor_id INTEGER,action TEXT NOT NULL,details TEXT NOT NULL DEFAULT '',created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,sku TEXT NOT NULL UNIQUE,name TEXT NOT NULL,category TEXT NOT NULL,product_type TEXT NOT NULL,metal TEXT NOT NULL DEFAULT 'none',purity TEXT NOT NULL DEFAULT '',weight_g REAL NOT NULL DEFAULT 0,making_per_g REAL NOT NULL DEFAULT 0,stone_charge REAL NOT NULL DEFAULT 0,price_mode TEXT NOT NULL DEFAULT 'rate',fixed_price REAL NOT NULL DEFAULT 0,stock INTEGER NOT NULL DEFAULT 0,image_path TEXT NOT NULL DEFAULT '',description TEXT NOT NULL DEFAULT '',features TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1,created TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER NOT NULL,items_json TEXT NOT NULL,total REAL NOT NULL,status TEXT NOT NULL DEFAULT 'Received',phone TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL,address TEXT NOT NULL DEFAULT '',city TEXT NOT NULL DEFAULT '',state TEXT NOT NULL DEFAULT '',pincode TEXT NOT NULL DEFAULT '',delivery_note TEXT NOT NULL DEFAULT '',payment_status TEXT NOT NULL DEFAULT 'Not received',payment_method TEXT NOT NULL DEFAULT '',payment_amount REAL NOT NULL DEFAULT 0,payment_reference TEXT NOT NULL DEFAULT '',bill_id INTEGER,FOREIGN KEY(customer_id) REFERENCES customers(id));
        CREATE TABLE IF NOT EXISTS product_enquiries(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,product_name TEXT NOT NULL,category TEXT NOT NULL DEFAULT '',image_path TEXT NOT NULL DEFAULT '',weight_g REAL NOT NULL DEFAULT 0,customer_name TEXT NOT NULL,phone TEXT NOT NULL,email TEXT NOT NULL DEFAULT '',message TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'New',created TEXT NOT NULL,updated TEXT NOT NULL DEFAULT '');''')
        def get(k):
            r=db.execute('SELECT v FROM kv WHERE k=?',(k,)).fetchone(); return r['v'] if r else None
        if not get('user'):
            u=os.environ.get('ADMIN_USER') or 'asianadmin'; p=os.environ.get('ADMIN_PASS') or secrets.token_urlsafe(18)
            if not os.environ.get('ADMIN_PASS'):
                print('\nFIRST-RUN ADMIN PASSWORD (save it now; it is not shown again):', p, '\n')
            db.execute('INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)',('user',u))
            db.execute('INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)',('hash',generate_password_hash(p)))
        if not get('secret'): db.execute('INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)',('secret',secrets.token_hex(32)))
        if not get('shop'):
            db.execute('INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)',('shop',json.dumps({'name':'Asian Jewellery','address':'Kozhikode, Kerala','phone':'9895232441','gstin':'GST1234567890','about':'Asian Jewellery, Kozhikode — trusted jewellers of gold and silver in Kerala.'})))
init_db()
# Owner-requested local administrator accounts. Seed once so subsequent password
# changes made through the admin workflow are not overwritten on every restart.
_ADMIN_SEED_MARKER='two_admin_accounts_seeded_v33'
with conn() as _admin_seed_db:
    _seeded=_admin_seed_db.execute('SELECT v FROM kv WHERE k=?',(_ADMIN_SEED_MARKER,)).fetchone()
    if not _seeded:
        _now=datetime.now().isoformat(timespec='seconds')
        if APP_ENV == 'production':
            # Never create publicly known demo credentials in production.
            _username=os.environ.get('ADMIN_USER','').strip()
            _password=os.environ.get('ADMIN_PASS','')
            if not _username or not _password or _password.startswith('REPLACE_WITH_'):
                raise RuntimeError('Production startup blocked: set ADMIN_USER and a unique ADMIN_PASS in the hosting environment.')
            _admin_seed_db.execute('INSERT OR REPLACE INTO admin_accounts(username,password_hash,active,created,updated) VALUES(?,?,1,COALESCE((SELECT created FROM admin_accounts WHERE username=?),?),?)',(_username,generate_password_hash(_password),_username,_now,_now))
        else:
            for _username,_password in (('asianadmin','asianadmin916'),('asian','asian916')):
                _admin_seed_db.execute('INSERT OR REPLACE INTO admin_accounts(username,password_hash,active,created,updated) VALUES(?,?,1,COALESCE((SELECT created FROM admin_accounts WHERE username=?),?),?)',(_username,generate_password_hash(_password),_username,_now,_now))
        _admin_seed_db.execute('INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)',(_ADMIN_SEED_MARKER,'1'))
# Apply the owner-requested initial admin credentials once to an existing database.
# The marker prevents this startup setting from overwriting later password changes.
_admin_env_user=os.environ.get('ADMIN_USER','').strip()
_admin_env_pass=os.environ.get('ADMIN_PASS','').strip()
if _admin_env_user and _admin_env_pass and not _admin_env_pass.startswith('REPLACE_WITH_'):
    with conn() as _admin_bootstrap:
        # One-time v32 recovery migration fixes existing local installs while preserving all other data.
        _already_applied=_admin_bootstrap.execute("SELECT v FROM kv WHERE k='admin_env_credentials_applied_v32'").fetchone()
        if not _already_applied:
            _admin_bootstrap.execute("INSERT OR REPLACE INTO kv(k,v) VALUES('user',?)",(_admin_env_user,))
            _admin_bootstrap.execute("INSERT OR REPLACE INTO kv(k,v) VALUES('hash',?)",(generate_password_hash(_admin_env_pass),))
            _admin_bootstrap.execute("INSERT OR REPLACE INTO kv(k,v) VALUES('admin_env_credentials_applied_v32','1')")
# Safe additive migration for delivery details on existing databases.
with conn() as _mig:
    _prod_cols={r['name'] for r in _mig.execute('PRAGMA table_info(products)').fetchall()}
    if 'features' not in _prod_cols: _mig.execute("ALTER TABLE products ADD COLUMN features TEXT NOT NULL DEFAULT ''")
    _cust_cols={r['name'] for r in _mig.execute('PRAGMA table_info(customers)').fetchall()}
    if 'active' not in _cust_cols: _mig.execute('ALTER TABLE customers ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
    _cols={r['name'] for r in _mig.execute('PRAGMA table_info(orders)').fetchall()}
    for _name in ('address','city','state','pincode','delivery_note','payment_status','payment_method','payment_reference'):
        if _name not in _cols:
            _mig.execute(f"ALTER TABLE orders ADD COLUMN {_name} TEXT NOT NULL DEFAULT ''")
    if 'payment_amount' not in _cols: _mig.execute("ALTER TABLE orders ADD COLUMN payment_amount REAL NOT NULL DEFAULT 0")
    if 'bill_id' not in _cols: _mig.execute("ALTER TABLE orders ADD COLUMN bill_id INTEGER")
with conn() as _ds: app.secret_key=os.environ.get('SESSION_SECRET') or _ds.execute("SELECT v FROM kv WHERE k='secret'").fetchone()['v']
if APP_ENV=='production':
    if os.environ.get('ADMIN_PASS','').startswith('REPLACE_WITH_'):
        raise RuntimeError('Production startup blocked: replace the placeholder ADMIN_PASS in your environment.')
    if not os.environ.get('SESSION_SECRET') or len(os.environ.get('SESSION_SECRET','')) < 32:
        raise RuntimeError('Production startup blocked: set SESSION_SECRET to a unique random value of at least 32 characters in the environment.')
    if not os.environ.get('ADMIN_USER','').strip() or not os.environ.get('ADMIN_PASS','') or os.environ.get('ADMIN_PASS','').startswith('REPLACE_WITH_'):
        raise RuntimeError('Production startup blocked: set ADMIN_USER and a unique ADMIN_PASS in the hosting environment.')
    with conn() as _secure_db:
        _legacy_hash_row=_secure_db.execute("SELECT v FROM kv WHERE k='hash'").fetchone()
        _legacy_hash=_legacy_hash_row['v'] if _legacy_hash_row else None
        _accounts=_secure_db.execute("SELECT username,password_hash FROM admin_accounts WHERE active=1").fetchall()
    if _legacy_hash and check_password_hash(_legacy_hash,'asianadmin916'):
        raise RuntimeError('Production startup blocked: the legacy admin account still uses a known default password.')
    for _account in _accounts:
        if (_account['username'], _account['password_hash']) and (
            (_account['username']=='asianadmin' and check_password_hash(_account['password_hash'],'asianadmin916')) or
            (_account['username']=='asian' and check_password_hash(_account['password_hash'],'asian916'))
        ):
            raise RuntimeError('Production startup blocked: a known default admin account exists. Use a fresh production database or change the account password first.')
with conn() as _d0: rates_sync.migrate(_d0)
with conn() as _d:  # fill shop phone/GSTIN on existing databases if still empty
    _r=_d.execute("SELECT v FROM kv WHERE k='shop'").fetchone(); _s=json.loads(_r['v']) if _r else {}
    if _r and (not _s.get('phone') or not _s.get('gstin')):
        _s['phone']=_s.get('phone') or '9895232441'; _s['gstin']=_s.get('gstin') or 'GST1234567890'
        _d.execute("UPDATE kv SET v=? WHERE k='shop'",(json.dumps(_s),))
def kv(k):
    with conn() as db:
        r=db.execute('SELECT v FROM kv WHERE k=?',(k,)).fetchone(); return r['v'] if r else None
def setkv(k,v):
    with conn() as db: db.execute('INSERT OR REPLACE INTO kv(k,v) VALUES(?,?)',(k,v))
@app.before_request
def _security_guard():
    if request.method in ('POST','PUT','PATCH','DELETE') and request.path.startswith('/api/'):
        origin=request.headers.get('Origin')
        referer=request.headers.get('Referer')
        supplied=origin or referer
        if supplied:
            try:
                u=urlparse(supplied)
                if u.netloc.lower()!=request.host.lower():
                    return jsonify(error='Cross-origin request blocked.'),403
            except Exception:
                return jsonify(error='Invalid request origin.'),403
        if request.content_length and request.content_length > 6*1024*1024:
            return jsonify(error='Request too large.'),413

def _admin_session_valid(refresh=True):
    if not session.get('admin') or not session.get('admin_username') or not session.get('admin_session_token'):
        return False
    username=session.get('admin_username'); token=session.get('admin_session_token'); now_ts=time.time()
    with conn() as db:
        row=db.execute('SELECT token,expires FROM admin_sessions WHERE username=?',(username,)).fetchone()
        if not row or row['expires'] <= now_ts or not hmac.compare_digest(row['token'],token):
            return False
        if refresh:
            db.execute('UPDATE admin_sessions SET expires=? WHERE username=? AND token=?',(now_ts+86400,username,token))
    return True
def auth(fn):
    @wraps(fn)
    def wrap(*a,**kw):
        if not _admin_session_valid():
            session.clear()
            return jsonify(error='Login required. This admin session is no longer active; please sign in again.'),401
        return fn(*a,**kw)
    return wrap
def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def log_activity(actor_type, actor_id, action, details=''):
    # Store concise audit events only; never store passwords, session cookies, or payment credentials.
    with conn() as db: db.execute('INSERT INTO activity_log(actor_type,actor_id,action,details,created) VALUES(?,?,?,?,?)',(str(actor_type)[:20],actor_id,str(action)[:100],str(details)[:500],now()))
def n(x):
    try: v=float(x or 0); return v if v==v and abs(v)!=float('inf') else 0.0
    except (TypeError,ValueError): return 0.0
def rnd(x): return round(n(x)+1e-10,2)
def calc_item(i):
    qty=max(0,n(i.get('qty',1))) or 1
    gross=max(0,n(i.get('gross'))); stone=max(0,n(i.get('stone')))
    net=rnd(max(0,gross-stone)*qty); metal=rnd(net*max(0,n(i.get('rate'))))
    mk_type=i.get('mkType','perGram'); mkval=max(0,n(i.get('mk')))
    mk=rnd(metal*mkval/100 if mk_type=='percent' else mkval*qty if mk_type=='item' else mkval*net)
    w=rnd(metal*max(0,n(i.get('wp')))/100)
    b1=metal+w; b2=mk+max(0,n(i.get('extra'))); base=b1+b2; f=max(0,base-max(0,n(i.get('disc'))))/base if base>0 else 0
    t1,t2=rnd(b1*f),rnd(b2*f); tr=max(0,n(i.get('tax',3)))
    if i.get('gstMode')=='split': g1,g2=rnd(t1*tr/100),rnd(t2*max(0,n(i.get('mtax',5)))/100)   # 3% on metal, making-charge rate separately
    else: g1,g2=rnd((t1+t2)*tr/100),0.0                                                         # single rate on total value
    taxable=rnd(t1+t2); gst=rnd(g1+g2)
    return {'net':net,'metal':metal,'mk':mk,'w':w,'taxable':taxable,'gst':gst,'gstm':g1,'gstk':g2,'total':rnd(taxable+gst)}
def calc_bill(b):
    lines=[calc_item(i) for i in b.get('items',[])]; total=rnd(sum(x['total'] for x in lines)); gst=rnd(sum(x['gst'] for x in lines)); paid=max(0,n(b.get('paid')))
    return {'lines':lines,'total':total,'gst':gst,'gstm':rnd(sum(x['gstm'] for x in lines)),'gstk':rnd(sum(x['gstk'] for x in lines)),'balance':rnd(total-paid)}
def bill_status(b,total): return 'Draft' if b.get('draft') else ('Paid' if n(b.get('paid'))>=total else ('Partial' if n(b.get('paid'))>0 else 'Unpaid'))

def rows(sql,args=()):
    with conn() as db: return [dict(r) for r in db.execute(sql,args).fetchall()]
def one(sql,args=()):
    with conn() as db:
        r=db.execute(sql,args).fetchone(); return dict(r) if r else None

@app.get('/')
def index(): return send_from_directory(PUBLIC,'index.html')
@app.get('/<path:name>')
def static_files(name):
    # Never serve dotfiles, environment files, DB files, or Python source.
    if name.startswith('.') or name.endswith(('.py','.db','.sqlite','.env')) or name in ('data.db','app.py'): abort(404)
    return send_from_directory(PUBLIC,name)
@app.get('/api/me')
def me():
    isadmin=bool(session.get('admin')) and _admin_session_valid()
    if session.get('admin') and not isadmin: session.clear()
    dflt=False; customer=None
    if isadmin:
        r=one("SELECT v FROM kv WHERE k='hash'"); dflt=bool(r) and check_password_hash(r['v'],'asianadmin916')
    elif session.get('customer_id'):
        customer=one('SELECT id,name,email,phone,created,active FROM customers WHERE id=?',(session['customer_id'],))
        if not customer or not customer['active']:
            session.pop('customer_id',None); customer=None
        elif customer: customer={k:customer[k] for k in ('id','name','email','phone','created')}
    return jsonify(admin=isadmin,default_password=dflt,customer=customer)
@app.post('/api/login')
def login():
    ip=request.remote_addr or 'unknown'
    if _auth_limited(ip): return jsonify(error='Too many login attempts. Wait 10 minutes and try again.'),429
    body=request.get_json(silent=True) or {}; username=str(body.get('username','')).strip(); password=str(body.get('password',''))
    admin_row=one('SELECT username,password_hash FROM admin_accounts WHERE username=? AND active=1',(username,)) if username else None
    valid=bool(admin_row and check_password_hash(admin_row['password_hash'],password))
    # Backward compatibility for a legacy single-admin record if it is not one of the seeded accounts.
    if not valid and username not in ('asianadmin','asian'):
        legacy_user=kv('user'); legacy_hash=kv('hash')
        valid=bool(legacy_user and legacy_hash and hmac.compare_digest(username,legacy_user) and check_password_hash(legacy_hash,password))
    if valid:
        # Enforce one active device/session per admin username. A 24-hour lease expires
        # abandoned sessions; valid requests extend the lease, and logout releases it.
        _auth_succeeded(ip)
        token=secrets.token_urlsafe(32); stamp=now(); expiry=time.time()+86400
        with conn() as db:
            existing=db.execute('SELECT token,expires FROM admin_sessions WHERE username=?',(username,)).fetchone()
            if existing and existing['expires'] > time.time():
                return jsonify(error='Admin already login on another device. Please log out from that device and try again.'),409
            db.execute('INSERT OR REPLACE INTO admin_sessions(username,token,expires,created) VALUES(?,?,?,?)',(username,token,expiry,stamp))
        session.clear(); session['admin']=True; session['admin_username']=username; session['admin_session_token']=token; session.permanent=True
        log_activity('admin',None,'admin_login',f'Administrator {username} signed in'); return jsonify(ok=1,role='admin')
    _auth_failed(ip)
    return jsonify(error='Invalid admin credentials.'),401
@app.post('/api/customer/register')
def customer_register():
    b=request.get_json(silent=True) or {}; name=str(b.get('name','')).strip(); email=str(b.get('email','')).strip().lower(); phone=''.join(ch for ch in str(b.get('phone','')) if ch.isdigit()); password=str(b.get('password',''))
    if len(name)<2: return jsonify(error='Enter your full name.'),400
    if len(email)>254 or '@' not in email or '.' not in email.rsplit('@',1)[-1]: return jsonify(error='Enter a valid email address.'),400
    if len(phone)<10 or len(phone)>15: return jsonify(error='Enter a valid phone number with country code if needed.'),400
    if len(password)<8: return jsonify(error='Password must contain at least 8 characters.'),400
    try:
        with conn() as db:
            cur=db.execute('INSERT INTO customers(name,email,phone,password_hash,created,active) VALUES(?,?,?,?,?,1)',(name,email,phone,generate_password_hash(password),now())); cid=cur.lastrowid
    except INTEGRITY_ERRORS:
        return jsonify(error='An account with that email or phone number already exists. Please log in.'),409
    log_activity('customer',cid,'account_registered',f'New account: {email}')
    session.clear(); session['customer_id']=cid; session.permanent=True
    return jsonify(ok=1,customer={'id':cid,'name':name,'email':email,'phone':phone})
@app.post('/api/customer/login')
def customer_login():
    ip=request.remote_addr or 'unknown'
    if _auth_limited(ip): return jsonify(error='Too many login attempts. Wait 10 minutes and try again.'),429
    b=request.get_json(silent=True) or {}; identity=str(b.get('identity','')).strip().lower(); phone_identity=''.join(ch for ch in identity if ch.isdigit()); password=str(b.get('password',''))
    customer=one('SELECT * FROM customers WHERE email=? OR phone=?',(identity,phone_identity))
    if not customer or not check_password_hash(customer['password_hash'],password):
        log_activity('visitor',None,'customer_login_failed','Invalid customer credentials; identifier not stored')
        _auth_failed(ip)
        return jsonify(error='Invalid email/phone or password.'),401
    if not customer['active']:
        log_activity('customer',customer['id'],'login_blocked','Account disabled by administrator')
        return jsonify(error='This account is disabled. Please contact Asian Jewellery.'),403
    _auth_succeeded(ip); log_activity('customer',customer['id'],'customer_login','Customer signed in')
    session.clear(); session['customer_id']=customer['id']; session.permanent=True
    return jsonify(ok=1,customer={'id':customer['id'],'name':customer['name'],'email':customer['email'],'phone':customer['phone']})
@app.post('/api/customer/logout')
def customer_logout():
    cid=session.get('customer_id')
    if cid: log_activity('customer',cid,'customer_logout','Customer signed out')
    session.pop('customer_id',None); return jsonify(ok=1)
@app.get('/api/customer/profile')
def customer_profile():
    if not session.get('customer_id'): return jsonify(error='Customer login required.'),401
    c=one('SELECT id,name,email,phone,created,active FROM customers WHERE id=?',(session['customer_id'],))
    if not c or not c['active']:
        session.pop('customer_id',None); return jsonify(error='Account unavailable. Please contact Asian Jewellery.'),403
    return jsonify(customer={k:c[k] for k in ('id','name','email','phone','created')})
@app.post('/api/customer/orders')
def create_customer_order():
    # In production, managed catalogue items are repriced and stock-checked server-side; demo items are rejected.
    cid=session.get('customer_id')
    if not cid: return jsonify(error='Please sign in before placing an order.'),401
    b=request.get_json(silent=True) or {}; items=b.get('items')
    if not isinstance(items,list) or not items or len(items)>50: return jsonify(error='Your cart is empty or invalid.'),400
    address=str(b.get('address','')).strip()[:300]; city=str(b.get('city','')).strip()[:80]; state=str(b.get('state','')).strip()[:80]; pincode=str(b.get('pincode','')).strip(); delivery_note=str(b.get('delivery_note','')).strip()[:500]
    if len(address)<8 or not city or not state or not (len(pincode)==6 and pincode.isdigit()): return jsonify(error='Enter a full delivery address, city, state and valid 6-digit PIN code.'),400
    clean=[]; total=0.0
    for item in items:
        if not isinstance(item,dict): return jsonify(error='Invalid cart item.'),400
        name=str(item.get('name','')).strip()[:120]; category=str(item.get('category','')).strip()[:80]
        try: price=float(item.get('price') or 0); qty=int(item.get('qty'))
        except (TypeError,ValueError): return jsonify(error='Invalid item price or quantity.'),400
        if not name or not (0 <= price <= 100000000) or not (1 <= qty <= 99): return jsonify(error='Invalid item details.'),400
        product_id=item.get('product_id')
        if product_id:
            try: product_id=int(product_id)
            except (TypeError,ValueError): return jsonify(error='Invalid catalogue product reference.'),400
            product=one('SELECT * FROM products WHERE id=? AND active=1',(product_id,))
            if not product: return jsonify(error=f'Product {name} is no longer available.'),409
            if product['stock'] < qty: return jsonify(error=f'Insufficient stock for {product["name"]}. Available: {product["stock"]}.'),409
            price=product_price(product); name=product['name']; category=product['category']
            weight_grams=float(product['weight_g'] or 0)
            sku=product['sku']
        else:
            if APP_ENV=='production' and os.environ.get('ALLOW_CLIENT_PRICED_ORDERS','0')!='1':
                return jsonify(error=f'{name} is a demo item and cannot be ordered online yet. Please contact the shop for a confirmed quote.'),503
            try: weight_grams=float(item.get('weight_grams', item.get('weight', 0)) or 0)
            except (TypeError,ValueError): return jsonify(error='Invalid item weight.'),400
            sku=''
        if not (0 <= weight_grams <= 100000): return jsonify(error='Invalid item weight.'),400
        clean.append({'product_id':int(product_id) if product_id else None,'sku':sku,'name':name,'category':category,'price':round(price,2),'qty':qty,'weight_grams':round(weight_grams,3)}); total += price*qty
    total=round(total,2); customer=one('SELECT phone,active FROM customers WHERE id=?',(cid,))
    if not customer or not customer['active']:
        session.pop('customer_id',None); return jsonify(error='Your account is disabled or expired. Please contact Asian Jewellery.'),403
    stamp=now()
    with conn() as db:
        cur=db.execute('INSERT INTO orders(customer_id,items_json,total,status,phone,created,updated,address,city,state,pincode,delivery_note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,json.dumps(clean),total,'Received',customer['phone'],stamp,stamp,address,city,state,pincode,delivery_note)); oid=cur.lastrowid
    log_activity('customer',cid,'order_created',f'Order #{oid}; total ₹{total:.2f}')
    return jsonify(ok=1,order={'id':oid,'items':clean,'total':total,'status':'Received','created':stamp,'address':address,'city':city,'state':state,'pincode':pincode,'delivery_note':delivery_note}),201
@app.get('/api/customer/orders')
def customer_orders():
    cid=session.get('customer_id')
    if not cid: return jsonify(error='Customer login required.'),401
    active=one('SELECT active FROM customers WHERE id=?',(cid,))
    if not active or not active['active']:
        session.pop('customer_id',None); return jsonify(error='Account unavailable. Please contact Asian Jewellery.'),403
    result=[]
    for r in rows('SELECT id,items_json,total,status,phone,created,updated,address,city,state,pincode,delivery_note,payment_status,payment_method,payment_amount,payment_reference,bill_id FROM orders WHERE customer_id=? ORDER BY id DESC LIMIT 100',(cid,)):
        result.append({'id':r['id'],'items':json.loads(r['items_json']),'total':r['total'],'status':r['status'],'phone':r['phone'],'created':r['created'],'updated':r['updated'],'address':r['address'],'city':r['city'],'state':r['state'],'pincode':r['pincode'],'delivery_note':r['delivery_note'],'payment_status':r['payment_status'],'payment_method':r['payment_method'],'payment_amount':r['payment_amount'],'payment_reference':r['payment_reference'],'bill_id':r['bill_id']})
    return jsonify(orders=result)
@app.get('/api/admin/customers')
@auth
def admin_customers():
    result=[]
    for r in rows("SELECT c.id,c.name,c.email,c.phone,c.created,c.active,COUNT(DISTINCT o.id) AS order_count,COALESCE(SUM(CASE WHEN o.status!='Cancelled' THEN o.total ELSE 0 END),0) AS order_total FROM customers c LEFT JOIN orders o ON o.customer_id=c.id GROUP BY c.id ORDER BY c.id DESC LIMIT 500"):
        result.append(dict(r))
    return jsonify(customers=result)

@app.patch('/api/admin/customers/<int:cid>')
@auth
def admin_update_customer(cid):
    b=request.get_json(silent=True) or {}; current=one('SELECT * FROM customers WHERE id=?',(cid,))
    if not current: return jsonify(error='Customer not found.'),404
    name=str(b.get('name',current['name'])).strip()[:120]
    email=str(b.get('email',current['email'])).strip().lower()[:254]
    phone=''.join(ch for ch in str(b.get('phone',current['phone'])) if ch.isdigit())[:20]
    active=1 if str(b.get('active',current['active'])).lower() in ('1','true','yes','active') else 0
    if len(name)<2 or '@' not in email or len(phone)<8: return jsonify(error='Enter a valid name, email and phone number.'),400
    try:
        with conn() as db: db.execute('UPDATE customers SET name=?,email=?,phone=?,active=? WHERE id=?',(name,email,phone,active,cid))
    except INTEGRITY_ERRORS:
        return jsonify(error='That email address or phone number is already used by another account.'),409
    log_activity('admin',None,'customer_updated',f'Customer #{cid}; active={active}; contact/profile updated')
    return jsonify(ok=1,id=cid,name=name,email=email,phone=phone,active=active)

@app.post('/api/admin/customers/<int:cid>/reset-password')
@auth
def admin_reset_customer_password(cid):
    b=request.get_json(silent=True) or {}; password=str(b.get('password',''))
    if len(password)<10: return jsonify(error='New password must contain at least 10 characters.'),400
    with conn() as db:
        cur=db.execute('UPDATE customers SET password_hash=? WHERE id=?',(generate_password_hash(password),cid))
        if not cur.rowcount: return jsonify(error='Customer not found.'),404
    log_activity('admin',None,'customer_password_reset',f'Password reset for customer #{cid}')
    return jsonify(ok=1)

@app.get('/api/admin/activity')
@auth
def admin_activity():
    limit=max(1,min(500,int(request.args.get('limit','200') or 200)))
    result=[]
    for r in rows('SELECT id,actor_type,actor_id,action,details,created FROM activity_log ORDER BY id DESC LIMIT ?', (limit,)):
        result.append(dict(r))
    return jsonify(events=result)

@app.get('/api/admin/orders')
@auth
def admin_orders():
    result=[]
    for r in rows('SELECT o.id,o.customer_id,c.name,c.email,o.phone,o.items_json,o.total,o.status,o.created,o.updated,o.address,o.city,o.state,o.pincode,o.delivery_note,o.payment_status,o.payment_method,o.payment_amount,o.payment_reference,o.bill_id FROM orders o JOIN customers c ON c.id=o.customer_id ORDER BY o.id DESC LIMIT 200'):
        result.append({'id':r['id'],'customer_id':r['customer_id'],'name':r['name'],'email':r['email'],'phone':r['phone'],'items':json.loads(r['items_json']),'total':r['total'],'status':r['status'],'created':r['created'],'updated':r['updated'],'address':r['address'],'city':r['city'],'state':r['state'],'pincode':r['pincode'],'delivery_note':r['delivery_note'],'payment_status':r['payment_status'],'payment_method':r['payment_method'],'payment_amount':r['payment_amount'],'payment_reference':r['payment_reference'],'bill_id':r['bill_id']})
    return jsonify(orders=result)
@app.patch('/api/admin/orders/<int:oid>')
@auth
def update_order(oid):
    b=request.get_json(silent=True) or {}; status=str(b.get('status',''))
    if status not in ('Received','Accepted','Declined','Confirmed','Processing','Ready for pickup','Shipped','Completed','Cancelled'):
        return jsonify(error='Invalid order status.'),400
    current=one('SELECT id,status,items_json FROM orders WHERE id=?',(oid,))
    if not current: return jsonify(error='Order not found.'),404
    old_status=current['status']; items=json.loads(current['items_json'] or '[]')
    was_reserved=old_status in ('Accepted','Confirmed','Processing','Ready for pickup','Shipped','Completed')
    will_reserve=status in ('Accepted','Confirmed','Processing','Ready for pickup','Shipped','Completed')
    with conn() as db:
        if not was_reserved and will_reserve:
            for item in items:
                pid=item.get('product_id')
                if not pid: continue
                prod=db.execute('SELECT stock,name FROM products WHERE id=? AND active=1',(pid,)).fetchone()
                if not prod or prod['stock'] < int(item.get('qty',1)):
                    return jsonify(error=f'Cannot accept order: insufficient stock for {item.get("name","product")}.'),409
            for item in items:
                if item.get('product_id'):
                    db.execute('UPDATE products SET stock=stock-?,updated=? WHERE id=?',(int(item.get('qty',1)),now(),item['product_id']))
        elif was_reserved and not will_reserve:
            for item in items:
                if item.get('product_id'):
                    db.execute('UPDATE products SET stock=stock+?,updated=? WHERE id=?',(int(item.get('qty',1)),now(),item['product_id']))
        db.execute('UPDATE orders SET status=?,updated=? WHERE id=?',(status,now(),oid))
    log_activity('admin',None,'order_status_updated',f'Order #{oid} status {old_status} -> {status}')
    return jsonify(ok=1,id=oid,status=status)

@app.patch('/api/admin/orders/<int:oid>/payment')
@auth
def update_order_payment(oid):
    b=request.get_json(silent=True) or {}
    state=str(b.get('payment_status','Not received'))
    method=str(b.get('payment_method',''))
    reference=str(b.get('payment_reference','')).strip()[:120]
    amount=rnd(max(0,n(b.get('payment_amount',0))))
    order=one('SELECT total FROM orders WHERE id=?',(oid,))
    if not order: return jsonify(error='Order not found.'),404
    amount=min(amount,rnd(order['total']))
    if state not in ('Not received','Pending verification','Received','Refunded'):
        return jsonify(error='Invalid payment status.'),400
    if method not in ('','UPI','Card','Cash','Bank transfer','Other'):
        return jsonify(error='Invalid payment method.'),400
    if state=='Received' and method in ('UPI','Card','Bank transfer') and not reference:
        return jsonify(error='Enter the payment transaction/reference number before marking this payment received.'),400
    if state=='Not received': amount=0; reference=''
    with conn() as db:
        cur=db.execute('UPDATE orders SET payment_status=?,payment_method=?,payment_amount=?,payment_reference=?,updated=? WHERE id=?',(state,method,amount,reference,now(),oid))
        if not cur.rowcount: return jsonify(error='Order not found.'),404
    log_activity('admin',None,'order_payment_updated',f'Order #{oid}; status={state}; method={method}; amount={amount:.2f}; reference_present={bool(reference)}')
    return jsonify(ok=1,id=oid,payment_status=state,payment_method=method,payment_amount=amount,payment_reference=reference)

@app.post('/api/admin/orders/<int:oid>/create-bill')
@auth
def create_bill_from_order(oid):
    order=one('SELECT o.*,c.name,c.email FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.id=?',(oid,))
    if not order: return jsonify(error='Order not found.'),404
    if order.get('status') in ('Received','Declined','Cancelled'):
        return jsonify(error='Accept this order before creating a bill.'),409
    if order.get('bill_id'):
        existing=one('SELECT id,no FROM bills WHERE id=?',(order['bill_id'],))
        if existing: return jsonify(ok=1,already_exists=True,**existing)
    order_items=json.loads(order['items_json'] or '[]')
    bill_items=[]
    for item in order_items:
        price=rnd(max(0,n(item.get('price')))); qty=max(1,min(99,int(n(item.get('qty',1)))))
        # Retail online-store price is stored as a fixed line amount in the invoice engine.
        bill_items.append({'metal':'gold','product':str(item.get('name','Online store item'))[:120],'purity':'916','hallmark':'Not applicable','qty':qty,'gross':0,'stone':0,'rate':0,'mkType':'item','mk':0,'wp':0,'extra':price,'disc':0,'tax':0,'mtax':0,'gstMode':'composite','auto':False,'onlineStorePrice':True,'category':item.get('category','')})
    b={'customer':order['name'],'phone':order['phone'],'address':', '.join(x for x in (order['address'],order['city'],order['state'],order['pincode']) if x),'date':date.today().isoformat(),'method':order.get('payment_method') or 'UPI','paid':min(rnd(order.get('payment_amount') or 0),rnd(order['total'])) if order.get('payment_status')=='Received' else 0,'items':bill_items,'metal':'gold','onlineOrderId':oid,'draft':False}
    c=calc_bill(b); b['paid']=min(b['paid'],c['total']); st=bill_status(b,c['total'])
    with conn() as db:
        num=db.execute('SELECT COALESCE(MAX(id),0)+1 AS n FROM bills').fetchone()['n']; no=f"AJ-{b['date'].replace('-','')}-{num:04d}"
        cur=db.execute('INSERT INTO bills(no,date,customer,phone,status,total,paid,data,created) VALUES(?,?,?,?,?,?,?,?,?)',(no,b['date'],b['customer'],b['phone'],st,c['total'],b['paid'],json.dumps(b),now())); bid=cur.lastrowid; b.update(id=bid,no=no)
        db.execute('UPDATE bills SET data=? WHERE id=?',(json.dumps(b),bid)); db.execute('UPDATE orders SET bill_id=?,updated=? WHERE id=?',(bid,now(),oid))
    log_activity('admin',None,'order_converted_to_bill',f'Order #{oid} linked to bill #{bid}')
    return jsonify(ok=1,id=bid,no=no,total=c['total'],status=st)
@app.post('/api/logout')
def logout():
    if session.get('admin'):
        username=session.get('admin_username'); token=session.get('admin_session_token')
        log_activity('admin',None,'admin_logout',f'Administrator {username or "unknown"} signed out')
        if username and token:
            with conn() as db: db.execute('DELETE FROM admin_sessions WHERE username=? AND token=?',(username,token))
    if session.get('customer_id'): log_activity('customer',session.get('customer_id'),'customer_logout','Customer signed out')
    session.clear(); return jsonify(ok=1)
@app.post('/api/admin/password')
@auth
def change_password():
    b=request.get_json(silent=True) or {}; h=kv('hash')
    if not h or not check_password_hash(h,str(b.get('current',''))): return jsonify(error='Current password wrong'),400
    new=str(b.get('next',''))
    if len(new)<10: return jsonify(error='Min 10 characters'),400
    setkv('hash',generate_password_hash(new)); return jsonify(ok=1)
@app.get('/api/rates')
def rates():
    # Public page visits automatically refresh external rates on the server.
    # The sync module has a shared 120-second claim to prevent concurrent
    # browser requests from hammering source websites. Manual admin corrections
    # remain protected by rates_sync.run_sync().
    sync_result = None
    try:
        with conn() as db:
            last = db.execute('SELECT ts FROM sync_log ORDER BY id DESC LIMIT 1').fetchone()
        last_ts = last['ts'] if last else None
        age = 10**9
        if last_ts:
            try:
                from datetime import datetime, timezone
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(last_ts)).total_seconds()
            except (ValueError, TypeError):
                age = 10**9
        # Refresh when a visitor opens/loads the rate sections, and periodically
        # while the site is in use. If sources are down, existing saved rates remain visible.
        if age > 300 and _rate_refresh_lock.acquire(blocking=False):
            # Do not make customers wait for third-party websites; refresh in the background.
            threading.Thread(target=_background_rate_refresh, name='public-rate-refresh', daemon=True).start()
            sync_result = {'scheduled': True}
    except Exception as e:
        app.logger.warning('Automatic visitor rate refresh could not be scheduled: %s', e)
    out={'gold':{},'silver':{}}
    for metal,purities in P.items():
        for purity in purities: out[metal][purity]=one('SELECT per_gram,source,ts,kind,rate_date FROM rates WHERE metal=? AND purity=? ORDER BY id DESC LIMIT 1',(metal,purity))
    with conn() as db: st=rates_sync.status(db)
    return jsonify(rates=out,status=st,stale={m:st[m]['state']!='current' for m in st},auto_refresh=True,sync=sync_result)
@app.post('/api/admin/rates')
@auth
def save_rates():
    b=request.get_json(silent=True) or {}; metal=b.get('metal'); values=b.get('rates')
    if metal not in P or not isinstance(values,dict): return jsonify(error='Bad input'),400
    today=datetime.now(rates_sync.IST).date().isoformat()
    with conn() as db:
        for p,v in values.items():
            x=n(v)
            if p in P[metal] and 0<x<1e7:
                old=db.execute('SELECT per_gram FROM rates WHERE metal=? AND purity=? ORDER BY id DESC LIMIT 1',(metal,p)).fetchone()
                db.execute('INSERT INTO rates(metal,purity,per_gram,source,ts,kind,rate_date) VALUES(?,?,?,?,?,?,?)',(metal,p,x,'Manual correction (admin)',now(),'manual',today))
                db.execute('INSERT INTO rate_audit(ts,metal,purity,old,new,source) VALUES(?,?,?,?,?,?)',(now(),metal,p,old['per_gram'] if old else None,x,'Manual correction (admin)'))
    return jsonify(ok=1)
@app.post('/api/admin/rates/release')
@auth
def release():
    m=(request.get_json(silent=True) or {}).get('metal')
    if m not in P: return jsonify(error='Bad input'),400
    with conn() as db: db.execute("UPDATE rates SET kind='manual (released)' WHERE metal=? AND kind='manual'",(m,))
    return jsonify(ok=1)
@app.get('/api/admin/rates/history')
@auth
def rate_history(): return jsonify(rows('SELECT * FROM rates WHERE metal=? ORDER BY id DESC LIMIT 80',('silver' if request.args.get('metal')=='silver' else 'gold',)))
@app.post('/api/admin/sync')
@auth
def sync_now(): return jsonify(rates_sync.run_sync(DB_TARGET,'manual'))
@app.get('/api/admin/sync-status')
@auth
def sync_status():
    with conn() as db: c=rates_sync.cfg(db)
    return jsonify(cfg=c,names={k:v[0] for k,v in rates_sync.SOURCES.items()},times=os.environ.get('SYNC_TIMES','10:30'),logs=rows('SELECT * FROM sync_log ORDER BY id DESC LIMIT 10'),audit=rows('SELECT * FROM rate_audit ORDER BY id DESC LIMIT 15'))
@app.put('/api/admin/sync-config')
@auth
def sync_cfg():
    b=request.get_json(silent=True) or {}; c={k:bool(b.get(k)) for k in rates_sync.SOURCES}
    with conn() as db: db.execute("INSERT OR REPLACE INTO kv(k,v) VALUES('sync_cfg',?)",(json.dumps(c),))
    return jsonify(c)
@app.get('/api/ticker')
def ticker():
    with conn() as db: st=rates_sync.status(db)['gold']
    g=one("SELECT per_gram FROM rates WHERE metal='gold' AND purity='916' ORDER BY id DESC LIMIT 1")
    s=one("SELECT per_gram FROM rates WHERE metal='silver' AND purity='999' ORDER BY id DESC LIMIT 1")
    return jsonify(g22=g and g['per_gram'],silver=s and s['per_gram'],ts=st['last_ok'],source=st['source'],rate_date=st['rate_date'],state=st['state'])
DEF_SHOP={'name':'Asian Jewellery','address':'Kozhikode, Kerala','phone':'9895232441','gstin':'GST1234567890','about':'Asian Jewellery, Kozhikode — trusted jewellers of gold and silver in Kerala.'}
@app.get('/api/products')
def public_products():
    result=[]
    for p in rows("SELECT * FROM products WHERE active=1 ORDER BY id DESC LIMIT 500"):
        p['price']=product_price(p)
        result.append(p)
    return jsonify(products=result)

def product_price(p):
    if p.get('price_mode')=='fixed': return round(max(0,float(p.get('fixed_price') or 0)),2)
    metal=p.get('metal'); purity=str(p.get('purity') or '')
    if metal not in ('gold','silver'): return round(max(0,float(p.get('fixed_price') or 0)),2)
    r=one('SELECT per_gram FROM rates WHERE metal=? AND purity=? ORDER BY id DESC LIMIT 1',(metal,purity))
    rate=float(r['per_gram']) if r else 0
    if not rate and metal=='silver' and purity=='925':
        rr=one("SELECT per_gram FROM rates WHERE metal='silver' AND purity='999' ORDER BY id DESC LIMIT 1"); rate=float(rr['per_gram'])*.925 if rr else 0
    if not rate and metal=='gold' and purity=='750':
        rr=one("SELECT per_gram FROM rates WHERE metal='gold' AND purity='916' ORDER BY id DESC LIMIT 1"); rate=float(rr['per_gram'])*750/916 if rr else 0
    return round(rate*float(p.get('weight_g') or 0)+float(p.get('making_per_g') or 0)*float(p.get('weight_g') or 0)+float(p.get('stone_charge') or 0),2)

@app.post('/api/enquiries')
def create_product_enquiry():
    b=request.get_json(silent=True) or {}
    name=str(b.get('customer_name','')).strip()[:120]
    phone=''.join(ch for ch in str(b.get('phone','')) if ch.isdigit())[:15]
    email=str(b.get('email','')).strip()[:254]
    product_name=str(b.get('product_name','')).strip()[:160]
    category=str(b.get('category','')).strip()[:100]
    image_path=str(b.get('image_path','')).strip()[:240]
    message=str(b.get('message','')).strip()[:1000]
    try: weight=float(b.get('weight_g') or 0); product_id=int(b.get('product_id') or 0) or None
    except (TypeError,ValueError): return jsonify(error='Invalid product details.'),400
    if len(name)<2 or len(phone)<10 or len(phone)>15 or len(product_name)<2:
        return jsonify(error='Enter your name, valid phone number and product.'),400
    if not (0<=weight<=10000): return jsonify(error='Invalid product weight.'),400
    # Only allow local relative image paths, never arbitrary external URLs.
    if image_path.startswith('https://'):
        parsed_image=urlparse(image_path)
        if not parsed_image.netloc or parsed_image.username or parsed_image.password: image_path=''
    elif image_path.startswith('//') or '://' in image_path or '..' in Path(image_path).parts:
        image_path=''
    stamp=now()
    with conn() as db:
        cur=db.execute('INSERT INTO product_enquiries(product_id,product_name,category,image_path,weight_g,customer_name,phone,email,message,status,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(product_id,product_name,category,image_path,weight,name,phone,email,message,'New',stamp,stamp))
        eid=cur.lastrowid
    log_activity('visitor',None,'product_enquiry_created',f'Enquiry #{eid} for {product_name}; contact phone saved')
    return jsonify(ok=True,id=eid,message='Enquiry sent to Asian Jewellery. The shop will contact you.'),201

@app.get('/api/admin/enquiries')
@auth
def admin_enquiries():
    return jsonify(enquiries=rows("SELECT * FROM product_enquiries ORDER BY CASE status WHEN 'New' THEN 0 WHEN 'Contacted' THEN 1 ELSE 2 END,id DESC LIMIT 500"))

@app.patch('/api/admin/enquiries/<int:eid>')
@auth
def update_enquiry(eid):
    b=request.get_json(silent=True) or {}; status=str(b.get('status',''))
    if status not in ('New','Contacted','Quoted','Converted','Closed'): return jsonify(error='Invalid enquiry status.'),400
    with conn() as db:
        cur=db.execute('UPDATE product_enquiries SET status=?,updated=? WHERE id=?',(status,now(),eid))
        if not cur.rowcount: return jsonify(error='Enquiry not found.'),404
    log_activity('admin',None,'product_enquiry_updated',f'Enquiry #{eid} status={status}')
    return jsonify(ok=True)

@app.get('/api/admin/products')
@auth
def admin_products(): return jsonify(products=rows('SELECT * FROM products ORDER BY id DESC LIMIT 1000'))

@app.post('/api/admin/products')
@auth
def create_product():
    b=request.get_json(silent=True) or {}
    return save_product(None,b)

@app.put('/api/admin/products/<int:pid>')
@auth
def update_product(pid):
    b=request.get_json(silent=True) or {}
    if not one('SELECT id FROM products WHERE id=?',(pid,)): return jsonify(error='Product not found.'),404
    return save_product(pid,b)

def save_product(pid,b):
    import base64, re
    sku=str(b.get('sku','')).strip().upper()[:60]; name=str(b.get('name','')).strip()[:160]
    category=str(b.get('category','')).strip()[:100]; typ=str(b.get('product_type','gold')).lower()
    metal=str(b.get('metal','none')).lower(); purity=str(b.get('purity','')).strip()[:20]
    mode=str(b.get('price_mode','rate')).lower(); desc=str(b.get('description','')).strip()[:1000]; features=str(b.get('features','')).strip()[:3000]
    try:
        weight=float(b.get('weight_g') or 0); making=float(b.get('making_per_g') or 0); stone=float(b.get('stone_charge') or 0); fixed=float(b.get('fixed_price') or 0); stock=int(b.get('stock') or 0)
    except (TypeError,ValueError): return jsonify(error='Enter valid numeric values.'),400
    if len(sku)<2 or len(name)<2 or len(category)<2: return jsonify(error='SKU, product name and category are required.'),400
    if typ not in ('gold','silver','diamond','gemstone','other') or metal not in ('gold','silver','none') or mode not in ('rate','fixed'):
        return jsonify(error='Invalid product type, metal or pricing mode.'),400
    if min(weight,making,stone,fixed,stock)<0 or weight>10000 or making>1000000 or stone>100000000 or fixed>100000000 or stock>1000000: return jsonify(error='Weight, price, making charges and stock must be valid non-negative values.'),400
    image_path=''
    if pid:
        old=one('SELECT image_path FROM products WHERE id=?',(pid,)); image_path=old['image_path'] if old else ''
    image_data=b.get('image_data')
    if image_data:
        match=re.fullmatch(r'data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)',str(image_data))
        if not match: return jsonify(error='Upload a JPG, PNG or WebP image.'),400
        try: raw=base64.b64decode(match.group(2),validate=True)
        except Exception: return jsonify(error='The uploaded image data is invalid.'),400
        if len(raw)>4*1024*1024: return jsonify(error='Image must be 4 MB or smaller.'),400
        ext={'jpeg':'jpg','png':'png','webp':'webp'}[match.group(1)]
        if USE_POSTGRES:
            # Persist uploaded product images in the database-backed product record.
            image_path=f'data:image/{match.group(1)};base64,{match.group(2)}'
        else:
            fname=secrets.token_hex(16)+'.'+ext; folder=PUBLIC/'uploads'; folder.mkdir(parents=True,exist_ok=True)
            (folder/fname).write_bytes(raw); image_path='uploads/'+fname
    active=1 if str(b.get('active',1)).lower() not in ('0','false','no','off') else 0
    ts=now()
    try:
        with conn() as db:
            vals=(sku,name,category,typ,metal,purity,weight,making,stone,mode,fixed,stock,image_path,desc,features,active,ts)
            if pid:
                db.execute('UPDATE products SET sku=?,name=?,category=?,product_type=?,metal=?,purity=?,weight_g=?,making_per_g=?,stone_charge=?,price_mode=?,fixed_price=?,stock=?,image_path=?,description=?,features=?,active=?,updated=? WHERE id=?',vals+(pid,))
            else:
                cur=db.execute('INSERT INTO products(sku,name,category,product_type,metal,purity,weight_g,making_per_g,stone_charge,price_mode,fixed_price,stock,image_path,description,features,active,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals+(ts,))
                pid=cur.lastrowid if USE_POSTGRES else db.execute('SELECT last_insert_rowid()').fetchone()[0]
    except INTEGRITY_ERRORS: return jsonify(error='That SKU already exists.'),409
    log_activity('admin',None,'product_saved',f'Product #{pid} {sku}; active={active}; type={typ}')
    return jsonify(ok=True,id=pid,product=one('SELECT * FROM products WHERE id=?',(pid,)))

@app.delete('/api/admin/products/<int:pid>')
@auth
def archive_product(pid):
    with conn() as db:
        cur=db.execute('UPDATE products SET active=0,updated=? WHERE id=?',(now(),pid))
        if not cur.rowcount: return jsonify(error='Product not found.'),404
    log_activity('admin',None,'product_archived',f'Product #{pid} hidden from storefront')
    return jsonify(ok=True)

@app.get('/api/shop')
def get_shop():
    try: data=json.loads(kv('shop') or '{}')
    except Exception: data={}
    return jsonify({**DEF_SHOP,**data})
@app.put('/api/admin/shop')
@auth
def save_shop():
    b=request.get_json(silent=True) or {}; data={k:str(b.get(k,'') or '')[:500] for k in DEF_SHOP}; setkv('shop',json.dumps(data)); return jsonify(data)
@app.post('/api/admin/bills')
@auth
def save_bill():
    b=request.get_json(silent=True) or {}; items=b.get('items')
    if not isinstance(items,list) or len(items)>100 or (not b.get('draft') and not items): return jsonify(error='Add at least one item'),400
    for i in items:
        if i.get('metal') not in ('gold','silver') or any(n(i.get(k))<0 for k in ('gross','rate','qty')): return jsonify(error='Invalid item'),400
    b['paid']=max(0,n(b.get('paid'))); c=calc_bill(b); st=bill_status(b,c['total']); ds=b.get('date') or date.today().isoformat()
    try:
        with conn() as db:
            bid=int(b.get('id') or 0)
            found=db.execute('SELECT id,no FROM bills WHERE id=?',(bid,)).fetchone() if bid else None
            if found:
                b['no']=found['no']; db.execute('UPDATE bills SET date=?,customer=?,phone=?,status=?,total=?,paid=?,data=? WHERE id=?',(ds,b.get('customer',''),b.get('phone',''),st,c['total'],b['paid'],json.dumps(b),bid))
            else:
                num=(db.execute('SELECT COALESCE(MAX(id),0)+1 AS n FROM bills').fetchone()['n']); no=f"AJ-{ds.replace('-','')}-{num:04d}"; b['no']=no
                cur=db.execute('INSERT INTO bills(no,date,customer,phone,status,total,paid,data,created) VALUES(?,?,?,?,?,?,?,?,?)',(no,ds,b.get('customer',''),b.get('phone',''),st,c['total'],b['paid'],json.dumps(b),now())); bid=cur.lastrowid; b['id']=bid
                db.execute('UPDATE bills SET data=? WHERE id=?',(json.dumps(b),bid))
        return jsonify(id=bid,no=b['no'],status=st,total=c['total'])
    except DB_ERRORS as e: app.logger.warning('Could not save bill: %s', e); return jsonify(error='Could not save bill'),400
@app.get('/api/admin/bills')
@auth
def list_bills():
    t='%'+str(request.args.get('q',''))[:50]+'%'
    return jsonify(rows('SELECT id,no,date,customer,phone,status,total,paid FROM bills WHERE no LIKE ? OR customer LIKE ? OR phone LIKE ? ORDER BY id DESC LIMIT 100',(t,t,t)))
@app.get('/api/admin/bills/<int:bid>')
@auth
def get_bill(bid):
    r=one('SELECT data FROM bills WHERE id=?',(bid,))
    return (jsonify(json.loads(r['data'])) if r else (jsonify(error='Not found'),404))
@app.post('/api/admin/bills/<int:bid>/payment')
@auth
def payment(bid):
    b=request.get_json(silent=True) or {}; amount=n(b.get('amount')); r=one('SELECT data FROM bills WHERE id=?',(bid,))
    if not r or amount<=0: return jsonify(error='Invalid'),400
    bill=json.loads(r['data']); bill['paid']=rnd(n(bill.get('paid'))+amount); bill['draft']=False; c=calc_bill(bill); st=bill_status(bill,c['total'])
    with conn() as db: db.execute('UPDATE bills SET paid=?,status=?,data=? WHERE id=?',(bill['paid'],st,json.dumps(bill),bid))
    return jsonify(paid=bill['paid'],status=st)
def _grams_from_bill_data(raw):
    """Return recorded gross grams from an in-store bill JSON payload."""
    try: bill=json.loads(raw or '{}')
    except (TypeError, ValueError): return 0.0
    total=0.0
    for item in bill.get('items',[]) if isinstance(bill,dict) else []:
        if not isinstance(item,dict): continue
        try:
            gross=max(0.0,float(item.get('gross') or 0))
            qty=max(0.0,float(item.get('qty') or 0))
            total += gross*qty
        except (TypeError,ValueError): pass
    return total

def _grams_from_order_items(raw):
    """Return recorded item weight in grams; old orders without weight are not guessed."""
    try: items=json.loads(raw or '[]')
    except (TypeError, ValueError): return 0.0
    total=0.0
    for item in items if isinstance(items,list) else []:
        if not isinstance(item,dict): continue
        try:
            weight=max(0.0,float(item.get('weight_grams', item.get('weight', 0)) or 0))
            qty=max(0.0,float(item.get('qty') or 0))
            total += weight*qty
        except (TypeError,ValueError): pass
    return total

def _sales_grams(today_only=False):
    d=date.today().isoformat()
    with conn() as db:
        # Online orders are counted in the online channel; bills created from online orders
        # are excluded from in-store gram totals to avoid double-counting.
        bill_sql="SELECT data,date FROM bills WHERE status!='Draft'"
        order_sql="SELECT items_json,created,status FROM orders WHERE status NOT IN ('Received','Declined','Cancelled')"
        if today_only:
            bill_sql += ' AND date=?'; order_sql += ' AND substr(created,1,10)=?'
            bill_rows=db.execute(bill_sql,(d,)).fetchall(); order_rows=db.execute(order_sql,(d,)).fetchall()
        else:
            bill_rows=db.execute(bill_sql).fetchall(); order_rows=db.execute(order_sql).fetchall()
        store_grams=0.0
        for r in bill_rows:
            grams=_grams_from_bill_data(r['data'])
            try: data=json.loads(r['data'] or '{}')
            except (TypeError,ValueError): data={}
            if isinstance(data,dict) and data.get('onlineOrderId'): continue
            store_grams += grams
        online_grams=sum(_grams_from_order_items(r['items_json']) for r in order_rows)
    return round(store_grams,3), round(online_grams,3)

@app.get('/api/admin/summary')
@auth
def summary():
    d=date.today().isoformat()
    store=one("SELECT COALESCE(SUM(total),0) AS t FROM bills WHERE date=? AND status!='Draft'",(d,))['t']
    online=one("SELECT COALESCE(SUM(total),0) AS t FROM orders WHERE substr(created,1,10)=? AND status NOT IN ('Received','Declined','Cancelled')",(d,))['t']
    store_paid=one("SELECT COALESCE(SUM(paid),0) AS t FROM bills WHERE date=? AND status!='Draft'",(d,))['t']
    online_paid=one("SELECT COALESCE(SUM(payment_amount),0) AS t FROM orders WHERE substr(created,1,10)=? AND payment_status='Received' AND status NOT IN ('Received','Declined','Cancelled')",(d,))['t']
    all_store=one("SELECT COALESCE(SUM(total),0) AS t FROM bills WHERE status!='Draft'")['t']
    all_online=one("SELECT COALESCE(SUM(total),0) AS t FROM orders WHERE status NOT IN ('Received','Declined','Cancelled')")['t']
    today_store_g,today_online_g=_sales_grams(True)
    lifetime_store_g,lifetime_online_g=_sales_grams(False)
    return jsonify(today=round(float(store)+float(online),2),today_store=store,today_online=online,today_store_paid=store_paid,today_online_paid=online_paid,lifetime_store=all_store,lifetime_online=all_online,today_store_grams=today_store_g,today_online_grams=today_online_g,today_total_grams=round(today_store_g+today_online_g,3),lifetime_store_grams=lifetime_store_g,lifetime_online_grams=lifetime_online_g,lifetime_total_grams=round(lifetime_store_g+lifetime_online_g,3),recent=rows('SELECT id,no,date,customer,total,status FROM bills ORDER BY id DESC LIMIT 5'))

@app.get('/api/admin/report')
@auth
def admin_report():
    """Date-specific sales, bill and online-order report for the admin calendar."""
    raw=str(request.args.get('date') or date.today().isoformat())
    try:
        selected=date.fromisoformat(raw).isoformat()
    except ValueError:
        return jsonify(error='Date must be YYYY-MM-DD.'),400
    with conn() as db:
        bills=db.execute("SELECT id,no,date,customer,phone,status,total,paid,data FROM bills WHERE date=? ORDER BY id DESC",(selected,)).fetchall()
        orders=db.execute("SELECT o.id,o.customer_id,c.name,c.email,o.phone,o.items_json,o.total,o.status,o.created,o.updated,o.address,o.city,o.state,o.pincode,o.delivery_note,o.payment_status,o.payment_method,o.payment_amount,o.payment_reference,o.bill_id FROM orders o JOIN customers c ON c.id=o.customer_id WHERE substr(o.created,1,10)=? ORDER BY o.id DESC",(selected,)).fetchall()
    in_store_sales=0.0; in_store_paid=0.0; in_store_grams=0.0; bill_list=[]
    for b in bills:
        try: data=json.loads(b['data'] or '{}')
        except (TypeError,ValueError): data={}
        is_online_bill=isinstance(data,dict) and bool(data.get('onlineOrderId'))
        if b['status']!='Draft' and not is_online_bill:
            in_store_sales+=n(b['total']); in_store_paid+=n(b['paid']); in_store_grams+=_grams_from_bill_data(b['data'])
        bill_list.append({'id':b['id'],'no':b['no'],'date':b['date'],'customer':b['customer'],'phone':b['phone'],'status':b['status'],'total':n(b['total']),'paid':n(b['paid']),'channel':'Online order bill' if is_online_bill else 'In-store'})
    online_sales=0.0; online_paid=0.0; online_grams=0.0; order_list=[]
    for o in orders:
        try: items=json.loads(o['items_json'] or '[]')
        except (TypeError,ValueError): items=[]
        accepted=o['status'] not in ('Received','Declined','Cancelled')
        if accepted:
            online_sales+=n(o['total']); online_grams+=_grams_from_order_items(o['items_json'])
            if o['payment_status']=='Received': online_paid+=n(o['payment_amount'])
        order_list.append({'id':o['id'],'customer_id':o['customer_id'],'name':o['name'],'email':o['email'],'phone':o['phone'],'items':items if isinstance(items,list) else [],'total':n(o['total']),'status':o['status'],'created':o['created'],'updated':o['updated'],'address':o['address'],'city':o['city'],'state':o['state'],'pincode':o['pincode'],'delivery_note':o['delivery_note'],'payment_status':o['payment_status'],'payment_method':o['payment_method'],'payment_amount':n(o['payment_amount']),'payment_reference':o['payment_reference'],'bill_id':o['bill_id'],'accepted_for_sales':accepted})
    return jsonify(date=selected,totals={'in_store_sales':round(in_store_sales,2),'online_sales':round(online_sales,2),'total_sales':round(in_store_sales+online_sales,2),'in_store_paid':round(in_store_paid,2),'online_paid':round(online_paid,2),'in_store_grams':round(in_store_grams,3),'online_grams':round(online_grams,3),'total_grams':round(in_store_grams+online_grams,3)},bills=bill_list,orders=order_list)

@app.get('/api/admin/backup')
@auth
def admin_backup():
    """Download a private JSON snapshot of all operational tables."""
    import io
    from flask import send_file
    tables=('kv','admin_accounts','admin_sessions','rates','bills','customers','activity_log','products','orders','product_enquiries','sync_log','rate_audit')
    snapshot={'created_at':now(),'format':'asian-jewellery-backup-v1','tables':{}}
    with conn() as db:
        for table in tables:
            try: snapshot['tables'][table]=[dict(r) for r in db.execute(f'SELECT * FROM {table}').fetchall()]
            except Exception:
                snapshot['tables'][table]=[]
    payload=json.dumps(snapshot,ensure_ascii=False,indent=2,default=str).encode('utf-8')
    return send_file(io.BytesIO(payload),mimetype='application/json',as_attachment=True,download_name='asian-jewellery-backup-'+datetime.now().date().isoformat()+'.json')

@app.after_request
def _nc(r):
    r.headers['Cache-Control']='no-cache'
    r.headers['X-Content-Type-Options']='nosniff'
    r.headers['X-Frame-Options']='DENY'
    r.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    r.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    r.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://images.unsplash.com https:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self' https://wa.me mailto:"
    if APP_ENV=='production': r.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    return r
rates_sync.start_scheduler(DB_TARGET)

if __name__=='__main__':
    port=int(os.environ.get('PORT','9000'))
    print(f'Asian Jewellery running on port {port}. Open http://127.0.0.1:{port} on this PC; use this PC\'s LAN IP from another device on the same Wi-Fi.')
    app.run(host='0.0.0.0',port=port,debug=False)
