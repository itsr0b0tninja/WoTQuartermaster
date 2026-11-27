"""Verify progression source, UI, module sets, compiled upgrade and gated publication."""
import os,sys,json,hashlib,threading,io,time,tempfile,subprocess,shutil,importlib.machinery,importlib.util
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path('desktop').resolve()))
from module_manager import validate_entry,checked_bytes,validate_modules,check_set
from module_manager_online import ModuleManager
import publish_0_5_0 as old
REPO='itsr0b0tninja/WoTQuartermaster'
CORE_SHA='3a85c336c1ad41694256fe65c6559d2fbc5e11e8db9571d5719a622d9a7ed4cc'
VERSIONS={'battle_performance':'0.1.3','finance':'0.1.1','research':'0.1.1','progression':'0.1.0'}
DEPS={'battle_performance':{},'finance':{'battle_performance':'0.1.3'},'research':{},'progression':{'research':'0.1.1','finance':'0.1.1','battle_performance':'0.1.3'}}
def module_path(mid): return Path('modules')/mid/VERSIONS[mid]/(mid+'.qmodule')
def entry(mid):
    p=module_path(mid); raw=p.read_bytes(); tag=mid+'-v'+VERSIONS[mid]
    e=dict(version=VERSIONS[mid],api=1,min_core='0.6.0',dependencies=DEPS[mid],size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),release=tag,asset=p.name,url=f'https://github.com/{REPO}/releases/download/{tag}/{p.name}',channel='alpha',required=True)
    validate_entry(mid,e); checked_bytes(raw,mid,e); return e
def namespace(mid):
    p=module_path(mid); n={'__file__':str(p)}; exec(compile(p.read_bytes(),str(p),'exec'),n); return n
def vehicle(k,t,kind='lightTank',next_=None,params=None):
    p={'circularVisionRadius':[320+t*10],'invisibilityStillFactor':{'current':20,'atShot':5},'invisibilityMovingFactor':{'current':18,'atShot':4},'enginePowerPerTon':[20+t],'speedLimits':[60,20],'chassisRotationSpeed':40,'avgDamagePerMinute':1000+t*100,'avgPiercingPower':50+t*20,'avgDamage':30+t*20,'shotDispersionAngle':[.4],'aimingTime':[2.1],'maxHealth':200+t*100,'hullArmor':[20,15,10],'turretArmor':[25,15,10],'pitchLimits':[-8,15],'turretRotationSpeed':[40]}
    p.update(params or {})
    return dict(intCD=int(k),userName='Tank '+k,level=t,nationID=0,type=kind,isPremium=False,isSecret=False,isCollectible=False,default_buy={'credits':10000*t},stock_parameters=p,stock_modules={'gun':{'compactDescr':4}},vehicle_type={'crewRoles':[['commander']]},research_edges=next_ or [])
def fixture():
    rows={'1':vehicle('1',1,next_=[[100,17,2],[50,2]]),'17':vehicle('17',2,next_=[[200,33,2]]),'33':vehicle('33',5,next_=[[1000,49]]),'49':vehicle('49',7)}
    rows['65']=dict(vehicle('65',5),isPremium=True)
    own=old.tank('1',1); own.update(nationID=0,isElite=False,isPremium=False,combat_xp=0)
    own['userName']='Tank 1'
    section={'garage':{},'research':{'unlocked_item_ids':[1],'initial_unlocks':[1],'vehicle_xp':{'1':0}},'progression':{'owned_vehicle_paths':{'1':{'vehicle_id':1,'edges':[{'target_id':17,'xp_raw':100,'target':{'blueprint_adjusted_xp':80,'buy':{'credits':20000}}}]}}},'crew':{},'account_extra':{'free_vehicle_slots':3},'depot':{'SHELL':{'10':5}},'current_shop_prices':{'prices':{'10':{'credits':20}}},'configured_performance':{}}
    cats={('vehicles',False):rows,('vehicles',True):{k:{'ammo_capacity':20} for k in rows},('guns',True):{'4':{'shots':[{'shell_id':10,'speed':500,'defaultPortion':.95}]}},('ammunition',False):{'10':{'default_buy':{'credits':20}}}}
    class Cat:
        identity='fixture'
        def category(self,k,enriched=False):return cats.get((k,enriched),{})
        def item(self,k,i,enriched=False):return self.category(k,enriched).get(str(i),{})
    g=SimpleNamespace(catalogue=Cat(),section=lambda k:section.get(k),status=lambda k:'ok',vehicles={'1':own})
    return rows,own,section,g
