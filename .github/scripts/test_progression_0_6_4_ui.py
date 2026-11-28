"""Activate the new pair using the real 0.6.1 core and its portable updater."""
import sys,os,json,subprocess,tempfile,importlib.machinery,importlib.util
from pathlib import Path
import publish_0_6_0 as p
import publish_progression_0_6_4 as release
from module_manager import validate_modules,check_set

def main():
    loader=importlib.machinery.SourceFileLoader('qm_061','desktop/WoTQuartermaster_v0.6.1.txt')
    spec=importlib.util.spec_from_loader(loader.name,loader);core=importlib.util.module_from_spec(spec);loader.exec_module(core)
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp);root=p.fixture_settings(base);prior,_=validate_modules(json.loads(Path('components.json').read_text()));offered,_=validate_modules(release.proposed());raw={}
        for mid,e in prior.items():
            if mid in release.VERSIONS:continue
            d=base/'assets'/mid;d.mkdir(parents=True)
            subprocess.check_call(['gh','release','download',e['release'],'--repo',release.REPO,'--pattern',e['asset'],'--dir',str(d)])
            raw[e['url']]=(d/e['asset']).read_bytes()
        for mid in release.VERSIONS:raw[offered[mid]['url']]=release.module_path(mid).read_bytes()
        check_set(offered,'0.6.1');p.stage_set(base,offered,raw,'0.6.1');os.environ['QT_QPA_PLATFORM']='offscreen'
        def exercise(w):
            assert w.runtime.ready(),w.runtime.errors
            assert w.over_play_combo.count()==w.play_combo.count()==11
            assert set(w.prog_tables)=={'Overview','Career','Technology Trees','Vehicles','Research','Garage & Depot','Data Quality'}
            assert set(w.fin_tables)=={'Overview','Vehicles','Transactions','Forecast'}
            for page in ('Garage','Depot','Finance','Progression','Map atlas','History','Overview'):w.navigate(page)
            assert w.runtime.ready(),w.runtime.errors
            # Use a synthetic fully scored catalogue, but exercise actual activated modules and Qt widgets.
            saved_shared=sys.modules.get('module_shared')
            import test_progression_0_6_4 as t
            if saved_shared is not None:sys.modules['module_shared']=saved_shared
            test,sec=t.fixture(root);real=w.model;w.model=test.model;w.model.context=None;w.bp_rows=[];w.prog_static=test.prog_static;w.prog_stamp=None;w.prog_route_cache=None
            try:
                w.settings.values.update(playstyle=t.STYLE,advisor_mode='Full Advisor')
                w.coordinate_advice(True)
                assert w.next_action_title.text()=='Review purchase budget for Tank 18',w.next_action_title.text()
                assert w.prog_tables['Career'].rowCount()>=2 and w.prog_finance_target['id']=='18'
                w.model.account['credits']=0;w.coordinate_advice(True);assert w.next_action_title.text()=='Earn credits',w.next_action_title.text()
                w.model.account['credits']=100000
                w.settings.values['advisor_mode']='Information Only';w.coordinate_advice(True);assert w.next_action_title.text()=='Information only'
                w.settings.values.update(advisor_mode='Full Advisor',playstyle='Brawler');w.coordinate_advice(True)
                d=json.loads((root/'progression'/'careers.json').read_text());assert len(d['accounts']['a'*24]['careers'])==10
                w.settings.values['playstyle']=t.STYLE;w.model.sources['diagnostics']['session']='stale';w.coordinate_advice(True);assert w.next_action_title.text()=='Waiting for live garage data'
            finally:w.model=real;w.settings.values['playstyle']='Passive Scout';w.settings.save()
            assert w.runtime.ready(),w.runtime.errors
        assert core.run_gui(base,test_callback=exercise)==0
    print('PASS: actual core 0.6.1 module activation, seven Progression tabs, navigation, purchase/saving, independent careers and stale data')
if __name__=='__main__':main()
