"""Single-flight worker, stale-result and unchanged snapshot regression tests."""
import time,threading,tempfile
from pathlib import Path
from types import SimpleNamespace
import test_progression_0_6_6 as t
n=t.n

def wait(w, expected):
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        n['coordinate'](w)
        if w.next_action_title.text==expected and w.prog_job is None:return
        time.sleep(.01)
    raise AssertionError((expected,w.next_action_title.text))

def run():
    with tempfile.TemporaryDirectory() as tmp:
        w,sec=t.fixture(Path(tmp));w.prog_tabs=SimpleNamespace(tabText=lambda _: 'Career',currentIndex=lambda:0);page=object();w.pages={'Progression':page};w.stack=SimpleNamespace(currentWidget=lambda:page);w.prog_epoch=1;w.prog_pending_rows={};w.prog_applied_key=None;w.prog_route_cache=None
        # Fake deliberately slow worker; no UI calls are permitted off the main thread.
        calc=n['calculate'];entered=threading.Event();release=threading.Event();count=[];main=threading.get_ident()
        def slow(p,force):
            assert threading.get_ident()!=main;count.append(1);entered.set();assert release.wait(5);calc(p,force)
        n['calculate']=slow
        old_set=w.set_rows
        def ui(table,rows):assert threading.get_ident()==main;old_set(table,rows)
        w.set_rows=ui
        start=time.monotonic();n['coordinate'](w,True);assert time.monotonic()-start<.2;assert entered.wait(2)
        for _ in range(10):n['coordinate'](w,True)
        assert len(count)==1 and w.next_action_title.text=='Updating progression advice…'
        w.model.account={'credits':0,'free_xp':0,'premium':False};n['coordinate'](w,True)
        release.set();wait(w,'Earn credits');assert len(count)==2
        state=Path(tmp)/'progression'/'careers.json';assert state.exists()
        w.model.garage_signature='heartbeat-new';w.model.sources['diagnostics']={'session':'x','game_version':'v','revision':99}
        for _ in range(20):n['coordinate'](w,True)
        assert len(count)==2 and w.prog_job is None
        w.model.state='in_battle';n['coordinate'](w,True);assert len(count)==2
        w.model.state='garage';w.model.account={'credits':100000,'free_xp':0,'premium':False};n['coordinate'](w,True);wait(w,'Review purchase of Tank 18');assert len(count)==3
        w.model.sources['diagnostics']={'session':'stale','game_version':'v'};n['coordinate'](w);assert w.next_action_title.text=='Waiting for live garage data';assert w.prog_finance_target is None
        n['calculate']=calc
    print('PASS: non-blocking single worker, stale result discarded, heartbeat and force ignored, battle deferral, postbattle update and stale account protection')
if __name__=='__main__':run()
