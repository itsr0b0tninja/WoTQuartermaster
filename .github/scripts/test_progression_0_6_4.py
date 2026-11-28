"""Production module tests with synthetic account/catalogue; no private exports."""
from pathlib import Path
from types import SimpleNamespace
import sys,types,json,tempfile,math,hashlib
shared=types.ModuleType('module_shared');shared.obj=lambda x:x if isinstance(x,dict) else {};shared.seq=lambda x:x if isinstance(x,list) else [];shared.key=lambda x:str(x) if x is not None else '';shared.name=lambda x,f='Unknown':x.get('userName',f)
sys.modules['module_shared']=shared
ROOT=Path(__file__).resolve().parents[2]
def load(path):
    n={'__file__':str(path)};exec(compile(path.read_bytes(),str(path),'exec'),n);return n
n=load(ROOT/'modules/progression/0.1.4/progression.qmodule');fin=load(ROOT/'modules/finance/0.1.2/finance.qmodule')
# Build a tiny, fully specified synthetic catalogue: two ordinary lines and an artillery branch.
STYLE='Hybrid Scout'
def v(k,t,ns,kind='lightTank',edges=()):
    ids={a:10000+int(k)*10+i for i,a in enumerate(('chassis','turret','gun','engine','radio','fuelTank'))}
    return dict(intCD=int(k),userName='Tank '+k,level=t,nationID=ns,type=kind,isPremium=False,isSecret=False,isCollectible=False,default_buy={'credits':t*10000},stock_modules={a:{'compactDescr':x} for a,x in ids.items()},vehicle_type={'crewRoles':[['commander'],['driver']]},research_edges=list(edges),compatible_modules={'chassis':[ids['chassis']],'engines':[ids['engine']],'radios':[ids['radio']],'fuelTanks':[ids['fuelTank']],'turrets_and_guns':[{'turret':ids['turret'],'guns':[ids['gun']]}]})
rows={'1':v('1',1,0,edges=[[100,17]]),'17':v('17',2,0,edges=[[500,33]]),'33':v('33',9,0,edges=[[10000,49]]),'49':v('49',11,0),
      '2':v('2',1,1,edges=[[100,18],[150,66]]),'18':v('18',2,1,edges=[[500,34]]),'34':v('34',9,1,edges=[[5000,50]]),'50':v('50',11,1),'66':v('66',3,1,'SPG',edges=[[400,82]]),'82':v('82',8,1,'SPG')}
# Required module before the next tank; optional engine with excessive additional XP.
rows['18']['research_edges']=[[50,9876],[500,34,9876],[400,9877]]
rows['18']['compatible_modules']['engines'] += [9876,9877]
def ids(k):return {a:str(x['compactDescr']) for a,x in rows[k]['stock_modules'].items()}
def option(k,score,engine=None):
    md=ids(k)
    if engine is not None:md['engine']=str(engine)
    return dict(ids=md,fit=score,raw={'shots':[{'shell_id':501}],'gun':{'values':{'maxAmmo':10}}})
base={'1':20,'17':30,'33':70,'49':60,'2':40,'18':45,'34':90,'50':80,'66':55,'82':80}
scores={k:{sty:dict(score=x,stock=x,potential=x,coverage=100,categories=[x]*7,available_fields=('fixture',),configurations=[option(k,x)]) for sty in n['WEIGHTS'] if n['artillery'](rows[k])==(sty=='Artillery Support')} for k,x in base.items()}
for sty in scores['18']:
    scores['18'][sty]['configurations'] += [option('18',60,9876),option('18',75,9877)]
    scores['18'][sty]['potential']=75
# All combat destinations deliberately tier IX, except Brawler which favours another line.
for k in ('33','34'):
    x=95 if k=='33' else 55;scores[k]['Brawler'].update(potential=x,score=x,stock=x,configurations=[option(k,x)])
