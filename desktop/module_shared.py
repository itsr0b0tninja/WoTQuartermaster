from module_runtime import ModuleUnavailable
import hashlib, json, logging, time, io
from pathlib import Path
def obj(v): return v if isinstance(v,dict) else {}
def seq(v): return v if isinstance(v,list) else []
def key(v): return str(v) if v is not None else ''
def num(v): return isinstance(v,(int,float)) and not isinstance(v,bool)
def display(v):
    if v is None: return 'Unknown'
    if isinstance(v,bool): return 'Yes' if v else 'No'
    if isinstance(v,int): return f'{v:,}'
    if isinstance(v,float): return f'{v:,.2f}'.rstrip('0').rstrip('.')
    if isinstance(v,list): return ' / '.join(display(x) for x in v) if v else 'None recorded'
    if isinstance(v,dict): return '; '.join(str(k)+': '+display(x) for k,x in v.items()) if v else 'None recorded'
    return str(v)
def money(v):
    if not isinstance(v,dict): return 'Unknown'
    names={'credits':'credits','gold':'gold','crystal':'bonds','eventCoin':'event coins','bpcoin':'BP points','equipCoin':'equipment coins'}
    vals=[display(x)+' '+names.get(k,k) for k,x in v.items() if num(x) and x!=0]
    return ' + '.join(vals) if vals else ('0' if any(num(x) for x in v.values()) else 'Unknown')
def name(row, fallback='Unknown'):
    return obj(row).get('userName') or obj(row).get('display_name') or obj(row).get('name') or fallback

class Catalogue:
    """Checksum-verified lazy category reads from one matching generation."""
    def __init__(self, root):
        self.root=Path(root)/'catalogue'; self.rows={}; self.errors={}; self.identity=None; self.folder=None; self.manifest={}; self.enrich={}
    def refresh(self, version):
        try:
            pointer=json.loads((self.root/'manifest.json').read_text(encoding='utf-8-sig'))
            rel=pointer['relative_path'].replace('\\','/')
            if ':' in rel or Path(rel).is_absolute() or '..' in Path(rel).parts: raise ValueError('Unsafe catalogue path')
            folder=(self.root/rel).resolve()
            if not folder.is_relative_to(self.root.resolve()): raise ValueError('Unsafe catalogue path')
            manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8-sig'))
            if not version or pointer.get('schema')!=2 or pointer.get('status')!='complete' or pointer.get('game_version')!=version or manifest.get('schema')!=2 or manifest.get('status')!='complete' or manifest.get('game_version')!=version: raise ValueError('Matching complete catalogue unavailable')
            hashes={k:obj(v).get('sha256') for k,v in obj(manifest.get('files')).items()}
            enrich={}
            try:
                e=json.loads((folder/'enrichment-v1'/'manifest.json').read_text(encoding='utf-8-sig'))
                if e.get('schema')==1 and e.get('status') in ('complete','partial') and e.get('game_version')==version and e.get('base_checksums')==hashes: enrich=e
            except (OSError,ValueError,TypeError): pass
            ident=(str(folder),version,tuple(sorted(hashes.items())),tuple(sorted((k,obj(v).get('sha256')) for k,v in obj(enrich.get('files')).items())))
            if ident!=self.identity:
                self.rows={}; self.errors={}; self.identity=ident
            self.folder=folder; self.manifest=manifest; self.enrich=enrich
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as e:
            self.identity=None; self.folder=None; self.rows={}; self.manifest={}; self.enrich={}; self.errors={'catalogue':str(e)}
    def category(self,cat,enriched=False):
        if not cat or self.folder is None: return {}
        cache=(cat,enriched)
        if cache in self.rows: return self.rows[cache]
        manifest=self.enrich if enriched else self.manifest
        info=obj(obj(manifest.get('files')).get(cat))
        try:
            path=(self.folder/'enrichment-v1' if enriched else self.folder)/(cat+'.json')
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=info.get('sha256'): raise ValueError('Checksum mismatch')
            payload=json.loads(raw); rows=payload.get('rows')
            if not isinstance(rows,dict) or payload.get('category')!=cat or payload.get('schema')!=(1 if enriched else 2) or payload.get('game_version')!=manifest.get('game_version') or len(rows)!=info.get('count'): raise ValueError('Category identity mismatch')
            if enriched and payload.get('base_checksums')!=manifest.get('base_checksums'): raise ValueError('Enrichment mismatch')
            self.rows[cache]=rows; return rows
        except (OSError,ValueError,TypeError,AttributeError) as e:
            self.errors[str(cache)]=str(e); self.rows[cache]={}; return {}
    def item(self,cat,i,enriched=False): return obj(self.category(cat,enriched).get(key(i)))

class Snapshot:
    def __init__(self,root,runtime):
        self.runtime=runtime
        self.catalogue=Catalogue(root); self.diag={}; self.sections={}; self.vehicles={}; self.by_type={}; self.state='missing'; self.identity=None
    def refresh(self,diagnostics,connector,state):
        self.state=state
        d=obj(diagnostics); c=obj(connector)
        # No mixing account sessions or game builds; old snapshots remain on disk.
        if c and (d.get('session')!=c.get('session') or d.get('game_version')!=c.get('game_version')): d={}
        self.diag=d; self.sections=obj(d.get('sections'))
        self.catalogue.refresh(d.get('game_version'))
        self.vehicles={}; self.by_type={}
        for item in seq(self.section('garage')):
            v=obj(obj(item).get('vehicle')); inv=v.get('invID',obj(item).get('inventory_id'))
            if inv is not None and v.get('intCD') is not None:
                self.vehicles[key(inv)]=v; self.by_type.setdefault(key(v['intCD']),[]).append(key(inv))
    def section(self,n): return obj(self.sections.get(n)).get('data')
    def status(self,n): return obj(self.sections.get(n)).get('status','unavailable')

    def __getattr__(self,name):
        if name.startswith('_'): raise AttributeError(name)
        if name not in self.runtime.services: raise ModuleUnavailable('Module service unavailable: '+name)
        return lambda *a,**kw:self.runtime.invoke_service(self,name,*a,**kw)
