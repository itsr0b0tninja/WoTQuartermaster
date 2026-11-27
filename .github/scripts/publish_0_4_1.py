"""Synthetic verification of the independent battle module and compiled core integration."""
import os, sys, json, struct, hashlib, threading, io, time, tempfile, subprocess, shutil
from pathlib import Path
sys.path.insert(0,str(Path('desktop').resolve()))
from module_manager import validate_entry, checked_bytes, validate_modules, check_set
from module_manager_online import ModuleManager
PATH=Path('modules/battle_performance/0.1.1/battle_performance.qmodule')
MID='battle_performance'; VERSION='0.1.1'; TAG=MID+'-v'+VERSION
REPO='itsr0b0tninja/WoTQuartermaster'
CORE_SHA='58a8540078d6bf5df4b97f0bf667bb98a48dd023acbe3c7a62646c49097e0211'
def module_entry():
    raw=PATH.read_bytes()
    e=dict(version=VERSION,api=1,min_core='0.4.1',dependencies={},size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),release=TAG,asset=PATH.name,url=f'https://github.com/{REPO}/releases/download/{TAG}/{PATH.name}',channel='alpha',required=True)
    validate_entry(MID,e); checked_bytes(raw,MID,e)
    return e
def namespace():
    ns={'__file__':str(PATH)}
    exec(compile(PATH.read_bytes(),str(PATH),'exec'),ns)
    return ns
