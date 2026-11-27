"""0.3.3 online bootstrap, recovery and opt-in local modules. No bundled module code.
Official metadata is trusted via the official HTTPS manifest or prior local cache.
Local modules are deliberately unsandboxed and never automatically updated.
"""
import ast, hashlib, json, logging, os, secrets, types
from pathlib import Path
from module_manager import ModuleManager as LegacyManager, ManagedRuntime, validate_entry, valid_id, check_set, checked_bytes, version, fingerprint, json_bytes, atomic_bytes, API, MAX_MODULE_BYTES, MAX_MODULES
from module_runtime import Runtime, resource_folder

class OnlineRuntime(ManagedRuntime):
    def bootstrap(self):
        self.entries,self.folder=self.manager.read_set(self.generation)
    def ready(self):
        return bool(self.entries) and set(self.entries)<=set(self.loaded) and not any(k in self.errors for k in set(self.entries)|{'runtime'})
    def status_text(self):
        result=super().status_text()
        for mid,e in getattr(self,'local_entries',{}).items():
            result+='\n'+mid+' '+e['version']+' — Third-party: '+(self.errors[mid] if mid in self.errors else 'Loaded' if mid in self.loaded else 'Not loaded')
        for mid,e in getattr(self,'local_failures',{}).items(): result+='\nThird-party '+mid+': '+e
        return result

