"""Publish Garage 0.1.2 only, after verifying the exact module-only test change."""
import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

repo='itsr0b0tninja/WoTQuartermaster'
mid='garage'
version='0.1.2'
tag=mid+'-v'+version
name=mid+'.qmodule'
path=Path('modules/garage/0.1.2/garage.qmodule')
baseline=Path('modules/garage/0.1.1/garage.qmodule')
expected_sha='bd3169d5ea80e61c320bff4c7290922e631b21de'
old_meta="MODULE={'id':'garage','version':'0.1.1','api':1,'min_core':'0.3.2','dependencies':{}}"
new_meta="MODULE={'id':'garage','version':'0.1.2','api':1,'min_core':'0.3.2','dependencies':{}}"
old_heading="w,l=page(); heading(l,'Garage','Garage module v'+MODULE['version']+' · Read-only configuration · no purchases or crew changes are performed')"
new_heading="w,l=page(); heading(l,'Garage','Garage module v'+MODULE['version']+' · Read-only configuration · no purchases or crew changes are performed')"

def verify():
    actual=subprocess.check_output(['git','hash-object',str(path)],text=True).strip()
    if actual!=expected_sha: raise RuntimeError('Garage source hash mismatch')
    prior=baseline.read_text(encoding='utf-8')
    assert prior.count(old_meta)==1 and prior.count(old_heading)==1
    assert path.read_text(encoding='utf-8')==prior.replace(old_meta,new_meta).replace(old_heading,new_heading), 'Unexpected functional change'
    raw=path.read_bytes()
    sys.path.insert(0,str(Path('desktop').resolve()))
    from module_manager import checked_bytes,validate_entry
    entry=dict(version=version,api=1,min_core='0.3.2',dependencies={},size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),release=tag,asset=name,url=f'https://github.com/{repo}/releases/download/{tag}/{name}',channel='alpha',required=True)
    validate_entry(mid,entry)
    checked_bytes(raw,mid,entry)
    ns={'__file__':str(path)}
    exec(compile(raw,str(path),'exec'),ns)
    registration=ns['register']()
    assert {p['name'] for p in registration['pages']}=={'Garage'}
    assert set(registration['services'])=={'overview','performance'}
    # Exercise the actual heading code without modifying the desktop executable.
    captured=[]
    class HeadingReached(Exception): pass
    def heading(layout,title,subtitle):
        captured.append((title,subtitle))
        raise HeadingReached()
    ns.update(page=lambda:(None,None),heading=heading)
    try: registration['pages'][0]['build'](object())
    except HeadingReached: pass
    assert captured==[('Garage','Garage module v0.1.2 · Read-only configuration · no purchases or crew changes are performed')]
    print('Garage module-only source, metadata, registration and version heading verified')
    return entry

def publish(entry):
    p=Path('components.json')
    data=json.loads(p.read_text(encoding='utf-8'))
    assert data['schema']==1
    assert data['components']['desktop']['version']=='0.3.2'
    assert data['components']['desktop']['sha256']=='a1968f9b162a45f783854bf0ebc931b8dbe421a90a3ab3bec3a761e9f13ee44a'
    prior=data['modules'][mid]
    if prior['version'] not in ('0.1.1',version): raise RuntimeError('Refusing module version regression')
    if prior['version']==version and prior!=entry: raise RuntimeError('Existing module version differs')
    result=subprocess.run(['gh','release','view',tag,'--repo',repo],capture_output=True)
    if result.returncode:
        subprocess.check_call(['gh','release','create',tag,'--repo',repo,'--target',os.environ['GITHUB_SHA'],'--title','Garage module v0.1.2','--prerelease','--notes','Independent module updater test C. Version-only update to establish a previous Garage version for rollback. No executable or game-data changes.',str(path)])
    release=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/releases/tags/{tag}'],text=True,encoding='utf-8'))
    assert release['tag_name']==tag and release['prerelease'] and not release['draft']
    asset=next(a for a in release['assets'] if a['name']==name)
    assert asset['digest']=='sha256:'+entry['sha256'] and asset['size']==entry['size'] and asset['browser_download_url']==entry['url']
    # Retire only the temporary Diagnostic module, preserve all other entries.
    if 'diagnostic' in data['modules']:
        assert data['modules']['diagnostic']['version']=='0.1.0'
        data['modules'].pop('diagnostic')
    elif 'diagnostic' not in data['retired_modules']: raise RuntimeError('Diagnostic missing without retirement marker')
    data['retired_modules']=sorted(set(data['retired_modules'])|{'diagnostic'})
    data['modules'][mid]=entry
    from module_manager import validate_modules,check_set
    offered,retired=validate_modules(data)
    check_set(offered,'0.3.2')
    assert 'diagnostic' in retired and 'diagnostic' not in offered
    p.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('Verified release and updated Garage manifest entry:',entry['sha256'])

if __name__=='__main__':
    e=verify()
    if '--publish' in sys.argv: publish(e)