def progression_tests():
    n=namespace('progression'); rows,own,s,g=fixture()
    tree=n['graph'](rows); assert set(tree)=={'1','17','33','49'} and tree['1']==['17']
    assert len(n['WEIGHTS'])==10 and all(sum(w)==100 for w in n['WEIGHTS'].values())
    assert n['percentile']([1,2,3],2)==50 and n['percentile']([1,1,1],1)==50
    scores,refs=n['catalogue_scores'](rows,tree,g.catalogue.category('guns',True))
    assert all(0<=v['score']<=100 for x in scores.values() for v in x.values() if v['score'] is not None)
    live=n['live_edges'](g); plan=n['dependency_plan'](rows,'1','17',{'1'},live)
    assert [x['id'] for x in plan]==['2','17'] and sum(x['xp'] for x in plan)==130,plan
    assert sum(x['xp'] for x in n['dependency_plan'](rows,'1','17',{'1','2'},live))==80
    assert n['dependency_plan'](rows,'1','17',{'1','17'},live)==[]
    assert n['dependency_plan'](rows,'1','999',{'1'},live) is None
    candidates=n['route_candidates'](rows,tree,scores,'Hybrid Scout',{'1':own},{'1','33'},{'1':100},g,live,[])
    assert any(x['start']=='33' for x in candidates),candidates
    assert all(x['destination']!='65' for x in candidates)
    assert n['select_route']([{'rank':80,'destination':'49','path':['33','49'],'start':'33'},{'rank':78,'destination':'33','path':['1','33'],'start':'1'}],{'destination':'33','path':['1','33']},{},{})['destination']=='33'
    assert n['grind'](10000,0,220000,500,5000,12000)==dict(xp_battles=20,remaining=120000,stay=44,switch=30)
    assert n['grind'](10000,0,220000,500,-1000,12000)['switch']==40
    assert n['grind'](0,50000,40000,None,None,None)['stay']==0
    assert n['grind'](100,0,None,100,500,None)['stay'] is None
    q=n['quote'](g,rows,'17','1',{'1':own},[],live)
    assert q['purchase']==20000 and q['ammo']==300 and q['reserve'] is None and not q['complete'],q
    account='a'*24
    rr=[dict(old.fixture_row({},'1',i=i),personal={'originalXP':200,'xp':900}) for i in range(8)]
    rr+=[dict(old.fixture_row({},'1',mode='ai_or_mixed',i=i),personal={'originalXP':9000}) for i in range(10)]
    assert n['xp_profile'](rr,account,'1','random_pvp','Hybrid Scout',False)['average']==200
    assert n['xp_profile'](rr,account,'1','random_pvp','Hybrid Scout',True)['average']==300
    assert n['xp_profile'](rr[:4],account,'1','random_pvp','Hybrid Scout',False)['average'] is None
    assert n['discovery'](rr,account,'random_pvp','Hybrid Scout',{'1':own},scores) is None
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'progression'/'careers.json'; data={'schema':1,'accounts':{account:{'careers':{'Hybrid Scout':{'path':['1','17']},'Brawler':{'path':['33']}}}}}
        n['save_state'](path,data); assert n['load_state'](path)==data
        path.write_text('{broken'); assert n['load_state'](path)=={'schema':1,'accounts':{}}
    print('Progression graph, weights, prerequisites, unlocked career starts, stability, combined grind, reserve uncertainty, ammo cost, XP modes, optional history and persistence passed',flush=True)
