"""Mocked-response tests (no network). Run: python -m unittest discover tests"""
import os, sys, tempfile, unittest, json, sqlite3
os.environ['SYNC_SCHEDULER']='0'; sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
import rates_sync as rs
AK='<h3>Today\'s Rate (17/10/2026)</h3><ul><li><b>22K916 (1gm) - &#8377; 13535</b></li><li><b>18K750 (1gm) - &#8377; 11075</b></li><li><b>Silver (1gm) - &#8377; 230</b></li><li><b>925 Hall Marked Silver (1gm) - &#8377; NA</b></li></ul>'
LG='<h1>Gold Rate Today in Kozhikode</h1><p>Verified AKGSMA Board Rate</p><p>Sunday, 18 October 2026 · Updated by 10 AM IST</p><!-- --><div>22 Karat Gold 916 Hallmark <b>₹13,413</b></div><div>18 Karat 750 <span>₹10,982</span>/ g</div><div>Silver Rate Today Ag 999 · Kerala Board Rate ₹240/g</div>'
def fake(a=AK,b=LG):
    return lambda u: {'https://akgsma.com/':a,'https://www.livegoldkerala.com/kozhikode':b}[u] if (a if 'akgsma' in u else b) is not None else (_ for _ in ()).throw(OSError('down'))
class T(unittest.TestCase):
    def setUp(self): self.f=tempfile.mktemp(suffix='.db')
    def rows(self,q,*a): d=sqlite3.connect(self.f); d.row_factory=sqlite3.Row; return d.execute(q,a).fetchall()
    def test_parsers(self):
        a=rs.parse_akgsma(AK); self.assertEqual((a['date'],a['g916'],a['g750'],a['s999'],a['s925']),('2026-10-17',13535,11075,230,None))
        l=rs.parse_livegold(LG); self.assertEqual((l['date'],l['g916'],l['g750'],l['s999']),('2026-10-18',13413,10982,240))
    def test_layout_change_fails_safely(self):
        with self.assertRaises(ValueError): rs.parse_akgsma('<html>nothing</html>')
    def test_validation(self):
        with self.assertRaises(ValueError): rs.validate({'g916':5})
    def test_freshest_source_and_labels(self):
        r=rs.run_sync(self.f,'t',fake()); self.assertTrue(r['ok'])
        g=self.rows("SELECT * FROM rates WHERE metal='gold' AND purity='916' ORDER BY id DESC")[0]
        self.assertEqual((g['per_gram'],g['rate_date'],g['kind']),(13413,'2026-10-18','quoted'))
        k={x['purity']:x['kind'] for x in self.rows("SELECT purity,kind FROM rates WHERE metal='gold'")}
        self.assertEqual((k['999'],k['995'],k['585'],k['750']),('calculated',)*3+('quoted',))
    def test_failover_and_total_failure_keeps_last(self):
        r=rs.run_sync(self.f,'t',fake(a=None)); self.assertTrue(r['ok']); n=len(self.rows('SELECT 1 FROM rates'))
        r=rs.run_sync(self.f,'t',fake(None,None)) if False else None
        db=sqlite3.connect(self.f); db.execute("UPDATE kv SET v='0' WHERE k='sync_claim'"); db.commit()
        r=rs.run_sync(self.f,'t',fake(a=None,b=None)); self.assertFalse(r['ok']); self.assertEqual(n,len(self.rows('SELECT 1 FROM rates')))
    def test_manual_not_overwritten(self):
        rs.run_sync(self.f,'t',fake()); db=sqlite3.connect(self.f)
        db.execute("INSERT INTO rates(metal,purity,per_gram,source,ts,kind,rate_date) VALUES('gold','916',13000,'m','2026-10-19T00:00:00+00:00','manual','2026-10-19')"); db.execute("UPDATE kv SET v='0' WHERE k='sync_claim'"); db.commit()
        r=rs.run_sync(self.f,'t',fake(a=AK.replace('13535','13400'))); self.assertTrue(any('manual' in n for n in r['notes']))
        self.assertEqual(self.rows("SELECT per_gram FROM rates WHERE metal='gold' AND purity='916' ORDER BY id DESC")[0][0],13000)
    def test_duplicate_run_blocked(self):
        rs.run_sync(self.f,'t',fake()); self.assertIn('skipped',rs.run_sync(self.f,'t',fake()))
if __name__=='__main__': unittest.main()
