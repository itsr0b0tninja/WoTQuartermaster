"""Production core model worker test: slow read, thread-owned SQLite, reset, session changes."""
from pathlib import Path
from types import SimpleNamespace
import importlib.machinery,importlib.util,sys,json,time,tempfile,threading,sqlite3
sys.path.insert(0,str(Path('desktop').resolve()))
loader=importlib.machinery.SourceFileLoader('qm_063','desktop/WoTQuartermaster_v0.6.3.txt')
spec=importlib.util.spec_from_loader(loader.name,loader);core=importlib.util.module_from_spec(spec);loader.exec_module(core)
class Runtime:
    def __init__(self):self.errors={};self.services={}
    def factory(self,*a):return None

def run():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);folder=root/'connector';folder.mkdir()
        def write(session,credits,diagnostic_session=None):
            now=time.time();d=dict(schema=1,connector_version='0.0.9',session=session,game_version='v',heartbeat_at=now,data={'credits':credits})
            ctx=dict(schema=1,connector_version='0.0.9',session=session,game_version='v',heartbeat_at=now,state='garage')
            diag=dict(schema=1,session=diagnostic_session or session,game_version='v',account={'credits':credits},sections={'garage':{'status':'ok','data':[]},'research':{'status':'ok','data':{}}})
            for k,x in [('connector',d),('battle_context',ctx),('diagnostics',diag)]:core.atomic_text(folder/(k+'.json'),json.dumps(x))
        write('s1',1234);m=core.BackgroundModel(root,Runtime());main=threading.get_ident();entered=threading.Event();release=threading.Event();count=[];original=core.Model._read;old_put=core.Store.put
        def blocked(p,k):
            assert threading.get_ident()!=main
            if k=='connector' and not entered.is_set():count.append(1);entered.set();assert release.wait(8)
            return original(p,k)
        def worker_put(store,k,value):assert threading.get_ident()!=main;return old_put(store,k,value)
        core.Model._read=blocked;core.Store.put=worker_put
        def wait(predicate):
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                start=time.monotonic();m.poll();assert time.monotonic()-start<.25
                if predicate():return
                time.sleep(.02)
            raise AssertionError((m.state,m.account,m.errors))
        try:
            start=time.monotonic();m.poll();assert time.monotonic()-start<.25;assert entered.wait(2)
            for _ in range(15):m.poll(True)
            assert count==[1] and m.state=='missing' and not m.account
            release.set();wait(lambda:m.state=='garage' and m.account.get('credits')==1234)
            assert m.store.get('connector')['data']['credits']==1234
            old=m.sources['diagnostics'];write('s2',4321,diagnostic_session='s1');wait(lambda:m.account.get('credits')==4321)
            assert old['session']=='s1' and m.sources['connector']['session']=='s2' and m.garage_data.status('garage')=='unavailable'
            write('s2',4321);wait(lambda:m.garage_data.status('garage')=='ok')
            m.reset_cache();assert m.store.get('connector')=={} and m.store.get('diagnostics')=={}
        finally:release.set();m.close();core.Model._read=original;core.Store.put=old_put
        # Closed worker cannot repopulate reset DB.
        with sqlite3.connect(root/'database'/'quartermaster.sqlite3') as conn:assert conn.execute('select count(*) from snapshots').fetchone()[0]==0
    print('PASS: non-blocking model reads, single flight, SQLite on worker, account isolation, reset drains writer')
if __name__=='__main__':run()
