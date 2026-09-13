import unittest
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app

class KitchenTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app(self.temp.name)
        self.app.config['TESTING']=True
        self.c=self.app.test_client()
        self.origin={'Origin':'http://localhost'}
        self.counter=0
        self.post('/api/join',{'name':'Anna'})
    def tearDown(self):
        self.temp.cleanup()
    def post(self,path,data,client=None):
        return (client or self.c).post(path,json=data,headers=self.origin)
    def state(self):
        return self.c.get('/api/state?day=2026-09-13').get_json()
    def act(self,action,http_status=200,**data):
        self.counter+=1
        r=self.post('/api/action',{'action':action,'requestId':str(self.counter),**data})
        self.assertEqual(r.status_code,http_status,r.get_json())
        return r
    def item(self,name='Radicchio',**extra):
        self.act('item',name=name,kind='ingredient',unit='kg',icon='🥬',**extra)
        return next(i for i in self.state()['items'] if i['name']==name)
    def move(self,i,kind,qty,expected=200,**extra):
        current=next(x for x in self.state()['items'] if x['id']==i['id'])
        return self.act('movement',expected,item=i['id'],version=current['version'],kind=kind,qty=qty,day='2026-09-13',**extra)
    def test_menu_confirmation_shared_stock(self):
        with patch('app.ask',return_value={'dishes':[{'name':'Chicory salad','icon':'🥬','ingredients':[{'name':'Radicchio','kind':'ingredient','icon':'🥬'}]}]}):
            draft=self.post('/api/menu/read',{'text':'Chicory salad'}).get_json()
        self.assertEqual(self.state()['dishes'],[])
        self.act('menu_confirm',draft=draft['id'],dishes=draft['dishes'])
        self.assertEqual(self.state()['items'],[])
        d=self.state()['dishes'][0]
        i=self.item(dish=d['id'])
        self.act('dish',name='Second salad',icon='🥗')
        d2=next(x for x in self.state()['dishes'] if x['name']=='Second salad')
        self.item(dish=d2['id'])
        self.assertEqual(len(self.state()['items']),1)
        self.assertEqual(len(self.state()['dish_items']),2)
        self.move(i,'count',5)
        self.assertEqual(self.state()['items'][0]['qty'],5)
    def test_idempotency_concurrency_atomic_negative_prevention(self):
        i=self.item()
        payload={'action':'movement','requestId':'fixed','item':i['id'],'version':0,'kind':'count','qty':4,'day':'2026-09-13'}
        self.assertEqual(self.post('/api/action',payload).status_code,200)
        self.assertEqual(self.post('/api/action',payload).status_code,200)
        self.assertEqual(len(self.state()['movements']),1)
        self.act('movement',409,item=i['id'],version=0,kind='count',qty=5)
        self.move(i,'used',9,409)
        self.assertEqual(self.state()['items'][0]['qty'],4)
        self.move(i,'used',1)
        self.assertEqual(self.state()['items'][0]['qty'],3)
    def test_batches_dates_transfers_use_by(self):
        i=self.item()
        self.move(i,'received',2,location='Fridge',use_by='2026-09-13')
        self.move(i,'received',3,location='Fridge',use_by='2026-09-15')
        self.move(i,'count',4,400)
        self.move(i,'transfer',1,location='Backup fridge')
        self.assertEqual(self.state()['items'][0]['qty'],5)
        self.assertTrue(any(b['location']=='Backup fridge' and b['use_by']=='2026-09-13' for b in self.state()['batches']))
        self.assertTrue(any(x['kind']=='check' for x in self.state()['suggestions']))
        self.move(i,'waste',1,note='Spoiled')
        self.assertEqual(self.state()['items'][0]['qty'],4)
    def test_predictions_actual_outcomes_and_usage(self):
        i=self.item()
        self.move(i,'count',6)
        self.act('service',day='2026-09-13',phase='live',covers=50)
        self.act('prediction',item=i['id'],services=3,day='2026-09-13')
        self.move(i,'used',2)
        self.act('service',day='2026-09-13',phase='closed',covers=49)
        self.act('service',day='2026-09-14',phase='live',covers=60)
        cur=self.state()['items'][0]
        self.act('movement',item=i['id'],version=cur['version'],kind='used',qty=2,day='2026-09-14')
        self.act('service',day='2026-09-14',phase='closed',covers=58)
        cur=self.state()['items'][0]
        self.act('item_settings',item=i['id'],version=cur['version'],lead=2)
        s=next(x for x in self.state()['suggestions'] if x['kind']=='buy')
        self.assertEqual(s['rate'],2)
        self.assertEqual(s['remaining'],1)
        cur=self.state()['items'][0]
        self.act('movement',item=i['id'],version=cur['version'],kind='used',qty=2,day='2026-09-14')
        self.assertEqual(self.state()['predictions'][0]['outcome'],2)
    def test_concern_claim_resolution_and_restart(self):
        self.act('concern',body='Prep may be short',message='🥣 Anna flagged prep. Check the crumble?',location='Fridge')
        c=self.state()['concerns'][0]
        self.act('concern_update',id=c['id'],status='checking')
        self.act('concern_update',400,id=c['id'],status='resolved',resolution='')
        self.act('concern_update',id=c['id'],status='resolved',resolution='Made one batch')
        new=create_app(self.temp.name).test_client()
        self.post('/api/join',{'name':'Sam'},new)
        s=new.get('/api/state').get_json()
        self.assertEqual(s['concerns'][0]['status'],'resolved')
        self.assertEqual(len(s['people']),2)
        export=new.get('/api/export').get_json()
        self.assertNotIn('sessions',export)
        self.assertNotIn('settings',export)
        self.assertTrue(export['activity'])
    def test_access_validation_and_component_cycles(self):
        anonymous=self.app.test_client()
        self.assertEqual(self.post('/api/action',{'action':'dish'},anonymous).status_code,401)
        self.assertEqual(self.c.post('/api/join',json={'name':'Bad'},headers={'Origin':'https://bad.example'}).status_code,403)
        i=self.item()
        self.move(i,'count',float('nan'),400)
        self.assertEqual(self.state()['movements'],[])
        self.act('item',name='Sauce',kind='prep',unit='L')
        p=next(i for i in self.state()['items'] if i['name']=='Sauce')
        self.act('item',400,name='Sauce',kind='prep',unit='L',parent=p['id'])
    def test_detailed_past_shift_is_editable_and_never_moves_current_stock(self):
        i=self.item()
        self.move(i,'count',5)
        self.act('past_shift',day='2026-09-11',expected=70,actual=74,reservations=60,walkins=14,rush='20:00–21:30',weather='Rain',terrace='Closed',prep='Chicory prep ran low',tags=['Running low','Waste'],events='Missed radicchio order',note='Ask earlier next time',version=0)
        s=self.state()
        self.assertEqual(s['items'][0]['qty'],5)
        detail=s['shift_details'][0]
        self.assertEqual(detail['walkins'],14)
        self.assertEqual(len(s['movements']),1)
        self.assertEqual(detail['version'],1)
        self.act('past_shift',409,day='2026-09-11',actual=75,version=0)
        self.act('past_shift',day='2026-09-11',actual=75,prep='Corrected debrief',version=1)
        self.assertEqual(self.state()['shift_details'][0]['version'],2)
        history=self.c.get('/api/history?day=2026-09-11').get_json()['events']
        self.assertEqual(len(history),2)
        self.assertTrue(all(h['day']=='2026-09-11' for h in history))

    def test_ai_failure_never_changes_stock(self):
        from intelligence import AIError
        with patch('app.ask',side_effect=AIError('Unavailable')):
            self.assertEqual(self.post('/api/menu/read',{'text':'Salad'}).status_code,400)
        self.assertEqual(self.state()['items'],[])
        self.assertEqual(self.state()['dishes'],[])
        self.assertEqual(self.post('/api/menu/read',{'image':'data:image/png;base64,bm90IGltYWdl'}).status_code,400)
if __name__=='__main__':
    unittest.main()
