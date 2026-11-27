"""Synthetic regression tests for playstyle-led progression, no private data."""
import sys, pathlib, types
from types import SimpleNamespace
shared=types.ModuleType('module_shared')
shared.obj=lambda x:x if isinstance(x,dict) else {}
shared.seq=lambda x:x if isinstance(x,list) else []
shared.key=lambda x:str(x) if x is not None else ''
shared.name=lambda x,fallback='Unknown':x.get('userName',fallback)
sys.modules['module_shared']=shared
p=pathlib.Path('modules/progression/0.1.1/progression.qmodule')
n={'__file__':str(p)}
exec(compile(p.read_bytes(),str(p),'exec'),n)
def v(k,t,nation,edges=(),stock=()):
    return dict(intCD=int(k),userName='Tank '+k,level=t,nationID=nation,type='lightTank',isPremium=False,isSecret=False,isCollectible=False,default_buy={'credits':100*t},stock_modules={str(i):{'compactDescr':int(x)} for i,x in enumerate(stock)},vehicle_type={'crewRoles':[['commander']]},research_edges=list(edges))
rows={'1':v('1',1,0,[[10,17]]),'17':v('17',2,0,[[20,33,101]],['101']),'33':v('33',3,0,[[30,49,102]],['102']),'49':v('49',4,0),
      '2':v('2',1,1,[[10,18]]),'18':v('18',2,1,[[20,34,201]],['201']),'34':v('34',3,1,[[30,50,202]],['202']),'50':v('50',4,1)}
tree=n['graph'](rows); assert len(tree)==8
style='Hybrid Scout'
scores={k:{style:{'score':x}} for k,x in {'1':20,'17':40,'33':45,'49':99,'2':25,'18':90,'34':85,'50':50}.items()}
g=SimpleNamespace(section=lambda k:{})
known={'1','17','2','18'}; owned={'17':{}}
def routes(own=owned,unlock=known):
    return n['route_candidates'](rows,tree,scores,style,own,unlock,{'17':0,'18':0,'34':0},g,{},[])
r=routes()
assert {x['destination'] for x in r}==set(rows)
assert next(x for x in r if x['destination']=='50')['xp']==50
assert known=={'1','17','2','18'} # simulation does not mutate real state
pick=lambda candidates,prior,own,unlocked:n['select_progression'](candidates,prior,own,unlocked,rows,tree,style)
first=pick(r,None,owned,known)
assert first['destination']=='18' and first['start']=='18',first
assert first['destination'] not in owned # stronger unowned candidate wins
assert pick(r,{'formula':1,'destination':'49'},owned,known)['destination']=='18'
prior={'formula':n['FORMULA'],'destination':'18','full_path':first['full_path']}
assert pick(r,prior,owned,known)['destination']=='18'
own2={**owned,'18':{}}
second=pick(routes(own2),prior,own2,known)
assert second['destination']=='34' and second['path']==['18','34'],second
assert n['dependency_plan'](rows,'18','34',known|{'201'},{})[0]['xp']==20
assert pick(routes({'17':{}},{'1','17','2'}),None,{'17':{}},{'1','17','2'})['destination']=='18'
# A distant high-scoring terminal never preempts the next stage.
assert first['destination']!='49'
# Approved style weights remain intact.
assert len(n['WEIGHTS'])==10 and all(sum(x)==100 for x in n['WEIGHTS'].values())
# Verify conservative upgrade gates.
rows['17']['compatible_modules']={'engines':[1,2,3]}
cat={'1':{'descriptor_fields':{'power':100,'weight':100}},'2':{'userName':'Better engine','descriptor_fields':{'power':120,'weight':90},'default_buy':{'credits':50}},'3':{'descriptor_fields':{'power':150,'weight':200}}}
vehicle={'modules':{'engine':{'intCD':1}}}
def eng(depot):
    return SimpleNamespace(catalogue=SimpleNamespace(category=lambda k:cat),section=lambda k:{'ENGINE':depot} if k=='depot' else {})
assert n['useful_engine_upgrade'](eng({'2':1}),rows,'17',vehicle,style,{'2','3'},0,None)['id']=='2'
assert n['useful_engine_upgrade'](eng({}),rows,'17',vehicle,style,{'2'},100,100) is None
assert n['useful_engine_upgrade'](eng({}),rows,'17',vehicle,style,{'2'},150,100)['cost']==50
assert n['useful_engine_upgrade'](eng({}),rows,'17',vehicle,'Brawler',{'2'},150,100) is None
print('PASS: new national entry, near-term tier, stable target, advancement, stock grants, migration, upgrade budget gates')