class ModuleManager(LegacyManager):
    def __init__(self,base,core='0.3.3',resources=None):
        super().__init__(base,core,resources)
        self.backups=self.folder/'backups'; self.third=self.folder/'third-party'
        self.state.update(backup_entries={},holds=[],pending_holds=None,product_version=core,pending_product=None)
        self.offered_product=core
    def initialize(self):
        super().initialize()
        self.safe_dir(self.backups,self.folder); self.safe_dir(self.third,self.folder)
        if not self.state['pending'] and (self.state['pending_holds'] is not None or self.state['pending_product'] is not None): self.save(pending_holds=None,pending_product=None)
        if not isinstance(self.state['backup_entries'],dict) or len(self.state['backup_entries'])>MAX_MODULES: raise ValueError('Invalid backups')
        for mid,e in self.state['backup_entries'].items(): validate_entry(mid,e,'url' in e)
        for field in ('holds','pending_holds'):
            value=self.state[field]
            if field=='pending_holds' and value is None: continue
            if not isinstance(value,list) or len(value)>MAX_MODULES: raise ValueError('Invalid module holds')
            for mid in value: valid_id(mid)
        for k in ('product_version','pending_product'):
            if self.state[k] is not None: version(self.state[k])
        # Import any valid previous-set backups from 0.3.2, even offline.
        if self.state['has_previous'] and not self.state['backup_entries']:
            try:
                current,_=self.read_set(self.state['active'])
                old,folder=self.read_set(self.state['previous'])
                entries=self.archive_changes(old,folder,current,{})
                if entries: self.save(backup_entries=entries)
            except Exception: logging.exception('Legacy backup import incomplete')
    def read_set(self,g):
        if g is not None: return super().read_set(g)
        # The executable contains only the historical index, not the source files.
        marker=self.folder/'installed.json'
        if marker.is_file() and not marker.is_symlink():
            r=Runtime(self.base,self.core,self.resources)
            return {mid:validate_entry(mid,e,False) for mid,e in r._index().items()},self.folder
        return {},self.folder
    def backup_path(self,mid,e):
        return self.backups/(valid_id(mid)+'-'+e['sha256']+'.qmodule')
    def backup_bytes(self,mid,e):
        p=self.backup_path(mid,e)
        if p.is_symlink() or p.resolve().parent!=self.backups.resolve() or p.stat().st_size!=e['size']: raise ValueError('Invalid backup')
        return checked_bytes(p.read_bytes(),mid,e)
    def archive_changes(self,old,folder,new,backups):
        backups=dict(backups)
        for mid,e in old.items():
            if mid not in new or new[mid]['sha256']==e['sha256']: continue
            try:
                raw=self.get_bytes(folder,mid,e)
                dest=self.backup_path(mid,e)
                if dest.is_symlink(): raise ValueError('Unsafe backup')
                atomic_bytes(dest,raw); backups[mid]=e
            except Exception: logging.warning('Could not retain backup for %s',mid,exc_info=True)
        # Retired modules are retained only in the previous transaction, not the
        # individual rollback catalogue.
        return {mid:e for mid,e in backups.items() if mid in new}
    def clean_backups(self,old):
        keep={self.backup_path(mid,e) for mid,e in self.state['backup_entries'].items()}
        for mid,e in old.items():
            p=self.backup_path(mid,e)
            if p not in keep and p.is_file() and not p.is_symlink():
                try: p.unlink()
                except OSError: logging.warning('Backup cleanup failed')
    def start(self,activate=True):
        try: self.initialize()
        except Exception as exc:
            self.warning='Module state unavailable: '+str(exc); logging.exception(self.warning)
            self.runtime=OnlineRuntime(self,self.state['active']).load(); return self.runtime
        if activate and self.state['pending']:
            g=self.state['pending']
            try:
                self.save(trial=g)
                r=OnlineRuntime(self,g).load()
                if not r.ready(): raise ValueError(r.status_text())
                self.runtime=r; return r
            except Exception as exc: self.reject_trial(str(exc))
        self.runtime=OnlineRuntime(self,self.state['active']).load()
        if not self.runtime.ready() and self.state['active'] is not None and self.state['has_previous']:
            prior=self.state['previous']; r=OnlineRuntime(self,prior).load()
            if r.ready():
                bad=self.state['active']
                try:
                    bad_entries=self.generation_entries(bad)
                    affected=[mid for mid,e in bad_entries.items() if mid not in r.entries or e['sha256']!=r.entries[mid]['sha256']]
                except Exception: affected=list(r.entries)
                self.save(active=prior,previous=None,has_previous=False,holds=sorted(set(self.state['holds'])|set(affected)),message='Damaged active set; restored previous compatible set')
                self.discard(bad); self.runtime=r
        return self.runtime
    def confirm(self):
        g=self.state['trial']
        if not g: return
        if not self.runtime or not self.runtime.ready(): raise ValueError('Module trial not healthy')
        old=self.state['active']; previous_backups=dict(self.state['backup_entries'])
        try: entries,folder=self.read_set(old); backups=self.archive_changes(entries,folder,self.runtime.entries,previous_backups)
        except Exception: backups=previous_backups; logging.exception('Backup retention incomplete')
        self.save(active=g,previous=old,has_previous=bool(old or (self.folder/'installed.json').is_file()),pending=None,trial=None,rejected=None,backup_entries=backups,holds=self.state['pending_holds'] if self.state['pending_holds'] is not None else self.state['holds'],pending_holds=None,product_version=self.state['pending_product'] or self.state['product_version'],pending_product=None,message='Module set activated successfully')
        self.clean_backups(previous_backups); self.cleanup()
    def reject_trial(self,why):
        super().reject_trial(why)
        self.save(pending_holds=None,pending_product=None)
    def cancel_pending(self):
        super().cancel_pending()
        self.save(pending_holds=None,pending_product=None)
    def plan(self,offered,retired,include_alpha=True,selected=None,manual=False):
        # A hold also applies to manual "prepare updates"; explicitly release it first.
        filtered={mid:e for mid,e in offered.items() if mid not in self.state['holds']}
        # Required but incompatible modules must never result in a partial fresh setup.
        current=self.runtime.entries if self.runtime else {}
        if not current:
            required={mid for mid,e in offered.items() if e['required'] and (include_alpha or e['channel']=='stable')}
            if not required: raise ValueError('No compatible required modules in manifest')
            if any(not self.compatible(offered[mid]) for mid in required): raise ValueError('Required modules need a newer core')
        return super().plan(filtered,retired,include_alpha,selected,manual)
    def stage(self,target,opener,cancel,progress=lambda n,total:None,source_generation=None,manual=False,rollback=False,repair=False,holds=None):
        check_set(target,self.core)
        if not target: raise ValueError('No required modules')
        current,folder=self.read_set(self.state['active'])
        if target==current and not rollback and not repair: return False
        if not manual and fingerprint(target)==self.state['rejected']: return False
        if self.state['pending']:
            if self.generation_entries(self.state['pending'])==target: return False
            raise ValueError('Cancel or activate prepared modules first')
        prior_entries,prior_folder=({},None)
        if self.state['has_previous']:
            try: prior_entries,prior_folder=self.read_set(self.state['previous'])
            except Exception: pass
        g=secrets.token_hex(16); dest=self.sets/g; dest.mkdir(exist_ok=False)
        try:
            atomic_bytes(dest/'set.json',json_bytes({'schema':1,'generation':g,'modules':target}))
            total=sum(e['size'] for e in target.values()); done=0
            for mid,e in target.items():
                if cancel.is_set(): raise InterruptedError('Cancelled')
                raw=None
                for entries,source in ((current,folder),(prior_entries,prior_folder)):
                    if mid in entries and entries[mid]['sha256']==e['sha256']:
                        try: raw=self.get_bytes(source,mid,e); break
                        except (OSError,ValueError,SyntaxError): pass
                if raw is None and self.state['backup_entries'].get(mid,{}).get('sha256')==e['sha256']:
                    try: raw=self.backup_bytes(mid,e)
                    except (OSError,ValueError,SyntaxError): pass
                if raw is None:
                    # Old flat entries have no URL. Only an identical official
                    # manifest entry can supply their recovery download.
                    online=e
                    if 'url' not in online:
                        online=getattr(self,'repair_offered',{}).get(mid,{})
                        if online.get('sha256')!=e['sha256']: raise ValueError('No matching official download for '+mid)
                    validate_entry(mid,online)
                    chunks=[]; n=0
                    with opener(online['url']) as response:
                        while True:
                            if cancel.is_set(): raise InterruptedError('Cancelled')
                            block=response.read(65536)
                            if not block: break
                            n+=len(block)
                            if n>e['size']: raise ValueError('Oversized module '+mid)
                            chunks.append(block); progress(done+n,total)
                    raw=checked_bytes(b''.join(chunks),mid,e)
                atomic_bytes(dest/(mid+'.qmodule'),raw); done+=len(raw); progress(done,total)
            if cancel.is_set(): raise InterruptedError('Cancelled')
            for mid,e in target.items(): self.get_bytes(dest,mid,e)
            self.save(pending=g,pending_holds=holds,pending_product=(self.state['product_version'] if rollback or self.state['holds'] else max(self.core,self.offered_product,key=version)), rejected=None if manual else self.state['rejected'],message='Module changes prepared; restart to activate')
            return True
        except Exception:
            self.discard(g)
            try: dest.rmdir()
            except OSError: pass
            raise
    def recover(self,offered,retired,opener,cancel,progress,include_alpha=True):
        self.repair_offered=offered
        current,_=self.read_set(self.state['active'])
        target=self.plan(offered,retired,include_alpha,manual=True)
        # Use official downloadable metadata for exact versions where available.
        for mid,e in list(target.items()):
            online=offered.get(mid)
            if online and e['sha256']==online['sha256']: target[mid]=online
        if not target: raise ValueError('No required modules available')
        return self.stage(target,opener,cancel,progress,manual=True,repair=True)
    def stage_rollback(self,mid,opener,cancel,progress):
        current,_=self.read_set(self.state['active'])
        if mid:
            old=self.state['backup_entries'].get(mid)
            if not old or mid not in current or old['sha256']==current[mid]['sha256']: raise ValueError('No different previous version for '+mid)
            target=dict(current,**{mid:old}); holds=sorted(set(self.state['holds'])|{mid})
        else:
            if not self.state['has_previous']: raise ValueError('No previous compatible module set')
            target,_=self.read_set(self.state['previous'])
            holds=sorted(set(self.state['holds'])|{m for m,e in target.items() if current.get(m,{}).get('sha256')!=e['sha256']})
        return self.stage(target,opener,cancel,progress,manual=True,rollback=True,holds=holds)
    def module_rows(self,offered,retired,include_alpha):
        rows=super().module_rows(offered,retired,include_alpha)
        rows=[(mid,i,a,'On hold' if mid in self.state['holds'] and not status.startswith('Prepared') and mid not in retired else status) for mid,i,a,status in rows]
        if self.runtime:
            for mid,e in getattr(self.runtime,'local_entries',{}).items(): rows.append(('Third-party: '+mid,e['version'],'—','Unavailable' if mid in self.runtime.errors else 'Loaded · unofficial'))
            for mid,e in getattr(self.runtime,'local_failures',{}).items(): rows.append(('Third-party: '+mid,'—','—',e))
        return rows
    def load_third_party(self,runtime):
        runtime.local_entries={}; runtime.local_failures={}
        pending={}
        for p in sorted(self.third.glob('*.qmodule'))[:MAX_MODULES]:
            try:
                mid=valid_id(p.stem)
                if mid in runtime.entries: raise ValueError('Official module ID takes precedence')
                if p.is_symlink() or p.resolve().parent!=self.third.resolve() or not 0<p.stat().st_size<=MAX_MODULE_BYTES: raise ValueError('Unsafe local module file')
                raw=p.read_bytes(); tree=ast.parse(raw)
                metas=[ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MODULE' for t in n.targets)]
                if len(metas)!=1 or metas[0].get('id')!=mid: raise ValueError('Invalid local metadata')
                e=dict(metas[0],size=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                e=validate_entry(mid,e,False)
                if not self.compatible(e): raise ValueError('Incompatible API/core')
                pending[mid]=(p,raw,e); runtime.local_entries[mid]=e
            except Exception as exc: runtime.local_failures[p.stem]=str(exc)
        while pending:
            ready=[mid for mid,(_,_,e) in pending.items() if not set(e['dependencies'])&set(pending)]
            if not ready:
                for mid in pending: runtime.errors[mid]='Cyclic local dependencies'
                break
            for mid in ready:
                p,raw,e=pending.pop(mid)
                try:
                    for d,v in e['dependencies'].items():
                        dep=runtime.entries.get(d) or runtime.local_entries.get(d)
                        if d not in runtime.loaded or version(dep['version'])<version(v): raise ValueError('Missing dependency '+d)
                    mod=types.ModuleType('qm_local_'+mid); mod.__file__=str(p)
                    exec(compile(raw,str(p),'exec'),mod.__dict__)
                    runtime._register(mid,mod,mod.register()); runtime.loaded[mid]=mod
                except BaseException as exc:
                    runtime.errors[mid]=str(exc); logging.exception('Third-party module failed: %s',mid)