def synthetic(root):
    ns=namespace()
    hist=root/'history'; hist.mkdir(parents=True,exist_ok=True)
    replays=root.parent/'game'/'replays'; replays.mkdir(parents=True,exist_ok=True)
    account=ns['account_hash'](1234567)
    stats={'typeCompDescr':100,'team':1,'damageDealt':250,'damageReceived':100,'damageAssistedRadio':200,'damageAssistedTrack':20,'damageAssistedStun':0,'shots':10,'directHits':8,'piercings':6,'spotted':2,'kills':1,'deathCount':0,'lifeTime':300,'damageBlockedByArmor':40,'droppedCapturePoints':10,'originalXP':150,'credits':5000,'originalCredits':4000}
    common={'bonusType':1,'winnerTeam':1,'duration':300,'arenaTypeID':6,'arenaCreateTime':1700000000}
    result={'arenaUniqueID':11,'common':dict(common,bots=[]),'personal':{'100':stats}}
    meta={'playerID':1234567,'playerVehicle':'fixture_tank','mapName':'06_ensk'}
    def block(v):
        raw=json.dumps(v).encode(); return struct.pack('<I',len(raw))+raw
    raw=ns['MAGIC']+struct.pack('<I',2)+block(meta)+block([result])
    (replays/'complete.wotreplay').write_bytes(raw); (replays/'copied.wotreplay').write_bytes(raw)
    (replays/'unfinished.wotreplay').write_bytes(ns['MAGIC']+struct.pack('<I',1)+block(meta))
    record={'account_key':account,'battle_id':'11','data':ns['result_projection'](result),'mode':'random_pvp'}
    (hist/'battle_results.jsonl').write_text(json.dumps(record)+'\n'+json.dumps(record)+'\n',encoding='utf-8')
    pending={'account_key':account,'battle_id':'12','kind':'battle_start_candidate','avatar_vehicle_id':100,'recorded_at':1700001000,'configuration_status':'queue_vehicle_matched','configuration':{'configuration':{'intCD':100,'modules':{},'optDevices':[],'crew':{},'consumables':[]}}}
    (hist/'configurations.jsonl').write_text(json.dumps(pending)+'\n',encoding='utf-8')
    (hist/'account_events.jsonl').write_text(json.dumps({'account_key':account})+'\n',encoding='utf-8')
    observed={account+':11':{'account_key':account,'battle_id':'11','vehicle_id':100,'style':'Hybrid Scout','recorded_at':1700000000},account+':12':{'account_key':account,'battle_id':'12','vehicle_id':100,'style':'Brawler','recorded_at':1700001000}}
    ns['atomic_record'](root/'performance'/'observed.json',{'schema':1,'records':observed})
    battles,report=ns['scan_performance'](root,replays,observed)
    assert len(battles)==2 and report['new_replays']==1 and report['incomplete_or_unsupported']==1
    a=ns['project'](battles[account+':11']); b=ns['project'](battles[account+':12'])
    assert a['eligible'] and a['status']=='linked' and a['style']=='Hybrid Scout' and a['stats']['combined']==470 and a['stats']['win']==1
    assert b['status']=='awaiting_result' and not b['eligible'] and b['stats']['damage'] is None
    assert ns['mean']([a,b],'damage')==(250,1)
    assert ns['aggregate']([a,b],'accuracy')==(.8,1)
    assert ns['assessment']([a,b],'Hybrid Scout')[2] is None
    samples=[dict(a,at=1700000000+i,stats=dict(a['stats'],damage=250 if i<20 else 500,radio=200 if i<20 else 400)) for i in range(40)]
    n,metrics,score=ns['assessment'](samples,'Hybrid Scout')
    assert n==40 and score==160 and len(metrics)==5
    assert len(ns['STYLES'])==10 and all(sum(w.values())==100 for w in ns['STYLES'].values())
    assert ns['style_name']('Support')=='Fire Support'
    # A result arriving later resolves exactly the previously observed battle.
    late=dict(record,battle_id='12',mode='ai_or_mixed',data=dict(record['data'],bots_present=True))
    with (hist/'battle_results.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(late)+'\n')
    battles,report=ns['scan_performance'](root,replays,observed)
    assert len(battles)==2 and ns['project'](battles[account+':12'])['mode']=='ai_or_mixed'
    assert ns['project'](battles[account+':12'])['style']=='Brawler'
    assert report['new_replays']==0
    # No source files modified; conflict explicitly excludes affected battle.
    bad=json.loads(json.dumps(record)); bad['data']['personal']['100']['damageDealt']=999
    with (hist/'battle_results.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(bad)+'\n')
    battles,report=ns['scan_performance'](root,replays,observed)
    assert not ns['project'](battles[account+':11'])['eligible']
    assert (replays/'complete.wotreplay').read_bytes()==raw
    print('Replay deduplication, incomplete retries, delayed results, conflicts, missing fields, mode separation, ten styles and formulas passed',flush=True)

def core_module():
    import importlib.machinery, importlib.util
    loader=importlib.machinery.SourceFileLoader('qm_041','desktop/WoTQuartermaster_v0.4.1.txt')
    spec=importlib.util.spec_from_loader(loader.name,loader); module=importlib.util.module_from_spec(spec); loader.exec_module(module)
    return module
def assets_for(base):
    manifest=json.loads(Path('components.json').read_text(encoding='utf-8'))
    assert manifest['components']['desktop']['sha256']==CORE_SHA
    offered,_=validate_modules(manifest); raw={}; assets=base/'assets'; assets.mkdir()
    for mid,e in offered.items():
        subprocess.check_call(['gh','release','download',e['release'],'--repo',REPO,'--pattern',e['asset'],'--dir',str(assets)])
        raw[e['url']]=(assets/e['asset']).read_bytes()
    prior=dict(offered); offered[MID]=module_entry(); raw[offered[MID]['url']]=PATH.read_bytes()
    check_set(offered,'0.4.1')
    return prior,offered,raw
def stage_set(base,offered,raw,core):
    mm=ModuleManager(base,core); mm.start(); mm.offered_product='0.4.1' if core=='0.4.1' else '0.4.0'
    assert mm.stage(mm.plan(offered,[]),lambda url:io.BytesIO(raw[url]),threading.Event())
    return mm.state['pending']
def fixture_settings(base):
    root=base/'data'; synthetic(root)
    legacy={'default':'Brawler','overrides':{'100':'Active Scout'},'temporary':{'vehicle':'100','style':'Flanker'},'advisor':'Information Only'}
    (root/'performance'/'preferences.json').write_text(json.dumps(legacy),encoding='utf-8')
    (base/'settings.ini').write_text('[Desktop]\nplaystyle = Passive scout\nupdate_checks = no\ngame_path = '+str(base/'game')+'\n',encoding='utf-8')
    return root
def ui():
    core=core_module(); ns=namespace()
    assert set(core.PLAYSTYLES)==set(ns['STYLES'])
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp); root=fixture_settings(base); prior,offered,raw=assets_for(base)
        stage_set(base,offered,raw,'0.4.1')
        orig=(root/'performance'/'observed.json').read_bytes()
        os.environ['QT_QPA_PLATFORM']='offscreen'
        def exercise(w):
            assert w.runtime.ready(),w.runtime.errors
            assert w.settings.values['playstyle']=='Brawler'
            assert w.settings.values['advisor_mode']=='Information Only'
            assert w.over_play_combo.count()==w.play_combo.count()==10
            assert w.over_play_combo.currentText()==w.play_combo.currentText()=='Brawler'
            w.over_play_combo.setCurrentText('Passive Scout'); w.over_play_combo.activated.emit(w.over_play_combo.currentIndex())
            assert w.play_combo.currentText()=='Passive Scout'
            assert core.Settings(base).values['playstyle']=='Passive Scout'
            w.play_combo.setCurrentText('Concealed Sniper'); w.play_combo.activated.emit(w.play_combo.currentIndex())
            assert w.over_play_combo.currentText()=='Concealed Sniper'
            assert core.Settings(base).values['playstyle']=='Concealed Sniper'
            assert 'Concealed Sniper' in w.atlas_style_label.text()
            w.navigate('History')
            assert w.nav['History'].text()=='Performance'
            assert 'Playstyles' in w.bp_tables and not hasattr(w,'bp_override') and not hasattr(w,'bp_default')
            assert w.bp_tables['Playstyles'].rowCount()==11
            assert w.settings.values['playstyle']=='Concealed Sniper'
            w.bp_style.setCurrentText('Brawler')
            assert w.settings.values['playstyle']=='Concealed Sniper'
            assert (root/'performance'/'observed.json').read_bytes()==orig
            module=w.runtime.loaded[MID]
            account=module.account_hash(1234567)
            w.model.state='matchmaking'; module.refresh_bp(w); w.sync_playstyle_controls()
            assert not w.over_play_combo.isEnabled() and not w.play_combo.isEnabled()
            w.model.state='battle_loading'; w.model.context={'account_key':account,'battle_id':'13','vehicle_id':100,'map_id':6}
            module.refresh_bp(w)
            assert w.bp_observed[account+':13']['style']=='Concealed Sniper'
            w.model.state='garage'; w.model.context=None; module.refresh_bp(w)
            w.sync_playstyle_controls()
            assert w.over_play_combo.isEnabled()
            w.over_play_combo.setCurrentText('Artillery Support'); w.over_play_combo.activated.emit(w.over_play_combo.currentIndex())
            assert w.bp_observed[account+':13']['style']=='Concealed Sniper'
            assert w.bp_observed[account+':11']['style']=='Hybrid Scout'
            assert core.Settings(base).values['playstyle']=='Artillery Support'
            w.navigate('Garage'); w.navigate('Map atlas')
            assert w.runtime.ready(),w.runtime.errors
        assert core.run_gui(base,test_callback=exercise)==0
        assert core.Settings(base).values['playstyle']=='Artillery Support'
        print('Linked Overview/Settings, legacy migration, persisted choice, historical filtering, battle snapshot, atlas and garage passed',flush=True)
def compiled():
    with tempfile.TemporaryDirectory(prefix='qm-041-') as tmp:
        base=Path(tmp); root=fixture_settings(base); prior,offered,raw=assets_for(base)
        # Exercise actual old core -> new core using the existing replacement helper.
        old=base/'old'; old.mkdir()
        subprocess.check_call(['gh','release','download','v0.3.3','--repo',REPO,'--pattern','WoTQuartermaster.exe','--dir',str(old)])
        target=base/'WoTQuartermaster.exe'; shutil.copyfile(old/target.name,target)
        assert hashlib.sha256(target.read_bytes()).hexdigest()==CORE_SHA
        g=stage_set(base,prior,raw,'0.3.3')
        mm=ModuleManager(base,'0.3.3'); assert mm.start().ready(); mm.confirm()
        assert mm.state['active']==g
        env=dict(os.environ,QT_QPA_PLATFORM='offscreen',PYINSTALLER_RESET_ENVIRONMENT='1')
        updates=base/'updates'; staging=updates/'staging'; staging.mkdir(parents=True)
        import secrets
        token=secrets.token_hex(16); runner=updates/('runner-'+token+'.exe')
        shutil.copyfile(target,runner); payload=Path('dist/WoTQuartermaster.exe').resolve()
        shutil.copyfile(payload,staging/target.name)
        parent=subprocess.Popen([sys.executable,'-c','import time; time.sleep(4)'])
        request=dict(token=token,parent=parent.pid,old_version='0.3.3',version='0.4.1',size=payload.stat().st_size,sha256=hashlib.sha256(payload.read_bytes()).hexdigest())
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
        new_generation=stage_set(base,offered,raw,'0.4.1')
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
            assert 'Loaded external module battle_performance 0.1.1' in log,log
            assert not any(x in log for x in ('Fatal desktop error','Module battle_performance unavailable','Module battle_performance callback failed','Module trial UI failed')),log
            assert 'playstyle = Brawler' in (base/'settings.ini').read_text()
            assert (root/'performance'/'observed.json').exists()
            assert proc.poll() is None
            print('Compiled core replacement and new module activation passed',flush=True)
        finally:
            stop()
            if proc.poll() is None: proc.wait(timeout=20)
def publish():
    e=module_entry()
    data=json.loads(Path('components.json').read_text(encoding='utf-8'))
    assert data['components']['desktop']['sha256']==CORE_SHA
    for tag,title,notes,paths in [
        (TAG,'Battle Performance module v0.1.1','Historical playstyle comparison and unified active playstyle capture. Requires core 0.4.1.',[str(PATH)]),
        ('v0.4.1','WoTQuartermaster v0.4.1 Alpha','One persistent active playstyle shared by Overview and Settings; read-only performance history. Update core and Battle Performance module.', ['dist/WoTQuartermaster.exe','dist/WoTQuartermaster.sha256.txt'])]:
        if subprocess.run(['gh','release','view',tag,'--repo',REPO],capture_output=True).returncode:
            subprocess.check_call(['gh','release','create',tag,'--repo',REPO,'--target',os.environ['GITHUB_SHA'],'--title',title,'--prerelease','--notes',notes,*paths])
    def verify(tag,name,path):
        r=json.loads(subprocess.check_output(['gh','api',f'repos/{REPO}/releases/tags/{tag}'],text=True,encoding='utf-8'))
        assert r['tag_name']==tag and r['prerelease'] and not r['draft']
        a=next(x for x in r['assets'] if x['name']==name); raw=Path(path).read_bytes()
        assert a['digest']=='sha256:'+hashlib.sha256(raw).hexdigest() and a['size']==len(raw)
        assert a['browser_download_url']==f'https://github.com/{REPO}/releases/download/{tag}/{name}'
        return a
    verify(TAG,PATH.name,PATH)
    exe=verify('v0.4.1','WoTQuartermaster.exe','dist/WoTQuartermaster.exe')
    data['modules'][MID]=e
    data['components']['desktop']=dict(version='0.4.1',release='v0.4.1',asset=exe['name'],url=exe['browser_download_url'],sha256=exe['digest'][7:],size=exe['size'],channel='alpha',min_desktop='0.2.0')
    data['product_version']='0.4.1'
    offered,_=validate_modules(data); check_set(offered,'0.4.1')
    Path('components.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('Both releases verified; manifest updated',flush=True)
if __name__=='__main__':
    module_entry()
    if '--publish' in sys.argv: publish()
    elif '--compiled' in sys.argv: compiled()
    elif '--ui' in sys.argv: ui()
    else:
        with tempfile.TemporaryDirectory() as tmp: synthetic(Path(tmp)/'data')