catdata={('vehicles',False):rows,('vehicles',True):{k:{'ammo_capacity':10,'slots':[] if rows[k]['level']==1 else [{'index':0}],'tags':['improvedVentilation_class3_user']} for k in rows},('guns',True):{ids(k)['gun']:{'shots':[{'shell_id':501,'speed':500}]} for k in rows},('guns',False):{ids(k)['gun']:{'shell_ids':[501]} for k in rows},('ammunition',False):{'501':{'default_buy':{'credits':20}}},('engines',False):{'9876':{'default_buy':{'credits':1000},'userName':'Required engine'},'9877':{'default_buy':{'credits':3000}}},('equipment',False):{'601':{'userName':'Optics','name':'coatedOptics_tier3','descriptor_fields':{'tags':['coatedOptics']},'vehicle_level_range':[2,11],'default_buy':{'credits':1000}},'602':{'userName':'Camo net','name':'camouflageNet_tier3','descriptor_fields':{'tags':['camouflageNet']},'vehicle_level_range':[2,11],'default_buy':{'credits':1000}},'603':{'userName':'Ventilation','name':'improvedVentilation_tier3','descriptor_fields':{'tags':['ventilation']},'vehicle_level_range':[2,11],'default_buy':{'credits':1000}},'604':{'userName':'Aiming drive','name':'enhancedAimDrives_tier3','descriptor_fields':{'tags':['enhancedAimDrives']},'vehicle_level_range':[2,11],'default_buy':{'credits':1000}},'605':{'userName':'Turbo','name':'turbocharger_tier3','descriptor_fields':{'tags':['turbocharger']},'vehicle_level_range':[2,11],'default_buy':{'credits':1000}}},('consumables',False):{str(701+i):{'userName':tag,'descriptor_fields':{'tags':[tag]},'default_buy':{'credits':3000}} for i,tag in enumerate(('repairkit','medkit','extinguisher'))}}
class Cat:
    identity='fixture-v2'
    def category(self,k,enriched=False):return catdata.get((k,enriched),{})
    def item(self,k,i,enriched=False):return self.category(k,enriched).get(str(i),{})
def tank(k):
    return {'intCD':int(k),'invID':int(k),'level':rows[k]['level'],'type':rows[k]['type'],'nationID':rows[k]['nationID'],'userName':rows[k]['userName'],'isLocked':False,'isRented':False,'isPremium':False,'combat_xp':0,'modules':{a:{'intCD':int(x)} for a,x in ids(k).items()},'optDevices':[],'crew_slots':[{'crew_id':11},{'crew_id':12}],'shells_layout':[{'intCD':501,'count':10}],'resale_price':{'credits':100}}
class Control:
    def __init__(self):self.text='';self.rows=[]
    def setText(self,s):self.text=s
    def setVisible(self,v):pass
    def currentRow(self):return -1
class FinanceFixture:
    def __getattr__(self,k):return fin[k]
    def sample(self,rows,premium=False):return {'n':5,'average':1000,'reserve':10000,'cost':1000,'high':1200,'low':800}
    def profiles(self,*args):return []
    def choose(self,*args):return None,''

def fixture(root):
    sec={'research':{'unlocked_item_ids':[1,2,17,18],'initial_unlocks':[1,2],'vehicle_xp':{'17':0,'18':0}},'garage':{},'account_extra':{'free_vehicle_slots':3,'free_barracks_slots':10,'vehicleSellsLeft':5},'current_shop_prices':{},'crew':{},'depot':{'SHELL':{'501':5},'ENGINE':{},'EQUIPMENT':{}},'depot_details':{'SHELL':{'501':{'count':5,'item':{'intCD':501,'sell':{'credits':10}}}}}}
    g=SimpleNamespace(catalogue=Cat(),section=lambda k:sec.get(k),status=lambda k:'ok',vehicles={})
    m=SimpleNamespace(root=root,state='garage',sources={'connector':{'session':'x','game_version':'v'},'battle_context':{'session':'x','account_key':'a'*24},'diagnostics':{'session':'x','game_version':'v','revision':1}},account={'credits':100000,'free_xp':0,'premium':False},selected={'tank_id':17,'combat_xp':0},garage=[tank('17')],garage_signature='fixture',garage_data=g)
    w=SimpleNamespace(model=m,settings=SimpleNamespace(values={'playstyle':STYLE,'advisor_mode':'Full Advisor','strategy':'F2P'}),runtime=SimpleNamespace(loaded={'finance':FinanceFixture()}),prog_tables={k:Control() for k in ('Overview','Career','Technology Trees','Vehicles','Research','Garage & Depot','Data Quality')},prog_stamp=None,prog_static=((g.catalogue.identity,None),n['graph'](rows),scores,{}),prog_note=Control(),prog_vehicle_note=Control(),next_action_title=Control(),next_action_detail=Control(),next_action_request=Control(),set_rows=lambda tb,rr:setattr(tb,'rows',rr),bp_rows=[])
    return w,sec

