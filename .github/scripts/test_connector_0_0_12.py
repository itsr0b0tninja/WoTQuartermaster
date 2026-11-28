from __future__ import print_function
import sys, types
sys.modules['BigWorld']=types.ModuleType('BigWorld')
try:
    import imp
except ImportError:
    from importlib.machinery import SourceFileLoader
    m=SourceFileLoader('connector','connector/WoT_Companion_Connector_v0.0.12_source.txt').load_module()
else:
    m=imp.load_source('connector','connector/WoT_Companion_Connector_v0.0.12_source.txt')
assert m.VERSION=='0.0.12'
def vehicle(tier,edges,nation=1,**kw):
    r=dict(level=tier,type='lightTank',nationID=nation,isPremium=False,isSecret=False,isCollectible=False,research_edges=edges);r.update(kw);return r
assert m.audit_tree({'1':vehicle(1,[[10,2],[10,3],[10,4]]),'2':vehicle(2,[]),'3':vehicle(2,[],isPremium=True),'4':vehicle(2,[],nation=2),'5':vehicle(8,[])})==['1','2']
class Obj(object):
    def __init__(self,**kwargs):self.__dict__.update(kwargs)
def component(i):return Obj(compactDescr=i)
turret=Obj(compactDescr=10,guns=[component(11),component(12)])
t=Obj(chassis=[component(1),component(2)],engines=[component(3)],radios=[component(4)],fuelTanks=[component(5)],turrets=[[turret]])
rows=m.audit_candidates(Obj(type=t))
assert len(rows)==4 and len(set(str(x) for x in rows))==4
assert m.audit_allowed((True,None)) and not m.audit_allowed((False,'invalid'))
try:
    m.audit_allowed((1,None))
except m.Unavailable:pass
else:raise AssertionError('unexpected compatibility result accepted')
t.engines=[]
try:
    m.audit_candidates(Obj(type=t))
except m.Unavailable:pass
else:raise AssertionError('incomplete module pool accepted')
print('Connector candidate enumeration and missing-data regression checks passed')
import tempfile,shutil,os,json,hashlib
# Native false and unknown are distinct. Never convert exceptions to false.
class Fit(object):
    def __init__(self,result):self.result=result
    def mayInstall(self,vehicle,slot):
        if isinstance(self.result,Exception):raise self.result
        return self.result
assert m.supplemental_fit(Fit((True,None)),None,0)['allowed'] is True
assert m.supplemental_fit(Fit((False,'denied')),None,0)['allowed'] is False
for result in (AttributeError('missing'),(1,None),None):
    assert m.supplemental_fit(Fit(result),None,0)['allowed'] is None
root=tempfile.mkdtemp()
try:
    a=m.SupplementalAudit(Obj())
    a.folder=root;a.identity={'schema':1,'collector_version':'0.0.12','game_version':'test','base_checksums':{'vehicles':'abc'}}
    a.finish('vehicle','1',{'status':'partial','fit':{'allowed':None}})
    a.files={};assert a.recover('vehicle','1')
    path=a.path('vehicle','1');r=m.read_json(path);r['data']['fit']['allowed']=True;m.atomic_write(path,r)
    assert not a.recover('vehicle','1')
    a.finish('vehicle','1',{'status':'partial'});a.identity=dict(a.identity,game_version='other');assert not a.recover('vehicle','1')
    old={'schema':1,'collector_version':'0.0.9','game_version':'test','base_checksums':{'vehicles':'abc'}}
    data={'identity':old,'vehicle_id':1,'finished':True,'counts':{'candidates':1,'calculated':1},'configurations':[{'modules':{'gun':1}}]}
    p=os.path.join(root,'1.json');m.atomic_write(p,data)
    manifest=dict(old,collection_finished=True,processed_vehicles=1,total_vehicles=1,files={'1':{'count':1,'sha256':m.digest_file(p)}},counts=data['counts'],status='partial')
    m.atomic_write(os.path.join(root,'manifest.json'),manifest)
    assert m.legacy_audit_manifest(root,old,['1'])==manifest
    assert m.legacy_audit_row(root,'1',old,manifest['files']['1'])==data['counts']
    try:m.legacy_audit_manifest(root,old,['1','2'])
    except m.Unavailable:pass
    else:raise AssertionError('Wrong coverage accepted')
    data['configurations'][0]['modules']['gun']=2;m.atomic_write(p,data)
    try:m.legacy_audit_row(root,'1',old,manifest['files']['1'])
    except m.Unavailable:pass
    else:raise AssertionError('Corrupt audit accepted')
    helpers=types.ModuleType('helpers');helpers.isPlayerAccount=lambda:True;sys.modules['helpers']=helpers
    owner=Obj(active=True,context_queue=False,context_snapshot={'state':'garage'},cache=Obj(waitForSync=False,isSynced=lambda:True))
    assert m.scan_ready(owner)
    owner.context_queue=True;assert not m.scan_ready(owner)
    owner.context_queue=False;owner.context_snapshot={'state':'battle_loading'};assert not m.scan_ready(owner)
    owner.context_snapshot={'state':'garage'};owner.cache.waitForSync=True;assert not m.scan_ready(owner)
    owner.cache.waitForSync=False;helpers.isPlayerAccount=lambda:False;assert not m.scan_ready(owner)
    # Pausing clears only unfinished preview state; complete files survive.
    a.owner=owner;a.current={'row':{}};a.preview=object();a.tick()
    assert a.status['status']=='paused' and a.current is None and a.preview is None and os.path.exists(path)
finally:shutil.rmtree(root)
print('Supplemental evidence, checksum, identity, pause and legacy audit regression checks passed')

# Targeted native fields: distinguish real null (full rotation) from absence.
p=m.Probe()
gun=Obj(compactDescr=1,turretYawLimits=None,autoreload=(2,3),autoreloadHasBoost=True,dualGun=Obj(chargeTime=4,reloadTimes=[5,6]))
r=m.targeted_gun(gun,p,'gun')
assert r['full_rotation'] is True and r['autoreload']['value']==[2,3]
assert r['dualGun']['chargeTime']['value']==4
assert m.targeted_gun(Obj(),m.Probe(),'missing')['full_rotation'] is None
class Shop(object):
    def getVehicleSlotsItemPrice(self,n):return Obj(price={'credits':250000},defPrice={'credits':300000})
    def getTankmanBerthPrice(self,n):return ({'gold':100},16)
q=m.targeted_slot_quotes(Obj(shop=Shop(),stats=Obj(vehicleSlots=10,tankmenBerthsCount=16)),m.Probe())
assert q['garage']['price']['credits']==250000 and q['barracks']['pack_size']==16
print('Targeted native fields and slot quote fixtures passed')

owner=Obj(session='s',account_key='a',game_version=lambda:'v',full_revision=0,current=Obj(item=Obj(intCD=42)),result_count=0,result_duplicates=0,results_service=None)
items=Obj(shop=Shop(),stats=Obj(vehicleSlots=1,tankmenBerthsCount=2))
original=m.targeted_purchase_quote
try:
    m.targeted_purchase_quote=lambda items,k,p:{'vehicle_id':k}
    assert m.supplemental_quotes(owner,items)['purchase_package_quotes']['vehicle_id']==42
finally:m.targeted_purchase_quote=original
print('Selected vehicle wrapper regression passed')
