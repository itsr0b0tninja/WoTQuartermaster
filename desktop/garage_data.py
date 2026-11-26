"""Read-only garage and inventory projection. No recommendations or game mutations."""
import hashlib
import json
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

MODULES={'chassis':('Suspension','chassis','CHASSIS'),'turret':('Turret','turrets','TURRET'),'gun':('Gun','guns','GUN'),'engine':('Engine','engines','ENGINE'),'radio':('Radio','radios','RADIO'),'fuelTank':('Fuel tank','', 'FUEL_TANK')}
DEPOT={'CHASSIS':'chassis','TURRET':'turrets','GUN':'guns','ENGINE':'engines','FUEL_TANK':'','RADIO':'radios','OPTIONALDEVICE':'equipment','SHELL':'ammunition','EQUIPMENT':'consumables','BATTLE_BOOSTER':'boosters','CREW_BOOKS':'crew_books','CREW_SKINS':'','CUSTOMIZATION':'','DEMOUNT_KIT':'','RECERTIFICATION_FORM':'','MENTORING_LICENSE':'','LOOT_BOX':''}
DEPOT_LABEL={'CHASSIS':'Suspension','TURRET':'Turrets','GUN':'Guns','ENGINE':'Engines','FUEL_TANK':'Fuel tanks','RADIO':'Radios','OPTIONALDEVICE':'Equipment','SHELL':'Ammunition','EQUIPMENT':'Consumables','BATTLE_BOOSTER':'Battle boosters','CREW_BOOKS':'Crew books','CREW_SKINS':'Crew skins','CUSTOMIZATION':'Customization','DEMOUNT_KIT':'Demounting kits','RECERTIFICATION_FORM':'Recertification forms','MENTORING_LICENSE':'Mentoring licenses','LOOT_BOX':'Loot boxes'}
PARAMS=[('Firepower','Average damage','avgDamage',''),('Firepower','Damage per minute','avgDamagePerMinute',''),('Firepower','Average penetration','avgPiercingPower',' mm'),('Firepower','Reload','reloadTimeSecs',' s'),('Firepower','Aim time','aimingTime',' s'),('Firepower','Dispersion','shotDispersionAngle',''),('Survivability','Hit points','maxHealth',' HP'),('Survivability','Hull armour','hullArmor',' mm'),('Survivability','Turret armour','turretArmor',' mm'),('Mobility','Engine power','enginePower',' hp'),('Mobility','Power / weight','enginePowerPerTon',' hp/t'),('Mobility','Top speed','speedLimit',' km/h'),('Mobility','Reverse speed','rearSpeedLimit',' km/h'),('Mobility','Hull traverse','chassisRotationSpeed',' °/s'),('Spotting','View range','circularVisionRadius',' m'),('Spotting','Radio range','radioDistance',' m'),('Concealment','Stationary concealment','invisibilityStillFactor',' %'),('Concealment','Moving concealment','invisibilityMovingFactor',' %')]
def parameter(p,k,unit):
    v=obj(p).get(k)
    if k.startswith('invisibility'): v=obj(v).get('current')
    if v is None: return 'Unknown'
    if isinstance(v,list) and len(v)==1: v=v[0]
    return display(v)+unit

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

