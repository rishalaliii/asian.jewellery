"""Local integration tests for product publication, customer checkout and backups."""
import os, tempfile, unittest
DB=tempfile.mktemp(suffix='.db')
os.environ['DB_FILE']=DB
os.environ['APP_ENV']='development'
os.environ['SYNC_SCHEDULER']='0'
os.environ.pop('DATABASE_URL',None)
import app as webapp

class AppFlowTests(unittest.TestCase):
    def setUp(self):
        self.client=webapp.app.test_client()
    def test_admin_product_customer_order_and_backup(self):
        # Admin login, then create a published fixed-price product.
        r=self.client.post('/api/login',json={'username':'asianadmin','password':'asianadmin916'})
        self.assertEqual(r.status_code,200,r.get_json())
        product={'sku':'TEST-001','name':'Test Gold Chain','category':'Gold Chains','product_type':'gold','metal':'gold','purity':'916','weight_g':2,'making_per_g':100,'stone_charge':0,'price_mode':'fixed','fixed_price':25000,'stock':3,'active':1,'description':'Test product'}
        r=self.client.post('/api/admin/products',json=product)
        self.assertEqual(r.status_code,200,r.get_json())
        pid=r.get_json()['id']
        self.assertGreater(pid,0)
        r=self.client.get('/api/products')
        self.assertEqual(r.status_code,200)
        self.assertTrue(any(p['id']==pid and p['name']=='Test Gold Chain' for p in r.get_json()['products']))
        # Log out admin, register a customer and create an order using the managed product ID.
        self.client.post('/api/logout')
        r=self.client.post('/api/customer/register',json={'name':'Test Customer','email':'test@example.com','phone':'9876543210','password':'testpassword123'})
        self.assertEqual(r.status_code,200,r.get_json())
        r=self.client.post('/api/customer/orders',json={'items':[{'name':'Test Gold Chain','category':'Gold Chains','price':1,'qty':1,'product_id':pid}],'address':'House, street, nearby landmark','city':'Kozhikode','state':'Kerala','pincode':'673001'})
        self.assertEqual(r.status_code,201,r.get_json())
        order_id=r.get_json()['order']['id']
        self.assertEqual(r.get_json()['order']['total'],25000)
        r=self.client.get('/api/customer/orders')
        self.assertTrue(any(o['id']==order_id for o in r.get_json()['orders']))
        self.client.post('/api/customer/logout')
        r=self.client.post('/api/login',json={'username':'asianadmin','password':'asianadmin916'})
        self.assertEqual(r.status_code,200,r.get_json())
        r=self.client.get('/api/admin/orders')
        self.assertTrue(any(o['id']==order_id for o in r.get_json()['orders']))
        r=self.client.get('/api/admin/backup')
        self.assertEqual(r.status_code,200)
        self.assertIn('asian-jewellery-backup',r.headers.get('Content-Disposition',''))

if __name__=='__main__': unittest.main()
