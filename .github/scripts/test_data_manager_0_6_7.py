import importlib.machinery,importlib.util,json,sys,tempfile,zipfile,types,hashlib
from pathlib import Path
# CI uses actual runtime; local standalone test provides equivalent atomic-write contract.
base=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(base/'desktop'))
try:import module_runtime
except ImportError:
    module_runtime=types.ModuleType('module_runtime')
    def atomic_bytes(path,raw):
        path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_bytes(raw);tmp.replace(path)
    module_runtime.atomic_bytes=atomic_bytes;sys.modules['module_runtime']=module_runtime
p=Path(__file__).with_name('data_manager.qmodule')
if not p.exists():p=base/'modules/data_manager/0.1.0/data_manager.qmodule'
l=importlib.machinery.SourceFileLoader('data_manager',str(p));spec=importlib.util.spec_from_loader(l.name,l);dm=importlib.util.module_from_spec(spec);l.exec_module(dm)
assert len(dm.REFERENCE['active_perks'])==43 and len({x['id'] for x in dm.REFERENCE['active_perks']})==43
assert len(dm.REFERENCE['equipment_family_candidates'])==89 and len(set(dm.REFERENCE['equipment_family_candidates'].values()))==17
assert len(dm.REFERENCE['consumable_candidates'])==50
for url in ['http://worldoftanks.eu/','https://evil.example','https://user@worldoftanks.eu/','https://worldoftanks.eu:444/']:
    try:dm.safe_url(url)
    except ValueError:pass
    else:raise AssertionError(url)
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);v='v.2.4.2.0 #1007';hashes=dm.REFERENCE['base_checksums'];ident={'version':v,'hashes':hashes};calls=[]
    def getter(url):
        calls.append(url)
        if url.endswith('specifications'):return b'{"results":[{"identity":{"tankId":4945},"specifications":{"gunArc":360}}]}'
        if url.endswith('changes'):raise TimeoutError()
        if url.endswith('.version_name'):return v.encode()
        return b'official public document'
    r=dm.refresh_sources(root,ident,'eu',getter=getter,now=100000);initial=len(calls)
    assert r['sources']['unicum_specs']['state']=='provisional' and r['sources']['unicum_changes']['state']=='retry'
    assert r['sources']['wg_vehicles']['state']=='blocked' and r['sources']['tanks_gg']['state']=='blocked'
    assert r['sources']['client_mirror']['verification']=='Exact mirror build matches'
    assert not any('account_id' in u for u in calls)
    r=dm.refresh_sources(root,ident,'eu',getter=getter,now=100060);assert len(calls)==initial
    r=dm.refresh_sources(root,ident,'eu',getter=getter,now=101000);assert len(calls)==initial+1
    original=(root/'current.json').read_bytes();ident2=dict(ident,version='v.2.4.3.0 #1008')
    r=dm.refresh_sources(root,ident2,'eu',getter=getter,now=101001);assert (root/'current.json').read_bytes()!=original
    assert len(list((root/'generations').iterdir()))==2 and r['sources']['client_mirror']['state']=='provisional'
    cat=types.SimpleNamespace(folder=root,manifest={'game_version':v,'files':{k:{'sha256':h} for k,h in hashes.items()}});ctx=types.SimpleNamespace(catalogue=cat)
    assert dm.reference(ctx) is dm.REFERENCE
    folder=root/'supplemental-audit-v1';folder.mkdir();k='4945';d={'vehicle_id':4945,'scope':'isolated_stock_preview','fit_scope':'stock_preview_only_not_purchase_eligibility','observed_account_key':'private','preview_shells':[{'intCD':123,'count':10}]}
    identity={'schema':1,'collector_version':'0.0.10','game_version':v,'base_checksums':hashes};rr={'identity':identity,'category':'vehicle','key':k,'finished':True,'data':d,'data_sha256':dm.digest(dm.canonical(d))};raw=dm.canonical(rr);f=folder/'vehicle-4945.json';f.write_bytes(raw)
    m=dict(identity,collection_finished=True,status='partial',files={'vehicle:4945':{'file':f.name,'sha256':dm.digest(raw)}});(folder/'manifest.json').write_bytes(dm.canonical(m))
    got=dm.record(ctx,'vehicle',k);assert got and got['preview_shells']==d['preview_shells'] and 'observed_account_key' not in got
    f.write_bytes(raw+b' ');assert dm.record(ctx,'vehicle',k) is None
    cat.manifest['game_version']='v.2.4.3.0 #1008';assert dm.reference(ctx) is None and dm.record(ctx,'vehicle',k) is None
    # Optional real user's audit validation; never upload test account data to CI.
    if len(sys.argv)>1:
        z=zipfile.ZipFile(sys.argv[1]);assert z.testzip() is None;z.extractall(root/'actual');cat.folder=root/'actual';cat.manifest['game_version']=v
        m=json.loads(z.read('supplemental-audit-v1/manifest.json'));n=0
        for entry in m['files']:
            category,item_id=entry.split(':',1);assert dm.record(ctx,category,item_id) is not None,entry;n+=1
        assert n==627;print('PASS 627/627 actual native supplemental records, exact hashes and identities')
print('PASS reference, source retry, build change, safe URL, record integrity, account data exclusion and stale rejection')
