"""Synthetic verification of the independent battle module and compiled core integration."""
import os, sys, json, struct, hashlib, threading, io, time, tempfile, subprocess, shutil
from pathlib import Path
sys.path.insert(0,str(Path('desktop').resolve()))
from module_manager import validate_entry, checked_bytes, validate_modules, check_set
from module_manager_online import ModuleManager
PATH=Path('modules/battle_performance/0.1.0/battle_performance.qmodule')
MID='battle_performance'; VERSION='0.1.0'; TAG=MID+'-v'+VERSION
REPO='itsr0b0tninja/WoTQuartermaster'
CORE_SHA='58a8540078d6bf5df4b97f0bf667bb98a48dd023acbe3c7a62646c49097e0211'
def module_entry():
    raw=PATH.read_bytes()
    e=dict(version=VERSION,api=1,min_core='0.3.3',dependencies={},size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),release=TAG,asset=PATH.name,url=f'https://github.com/{REPO}/releases/download/{TAG}/{PATH.name}',channel='alpha',required=True)
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
def compiled():
    manifest=json.loads(Path('components.json').read_text(encoding='utf-8'))
    assert manifest['components']['desktop']['sha256']==CORE_SHA and manifest['components']['desktop']['version']=='0.3.3'
    offered,_=validate_modules(manifest); offered[MID]=module_entry(); check_set(offered,'0.3.3')
    with tempfile.TemporaryDirectory(prefix='qm-performance-') as tmp:
        base=Path(tmp); root=base/'data'; assets=base/'assets'; assets.mkdir()
        target=base/'WoTQuartermaster.exe'
        subprocess.check_call(['gh','release','download','v0.3.3','--repo',REPO,'--pattern','WoTQuartermaster.exe','--dir',str(base)])
        assert hashlib.sha256(target.read_bytes()).hexdigest()==CORE_SHA
        raw={offered[MID]['url']:PATH.read_bytes()}
        for mid,e in offered.items():
            if mid==MID: continue
            subprocess.check_call(['gh','release','download',e['release'],'--repo',REPO,'--pattern',e['asset'],'--dir',str(assets)])
            raw[e['url']]=(assets/e['asset']).read_bytes()
        synthetic(root)
        (base/'settings.ini').write_text('[Desktop]\nupdate_checks = no\ngame_path = '+str(base/'game')+'\n',encoding='utf-8')
        mm=ModuleManager(base); mm.start(); mm.offered_product='0.4.0'
        assert mm.stage(mm.plan(offered,[]),lambda url:io.BytesIO(raw[url]),threading.Event())
        g=mm.state['pending']
        env=dict(os.environ,QT_QPA_PLATFORM='offscreen',PYINSTALLER_RESET_ENVIRONMENT='1')
        proc=subprocess.Popen([str(target)],cwd=base,env=env)
        try:
            deadline=time.monotonic()+75
            while time.monotonic()<deadline:
                if proc.poll() is not None: raise RuntimeError('Compiled core exited')
                state=json.loads(mm.state_path.read_text())
                report=root/'performance'/'import_status.json'
                if state.get('active')==g and not state.get('trial') and not state.get('pending') and state.get('product_version')=='0.4.0' and report.exists(): break
                time.sleep(.5)
            else: raise RuntimeError('Module activation did not confirm')
            time.sleep(4)
            log=(base/'logs'/'desktop.log').read_text(encoding='utf-8',errors='replace')
            assert 'Loaded external module battle_performance 0.1.0' in log,log
            assert not any(x in log for x in ('Fatal desktop error','Module battle_performance unavailable','Module battle_performance callback failed','Module trial UI failed')),log
            assert hashlib.sha256(target.read_bytes()).hexdigest()==CORE_SHA
            assert proc.poll() is None
            print('Actual compiled v0.3.3 loaded Battle Performance, product 0.4.0, unchanged EXE',flush=True)
        finally:
            if proc.poll() is None:
                subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=20)
                proc.wait(timeout=20)
def publish():
    e=module_entry()
    manifest=Path('components.json'); data=json.loads(manifest.read_text(encoding='utf-8'))
    assert data['components']['desktop']['sha256']==CORE_SHA and data['components']['desktop']['version']=='0.3.3'
    prior=data['modules'].get(MID)
    if prior and prior!=e: raise RuntimeError('Existing module version differs')
    if subprocess.run(['gh','release','view',TAG,'--repo',REPO],capture_output=True).returncode:
        subprocess.check_call(['gh','release','create',TAG,'--repo',REPO,'--target',os.environ['GITHUB_SHA'],'--title','WoTQuartermaster 0.4.0 — Battle Performance module 0.1.0','--prerelease','--notes','Independent Battle Performance module: local replay reconciliation, battle history, ten playstyle profiles, per-vehicle, map and loadout statistics, personal baseline assessment, and information-only mode. Requires existing core 0.3.3. Early-exit results are recovered when an actual result arrives; pending battles remain visible. No core or Connector replacement.',str(PATH)])
    release=json.loads(subprocess.check_output(['gh','api',f'repos/{REPO}/releases/tags/{TAG}'],text=True,encoding='utf-8'))
    assert release['tag_name']==TAG and release['prerelease'] and not release['draft']
    asset=next(a for a in release['assets'] if a['name']==PATH.name)
    assert asset['digest']=='sha256:'+e['sha256'] and asset['size']==e['size'] and asset['browser_download_url']==e['url']
    data['modules'][MID]=e; data['product_version']='0.4.0'
    offered,_=validate_modules(data); check_set(offered,'0.3.3')
    manifest.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('Verified module asset; manifest product 0.4.0, core unchanged',flush=True)
if __name__=='__main__':
    e=module_entry()
    if '--publish' in sys.argv: publish()
    elif '--compiled' in sys.argv: compiled()
    else:
        with tempfile.TemporaryDirectory() as tmp: synthetic(Path(tmp)/'data')
