from __future__ import print_function
import sys, types, imp
sys.modules['BigWorld']=types.ModuleType('BigWorld')
m=imp.load_source('connector','connector/WoT_Companion_Connector_v0.0.9_source.txt')
assert m.VERSION=='0.0.9'
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
