"""Budget provenance, current-price precedence and single allocation of stock."""
from pathlib import Path
import tempfile,copy
import test_progression_0_6_6 as t
n=t.n;rows=t.rows
with tempfile.TemporaryDirectory() as tmp:
    w,sec=t.fixture(Path(tmp));g=w.model.garage_data;owned={'17':t.tank('17')};known={'1','2','17','18'}
    choices,_,_=n['all_careers'](rows,n['graph'](rows),t.scores,owned,known,{'17':0},g,{},[],{},balance=100000,reserve=10000)
    def quote(reserve=10000,live=None,scores=None):return n['quote'](g,rows,'18',None,owned,[],live or {},t.STYLE,scores or t.scores,known,choices[t.STYLE],choices,reserve)
    sec['current_shop_prices']={'prices':{'18':{'credits':17500},'501':{'credits':15},'601':{'credits':800}}}
    q=quote();assert q['purchase']==17500 and q['ammo']==75 and q['equipment']==800
    assert q['verified_subtotal']==27500 and q['estimated_subtotal']==10875 and q['planning_total']==38375 and not q['complete'],q
    assert next(x for x in q['budget_lines'] if x['label']=='Vehicle purchase')['status']=='verified'
    assert quote(None)['planning_total'] is None and 'Operating reserve' in quote(None)['unknown_lines']
    # A personal quote overrides even a current general shop price.
    assert quote(live={(None,'18'):{'target':{'personal_discount_price':{'credits':16000}}}})['purchase']==16000
    assert quote(live={(None,'18'):{'target':{'personal_discount_price':{'gold':100},'buy':{'credits':20000}}}})['purchase'] is None
    sec['current_shop_prices']['prices']['18']={'gold':500};assert quote()['purchase'] is None
    sec['current_shop_prices']['prices']['18']={'credits':17500};sec['current_shop_prices']['prices']['601']={'gold':100}
    assert n['item_price'](g,'equipment','601') is None
    sec['current_shop_prices']['prices']['601']={'credits':800};sec['current_shop_prices']['hidden_item_ids']=[601]
    assert not any(x['id']=='601' for x in quote()['equipment_items'])
    sec['current_shop_prices']['hidden_item_ids']=[]
    sec['account_extra']['free_vehicle_slots']=0;assert 'Garage slot' in quote()['unknown_lines'] and quote()['planning_total'] is None
    sec['account_extra']['free_vehicle_slots']=3
    # One depot shell allocation across initial load and a planned gun change.
    scores=copy.deepcopy(t.scores);stock=t.ids('18');up=copy.deepcopy(scores['18'][t.STYLE]['configurations'][1]);up['ids']['gun']='9999';up['fit']=65
    scores['18'][t.STYLE]['configurations']=[scores['18'][t.STYLE]['configurations'][0],up]
    known.add('9999');t.catdata['guns',False]['9999']={'default_buy':{'credits':1000}}
    sec['depot']['SHELL']['501']=15;sec['depot_details']['SHELL']['501']['count']=15
    q=quote(scores=scores);assert q['ammo']==0 and q['upgrade_plan']['upgrade_shell_reuse']==5 and q['upgrade_plan']['upgrade_ammo']==75,q
    assert sec['depot']['SHELL']['501']==15 # no mutation of real depot
    assert t.fin['forecast'](q['planning_total']-1,q['planning_total']-q['reserve'],q['reserve'],{'n':5,'average':1000,'high':1000,'low':1000})['shortfall']==1
    # Incomplete depot details do not allow speculative reuse.
    sec['depot_details']['SHELL']['501']['count']=12;q=quote(scores=scores);assert q['ammo']==150 and q['upgrade_plan']['upgrade_shell_reuse']==0
    print('PASS: live/discount/catalogue price evidence, currency safety, hidden items, separate subtotals, reserve and slots, single depot ammunition allocation, no mutation')
