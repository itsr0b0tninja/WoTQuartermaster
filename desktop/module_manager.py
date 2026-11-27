"""Independent module distribution, API 1. Official repository trust; not a sandbox.
The immutable generation directory and one atomic state record form the transaction.
The 0.3.1 flat files remain available for executable rollback.
"""
import ast
import hashlib
import json
import logging
import os
import re
import secrets
from pathlib import Path
from module_runtime import Runtime, ModuleUnavailable, atomic_bytes, version, API, MAX_MODULE_BYTES

ROOT='https://github.com/itsr0b0tninja/WoTQuartermaster/releases/download/'
ID=re.compile(r'^[a-z][a-z0-9_]{0,39}$')
GEN=re.compile(r'^[0-9a-f]{32}$')
HEX=re.compile(r'^[0-9a-f]{64}$')
MAX_MODULES=40
CORE='0.3.2'

def valid_id(mid):
    if not isinstance(mid,str) or not ID.fullmatch(mid) or mid in ('con','prn','aux','nul','com1','com2','com3','com4','com5','com6','com7','com8','com9','lpt1','lpt2','lpt3','lpt4','lpt5','lpt6','lpt7','lpt8','lpt9'):
        raise ValueError('Invalid module ID')
    return mid

def json_bytes(value): return json.dumps(value,sort_keys=True,indent=2).encode('utf-8')
def fingerprint(value): return hashlib.sha256(json_bytes(value)).hexdigest()

def validate_entry(mid,e,online=True):
    valid_id(mid)
    if not isinstance(e,dict): raise ValueError('Invalid module entry')
    version(e.get('version')); version(e.get('min_core'))
    if type(e.get('api')) is not int or e['api']<1: raise ValueError('Invalid module API')
    if type(e.get('size')) is not int or not 0<e['size']<=MAX_MODULE_BYTES: raise ValueError('Invalid module size')
    if not isinstance(e.get('sha256'),str) or not HEX.fullmatch(e['sha256']): raise ValueError('Invalid module checksum')
    deps=e.get('dependencies')
    if not isinstance(deps,dict) or len(deps)>MAX_MODULES: raise ValueError('Invalid dependencies')
    for d,v in deps.items():
        valid_id(d); version(v)
        if d==mid: raise ValueError('Self dependency')
    fields=('version','min_core','api','size','sha256','dependencies')
    result={k:e[k] for k in fields}
    if online:
        tag=mid+'-v'+e['version']; asset=mid+'.qmodule'
        if e.get('release')!=tag or e.get('asset')!=asset or e.get('url')!=ROOT+tag+'/'+asset: raise ValueError('Unexpected module URL')
        if e.get('channel') not in ('alpha','stable') or type(e.get('required')) is not bool: raise ValueError('Invalid module channel or installation policy')
        result.update({k:e[k] for k in ('release','asset','url','channel','required')})
    else:
        result['required']=True
    return result

def validate_modules(raw):
    if not isinstance(raw,dict): raise ValueError('Invalid manifest')
    modules=raw.get('modules',{}); retired=raw.get('retired_modules',[])
    if not isinstance(modules,dict) or len(modules)>MAX_MODULES or not isinstance(retired,list) or len(retired)>MAX_MODULES: raise ValueError('Invalid module catalogue')
    entries={mid:validate_entry(mid,e) for mid,e in modules.items()}
    retired=list(dict.fromkeys(valid_id(mid) for mid in retired))
    if set(entries)&set(retired): raise ValueError('Module both offered and retired')
    return entries,retired

def check_set(entries,core):
    if not isinstance(entries,dict) or len(entries)>MAX_MODULES: raise ValueError('Invalid module set')
    for mid,e in entries.items():
        validate_entry(mid,e,'url' in e)
        if e['api']!=API or version(e['min_core'])>version(core): raise ValueError('Incompatible module: '+mid)
        for d,v in e['dependencies'].items():
            if d not in entries or version(entries[d]['version'])<version(v): raise ValueError(mid+' requires '+d+' '+v)
    pending=set(entries); complete=set()
    while pending:
        ready={mid for mid in pending if set(entries[mid]['dependencies'])<=complete}
        if not ready: raise ValueError('Cyclic module dependency')
        complete|=ready; pending-=ready

