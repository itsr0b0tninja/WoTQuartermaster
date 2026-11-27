"""Verify and publish the independent Diagnostic discovery test module."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

repo='itsr0b0tninja/WoTQuartermaster'
mid='diagnostic'
version='0.1.0'
tag=mid+'-v'+version
name=mid+'.qmodule'
path=Path('modules/diagnostic/0.1.0/diagnostic.qmodule')
expected_sha='d06124c411c8c6e8258fabe3ed86d17cf4e4d87e'

def verify():
    actual=subprocess.check_output(['git','hash-object',str(path)],text=True).strip()
    if actual!=expected_sha: raise RuntimeError('Diagnostic source hash mismatch')
    sys.path.insert(0,str(Path('desktop').resolve()))
    from module_manager import checked_bytes,validate_entry,check_set
    from module_runtime import Runtime
    raw=path.read_bytes()
    entry=dict(version=version,api=1,min_core='0.3.2',dependencies={},size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),release=tag,asset=name,url=f'https://github.com/{repo}/releases/download/{tag}/{name}',channel='alpha',required=True)
    validate_entry(mid,entry)
    checked_bytes(raw,mid,entry)
    manifest=json.loads(Path('components.json').read_text(encoding='utf-8'))
    check_set(dict(manifest['modules'],diagnostic=entry),'0.3.2')
    ns={'__file__':str(path)}
    exec(compile(raw,str(path),'exec'),ns)
    reg=ns['register']()
    assert set(reg)=={'pages'}
    assert len(reg['pages'])==1
    assert reg['pages'][0]['name']=='Diagnostic' and reg['pages'][0]['order']==75
    # Exercise actual registration and entire page construction against a minimal
    # fixture implementing the same core helper signatures.
    runtime=Runtime(Path('.'),'0.3.2')
    runtime._register(mid,None,reg)
    assert runtime.pages[0]['module']==mid
    class Layout:
        def __init__(self): self.children=[]
        def addWidget(self,w): self.children.append(w)
        def addStretch(self,n): pass
    class Window:
        def __init__(self): self.runtime=runtime; self.pages={}
        def add_page(self,name,w): self.pages[name]=w
    captured=[]
    root=object(); layout=Layout(); panel=object(); inner=Layout()
    def heading(l,title,subtitle): captured.append((title,subtitle))
    ns.update(page=lambda:(root,layout),panel=lambda:(panel,inner),label=lambda text,*a,**kw:text,heading=heading)
    window=Window()
    runtime.pages[0]['build'](window)
    assert window.pages=={'Diagnostic':root}
    assert captured==[('Diagnostic','Diagnostic module v0.1.0 · Independent module discovery test')]
    assert 'Core version: 0.3.2' in inner.children
    assert 'Module version: 0.1.0' in inner.children
    print('Diagnostic metadata, dependency compatibility, dynamic registration and page construction verified')
    return entry

def publish(entry):
    p=Path('components.json')
    data=json.loads(p.read_text(encoding='utf-8'))
    assert data['schema']==1
    assert data['components']['desktop']['version']=='0.3.2'
    assert data['components']['desktop']['sha256']=='a1968f9b162a45f783854bf0ebc931b8dbe421a90a3ab3bec3a761e9f13ee44a'
    assert data['modules']['garage']['version']=='0.1.1'
    if mid in data['retired_modules']: raise RuntimeError('Refusing to republish retired module')
    if mid in data['modules'] and data['modules'][mid]!=entry: raise RuntimeError('Existing module differs')
    result=subprocess.run(['gh','release','view',tag,'--repo',repo],capture_output=True)
    if result.returncode:
        subprocess.check_call(['gh','release','create',tag,'--repo',repo,'--target',os.environ['GITHUB_SHA'],'--title','Diagnostic module v0.1.0','--prerelease','--notes','Independent module updater test B. Adds a temporary Diagnostic sidebar entry and page without rebuilding the core executable. No game or database writes.',str(path)])
    release=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/releases/tags/{tag}'],text=True,encoding='utf-8'))
    assert release['tag_name']==tag and release['prerelease'] and not release['draft']
    asset=next(a for a in release['assets'] if a['name']==name)
    assert asset['digest']=='sha256:'+entry['sha256'] and asset['size']==entry['size'] and asset['browser_download_url']==entry['url']
    data['modules'][mid]=entry
    p.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('Verified new module release and manifest entry:',entry['sha256'])

if __name__=='__main__':
    e=verify()
    if '--publish' in sys.argv: publish(e)
