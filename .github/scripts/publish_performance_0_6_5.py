"""Validate and publish the performance core and progression module as a single manifest change."""
import ast,hashlib,json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path('desktop').resolve()))
from module_manager import validate_entry,checked_bytes,validate_modules,check_set
REPO='itsr0b0tninja/WoTQuartermaster'
VERSIONS={'progression':'0.1.5'}
CORE='0.6.2';PRODUCT='0.6.5'
def module_path(mid):return Path('modules')/mid/VERSIONS[mid]/(mid+'.qmodule')
def module_entry(mid):
    p=module_path(mid);raw=p.read_bytes();tag=mid+'-v'+VERSIONS[mid]
    meta=next(ast.literal_eval(n.value) for n in ast.parse(raw).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MODULE' for t in n.targets))
    assert meta['version']==VERSIONS[mid] and meta['min_core']=='0.6.1'
    e=dict(version=meta['version'],api=meta['api'],min_core=meta['min_core'],dependencies=meta['dependencies'],size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),release=tag,asset=p.name,url=f'https://github.com/{REPO}/releases/download/{tag}/{p.name}',channel='alpha',required=True)
    validate_entry(mid,e);checked_bytes(raw,mid,e);return e
def proposed():
    d=json.loads(Path('components.json').read_text(encoding='utf-8'))
    assert d['product_version'] in ('0.6.4',PRODUCT)
    assert d['components']['desktop']['version'] in ('0.6.1',CORE) and d['components']['connector']['version']=='0.0.9'
    assert d['modules']['finance']['version']=='0.1.2'
    for mid in VERSIONS:
        old=d['modules'][mid];e=module_entry(mid);assert old['version'] in ('0.1.4',VERSIONS[mid]);assert old['version']!=VERSIONS[mid] or old==e;d['modules'][mid]=e
    d['product_version']=PRODUCT;entries,_=validate_modules(d);check_set(entries,'0.6.1');check_set(entries,CORE);return d
def run(*args):return subprocess.check_output(args,text=True,encoding='utf-8').strip()
def release(tag,title,notes,paths):
    if subprocess.run(['gh','release','view',tag,'--repo',REPO],capture_output=True).returncode:
        subprocess.check_call(['gh','release','create',tag,'--repo',REPO,'--target',os.environ['GITHUB_SHA'],'--title',title,'--prerelease','--notes',notes,*map(str,paths)])
    r=json.loads(run('gh','api','repos/'+REPO+'/releases/tags/'+tag));assert r['tag_name']==tag and r['prerelease'] and not r['draft']
    p=paths[0];a=next(a for a in r['assets'] if a['name']==p.name);digest=hashlib.sha256(p.read_bytes()).hexdigest()
    assert a['digest']=='sha256:'+digest and a['size']==p.stat().st_size
    return dict(release=tag,asset=p.name,url=a['browser_download_url'],size=a['size'],sha256=digest,channel='alpha')
def publish():
    d=proposed();p=Path('dist/WoTQuartermaster.exe');sha=p.with_name('WoTQuartermaster.sha256.txt');sha.write_text(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n',encoding='ascii')
    a=release('v'+CORE,'WoTQuartermaster core '+CORE+' (performance)','Performance-only desktop core: meaningful garage changes, incremental table rendering, event-loop and slow-refresh diagnostics, safer obsolete generation cleanup. Connector 0.0.9 unchanged. Existing history and settings retained. Install through Updates with World of Tanks closed. Real-account acceptance pending.',[p,sha]);a.update(version=CORE,min_desktop='0.2.0');d['components']['desktop']=a
    for mid in VERSIONS:
        e=d['modules'][mid];a=release(e['release'],'WoTQuartermaster '+PRODUCT+' – '+mid+' '+e['version'],'Single-flight background progression calculations, versioned checksum-verified suitability cache, stale-result rejection, visible-tab updates. Advisor formulas unchanged. Existing core 0.6.1 compatible; core 0.6.2 recommended. Live acceptance pending.',[module_path(mid)])
        assert all(e[k]==a[k] for k in a)
    Path('components.json').write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('Verified both release assets; manifest ready')
if __name__=='__main__':
    d=proposed();print('Compatible progression module:',d['modules']['progression']['sha256'])
    if '--publish' in sys.argv:publish()
