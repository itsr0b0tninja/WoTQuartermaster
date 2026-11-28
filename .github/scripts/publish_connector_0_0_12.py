import hashlib,json,subprocess
from pathlib import Path
REPO='itsr0b0tninja/WoTQuartermaster'
def run(*args):return subprocess.check_output(args,text=True).strip()
def release(tag,title,notes,paths):
    # Do not silently replace an already published binary.
    proc=subprocess.run(['gh','release','view',tag,'--repo',REPO],capture_output=True)
    if proc.returncode:
        subprocess.check_call(['gh','release','create',tag,'--repo',REPO,'--target',run('git','rev-parse','HEAD'),'--title',title,'--notes',notes,'--prerelease',*map(str,paths)])
    r=json.loads(run('gh','api','repos/'+REPO+'/releases/tags/'+tag));assert r['tag_name']==tag and r['prerelease'] and not r['draft'];assets=r['assets']
    p=paths[0]; a=next(x for x in assets if x['name']==p.name)
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    assert a['size']==p.stat().st_size and a.get('digest')=='sha256:'+digest,(tag,'published asset mismatch')
    return dict(version=tag.split('-v')[-1] if '-v' in tag else tag[1:],release=tag,asset=p.name,url=a['browser_download_url'],size=a['size'],sha256=digest,channel='alpha')
p=Path('components.json'); d=json.loads(p.read_text(encoding='utf-8'))
assert d['product_version']=='0.6.8'
assert d['components']['desktop']['version'] in ('0.6.5','0.6.6')
assert d['components']['connector']['version'] in ('0.0.11','0.0.12')
assert d['modules']['progression']['version']=='0.1.7'
old_modules=d['modules'].copy()
connector=release('connector-v0.0.12','WoTQuartermaster Connector v0.0.12','Targeted native vehicle mechanics, default ammunition, and account slot and crew cost observations. Preserves matching supplementary audit. Live data validation remains required. Close the game before replacing the mod; preserve connector.ini.',[Path('connector-assets/wot_companion_connector.wotmod'),Path('connector-assets/connector.ini'),Path('connector-assets/wot_companion_connector.sha256.txt')])
core=release('v0.6.6','WoTQuartermaster Core v0.6.6 (connector compatibility)','Compatibility-only core update accepting connector 0.0.12 and prior supported versions. Existing advisor modules retained.',[Path('core-assets/WoTQuartermaster.exe'),Path('core-assets/WoTQuartermaster.sha256.txt')])
connector.update(min_desktop='0.6.6',context_schema=1,game_versions=['2.4.2.0'])
core.update(min_desktop='0.2.0')
manager=release('data_manager-v0.1.1','WoTQuartermaster Data Manager 0.1.1','Compatibility with connector 0.0.12 and matching repaired supplemental generations. Targeted observations are not promoted before live validation.',[Path('modules/data_manager/0.1.1/data_manager.qmodule')])
manager['version']='0.1.1'
d['modules']['data_manager']=dict(old_modules['data_manager'],**manager)
d['components']['connector']=connector;d['components']['desktop']=core;d['product_version']='0.6.9'
assert all(d['modules'][k]==v for k,v in old_modules.items() if k!='data_manager')
p.write_text(json.dumps(d,sort_keys=True,indent=2)+'\n',encoding='utf-8')
print('Verified both published assets and published product 0.6.9 with prior module versions')
