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
data={'schema':1,'components':{
    'desktop':component('0.2.0','v0.2.0','WoTQuartermaster.exe'),
    'connector':component('0.0.8','connector-v0.0.8','wot_companion_connector.wotmod',{'context_schema':1,'game_versions':['2.4.2.0']}),
    'replay_parser':component('0.0.7','replay-v0.0.7','WoT_Quartermaster_Replay_Parser.txt'),
}}
# Future component-specific publication must preserve other validated entries.
Path('components.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
