import hashlib,json,subprocess
from pathlib import Path
REPO='itsr0b0tninja/WoTQuartermaster'
def run(*args):return subprocess.check_output(args,text=True).strip()
def release(tag,title,notes,paths):
    # Do not silently replace an already published binary.
    proc=subprocess.run(['gh','release','view',tag,'--repo',REPO],capture_output=True)
    if proc.returncode:
        subprocess.check_call(['gh','release','create',tag,'--repo',REPO,'--target',run('git','rev-parse','HEAD'),'--title',title,'--notes',notes,'--prerelease',*map(str,paths)])
    assets=json.loads(run('gh','api','repos/'+REPO+'/releases/tags/'+tag))['assets']
    p=paths[0]; a=next(x for x in assets if x['name']==p.name)
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    assert a['size']==p.stat().st_size and a.get('digest')=='sha256:'+digest,(tag,'published asset mismatch')
    return dict(version=tag.split('-v')[-1] if '-v' in tag else tag[1:],release=tag,asset=p.name,url=a['browser_download_url'],size=a['size'],sha256=digest,channel='alpha')
p=Path('components.json'); d=json.loads(p.read_text(encoding='utf-8'))
assert d['product_version']=='0.6.3'
assert d['components']['desktop']['version'] in ('0.6.0','0.6.1')
assert d['components']['connector']['version'] in ('0.0.8','0.0.9')
assert d['modules']['progression']['version']=='0.1.3'
old_modules=d['modules'].copy()
connector=release('connector-v0.0.9','WoTQuartermaster Connector v0.0.9','Development data-collection prerelease. Existing exports retained; new isolated configuration audit and missing-field diagnostics. Python 2.7 build and synthetic checks passed; in-game native calculations, load legality, matchmaking and research prerequisite interpretation still require validation. Close the game before replacing the mod; preserve your existing connector.ini.',[Path('connector-assets/wot_companion_connector.wotmod'),Path('connector-assets/connector.ini'),Path('connector-assets/wot_companion_connector.sha256.txt')])
core=release('v0.6.1','WoTQuartermaster Core v0.6.1 (connector compatibility)','Compatibility-only core update: accepts connector 0.0.8 and 0.0.9 with matching session/version context. Product remains v0.6.3; advisor modules unchanged. Install core before upgrading connector.',[Path('core-assets/WoTQuartermaster.exe'),Path('core-assets/WoTQuartermaster.sha256.txt')])
connector.update(min_desktop='0.6.1',context_schema=1,game_versions=['2.4.2.0'])
core.update(min_desktop='0.2.0')
d['components']['connector']=connector;d['components']['desktop']=core
assert d['modules']==old_modules
p.write_text(json.dumps(d,sort_keys=True,indent=2)+'\n',encoding='utf-8')
print('Verified both published assets and preserved v0.6.3 product/module versions')