def core_module():
    loader=importlib.machinery.SourceFileLoader('qm_060','desktop/WoTQuartermaster_v0.6.0.txt')
    spec=importlib.util.spec_from_loader(loader.name,loader); module=importlib.util.module_from_spec(spec); loader.exec_module(module); return module
def assets_for(base):
    data=json.loads(Path('components.json').read_text(encoding='utf-8'))
    assert data['components']['desktop']['sha256']==CORE_SHA
    prior,_=validate_modules(data); raw={}; assets=base/'assets'; assets.mkdir()
    for mid,e in prior.items():
        subprocess.check_call(['gh','release','download',e['release'],'--repo',REPO,'--pattern',e['asset'],'--dir',str(assets)])
        raw[e['url']]=(assets/e['asset']).read_bytes()
    offered=dict(prior)
    for mid in VERSIONS:
        e=entry(mid); offered[mid]=e; raw[e['url']]=module_path(mid).read_bytes()
    check_set(offered,'0.6.0')
    return prior,offered,raw
def stage_set(base,offered,raw,core):
    mm=ModuleManager(base,core); mm.start(); mm.offered_product=core
    assert mm.stage(mm.plan(offered,[]),lambda url:io.BytesIO(raw[url]),threading.Event())
    return mm.state['pending']
def fixture_settings(base): return old.fixture_settings(base)
def ui():
    core=core_module()
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp); root=fixture_settings(base); prior,offered,raw=assets_for(base)
        stage_set(base,offered,raw,'0.6.0')
        os.environ['QT_QPA_PLATFORM']='offscreen'
        def exercise(w):
            assert w.runtime.ready(),w.runtime.errors
            assert w.over_play_combo.count()==11 and w.play_combo.count()==11
            assert set(w.prog_tables)=={'Overview','Career','Technology Trees','Vehicles','Research'}
            assert set(w.fin_tables)=={'Overview','Vehicles','Transactions','Forecast'}
            assert w.next_action_title.text()=='Waiting for live garage data'
            for page in ('Garage','Depot','Finance','Progression','Map atlas','History','Overview'): w.navigate(page)
            assert w.runtime.ready(),w.runtime.errors
            # Inject a synthetic coherent snapshot; no actual game or account required.
            rows,own,section,g=fixture(); real=w.model; account='a'*24
            w.model=SimpleNamespace(root=root,state='garage',sources={'connector':{'session':'x','game_version':'v'},'battle_context':{'session':'x','account_key':account},'diagnostics':{'session':'x','game_version':'v'}},account={'credits':50000,'free_xp':500,'premium':False},selected={'tank_id':1,'combat_xp':0},garage=[own],garage_signature='fixture',garage_data=g,context=None)
            w.bp_rows=[]
            try:
                w.settings.values['playstyle']='Hybrid Scout'
                w.coordinate_advice(True)
                assert w.next_action_title.text()=='Play Tank 1',w.next_action_title.text()
                assert w.prog_tables['Career'].rowCount()>=2
                assert w.prog_tables['Research'].rowCount()==2
                assert w.prog_tables['Vehicles'].rowCount()>=4
                assert w.prog_finance_target['id']=='17'
                f=w.runtime.loaded['finance']; f.refresh_finance(w,True)
                assert w.next_action_title.text()=='Play Tank 1'
                w.model.selected['combat_xp']=50; w.coordinate_advice(True)
                assert w.next_action_title.text()=='Research Vehicle 2',w.next_action_title.text()
                section['research']['unlocked_item_ids']=[1,2,17]; w.coordinate_advice(True)
                assert w.next_action_title.text()=='Review purchase of Tank 17',w.next_action_title.text()
                w.settings.values['advisor_mode']='Information Only'; w.coordinate_advice(True)
                assert w.next_action_title.text()=='Information only'
                w.settings.values['advisor_mode']='Full Advisor'
                w.settings.values['playstyle']='Brawler'; section['research']['unlocked_item_ids']=[1,2,17,33,49]
                w.coordinate_advice(True)
                data=json.loads((root/'progression'/'careers.json').read_text())
                assert {'Hybrid Scout','Brawler'}<=set(data['accounts'][account]['careers'])
                w.settings.values['playstyle']='Profit'; f.refresh_finance(w,True); w.coordinate_advice(True)
                assert 'Tank 1' in w.next_action_title.text(),w.next_action_title.text()
                assert json.loads((root/'progression'/'careers.json').read_text())==data
                w.settings.values['playstyle']='Hybrid Scout'; w.model.sources['diagnostics']['session']='stale'
                w.coordinate_advice(True); assert w.next_action_title.text()=='Waiting for live garage data'
            finally:
                w.model=real; w.settings.values['playstyle']='Passive Scout'; w.settings.save()
            assert w.runtime.ready(),w.runtime.errors
        assert core.run_gui(base,test_callback=exercise)==0
    print('Five Progression tabs, legacy navigation, single action, research transition, purchase estimate, account gating, separate careers and Profit passed',flush=True)
