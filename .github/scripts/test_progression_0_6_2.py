"""Synthetic regression tests for playstyle-led progression, no private data."""
import sys, pathlib, types
from types import SimpleNamespace
shared=types.ModuleType('module_shared')
shared.obj=lambda x:x if isinstance(x,dict) else {}
shared.seq=lambda x:x if isinstance(x,list) else []
shared.key=lambda x:str(x) if x is not None else ''
shared.name=lambda x,fallback='Unknown':x.get('userName',fallback)
sys.modules['module_shared']=shared
p=pathlib.Path('modules/progression/0.1.2/progression.qmodule')
n={'__file__':str(p)}
exec(compile(p.read_bytes(),str(p),'exec'),n)
def v(k,t,nation,edges=(),stock=()):
    return dict(intCD=int(k),userName='Tank '+k,level=t,nationID=nation,type='lightTank',isPremium=False,isSecret=False,isCollectible=False,default_buy={'credits':100*t},stock_modules={str(i):{'compactDescr':int(x)} for i,x in enumerate(stock)},vehicle_type={'crewRoles':[['commander']]},research_edges=list(edges))
rows={'1':v('1',1,0,[[10,17]]),'17':v('17',2,0,[[20,33,101]],['101']),'33':v('33',3,0,[[30,49,102]],['102']),'49':v('49',4,0),
      '2':v('2',1,1,[[10,18]]),'18':v('18',2,1,[[20,34,201]],['201']),'34':v('34',3,1,[[30,50,202]],['202']),'50':v('50',4,1)}
tree=n['graph'](rows); assert len(tree)==8
style='Hybrid Scout'
scores={k:{style:{'score':x}} for k,x in {'1':20,'17':25,'33':30,'49':35,'2':90,'18':95,'34':90,'50':95}.items()}
g=SimpleNamespace(section=lambda k:{})
known={'1','17','2','18'}; owned={'17':{}}
def routes(own=owned,unlock=known):
    return n['route_candidates'](rows,tree,scores,style,own,unlock,{'17':0,'18':0,'34':0},g,{},[])
r=routes()
assert {x['destination'] for x in r}=={'49','50'}
assert next(x for x in r if x['destination']=='50')['xp']==50
assert known=={'1','17','2','18'}
pick=lambda candidates,prior,own,unlocked:n['select_progression'](candidates,prior,own,unlocked,rows,tree,style)
first=pick(r,None,owned,known)
assert first['destination']=='50' and first['start']=='18',first
assert first['start'] not in owned
assert pick(r,{'formula':2,'destination':'49'},owned,known)==first
prior={'formula':n['FORMULA'],'destination':'50','full_path':first['full_path']}
assert pick(r,prior,owned,known)==first
own2={**owned,'18':{}}
second=pick(routes(own2),prior,own2,known)
assert second['destination']=='50' and second['path']==['18','34','50'],second
assert n['dependency_plan'](rows,'18','34',known|{'201'},{})[0]['xp']==20
assert pick(routes({'17':{}},{'1','17','2'}),None,{'17':{}},{'1','17','2'})['start']=='2'
# The approved weighted rank, rather than immediate stock fit, controls selection.
low=dict(r[1],rank=80,end=10); high=dict(r[0],rank=76,end=99)
assert pick([high,low],None,owned,known)==low
assert pick([low,high],prior,owned,known)==high
assert pick([dict(low,rank=81),high],prior,owned,known)['destination']=='49'
assert len(n['WEIGHTS'])==10 and all(sum(x)==100 for x in n['WEIGHTS'].values())
assert 'discovery' not in n and 'useful_engine_upgrade' not in n
# Completed mid-tier goals must continue rather than remain stuck.
intermediate=dict(first,destination='34',full_path=['2','18','34'],path=['34'],rank=99)
mid_prior={'formula':n['FORMULA'],'destination':'34','full_path':intermediate['full_path']}
assert pick([intermediate,first],mid_prior,{**own2,'34':{}},known)==first
print('PASS: weighted route ranking, new national entry, stock prerequisites, advancement, legacy revalidation and five-point safeguard')

# Exercise the real coordinator, including purchase/saving/research transitions.
import tempfile, json
class Control:
    def __init__(self): self.text=''; self.visible=True
    def setText(self,s): self.text=s
    def setVisible(self,v): self.visible=v
    def hide(self): self.visible=False
    def currentRow(self): return -1
class Cat:
    identity='fixture-v2'
    def category(self,k,enriched=False):
        return rows if k=='vehicles' and not enriched else {}
    def item(self,k,i,enriched=False): return {}
def tank(k):
    return {'intCD':int(k),'invID':int(k),'isLocked':False,'isRented':False,
            'isElite':False,'isPremium':False,'combat_xp':0,
            'modules':{'gun':{'intCD':4}},
            'crew_slots':[{'crew_id':1}],'shells_layout':[{'count':5}]}