class Garage:
    def __init__(self,root):
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
    def inventory(self,cat,i):
        stock=obj(self.section('depot')).get(cat)
        if not isinstance(stock,dict): return None
        v=stock.get(key(i),0)
        return v if num(v) and v>=0 else None
    def depot_detail(self,cat,i): return obj(obj(obj(self.section('depot_details')).get(cat)).get(key(i))).get('item')
    def price(self,cat,i,account_item=None):
        r=obj(account_item)
        if isinstance(r.get('buy'),dict) and any(num(x) for x in r['buy'].values()): return money(r['buy'])+' (snapshot)'
        # Shop table shape is preserved for future pricing. Do not infer currencies
        # from unlabelled arrays or replace absent dynamic values with zero.
        p=obj(obj(self.section('current_shop_prices')).get('prices')).get(key(i))
        if isinstance(p,dict):
            for field in ('buy','price'):
                if isinstance(p.get(field),dict) and any(num(x) for x in p[field].values()): return money(p[field])+' (snapshot)'
            if any(num(p.get(k)) for k in ('credits','gold','crystal')): return money(p)+' (snapshot)'
        static=self.catalogue.item(cat,i).get('default_buy')
        return money(static)+' (catalogue default)' if isinstance(static,dict) and any(num(x) for x in static.values()) else 'Unknown'
    def edge_rows(self,v):
        path=obj(obj(self.section('progression')).get('owned_vehicle_paths')).get(key(v.get('invID')))
        if not isinstance(path,dict) or key(path.get('vehicle_id'))!=key(v.get('intCD')): return []
        return [e for e in seq(path.get('edges')) if isinstance(e,dict) and e.get('target_id') is not None]
    def performance(self,v):
        static=self.catalogue.item('vehicles',v.get('intCD'))
        current=obj(obj(self.section('configured_performance')).get(key(v.get('invID'))))
        if key(current.get('vehicle_id'))!=key(v.get('intCD')) or any(key(i)!=key(obj(obj(v.get('modules')).get(k)).get('intCD')) for k,i in obj(current.get('modules')).items()): current={}
        return obj(static.get('stock_parameters')),obj(current.get('parameters'))
    def overview(self,v):
        stock,current=self.performance(v)
        rows=[(group,title,parameter(stock,k,u),parameter(current,k,u)) for group,title,k,u in PARAMS]
        return [('Vehicle','Combat XP','—',display(v.get('combat_xp'))),('Vehicle','Purchase price','—',money(v.get('purchase_price'))),('Vehicle','Resale value','—',money(v.get('resale_price'))),('Vehicle','Personal discount price','—',money(v.get('personal_discount_price')))]+rows
    def modules(self,v):
        mounted=obj(v.get('modules')); static=self.catalogue.item('vehicles',v.get('intCD')); compat=obj(static.get('compatible_modules'))
        unlocked=obj(self.section('research')).get('unlocked_module_ids')
        initial=obj(self.section('research')).get('initial_unlocks')
        known=isinstance(unlocked,list)
        ids=set(map(key,seq(unlocked)))|set(map(key,seq(initial)))
        edges={key(e['target_id']):e for e in self.edge_rows(v)}
        tg=[x for x in seq(compat.get('turrets_and_guns')) if isinstance(x,dict)]
        options={'chassis':seq(compat.get('chassis')),'engine':seq(compat.get('engines')),'radio':seq(compat.get('radios')),'fuelTank':seq(compat.get('fuelTanks')),'turret':[x.get('turret') for x in tg],'gun':[i for x in tg for i in seq(x.get('guns'))]}
        current_turret=key(obj(mounted.get('turret')).get('intCD')); current_gun=key(obj(mounted.get('gun')).get('intCD'))
        out=[]
        for role,(title,cat,depot) in MODULES.items():
            current=obj(mounted.get(role)); cid=key(current.get('intCD'))
            candidates=list(dict.fromkeys(([cid] if cid else [])+[key(i) for i in options.get(role,[]) if i is not None]))
            if not candidates: out.append((title,'Unknown','Not reported','Unknown','Unknown','Unknown','Unknown')); continue
            for i in candidates:
                e=obj(edges.get(i)); target=obj(e.get('target')); base=self.catalogue.item(cat,i)
                owned=self.inventory(depot,i)
                if i==cid: status='Mounted'
                elif e.get('unlocked') is True or e.get('default_unlock') is True or i in ids: status='Researched'
                elif e.get('unlocked') is False or known: status='Locked prerequisites' if False in obj(e.get('prerequisite_unlocked')).values() else 'Research available' if e and all(x is True for x in obj(e.get('prerequisite_unlocked')).values()) else 'Not researched'
                else: status='Research unknown'
                fit='Mounted' if i==cid else 'Vehicle-compatible; fitting not tested'
                if role=='gun' and current_turret and tg and not any(key(x.get('turret'))==current_turret and i in map(key,seq(x.get('guns'))) for x in tg): fit='Requires another turret'
                if role=='turret' and current_gun and tg and not any(key(x.get('turret'))==i and current_gun in map(key,seq(x.get('guns'))) for x in tg): fit='Requires another gun'
                item=current if i==cid else target or base
                out.append((title,name(item,'ID '+i),status,display(owned),display(e.get('xp_raw')),self.price(cat,i,target or self.depot_detail(depot,i)),fit))
        return out
    def perk_name(self,s):
        n=obj(s).get('name')
        if not n: return 'Unknown perk'
        return name(self.catalogue.item('crew_perks',n,True),name(self.catalogue.item('crew_perks',n),n))
    def crew_slots(self,c):
        primary=c.get('role') or 'Unknown role'; skills=c.get('skills'); out=[]
        free_names=set(seq(c.get('freeSkillsNames')))
        for i,s in enumerate(seq(skills)):
            level=obj(s).get('level')
            out.append((primary,'Primary '+str(i+1),self.perk_name(s),display(level)+'%' if num(level) else 'Unknown','Trained' if num(level) and level>=100 else 'Training' if num(level) else 'Unknown'))
        available=c.get('newSkillsCount'); available=available[0] if isinstance(available,list) and available and type(available[0]) is int else None
        maxslots=c.get('maxSkillsCount')
        if isinstance(skills,list) and type(maxslots) is int and 0<=maxslots<=30:
            for i in range(len(skills),maxslots):
                status='Unknown' if available is None else 'Available to select' if i-len(skills)<available else 'Locked'
                out.append((primary,'Primary '+str(i+1),'—','—',status))
        elif not isinstance(skills,list): out.append((primary,'Primary','Unknown','Unknown','Unavailable'))
        bonus=obj(c.get('bonus_skills')); roles=list(dict.fromkeys([r for r in seq(c.get('combinedRoles')) if r!=primary]+list(bonus)))
        for role in roles:
            values=bonus.get(role); levels=c.get('bonusSlotsLevels'); count=obj(c.get('newBonusSkillsCountByRole')).get(role)
            remaining=count if type(count) is int else None
            for i in range(3):
                s=values[i] if isinstance(values,list) and i<len(values) else None
                if isinstance(s,dict):
                    level=s.get('level'); status='Trained' if num(level) and level>=100 else 'Training' if num(level) else 'Unknown'
                    out.append((role,'Bonus '+str(i+1),self.perk_name(s),display(level)+'%' if num(level) else 'Unknown',status))
                else:
                    if not isinstance(values,list) or i>=len(values): status='Unknown'
                    elif isinstance(levels,list) and i<len(levels) and levels[i] is None: status='Locked'
                    elif remaining is not None and remaining>0: status='Available to select'; remaining-=1
                    elif isinstance(levels,list) and i<len(levels) and num(levels[i]): status='Unselected'
                    else: status='Unknown'
                    out.append((role,'Bonus '+str(i+1),'—','—',status))
        return out
    def crew(self,v):
        rows=[]; crew=obj(self.section('crew'))
        for slot in seq(v.get('crew_slots')):
            sid=obj(slot).get('crew_id'); c=obj(crew.get(key(sid)))
            if not c or key(c.get('vehicleInvID'))!=key(v.get('invID')):
                rows.append(('Slot '+display(obj(slot).get('slot')),'—','—','—','—','Empty' if sid is None else 'Unavailable')); continue
            title=c.get('fullUserName') or ('Crew '+key(sid))
            rows.append((title,'Qualification',display(c.get('combinedRoles')),display(c.get('roleLevel'))+'%' if num(c.get('roleLevel')) else 'Unknown','Efficiency '+display(c.get('currentVehicleSkillsEfficiency')),'Crew XP '+display(c.get('free_crew_xp'))))
            rows.extend((title,*r) for r in self.crew_slots(c))
            if c.get('freeSkillsNames'): rows.append((title,'Free perks',display(c['freeSkillsNames']),'—','—','Recorded'))
        return rows
    def equipment(self,v):
        rows=[]; fitted=v.get('optDevices')
        cfg=obj(obj(self.section('configured_performance')).get(key(v.get('invID'))))
        if key(cfg.get('vehicle_id'))!=key(v.get('intCD')): cfg={}
        categories={key(obj(x).get('index')):obj(obj(x).get('slot')).get('categories') for x in seq(cfg.get('equipment_slots'))}
        fit=obj(obj(self.section('equipment_compatibility')).get(key(v.get('invID'))))
        if key(fit.get('vehicle_id'))!=key(v.get('intCD')): fit={}
        costs=obj(self.section('equipment_removal_costs'))
        for i,x in enumerate(seq(fitted)):
            cd=obj(x).get('intCD')
            rows.append(('Slot '+str(i+1),name(x,'Empty' if x is None else 'Unknown'), 'Mounted' if x else 'Empty',display(categories.get(key(i))),display(self.inventory('OPTIONALDEVICE',cd)) if cd is not None else '—',money(costs.get(key(cd))), '—'))
        if not isinstance(fitted,list): rows.append(('Slots','Unknown','Unavailable','—','—','—','—'))
        for cd,e in obj(fit.get('equipment')).items():
            e=obj(e); slots=seq(e.get('slots')); allowed=[str(i+1) for i,x in enumerate(slots) if obj(x).get('allowed') is True]
            if not allowed and e.get('installed') is not True: continue
            item=self.catalogue.item('equipment',cd); transfers=[name(other) for other in self.vehicles.values() if other is not v and any(key(obj(x).get('intCD'))==cd for x in seq(other.get('optDevices')))]
            rows.append(('Compatible',name(item,'ID '+cd),'Mounted' if e.get('installed') is True else 'Allowed slots '+', '.join(allowed),'Current fit only',display(self.inventory('OPTIONALDEVICE',cd)),money(costs.get(cd)),self.price('equipment',cd,self.depot_detail('OPTIONALDEVICE',cd))+(' · mounted on '+', '.join(transfers) if transfers else '')))
        return rows
    def ammunition(self,v):
        gun=obj(obj(v.get('modules')).get('gun')).get('intCD')
        shots=seq(self.catalogue.item('guns',gun,True).get('shots'))
        shots_by={key(obj(x).get('shell_id')):obj(x) for x in shots if obj(x).get('shell_id') is not None}
        load=v.get('shells_layout'); installed=v.get('shells')
        # Explicit layout counts take precedence, including zero; unknown remains unknown.
        counts={key(obj(x).get('intCD')):obj(x).get('count') for x in seq(installed) if obj(x).get('intCD') is not None}
        counts.update({key(obj(x).get('intCD')):obj(x).get('count') for x in seq(load) if obj(x).get('intCD') is not None})
        ids=list(dict.fromkeys(list(shots_by)+list(counts)+[key(i) for i in seq(self.catalogue.item('guns',gun).get('shell_ids'))]))
        out=[]
        kinds={'ARMOR_PIERCING':'AP','ARMOR_PIERCING_CR':'APCR','HIGH_EXPLOSIVE':'HE','HOLLOW_CHARGE':'HEAT'}
        for cd in ids:
            item=self.catalogue.item('ammunition',cd); p=obj(item.get('parameters')); shot=shots_by.get(cd,{})
            kind=obj(item.get('descriptor_fields')).get('kind') or item.get('type')
            pen=shot.get('piercingPower')
            out.append((name(item,next((name(x,'ID '+cd) for x in seq(installed) if key(obj(x).get('intCD'))==cd),'ID '+cd)),kinds.get(kind,kind or 'Unknown'),display(counts.get(cd)),display(p.get('avgDamage')),display(pen if pen is not None else p.get('avgPiercingPower')),display(shot.get('speed')),display(self.inventory('SHELL',cd)),self.price('ammunition',cd,self.depot_detail('SHELL',cd))))
        return out
    def consumables(self,v):
        rows=[]
        for i,x in enumerate(seq(v.get('consumables'))):
            cd=obj(x).get('intCD'); rows.append((str(i+1),name(x,'Empty' if x is None else 'Unknown'),display(self.inventory('EQUIPMENT',cd)) if cd is not None else '—',self.price('consumables',cd,self.depot_detail('EQUIPMENT',cd)) if cd is not None else '—'))
        return rows
    def progression(self,v):
        out=[]
        for e in self.edge_rows(v):
            cd=e['target_id']; target=obj(e.get('target')); cat='vehicles' if target.get('item_type_name')=='vehicle' or target.get('tier') is not None else ''
            status='Researched' if e.get('unlocked') is True or e.get('default_unlock') is True else 'Locked prerequisites' if False in obj(e.get('prerequisite_unlocked')).values() else 'Available to research' if e.get('unlocked') is False and isinstance(e.get('prerequisite_unlocked'),dict) and all(x is True for x in e['prerequisite_unlocked'].values()) else 'Unknown'
            price=money(target.get('personal_discount_price')) if isinstance(target.get('personal_discount_price'),dict) and any(num(x) for x in target['personal_discount_price'].values()) else self.price(cat,cd,target)
            out.append((name(target,name(self.catalogue.item(cat,cd),'ID '+key(cd))), 'Vehicle' if cat else target.get('item_type_name') or 'Module / unknown',status,display(e.get('xp_raw')),display(target.get('blueprint_adjusted_xp')),price,display(e.get('prerequisite_ids'))))
        return out
    def depot_rows(self,category=None):
        stock=obj(self.section('depot')); out=[]
        for cat,label in DEPOT_LABEL.items():
            if category and cat!=category: continue
            data=stock.get(cat)
            if not isinstance(data,dict): out.append((label,'Unavailable','Unknown','—','—')); continue
            if not data: out.append((label,'No stock recorded','0','—','—')); continue
            for cd,count in data.items():
                detail=obj(self.depot_detail(cat,cd)); item=detail or self.catalogue.item(DEPOT[cat],cd)
                out.append((label,name(item,'ID '+cd),display(count),self.price(DEPOT[cat],cd,detail),money(detail.get('sell'))))
        return out
    def barracks(self):
        return [(c.get('fullUserName') or 'Crew '+i,display(c.get('combinedRoles')),display(c.get('roleLevel')),display(c.get('free_crew_xp'))) for i,c in obj(self.section('crew')).items() if isinstance(c,dict) and c.get('isInTank') is False and c.get('isDismissed') is False]