def compiled():
    with tempfile.TemporaryDirectory(prefix='qm-050-') as tmp:
        base=Path(tmp); root=fixture_settings(base); prior,offered,raw=assets_for(base)
        # Exercise actual old core -> new core using the existing replacement helper.
        old=base/'old'; old.mkdir()
        subprocess.check_call(['gh','release','download','v0.5.0','--repo',REPO,'--pattern','WoTQuartermaster.exe','--dir',str(old)])
        target=base/'WoTQuartermaster.exe'; shutil.copyfile(old/target.name,target)
        assert hashlib.sha256(target.read_bytes()).hexdigest()==CORE_SHA
        g=stage_set(base,prior,raw,'0.5.0')
        mm=ModuleManager(base,'0.5.0'); assert mm.start().ready(); mm.confirm()
        assert mm.state['active']==g
        env=dict(os.environ,QT_QPA_PLATFORM='offscreen',PYINSTALLER_RESET_ENVIRONMENT='1')
        updates=base/'updates'; staging=updates/'staging'; staging.mkdir(parents=True)
        import secrets
        token=secrets.token_hex(16); runner=updates/('runner-'+token+'.exe')
        shutil.copyfile(target,runner); payload=Path('dist/WoTQuartermaster.exe').resolve()
        shutil.copyfile(payload,staging/target.name)
        parent=subprocess.Popen([sys.executable,'-c','import time; time.sleep(4)'])
        request=dict(token=token,parent=parent.pid,old_version='0.5.0',version='0.6.0',size=payload.stat().st_size,sha256=hashlib.sha256(payload.read_bytes()).hexdigest())
        (updates/('request-'+token+'.json')).write_text(json.dumps(request))
        helper=subprocess.Popen([str(runner),'--apply-update',token,str(parent.pid)],cwd=base,env=env)
        def stop():
            subprocess.run(['taskkill','/IM','WoTQuartermaster.exe','/T','/F'],capture_output=True,timeout=20)
            time.sleep(2)
        try:
            parent.wait(timeout=15)
            assert helper.wait(timeout=145)==0
            assert json.loads((updates/'update-result.json').read_text())['status']=='success'
            assert hashlib.sha256(target.read_bytes()).hexdigest()==request['sha256']
            assert hashlib.sha256((updates/'backups'/'WoTQuartermaster.previous.exe').read_bytes()).hexdigest()==CORE_SHA
        finally:
            if helper.poll() is None: helper.kill(); helper.wait(timeout=10)
            stop()
        (updates/'desktop.lock').unlink(missing_ok=True)
        new_generation=stage_set(base,offered,raw,'0.6.0')
        proc=subprocess.Popen([str(target)],cwd=base,env=env)
        try:
            deadline=time.monotonic()+75
            state=base/'modules'/'module-state.json'
            while time.monotonic()<deadline:
                assert proc.poll() is None
                st=json.loads(state.read_text())
                if st.get('active')==new_generation and not st.get('trial') and not st.get('pending'): break
                time.sleep(.5)
            else: raise RuntimeError('New module did not activate')
            time.sleep(4)
            log=(base/'logs'/'desktop.log').read_text(encoding='utf-8',errors='replace')
            assert 'Loaded external module battle_performance 0.1.3' in log,log
            assert 'Loaded external module finance 0.1.1' in log,log
            assert 'Loaded external module progression 0.1.0' in log,log
            assert 'Loaded external module research 0.1.1' in log,log
            assert 'Module progression callback failed' not in log and 'Module progression unavailable' not in log,log
            assert not any(x in log for x in ('Module finance unavailable','Module finance callback failed','Fatal desktop error','Module battle_performance unavailable','Module battle_performance callback failed','Module trial UI failed')),log
            assert 'playstyle = Passive Scout' in (base/'settings.ini').read_text()
            assert (root/'performance'/'observed.json').exists()
            assert proc.poll() is None
            print('Compiled core replacement and new module activation passed',flush=True)
        finally:
            stop()
            if proc.poll() is None: proc.wait(timeout=20)


