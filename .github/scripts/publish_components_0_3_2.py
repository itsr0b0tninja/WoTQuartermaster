# Run in CI only after releases exist. Asset metadata must contain GitHub SHA-256 digests.
import json, subprocess, re
from pathlib import Path
repo='itsr0b0tninja/WoTQuartermaster'
def component(version,tag,name,extra=None):
    release=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/releases/tags/{tag}'],text=True,encoding='utf-8'))
    if release['draft'] or release['tag_name']!=tag: raise RuntimeError('Release not published: '+tag)
    asset=next(a for a in release['assets'] if a['name']==name)
    digest=asset.get('digest','')
    if not re.fullmatch('sha256:[a-f0-9]{64}',digest): raise RuntimeError('Missing GitHub SHA-256: '+name)
    expected=f'https://github.com/{repo}/releases/download/{tag}/{name}'
    if asset['browser_download_url']!=expected or asset['size']<=0: raise RuntimeError('Asset identity mismatch')
    return dict(version=version,release=tag,asset=name,url=expected,sha256=digest[7:],size=asset['size'],channel='alpha' if release['prerelease'] else 'stable',min_desktop='0.2.0',**(extra or {}))
data=json.loads(Path('components.json').read_text(encoding='utf-8'))
if data.get('schema')!=1 or not isinstance(data.get('components'),dict): raise RuntimeError('Unexpected manifest')
prior=data['components']['desktop']['version']
if tuple(map(int,prior.split('.')))> (0,3,2): raise RuntimeError('Refusing manifest downgrade')
data['components']['desktop']=component('0.3.2','v0.3.2','WoTQuartermaster.exe')
# Publish initial independent module assets only after successful build and tests.
index=json.loads(Path('desktop/runtime_modules/index.json').read_text(encoding='utf-8'))
modules={}
for mid,e in index['modules'].items():
    v=e['version']; tag=mid+'-v'+v; name=mid+'.qmodule'
    found=subprocess.run(['gh','release','view',tag,'--repo',repo],capture_output=True)
    if found.returncode:
        subprocess.check_call(['gh','release','create',tag,'--repo',repo,'--target',__import__('os').environ['GITHUB_SHA'],'--title',mid.capitalize()+' module '+v,'--prerelease','--notes','Independent official runtime module for WoTQuartermaster.','desktop/runtime_modules/'+name])
    asset=component(v,tag,name)
    if asset['sha256']!=e['sha256'] or asset['size']!=e['size']: raise RuntimeError('Published module byte mismatch: '+mid)
    asset.pop('min_desktop')
    modules[mid]=dict(asset,api=e['api'],min_core=e['min_core'],dependencies=e['dependencies'],required=True)
data['modules']=modules
data['retired_modules']=[]
# Preserve Connector and replay entries exactly.
Path('components.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