def coordinator(root, initial, unlocked, credits=1000):
    sections={'research':{'unlocked_item_ids':list(map(int,unlocked)),'initial_unlocks':[1,2],
                          'vehicle_xp':{}},
              'garage':{},'account_extra':{'free_vehicle_slots':3},
              'depot':{'SHELL':{},'ENGINE':{}},'crew':{},'current_shop_prices':{}}
    garage=[tank(k) for k in initial]
    cat=Cat()
    gg=SimpleNamespace(catalogue=cat,section=lambda k:sections.get(k),status=lambda k:'ok',
                       vehicles={str(x['invID']):x for x in garage})
    ss={k:{sty:{'score':(100-scores[k][style]['score'] if sty=='Brawler' else scores[k][style]['score']),'categories':[50]*7,'coverage':100}
           for sty in n['WEIGHTS'] if sty!='Artillery Support'} for k in rows}
    account='a'*24
    m=SimpleNamespace(root=root,state='garage',sources={'connector':{'session':'x','game_version':'v'},
        'battle_context':{'session':'x','account_key':account},
        'diagnostics':{'session':'x','game_version':'v'}},
        account={'credits':credits,'free_xp':0},selected={'tank_id':int(initial[0]),'combat_xp':0},
        garage=garage,garage_signature='fixture',garage_data=gg)
    w=SimpleNamespace(model=m,settings=SimpleNamespace(values={'playstyle':style,'advisor_mode':'Full Advisor'}),
        runtime=SimpleNamespace(loaded={}),prog_tables={k:Control() for k in
            ('Overview','Career','Technology Trees','Vehicles','Research')},
        prog_stamp=None,prog_static=(cat.identity,tree,ss,{}),prog_discovery=Control(),
        prog_dismiss=Control(),prog_note=Control(),prog_vehicle_note=Control(),
        next_action_title=Control(),next_action_detail=Control(),next_action_request=Control(),
        set_rows=lambda tb,rr:setattr(tb,'rows',rr))
    return w,sections,account
def refresh(w):
    n['coordinate'](w,True)
    return w.next_action_title.text
with tempfile.TemporaryDirectory() as tmp:
    root=pathlib.Path(tmp)
    w,sections,account=coordinator(root,['17'],{'1','2','17','18'})
    assert refresh(w)=='Review purchase of Tank 18',w.next_action_title.text
    assert w.prog_finance_target['id']=='18'
    w.model.account['credits']=0
    assert refresh(w)=='Earn credits'
    assert 'Tank 18' in w.next_action_detail.text
    w.model.account['credits']=1000
    sections['account_extra']['free_vehicle_slots']=0
    assert refresh(w)=='Free a garage slot'
    assert 'Tank 18' in w.next_action_detail.text
    sections['account_extra']['free_vehicle_slots']=3
    w.model.garage.append(tank('18'))
    w.model.selected={'tank_id':18,'combat_xp':0}
    sections['research']['unlocked_item_ids']+=[201]
    assert refresh(w)=='Play Tank 18',w.next_action_title.text
    assert w.prog_finance_target['id']=='34'
    w.model.selected['combat_xp']=20
    assert refresh(w)=='Research Tank 34',w.next_action_title.text
    sections['research']['unlocked_item_ids']+=[34]
    assert refresh(w)=='Review purchase of Tank 34'
    for sty in n['WEIGHTS']:
        if sty=='Artillery Support': continue
        w.settings.values['playstyle']=sty
        refresh(w)
        assert 'playstyle trial' not in w.next_action_detail.text.lower()
    saved=json.loads((root/'progression'/'careers.json').read_text())
    assert len(saved['accounts'][account]['careers'])==9
    assert saved['accounts'][account]['careers']['Brawler']['destination']=='49'
    w.settings.values['playstyle']=style
    assert refresh(w)=='Review purchase of Tank 34'
    assert w.prog_finance_target['id']=='34'
    w.model.sources['diagnostics']['session']='stale'
    assert refresh(w)=='Waiting for live garage data'
with tempfile.TemporaryDirectory() as tmp:
    w,sections,_=coordinator(pathlib.Path(tmp),['17'],{'1','2','17'})
    assert refresh(w)=='Review purchase of Tank 2',w.next_action_title.text
    assert w.prog_finance_target['id']=='2'
print('PASS: coordinator purchase, named saving, slots, progression, research, playstyle persistence, stale-data gate')

# Artillery uses its own eligible domain, including non-SPG prerequisites.
ar={'1':v('1',1,0,[[10,17]]),'17':v('17',2,0,[[20,33,101]],['101']),'33':v('33',3,0)}
ar['17']['type']='spg'; ar['33']['type']='spg'
atree=n['graph'](ar)
ascores={'1':{},'17':{'Artillery Support':{'score':90}},'33':{'Artillery Support':{'score':80}}}
ac=n['route_candidates'](ar,atree,ascores,'Artillery Support',{'1':{}},{'1'},{'1':0},g,{},[])
a=n['select_progression'](ac,None,{'1':{}},{'1'},ar,atree,'Artillery Support')
assert a['destination']=='33' and a['path']==['1','17','33']
assert next(x for x in ac if x['destination']=='33')['xp']==30
print('PASS: artillery progression across a non-artillery prerequisite')