def checked_bytes(raw,mid,e):
    if len(raw)!=e['size'] or hashlib.sha256(raw).hexdigest()!=e['sha256']: raise ValueError(mid+': size or SHA-256 mismatch')
    tree=ast.parse(raw,filename=mid+'.qmodule')
    metas=[ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MODULE' for t in n.targets)]
    expected={k:e[k] for k in ('version','api','min_core','dependencies')}
    expected['id']=mid
    if len(metas)!=1 or not isinstance(metas[0],dict) or any(metas[0].get(k)!=v for k,v in expected.items()): raise ValueError(mid+': module metadata mismatch')
    compile(tree,mid+'.qmodule','exec')
    return raw

class ManagedRuntime(Runtime):
    def __init__(self,manager,generation=None):
        super().__init__(manager.base,manager.core,manager.resources)
        self.manager=manager; self.generation=generation
    def bootstrap(self):
        if self.generation is None:
            super().bootstrap()
            self.entries={mid:validate_entry(mid,e,False) for mid,e in self.entries.items()}
        else:
            self.folder=self.manager.generation_path(self.generation)
            self.entries=self.manager.generation_entries(self.generation)
    def repair(self):
        if self.generation is not None: raise ValueError('Use previous-set recovery for downloaded modules')
        super().repair()

class ModuleManager:
    def __init__(self,base,core=CORE,resources=None):
        self.base=Path(base).resolve(); self.core=core
        self.resources=Runtime(self.base,core,resources).resources
        self.folder=self.base/'modules'; self.sets=self.folder/'sets'; self.state_path=self.folder/'module-state.json'
        self.state={'schema':1,'active':None,'previous':None,'pending':None,'trial':None,'has_previous':False,'hold':False,'rejected':None,'message':''}
        self.runtime=None; self.warning=''
    def safe_dir(self,path,parent):
        if path.is_symlink() or path.resolve().parent!=parent.resolve(): raise ValueError('Unsafe managed directory: '+path.name)
        path.mkdir(parents=True,exist_ok=True)
    def initialize(self):
        self.safe_dir(self.folder,self.base); self.safe_dir(self.sets,self.folder)
        if self.state_path.is_symlink(): raise ValueError('Unsafe module state')
        if self.state_path.exists():
            if self.state_path.stat().st_size>64*1024: raise ValueError('Oversized module state')
            s=json.loads(self.state_path.read_text(encoding='utf-8'))
            if s.get('schema')!=1: raise ValueError('Invalid module state')
            for k in ('active','previous','pending','trial'):
                if s.get(k) is not None and (not isinstance(s[k],str) or not GEN.fullmatch(s[k])): raise ValueError('Invalid generation pointer')
            if s.get('trial') is not None and s['trial']!=s.get('pending'): raise ValueError('Invalid trial state')
            if any(type(s.get(k)) is not bool for k in ('has_previous','hold')): raise ValueError('Invalid module recovery flags')
            if not isinstance(s.get('message',''),str): raise ValueError('Invalid module recovery message')
            self.state.update({k:s[k] for k in self.state if k in s})
        # The previous process died before confirming the trial. Old active was
        # never changed. Reject the failed candidate instead of looping.
        if self.state['trial']:
            bad=self.state['trial']
            try: rejected=fingerprint(self.generation_entries(bad))
            except Exception: rejected=None
            self.save(trial=None,pending=None,rejected=rejected,hold=True,message='Interrupted module activation; previous set restored')
            self.discard(bad)
        self.cleanup()
    def save(self,**updates):
        s=dict(self.state,**updates)
        if self.state_path.is_symlink(): raise ValueError('Unsafe module state')
        atomic_bytes(self.state_path,json_bytes(s)); self.state=s
    def generation_path(self,g):
        if not isinstance(g,str) or not GEN.fullmatch(g): raise ValueError('Invalid generation')
        p=self.sets/g
        if p.is_symlink() or p.resolve().parent!=self.sets.resolve() or not p.is_dir(): raise ValueError('Module set unavailable')
        return p
    def generation_entries(self,g):
        folder=self.generation_path(g); p=folder/'set.json'
        if p.is_symlink() or p.stat().st_size>256*1024: raise ValueError('Invalid module set index')
        data=json.loads(p.read_text(encoding='utf-8'))
        if data.get('schema')!=1 or data.get('generation')!=g: raise ValueError('Module set identity mismatch')
        entries=data['modules']; check_set(entries,self.core)
        return {mid:validate_entry(mid,e,'url' in e) for mid,e in entries.items()}
    def read_set(self,g):
        if g is None:
            r=Runtime(self.base,self.core,self.resources); entries={mid:validate_entry(mid,e,False) for mid,e in r._index().items()}
            # Immutable bundled bytes are used only to repair the initial set.
            return entries,self.folder
        return self.generation_entries(g),self.generation_path(g)
    def get_bytes(self,folder,mid,e):
        p=folder/(valid_id(mid)+'.qmodule')
        if p.is_symlink() or p.resolve().parent!=folder.resolve() or p.stat().st_size!=e['size']: raise ValueError('Unsafe or invalid module file: '+mid)
        return checked_bytes(p.read_bytes(),mid,e)
    def discard(self,g):
        if not g or g in (self.state['active'],self.state['previous'],self.state['pending'],self.state['trial']): return
        try:
            p=self.generation_path(g); marker=p/'set.json'
            if marker.is_symlink() or marker.stat().st_size>256*1024: return
            raw=json.loads(marker.read_text(encoding='utf-8'))
            if raw.get('schema')!=1 or raw.get('generation')!=g: return
            entries=raw.get('modules',{})
            if not isinstance(entries,dict) or len(entries)>MAX_MODULES: return
            names={valid_id(mid)+'.qmodule' for mid in entries}
            # Do not remove an unexpected file, or recursively delete anything.
            for child in p.iterdir():
                if child.name in names or (child.name.startswith('.qm-') and child.name.endswith('.tmp')):
                    if child.is_file() and not child.is_symlink(): child.unlink()
            if all(x.name=='set.json' for x in p.iterdir()): marker.unlink(); p.rmdir()
        except (OSError,ValueError,TypeError,KeyError): logging.warning('Could not clean obsolete module set %s',g)
    def cleanup(self):
        for p in self.sets.iterdir():
            if GEN.fullmatch(p.name): self.discard(p.name)
    def start(self,activate=True):
        try:
            self.initialize()
        except Exception as exc:
            self.warning='Module state unavailable: '+str(exc); logging.exception('Module state unavailable')
            self.runtime=ManagedRuntime(self,None).load(); return self.runtime
        if activate and self.state['pending']:
            g=self.state['pending']
            try:
                self.save(trial=g)
                r=ManagedRuntime(self,g).load()
                if not r.ready(): raise ValueError(r.status_text())
                self.runtime=r; return r
            except Exception as exc:
                self.reject_trial(str(exc))
        self.runtime=ManagedRuntime(self,self.state['active']).load()
        if not self.runtime.ready() and self.state['active'] is not None and self.state['has_previous']:
            prior=self.state['previous']
            r=ManagedRuntime(self,prior).load()
            if r.ready():
                bad=self.state['active']
                self.save(active=prior,previous=None,has_previous=False,hold=True,message='Active module set failed; restored previous set')
                self.discard(bad); self.runtime=r
        return self.runtime
    def reject_trial(self,why):
        bad=self.state['trial'] or self.state['pending']
        try: rejected=fingerprint(self.generation_entries(bad))
        except Exception: rejected=None
        self.save(trial=None,pending=None,rejected=rejected,hold=True,message='Module activation failed; previous set retained: '+why[:500])
        self.discard(bad)
    def confirm(self):
        g=self.state['trial']
        if not g: return
        if not self.runtime or not self.runtime.ready(): raise ValueError('Module trial not healthy')
        old=self.state['active']
        self.save(active=g,previous=old,has_previous=True,pending=None,trial=None,rejected=None,message='Module set activated successfully')
        self.cleanup()
    def cancel_pending(self):
        if self.state['trial']: raise ValueError('Activation already running')
        old=self.state['pending']; self.save(pending=None,message='Prepared module update cancelled'); self.discard(old)
    def compatible(self,e):
        return e['api']==API and version(e['min_core'])<=version(self.core)
    def plan(self,offered,retired,include_alpha=True,selected=None,manual=False):
        current=dict(self.runtime.entries if self.runtime else self.read_set(self.state['active'])[0])
        target=dict(current)
        if self.state['hold'] and not manual: return target
        selected=set(selected or ())
        eligible={mid:e for mid,e in offered.items() if self.compatible(e) and (include_alpha or e['channel']=='stable')}
        for mid,e in eligible.items():
            old=current.get(mid)
            if old:
                if version(e['version'])<version(old['version']): continue
                if version(e['version'])==version(old['version']) and e['sha256']!=old['sha256']: raise ValueError('Published version changed bytes: '+mid)
                if e['version']==old['version']: continue
            if old or e['required'] or mid in selected: target[mid]=e
        for mid in retired: target.pop(mid,None)
        # Required dependency closure; optional modules can be dependencies.
        for _ in range(MAX_MODULES+1):
            changed=False
            for mid,e in list(target.items()):
                for d,v in e['dependencies'].items():
                    if d in target and version(target[d]['version'])>=version(v): continue
                    candidate=eligible.get(d)
                    if not candidate or d in retired or version(candidate['version'])<version(v): raise ValueError(mid+' requires unavailable '+d+' '+v)
                    target[d]=candidate; changed=True
            if not changed: break
        check_set(target,self.core)
        if not target: raise ValueError('Refusing empty module set')
        return target
    def stage(self,target,opener,cancel,progress=lambda n,total:None,source_generation=None,manual=False,rollback=False):
        # Called by the single existing updater worker; UI never mutates active
        # module files. The old pointer remains active throughout download.
        check_set(target,self.core)
        current,folder=self.read_set(self.state['active'])
        if target==current and not rollback: return False
        if not manual and fingerprint(target)==self.state['rejected']: return False
        if self.state['pending']:
            if self.generation_entries(self.state['pending'])==target: return False
            raise ValueError('Cancel or activate the pending module set first')
        prior_entries,prior_folder=({},None)
        if rollback: prior_entries,prior_folder=self.read_set(source_generation)
        g=secrets.token_hex(16); dest=self.sets/g
        dest.mkdir(exist_ok=False)
        # Write ownership/index before any assets so interrupted staging is cleanable.
        try:
            atomic_bytes(dest/'set.json',json_bytes({'schema':1,'generation':g,'modules':target}))
            total=sum(e['size'] for e in target.values()); done=0
            for mid,e in target.items():
                if cancel.is_set(): raise InterruptedError('Module download cancelled')
                if mid in current and current[mid]['sha256']==e['sha256']:
                    raw=self.get_bytes(folder,mid,e)
                elif mid in prior_entries and prior_entries[mid]['sha256']==e['sha256']:
                    raw=self.get_bytes(prior_folder,mid,e)
                else:
                    validate_entry(mid,e)
                    chunks=[]; n=0
                    with opener(e['url']) as response:
                        while True:
                            if cancel.is_set(): raise InterruptedError('Module download cancelled')
                            block=response.read(65536)
                            if not block: break
                            n+=len(block)
                            if n>e['size']: raise ValueError(mid+': oversized download')
                            chunks.append(block); progress(done+n,total)
                    raw=checked_bytes(b''.join(chunks),mid,e)
                atomic_bytes(dest/(mid+'.qmodule'),raw); done+=len(raw); progress(done,total)
            if cancel.is_set(): raise InterruptedError('Module download cancelled')
            # Recheck complete set before staging pointer publication.
            for mid,e in target.items(): self.get_bytes(dest,mid,e)
            self.save(pending=g,hold=rollback,rejected=None if manual else self.state['rejected'],message='Module changes prepared; restart to activate')
            return True
        except Exception:
            self.discard(g)
            # A failed index write can leave an empty directory, owned by this call.
            try: dest.rmdir()
            except OSError: pass
            raise
    def stage_rollback(self,mid,opener,cancel,progress):
        if not self.state['has_previous']: raise ValueError('No previous compatible module set')
        prior=self.state['previous']; old,_=self.read_set(prior); current,_=self.read_set(self.state['active'])
        if mid:
            target=dict(current)
            if mid in old: target[mid]=old[mid]
            else: target.pop(mid,None)
            if target==current: raise ValueError('Selected module has no different previous version')
        else: target=old
        return self.stage(target,opener,cancel,progress,source_generation=prior,manual=True,rollback=True)
    def module_rows(self,offered,retired,include_alpha):
        installed=self.runtime.entries if self.runtime else {}
        pending={}
        if self.state['pending']:
            try: pending=self.generation_entries(self.state['pending'])
            except Exception: pass
        rows=[]
        for mid in sorted(set(installed)|set(offered)|set(pending)):
            local=installed.get(mid); e=offered.get(mid); p=pending.get(mid)
            available=e and (include_alpha or e['channel']=='stable')
            if self.state['pending'] and local!=p: status='Prepared: '+(p['version'] if p else 'Removal')
            elif mid in retired: status='Retirement available'
            elif local and mid in self.runtime.errors: status='Unavailable: '+self.runtime.errors[mid]
            elif available and not self.compatible(e): status='Requires newer core / API'
            elif available and not local: status='New required' if e['required'] else 'Optional download'
            elif available and version(e['version'])>version(local['version']): status='Update available'
            else: status='Loaded' if local else 'Not installed'
            rows.append((mid,local['version'] if local else '—',e['version'] if available else '—',status))
        return rows
