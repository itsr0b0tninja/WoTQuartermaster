"""Verify and publish the independent Progression 0.1.3 module for product 0.6.3."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path('desktop').resolve()))
from module_manager import validate_entry,checked_bytes,validate_modules,check_set
repo='itsr0b0tninja/WoTQuartermaster'
p=Path('modules/progression/0.1.3/progression.qmodule')
raw=p.read_bytes()
tag='progression-v0.1.3'
entry=dict(version='0.1.3',api=1,min_core='0.6.0',dependencies={'research':'0.1.1','finance':'0.1.1','battle_performance':'0.1.3'},size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),release=tag,asset=p.name,url=f'https://github.com/{repo}/releases/download/{tag}/{p.name}',channel='alpha',required=True)
validate_entry('progression',entry)
checked_bytes(raw,'progression',entry)
manifest=Path('components.json')
data=json.loads(manifest.read_text(encoding='utf-8'))
assert data['components']['desktop']['version']=='0.6.0'
assert data['product_version'] in ('0.6.2','0.6.3')
prior=data['modules']['progression']
assert prior['version'] in ('0.1.2','0.1.3')
if prior['version']=='0.1.3': assert prior==entry
data['modules']['progression']=entry
data['product_version']='0.6.3'
entries,retired=validate_modules(data)
check_set(entries,'0.6.0')
assert 'progression' not in retired
print('Verified module metadata, SHA256 and compatible dependencies:',entry['sha256'])
if '--publish' in sys.argv:
    if subprocess.run(['gh','release','view',tag,'--repo',repo],capture_output=True).returncode:
        subprocess.check_call(['gh','release','create',tag,'--repo',repo,'--target',os.environ['GITHUB_SHA'],'--title','WoTQuartermaster 0.6.3 - Progression Advisor 0.1.3','--prerelease','--notes','End-game progression: separate Tier X and XI cohorts, revised 45/30/5/15/5 weights, all ten careers reassessed, best stock-fit leaders, cross-career vehicle and depot retention with verified resale quotes, and Data Quality diagnostics. No automatic sales or style changes. Install through Quartermaster Updates; desktop core 0.6.0 and connector 0.0.8 unchanged. Exact acquisition costs, potential configurations and unresolved research prerequisites remain provisional. Live player acceptance pending.',str(p)])
    rel=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/releases/tags/{tag}'],text=True,encoding='utf-8'))
    assert rel['tag_name']==tag and rel['prerelease'] and not rel['draft']
    a=next(a for a in rel['assets'] if a['name']==p.name)
    assert a['digest']=='sha256:'+entry['sha256'] and a['size']==entry['size'] and a['browser_download_url']==entry['url']
    manifest.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('Verified module asset; manifest ready for publication.')