def run():
    assert n['ROUTE_WEIGHTS']==(60,25,15) and len(n['WEIGHTS'])==10
    assert n['percentile']([1,2,3],2)==50 and n['percentile']([1],1)==50
    assert all(sum(x)==100 for x in n['WEIGHTS'].values())
    # Unknown stats neutral, no invented zero.
    a=n['category_scores']({}, {},STYLE,rows['18']);assert a['score']==50 and a['coverage']==0
    assert n['cash']({'credits':100,'gold':'unknown'}) is None
    assert n['dependency_plan'](rows,'18','34',set(),{})==[dict(id='9876',xp=50,source='18',discount_known=True),dict(id='34',xp=500,source='18',discount_known=False)]
    with tempfile.TemporaryDirectory() as t:
        w,sec=fixture(Path(t));g=w.model.garage_data;tree=n['graph'](rows)
        known={'1','2','17','18'};owned={'17':tank('17')}
        choices,alts,sn=n['all_careers'](rows,tree,scores,owned,known,{'17':0},g,{},[],{},balance=100000,reserve=10000)
        assert len(choices)==10 and choices[STYLE]['destination']=='34' and choices[STYLE]['start']=='18'
        assert choices['Brawler']['destination']=='33' and choices['Artillery Support']['destination']=='82'
        assert all(r['destination']!='50' for r in choices.values())
        assert n['select_progression']([dict(end=90,rank=0,full_path=['1']),dict(end=80,rank=100,full_path=['2'])],None,{},set(),rows,tree,STYLE)['end']==90
        mod=n['module_plan'](rows,g,'18',STYLE,scores,known,{},'34');assert mod['config']['engine']=='9876' and mod['cost']==1000 and mod['extra_xp']==0,mod
        assert mod['optional_limit']==27 # 5% of mandatory 550 XP
        assert n['module_plan'](rows,g,'18',STYLE,scores,known,{},None)['config']['engine']=='9877'
        q=n['quote'](g,rows,'18',None,owned,[],{},STYLE,scores,known,choices[STYLE],choices,10000)
        assert q['purchase']==20000 and q['ammo']==100 and q['equipment']==1000 and q['consumables']==9000 and q['upgrade']==1000 and q['reserve']==10000 and q['planning_total']==41100 and not q['complete'],q
        inv=n['RouteInventory'](g);assert n['verified_depot'](inv,'SHELL','501')==5;inv.allocate('SHELL','501',5);assert n['verified_depot'](inv,'SHELL','501')==0 and n['verified_depot'](g,'SHELL','501')==5
        assert fin['forecast'](41099,q['planning_total']-q['reserve'],q['reserve'],{'n':5,'average':1000,'high':1000,'low':1000})['shortfall']==1
        assert fin['forecast'](41100,q['planning_total']-q['reserve'],q['reserve'],{'n':5,'average':1000,'high':1000,'low':1000})['shortfall']==0
        def refresh():
            w.prog_stamp=None;n['coordinate'](w,True);return w.next_action_title.text
        assert refresh()=='Review purchase of Tank 18',w.next_action_title.text
        assert w.prog_finance_target['preparation_cost']==31100 and w.prog_finance_target['planning_total']==41100
        w.model.account['credits']=41099;assert refresh()=='Earn credits',w.next_action_title.text
        w.model.account['credits']=41100;assert refresh()=='Review purchase of Tank 18'
        sec['account_extra']['free_vehicle_slots']=0;assert refresh()=='Free a garage slot';sec['account_extra']['free_vehicle_slots']=3
        # Purchase confirmed; after battle the planned required engine is ready to research.
        w.model.garage.append(tank('18'));w.model.selected={'tank_id':18,'combat_xp':50};sec['research']['unlocked_item_ids'].append(18);w.model.account['credits']=25000
        assert refresh()=='Research Required engine',w.next_action_title.text
        sec['research']['unlocked_item_ids'].append(9876);w.model.selected['combat_xp']=0
        assert refresh()=='Fit planned modules on Tank 18',w.next_action_title.text
        w.model.garage[-1]['modules']['engine']['intCD']=9876
        assert refresh()=='Play Tank 18',w.next_action_title.text
        w.model.selected['combat_xp']=500;assert refresh()=='Research Tank 34',w.next_action_title.text
        sec['research']['unlocked_item_ids'].append(34);assert refresh()=='Play Tank 18',w.next_action_title.text # save for next tank
        # Independent careers persist; style switching does not overwrite other routes.
        w.settings.values['playstyle']='Brawler';refresh();saved=n['load_state'](Path(t)/'progression'/'careers.json');assert len(saved['accounts']['a'*24]['careers'])==10 and saved['accounts']['a'*24]['careers'][STYLE]['destination']=='34'
        w.settings.values['playstyle']=STYLE;w.model.sources['diagnostics']['session']='stale';assert refresh()=='Waiting for live garage data'
    print('PASS: all ten careers, any-tier potential, research, optional cap, inventory reuse, full budget boundary, shared reserve, post-battle upgrade, persistence, stale-data gate')
    # Crew management: compatible experienced barracks members, later credit retraining, preserve protected source crew.
    with tempfile.TemporaryDirectory() as t:
        w,sec=fixture(Path(t));g=w.model.garage_data
        sec['crew']={'11':dict(invID=11,fullUserName='Experienced',nationID=1,role='commander',isDismissed=False,isInTank=False,native_vehicle_id=18,skills=[{'level':100}]),'12':dict(invID=12,nationID=1,role='driver',isDismissed=False,isInTank=True,vehicleInvID=18,native_vehicle_id=18,skills=[{'level':100}])}
        crew=n['crew_preparation'](g,rows,'34','18',{'18':tank('18')},{},['18']);assert crew['cost']==20000 and crew['lines'][0]['recovery_xp']==40000 and crew['lines'][1]['action']=='Recruit'
        low=n['crew_preparation'](g,rows,'18',None,{},{});assert low['cost']==0 and low['lines'][0]['action']=='Already trained'
        # Exact ID ammunition retention: a matching shell, loaded shell and obsolete shell.
        sec['depot']['SHELL'].update({'502':3,'503':7});sec['depot_details']['SHELL'].update({x:{'count':q,'item':{'intCD':int(x),'sell':{'credits':10}}} for x,q in [('502',3),('503',7)]})
        own={'17':tank('17')};own['17']['shells_layout'].append({'intCD':502,'count':1})
        ch,alt,snap=n['all_careers'](rows,n['graph'](rows),scores,own,{'1','2','17','18'},{'17':0},g,{},[],{})
        result,sales,complete,unknown=n['retention'](rows,n['graph'](rows),scores,{},g,own,set(rows),ch,alt,snap,[],['17'])
        assert complete and 'SHELL' not in unknown
        assert any(x['id']=='503' and x['count']==7 for x in sales),sales
        assert not any(x['id'] in ('501','502','17') for x in sales)
        g.status=lambda k:'partial' if k=='depot' else 'ok'
        assert not n['retention'](rows,n['graph'](rows),scores,{},g,own,set(rows),ch,alt,snap,[],['17'])[1]
    print('PASS: crew transfer and recovery, protected crew, obsolete ammunition, loaded ammunition, partial depot hold')
if __name__=='__main__':run()
