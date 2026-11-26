# Build the trusted bootstrap index from exact checked-out module bytes.
import ast, hashlib, json, subprocess
from pathlib import Path
root=Path('desktop/runtime_modules')
expected={'crew':'1037b183a42ed027564b92a0342c7cdd790a0407','garage':'145a5b67022ffd16caf571a61a5ebd27ad7db0ad','inventory':'a4a7b39a7795198ab7a01e69669f59f4baebbca8','maps':'7d883a6d44452d148f155e3f295de19b008bc5b7','research':'ffca976de816969a5d56931c5c3a84c355ec583b'}
entries={}
if {p.stem for p in root.glob('*.qmodule')}!=set(expected): raise RuntimeError('Unexpected module set')
for mid,sha in expected.items():
    path=root/(mid+'.qmodule')
    if subprocess.check_output(['git','hash-object',str(path)],text=True).strip()!=sha: raise RuntimeError('Module source mismatch: '+mid)
    raw=path.read_bytes(); parsed=ast.parse(raw,filename=str(path))
    meta=next(ast.literal_eval(n.value) for n in parsed.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MODULE' for t in n.targets))
    if meta['id']!=mid: raise RuntimeError('Module ID mismatch')
    entries[mid]={k:meta[k] for k in ('api','version','min_core','dependencies')}
    entries[mid].update(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
(root/'index.json').write_text(json.dumps({'schema':1,'api':1,'modules':entries},sort_keys=True,indent=2)+'\n',encoding='utf-8')
print('Verified bootstrap module index:',', '.join(entries))
