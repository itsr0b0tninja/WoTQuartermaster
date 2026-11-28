"""Exercise actual Qt window, real module activation and compiled upgrade."""
import sys,os,json,subprocess,tempfile,importlib.machinery,importlib.util,time,threading,shutil,secrets,hashlib,io
from pathlib import Path
import publish_0_6_0 as p
import publish_performance_0_6_6 as release
from module_manager import validate_modules,check_set
from module_manager_online import ModuleManager

def assets(base):
    prior,_=validate_modules(json.loads(Path('components.json').read_text()));offered,_=validate_modules(release.proposed());raw={}
    for mid,e in prior.items():
        d=base/'assets'/mid;d.mkdir(parents=True)
        subprocess.check_call(['gh','release','download',e['release'],'--repo',release.REPO,'--pattern',e['asset'],'--dir',str(d)])
        raw[e['url']]=(d/e['asset']).read_bytes()
    for mid in release.VERSIONS:raw[offered[mid]['url']]=release.module_path(mid).read_bytes()
    return prior,offered,raw

def stage(base,offered,raw,core,product):
    mm=ModuleManager(base,core);mm.start();mm.offered_product=product
    assert mm.stage(mm.plan(offered,[]),lambda url:io.BytesIO(raw[url]),threading.Event())
    return mm.state['pending']

def ui():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    loader=importlib.machinery.SourceFileLoader('qm_063','desktop/WoTQuartermaster_v0.6.3.txt')
    spec=importlib.util.spec_from_loader(loader.name,loader);core=importlib.util.module_from_spec(spec);loader.exec_module(core)
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp);root=p.fixture_settings(base);prior,offered,raw=assets(base)
        check_set(offered,'0.6.3');stage(base,offered,raw,'0.6.3','0.6.6');os.environ['QT_QPA_PLATFORM']='offscreen'
        def exercise(w):
            assert w.runtime.ready(),w.runtime.errors
            assert isinstance(w.model,core.BackgroundModel)
            assert w.over_play_combo.count()==w.play_combo.count()==11
            for page in ('Garage','Depot','Finance','Progression','Map atlas','History','Overview'):w.navigate(page)
            assert w.runtime.ready(),w.runtime.errors
            w.timer.stop();w.thumb_timer.stop();w.update_timer.stop();w.check_timer.stop()
            real=w.model;real.drain();real._next_read=0
            model_entered=threading.Event();model_release=threading.Event();old_read=core.Model._read
            def slow_read(model,key):
                if key=='connector' and not model_entered.is_set():
                    model_entered.set();assert model_release.wait(5)
                return old_read(model,key)
            core.Model._read=slow_read;model_ticks=[];model_timer=QTimer();model_timer.timeout.connect(lambda:model_ticks.append(time.monotonic()));model_timer.start(20)
            try:
                w.model.poll();assert model_entered.wait(2)
                until=time.monotonic()+.35
                while time.monotonic()<until:
                    QApplication.processEvents();w.model.poll();time.sleep(.01)
                assert len(model_ticks)>=5
            finally:
                model_release.set();real.drain();model_timer.stop();core.Model._read=old_read
            saved_shared=sys.modules.get('module_shared');import test_progression_0_6_6 as t
            if saved_shared is not None:sys.modules['module_shared']=saved_shared
            test,sec=t.fixture(root);real=w.model;real.drain();w.model=test.model;w.model.context=None;w.bp_rows=[];w.prog_static=test.prog_static;w.prog_route_cache=None;w.prog_applied_key=None;w.prog_pending_key=None
            mod=w.runtime.loaded['progression'];calc=mod.calculate;release_event=threading.Event();entered=threading.Event();main=threading.get_ident();count=[]
            def blocked(proxy,force):
                assert threading.get_ident()!=main;entered.set();count.append(1);assert release_event.wait(5);return calc(proxy,force)
            mod.calculate=blocked
            timer=QTimer();ticks=[];timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start(20)
            def wait(expected):
                until=time.monotonic()+8
                while time.monotonic()<until:
                    QApplication.processEvents();w.coordinate_advice(False)
                    if w.next_action_title.text()==expected and w.prog_job is None:return
                    time.sleep(.01)
                raise AssertionError((expected,w.next_action_title.text(),w.runtime.errors))
            try:
                w.settings.values.update(playstyle=t.STYLE,advisor_mode='Full Advisor')
                start=time.monotonic();w.coordinate_advice(True);assert time.monotonic()-start<.25;assert entered.wait(2)
                end=time.monotonic()+.35
                while time.monotonic()<end:
                    QApplication.processEvents();w.coordinate_advice(True);time.sleep(.01)
                assert len(ticks)>=5 and len(count)==1 and w.next_action_title.text()=='Updating progression advice…'
                # A queued stale purchase recommendation must not be applied after credits change.
                w.model.account={'credits':0,'free_xp':0,'premium':False};release_event.set();wait('Earn credits');assert len(count)==2
                w.model.account={'credits':100000,'free_xp':0,'premium':False};wait('Review purchase budget for Tank 18')
                assert w.prog_finance_target['id']=='18' and w.prog_finance_target['budget_status']=='incomplete'
                w.runtime.loaded['finance'].refresh_finance(w,True);assert 'Budget incomplete' in w.fin_forecast_note.text()
                # Only the visible table is materialised.
                w.stack.setCurrentWidget(w.pages['Progression']);w.prog_tabs.setCurrentIndex(1);mod.flush_progression(w)
                assert w.prog_tables['Career'].rowCount()>=2
                w.settings.values['advisor_mode']='Information Only';wait('Information only')
                w.settings.values.update(advisor_mode='Full Advisor',playstyle='Brawler');w.coordinate_advice(True)
                until=time.monotonic()+8
                while w.prog_job is not None and time.monotonic()<until:QApplication.processEvents();w.coordinate_advice(False);time.sleep(.01)
                assert w.prog_job is None
                d=json.loads((root/'progression'/'careers.json').read_text());assert len(d['accounts']['a'*24]['careers'])==10
                w.model.sources['diagnostics']={'session':'stale','game_version':'v'};w.coordinate_advice(True);assert w.next_action_title.text()=='Waiting for live garage data'
                assert w.runtime.ready(),w.runtime.errors
            finally:
                release_event.set();timer.stop();mod.calculate=calc;w.model=real;w.settings.values['playstyle']='Passive Scout';w.settings.save()
        assert core.run_gui(base,test_callback=exercise)==0
    print('PASS: core 0.6.3 activation, Qt event loop responsive during worker, stale result rejection, visible tab rendering, all careers persisted')

