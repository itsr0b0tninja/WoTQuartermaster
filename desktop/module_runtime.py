"""WoTQuartermaster Module API 1. Official runtime Python source, not a sandbox."""
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import types
from pathlib import Path

API=1
MAX_MODULE_BYTES=2*1024*1024
class ModuleUnavailable(RuntimeError): pass

def resource_folder():
    if getattr(sys,'frozen',False): return Path(sys._MEIPASS)/'runtime_modules'
    here=Path(__file__).resolve().parent
    return here/'runtime_modules' if (here/'runtime_modules').is_dir() else here/'desktop'/'runtime_modules'

def atomic_bytes(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.qm-',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def version(v):
    if not isinstance(v,str) or not re.fullmatch(r'(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})\.(0|[1-9]\d{0,3})',v): raise ValueError('Invalid module version')
    return tuple(map(int,v.split('.')))

class Runtime:
    def __init__(self,base,core_version,resources=None):
        self.base=Path(base).resolve(); self.folder=self.base/'modules'
        self.resources=Path(resources) if resources else resource_folder()
        self.core_version=core_version; self.entries={}; self.loaded={}; self.errors={}; self.services={}; self.views={}; self.hooks={}; self.pages=[]; self.tabs={}; self.factories={}
        self.initialized=False; self.failed_callbacks=set()
    def _check_folder(self):
        if self.folder.is_symlink() or self.folder.resolve().parent!=self.base: raise ValueError('Unsafe module folder')
        self.folder.mkdir(parents=True,exist_ok=True)
    def _path(self,mid):
        path=self.folder/(mid+'.qmodule')
        if path.is_symlink() or path.resolve().parent!=self.folder.resolve(): raise ValueError('Unsafe module path')
        return path
    def _read(self,path,e):
        if path.stat().st_size!=e['size'] or e['size']>MAX_MODULE_BYTES: raise ValueError('Module size mismatch')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=e['sha256']: raise ValueError('Module checksum mismatch')
        return raw
    def _index(self):
        # The trusted index and bootstrap bytes are build resources, NOT editable
        # installation metadata. 0.3.2 will add independently verified releases.
        data=json.loads((self.resources/'index.json').read_text(encoding='utf-8'))
        if data.get('schema')!=1 or data.get('api')!=API or not isinstance(data.get('modules'),dict): raise ValueError('Unsupported bootstrap index')
        entries={}
        for mid,e in data['modules'].items():
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,39}',mid) or not isinstance(e,dict): raise ValueError('Invalid module ID')
            if e.get('api')!=API or version(e['min_core'])>version(self.core_version): raise ValueError('Unsupported module API/core')
            version(e['version'])
            if not re.fullmatch(r'[0-9a-f]{64}',e.get('sha256','')) or type(e.get('size')) is not int or not 0<e['size']<=MAX_MODULE_BYTES: raise ValueError('Invalid module digest/size')
            deps=e.get('dependencies')
            if not isinstance(deps,dict): raise ValueError('Invalid dependencies')
            for name,v in deps.items(): version(v)
            entries[mid]=e
        return entries
    def bootstrap(self):
        self.entries=self._index(); self._check_folder()
        marker=self.folder/'installed.json'
        if marker.is_symlink(): raise ValueError('Unsafe module metadata')
        if marker.exists(): return
        # Initial offline installation, never overwrite pre-existing files.
        for mid,e in self.entries.items():
            try:
                dest=self._path(mid)
                if not dest.exists(): atomic_bytes(dest,self._read(self.resources/(mid+'.qmodule'),e))
            except Exception as exc: self.errors[mid]='Bootstrap: '+str(exc)
        atomic_bytes(marker,json.dumps({'schema':1,'bootstrap_core':self.core_version,'modules':{k:v['version'] for k,v in self.entries.items()}},indent=2).encode())
    def load(self):
        try: self.bootstrap()
        except Exception as exc:
            self.errors['runtime']=str(exc); logging.exception('Module bootstrap unavailable'); return self
        pending=dict(self.entries)
        while pending:
            progress=False
            for mid,e in list(pending.items()):
                deps=e['dependencies']
                if any(d in pending and d!=mid for d in deps): continue
                del pending[mid]; progress=True
                try:
                    for d,v in deps.items():
                        if d not in self.loaded or version(self.entries[d]['version'])<version(v): raise ModuleUnavailable('Required module unavailable: '+d)
                    path=self._path(mid); raw=self._read(path,e)
                    module=types.ModuleType('qm_runtime_'+mid); module.__file__=str(path)
                    # No import from the module directory, no bytecode or __pycache__.
                    exec(compile(raw,str(path),'exec'),module.__dict__)
                    meta=module.MODULE
                    for k in ('api','version','min_core','dependencies'):
                        if meta.get(k)!=e[k]: raise ValueError('Module metadata mismatch: '+k)
                    if meta.get('id')!=mid: raise ValueError('Module ID mismatch')
                    reg=module.register()
                    if not isinstance(reg,dict): raise ValueError('Invalid module registration')
                    self._register(mid,module,reg); self.loaded[mid]=module
                    self.errors.pop(mid,None)
                    logging.info('Loaded external module %s %s from %s',mid,e['version'],path)
                except Exception as exc:
                    self.errors[mid]=str(exc); logging.exception('Module %s unavailable',mid)
            if not progress:
                for mid in pending: self.errors[mid]='Unresolved or cyclic dependency'
                break
        self.initialized=True
        return self
    def _register(self,mid,module,reg):
        # Validate registration before mutating any shared registry.
        maps=[('services',self.services),('views',self.views),('factories',self.factories)]
        for field,target in maps:
            value=reg.get(field,{})
            if not isinstance(value,dict) or any(k in target or not isinstance(k,str) or not k.isidentifier() or not callable(f) for k,f in value.items()): raise ValueError('Invalid or duplicate '+field)
        hooks=reg.get('hooks',{})
        if not isinstance(hooks,dict) or any(k not in ('refresh','reset','thumbnail','navigate') or not callable(f) for k,f in hooks.items()): raise ValueError('Invalid hooks')
        pages=reg.get('pages',[])
        known={p['name'] for p in self.pages}|{'Overview','Settings','Updates'}
        for p in pages:
            if not isinstance(p,dict) or not isinstance(p.get('name'),str) or p['name'] in known or type(p.get('order')) is not int or not callable(p.get('build')): raise ValueError('Invalid or duplicate page')
            known.add(p['name'])
        tabs=reg.get('tabs',[])
        seen={(group,t['title']) for group,ts in self.tabs.items() for t in ts}
        for t in tabs:
            pair=(t.get('group'),t.get('title'))
            if pair in seen or not all(isinstance(x,str) and x for x in pair) or type(t.get('order')) is not int or not isinstance(t.get('headers'),list) or not all(isinstance(x,str) for x in t['headers']) or not isinstance(t.get('service'),str): raise ValueError('Invalid or duplicate tab')
            seen.add(pair)
        for field,target in maps:
            target.update({k:(mid,f) for k,f in reg.get(field,{}).items()})
        for event,f in hooks.items(): self.hooks.setdefault(event,[]).append((mid,f))
        self.pages.extend(dict(p,module=mid) for p in pages)
        for t in tabs: self.tabs.setdefault(t['group'],[]).append(dict(t,module=mid))
    def ready(self): return bool(self.entries) and set(self.loaded)==set(self.entries) and not self.errors
    def bind_ui(self,window,helpers):
        for module in self.loaded.values(): module.__dict__.update(helpers)
        for name,(mid,fn) in self.views.items():
            if hasattr(window,name):
                self.errors[mid]='View name collides with core: '+name
                continue
            def invoke(*a,_mid=mid,_fn=fn,**kw): return self.safe(_mid,_fn,window,*a,**kw)
            setattr(window,name,invoke)
    def safe(self,mid,fn,*a,**kw):
        callback=(mid,fn)
        if callback in self.failed_callbacks: return None
        try: return fn(*a,**kw)
        except Exception as exc:
            self.failed_callbacks.add(callback); self.errors[mid]='Runtime: '+str(exc); logging.exception('Module %s callback failed',mid); return None
    def dispatch(self,event,window,*args):
        for mid,fn in self.hooks.get(event,[]): self.safe(mid,fn,window,*args)
    def tab_specs(self,group):
        return sorted(self.tabs.get(group,[]),key=lambda t:t['order'])
    def invoke_service(self,context,name,*a,**kw):
        pair=self.services.get(name)
        if not pair: raise ModuleUnavailable('Module service unavailable: '+name)
        mid,fn=pair
        try: return fn(context,*a,**kw)
        except ModuleUnavailable: raise
        except Exception as exc:
            self.errors[mid]='Service: '+str(exc); logging.exception('Module %s service failed',mid); raise ModuleUnavailable(mid+': '+str(exc)) from exc
    def factory(self,name,*a):
        pair=self.factories.get(name)
        return self.safe(pair[0],pair[1],*a) if pair else None
    def repair(self):
        # Only restore known official filenames, never touch unowned files.
        if not self.entries: raise ValueError('No verified bootstrap index available')
        self._check_folder()
        for mid,e in self.entries.items():
            dest=self._path(mid)
            try: self._read(dest,e); continue
            except (OSError,ValueError): pass
            atomic_bytes(dest,self._read(self.resources/(mid+'.qmodule'),e))
    def status_text(self):
        lines=[]
        for mid,e in self.entries.items():
            lines.append(mid.capitalize()+' '+e['version']+' — '+('Unavailable: '+self.errors[mid] if mid in self.errors else 'Loaded' if mid in self.loaded else 'Not loaded'))
        if 'runtime' in self.errors: lines.append(self.errors['runtime'])
        return '\n'.join(lines) or 'No module index available'
