"""Validate and publish the paired independent modules for product 0.6.4."""
import ast,hashlib,json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path('desktop').resolve()))
from module_manager import validate_entry,checked_bytes,validate_modules,check_set
REPO='itsr0b0tninja/WoTQuartermaster'
VERSIONS={'finance':'0.1.2','progression':'0.1.4'}
PRIOR={'finance':'0.1.1','progression':'0.1.3'}
def module_path(mid):return Path('modules')/mid/VERSIONS[mid]/(mid+'.qmodule')
def entry(mid):
    p=module_path(mid);raw=p.read_bytes();tag=mid+'-v'+VERSIONS[mid]
    meta=next(ast.literal_eval(n.value) for n in ast.parse(raw).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MODULE' for t in n.targets))
    assert meta['version']==VERSIONS[mid] and meta['min_core']=='0.6.1'
    e=dict(version=meta['version'],api=meta['api'],min_core=meta['min_core'],dependencies=meta['dependencies'],size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),release=tag,asset=p.name,url=f'https://github.com/{REPO}/releases/download/{tag}/{p.name}',channel='alpha',required=True)
    validate_entry(mid,e);checked_bytes(raw,mid,e);return e
def proposed():
    d=json.loads(Path('components.json').read_text(encoding='utf-8'))
    assert d['product_version'] in ('0.6.3','0.6.4')
    assert d['components']['desktop']['version']=='0.6.1' and d['components']['connector']['version']=='0.0.9'
    for mid in VERSIONS:
        old=d['modules'][mid];e=entry(mid)
        assert old['version'] in (PRIOR[mid],VERSIONS[mid]);assert old['version']!=VERSIONS[mid] or old==e
        d['modules'][mid]=e
    d['product_version']='0.6.4';entries,_=validate_modules(d);check_set(entries,'0.6.1');return d
def publish():
    d=proposed()
    for mid in VERSIONS:
        e=d['modules'][mid];tag=e['release'];p=module_path(mid)
        if subprocess.run(['gh','release','view',tag,'--repo',REPO],capture_output=True).returncode:
            subprocess.check_call(['gh','release','create',tag,'--repo',REPO,'--target',os.environ['GITHUB_SHA'],'--title',f'WoTQuartermaster 0.6.4 – {mid} {e["version"]}','--prerelease','--notes','Development prerelease. Paired progression and finance module update for core 0.6.1 and connector 0.0.9. Verified native configuration audit, any-tier potential ranking, provisional route and preparation budgets, planned module investment, crew planning, reserve protection and cross-career retention. Exact future fitting, live prices and inventory remain subject to in-game verification; no automated actions. Live acceptance pending. Install through Quartermaster Updates.',str(p)])
        rel=json.loads(subprocess.check_output(['gh','api',f'repos/{REPO}/releases/tags/{tag}'],text=True,encoding='utf-8'))
        assert rel['tag_name']==tag and rel['prerelease'] and not rel['draft']
        a=next(a for a in rel['assets'] if a['name']==p.name)
        assert a['digest']=='sha256:'+e['sha256'] and a['size']==e['size'] and a['browser_download_url']==e['url']
    Path('components.json').write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('Verified both module assets; atomic manifest ready')
if __name__=='__main__':
    d=proposed();print('Verified compatible module set:',{k:d['modules'][k]['sha256'] for k in VERSIONS})
    if '--publish' in sys.argv:publish()