def compiled():
    with tempfile.TemporaryDirectory(prefix='qm-066-') as tmp:
        base=Path(tmp);root=p.fixture_settings(base);prior,offered,raw=assets(base)
        old=base/'old';old.mkdir();subprocess.check_call(['gh','release','download','v0.6.2','--repo',release.REPO,'--pattern','WoTQuartermaster.exe','--dir',str(old)])
        target=base/'WoTQuartermaster.exe';shutil.copyfile(old/target.name,target)
        manifest=json.loads(Path('components.json').read_text());assert hashlib.sha256(target.read_bytes()).hexdigest()==manifest['components']['desktop']['sha256']
        prior_gen=stage(base,prior,raw,'0.6.2','0.6.5');mm=ModuleManager(base,'0.6.2');assert mm.start().ready();mm.confirm();assert mm.state['active']==prior_gen
        env=dict(os.environ,QT_QPA_PLATFORM='offscreen',PYINSTALLER_RESET_ENVIRONMENT='1');updates=base/'updates';staging=updates/'staging';staging.mkdir(parents=True,exist_ok=True)
        token=secrets.token_hex(16);runner=updates/('runner-'+token+'.exe');shutil.copyfile(target,runner);payload=Path('dist/WoTQuartermaster.exe').resolve();shutil.copyfile(payload,staging/target.name)
        parent=subprocess.Popen([sys.executable,'-c','import time; time.sleep(4)']);request=dict(token=token,parent=parent.pid,old_version='0.6.2',version='0.6.3',size=payload.stat().st_size,sha256=hashlib.sha256(payload.read_bytes()).hexdigest());(updates/('request-'+token+'.json')).write_text(json.dumps(request));helper=subprocess.Popen([str(runner),'--apply-update',token,str(parent.pid)],cwd=base,env=env)
        def stop():subprocess.run(['taskkill','/IM','WoTQuartermaster.exe','/T','/F'],capture_output=True,timeout=20);time.sleep(2)
        try:
            parent.wait(timeout=15);assert helper.wait(timeout=145)==0;assert json.loads((updates/'update-result.json').read_text())['status']=='success';assert hashlib.sha256(target.read_bytes()).hexdigest()==request['sha256'];assert hashlib.sha256((updates/'backups'/'WoTQuartermaster.previous.exe').read_bytes()).hexdigest()==manifest['components']['desktop']['sha256']
        finally:
            if helper.poll() is None:helper.kill();helper.wait(timeout=10)
            stop()
        (updates/'desktop.lock').unlink(missing_ok=True);new_gen=stage(base,offered,raw,'0.6.3','0.6.6');proc=subprocess.Popen([str(target)],cwd=base,env=env)
        try:
            deadline=time.monotonic()+75;state=base/'modules'/'module-state.json'
            while time.monotonic()<deadline:
                assert proc.poll() is None;st=json.loads(state.read_text())
                if st.get('active')==new_gen and not st.get('trial') and not st.get('pending'):break
                time.sleep(.5)
            else:raise AssertionError('New module not activated')
            time.sleep(3);log=(base/'logs'/'desktop.log').read_text(encoding='utf-8',errors='replace');assert 'Loaded external module progression 0.1.6' in log;assert 'Loaded external module finance 0.1.3' in log;assert not any(x in log for x in ('Module progression callback failed','Module progression unavailable','Fatal desktop error','Module trial UI failed','Progression worker failed'));assert 'playstyle = Passive Scout' in (base/'settings.ini').read_text();assert proc.poll() is None
        finally:
            stop()
            if proc.poll() is None:proc.wait(timeout=20)
    print('PASS: compiled 0.6.2 to 0.6.3 update, rollback executable preserved, progression 0.1.6 activated')
if __name__=='__main__':
    if '--compiled' in sys.argv:compiled()
    else:ui()