def publish():
    data=json.loads(Path('components.json').read_text(encoding='utf-8'))
    assert data['components']['desktop']['sha256']==CORE_SHA
    def release(tag,title,notes,paths):
        if subprocess.run(['gh','release','view',tag,'--repo',REPO],capture_output=True).returncode:
            subprocess.check_call(['gh','release','create',tag,'--repo',REPO,'--target',os.environ['GITHUB_SHA'],'--title',title,'--prerelease','--notes',notes,*map(str,paths)])
    def verify(tag,path):
        r=json.loads(subprocess.check_output(['gh','api',f'repos/{REPO}/releases/tags/{tag}'],text=True,encoding='utf-8'))
        assert r['tag_name']==tag and r['prerelease'] and not r['draft']
        a=next(x for x in r['assets'] if x['name']==Path(path).name); raw=Path(path).read_bytes()
        assert a['digest']=='sha256:'+hashlib.sha256(raw).hexdigest() and a['size']==len(raw)
        assert a['browser_download_url']==f'https://github.com/{REPO}/releases/download/{tag}/{Path(path).name}'
        return a
    notes={'progression':'Stock and configured suitability, national research graph, persistent careers, required research, optional Free XP, combined grind forecasts and preliminary playstyle discovery. Exact acquisition quotes and hypothetical configurations remain incomplete.','finance':'Career target integration and shared recommendation handling. Partial stocking and reserve estimates.','battle_performance':'Mileage projection and retained battle intent.','research':'Research services retained; Progression page moved to new module.'}
    for mid in VERSIONS:
        e=entry(mid); p=module_path(mid); release(e['release'],mid.capitalize()+' '+e['version'],notes[mid],[p]); verify(e['release'],p); data['modules'][mid]=e
    tag='v0.6.0'; exe='dist/WoTQuartermaster.exe'
    release(tag,'WoTQuartermaster v0.6.0 Alpha','Progression Advisor alpha. Install the desktop and all four module updates. Connector 0.0.8 retained. Acquisition costs and missing data clearly provisional; additional verification in 0.6.x.',['dist/WoTQuartermaster.exe','dist/WoTQuartermaster.sha256.txt'])
    a=verify(tag,exe); verify(tag,'dist/WoTQuartermaster.sha256.txt')
    data['components']['desktop']=dict(version='0.6.0',release=tag,asset=a['name'],url=a['browser_download_url'],sha256=a['digest'][7:],size=a['size'],channel='alpha',min_desktop='0.2.0')
    data['product_version']='0.6.0'; offered,_=validate_modules(data); check_set(offered,'0.6.0')
    Path('components.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('Verified all five release assets and manifest',flush=True)
if __name__=='__main__':
    for mid in VERSIONS: entry(mid)
    if '--ui' in sys.argv: ui()
    elif '--compiled' in sys.argv: compiled()
    elif '--publish' in sys.argv: publish()
    else:
        # Exercise the new modules using the previous proven regression fixtures.
        old.PATH=module_path('battle_performance'); old.FIN=module_path('finance')
        with tempfile.TemporaryDirectory() as tmp: old.synthetic(Path(tmp)/'data')
        old.finances(); progression_tests()
