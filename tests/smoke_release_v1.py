"""Bounded assembled-runtime release smoke, not a frozen model-quality evaluation.

Actual reference GGUF, authenticated HTTP/frontend, process restart, rollback and resources.
All sources/data are synthetic and temporary. No external retrieval or holdout execution.
"""
import argparse
from contextlib import contextmanager, closing
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]


def serve(args):
    import uvicorn
    from dwindy.api import create_app
    from dwindy.config import load_config
    from dwindy.llama_backend import LlamaBackend
    from dwindy.server import ApiConfig
    from reach_support import no_network
    class Recorded(LlamaBackend):
        def generate(self,messages,options):
            with Path(args.audit).open('a',encoding='utf-8') as f:
                f.write(json.dumps([dict(role=m.role,content=m.content) for m in messages])+'\n')
            yield from super().generate(messages,options)
    model=load_config(args.config);backend=Recorded(model)
    app=create_app(model,ApiConfig(port=args.port,database_path=args.database,
                   retrieval_index_path=args.index),backend=backend,chat_root=ROOT)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=args.port,ws='none',
        proxy_headers=False,access_log=False,log_level='critical'))
    def stop():
        sys.stdin.readline();server.should_exit=True
    threading.Thread(target=stop,daemon=True).start()
    with no_network(allow_loopback=True) as outbound:
        server.run()
        assert not outbound
    assert backend._model is None


@contextmanager
def server(args,folder,database,index,audit,token):
    import httpx
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    env=dict(os.environ,DWINDY_API_TOKEN=token)
    with (folder/'server.log').open('a',encoding='utf-8') as log:
        start=time.perf_counter()
        process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--serve',
            '--config',str(Path(args.config).resolve()),'--port',str(port),'--database',str(database),
            '--index',str(index),'--audit',str(audit)],env=env,stdin=subprocess.PIPE,stdout=log,stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=180,trust_env=False) as client:
                deadline=time.monotonic()+120
                while True:
                    if process.poll() is not None:raise AssertionError('Startup failed: '+(folder/'server.log').read_text()[-2000:])
                    try:
                        unauthorized=client.get('/v1/health')
                        if unauthorized.status_code==401:break
                    except httpx.TransportError:pass
                    if time.monotonic()>deadline:raise AssertionError('Startup timeout')
                    time.sleep(.1)
                client.headers['Authorization']='Bearer '+token
                health=client.get('/v1/health');health.raise_for_status()
                yield client,process,time.perf_counter()-start
        finally:
            process.communicate(input=b'stop\n',timeout=30)
            assert process.returncode==0,(folder/'server.log').read_text()[-2000:]


def ask(client,message,**kwargs):
    start=time.perf_counter();first=None;started=None;completed=None;text=[];event=None
    with client.stream('POST','/v1/chat',json=dict(message=message,stream=True,**kwargs)) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith('event: '):event=line[7:]
            if not line.startswith('data: '):continue
            value=json.loads(line[6:])
            if event=='started':started=value
            if event=='delta':
                if first is None:first=time.perf_counter()-start
                text.append(value['text'])
            if event=='completed':completed=value
            if event=='error':raise AssertionError(value)
    assert started and completed and ''.join(text).strip()
    return dict(started=started,completed=completed,text=''.join(text),ttft_s=first,
                total_s=time.perf_counter()-start)


def stored(database,key):
    with closing(sqlite3.connect(database)) as db:
        return list(db.execute('SELECT user_text,assistant_text FROM turns WHERE conversation_id=? ORDER BY turn_number',(key,)))


def run(args):
    import psutil
    from dwindy.project import synchronize
    from dwindy.retrieval import RetrievalIndex
    from dwindy.evidence import quoted
    from browser_driver import launch_browser
    from browser_checks import submit,completed
    results={'reference_config':str(Path(args.config).resolve()),'network_calls':0,'checks':{},'turns':[]}
    with tempfile.TemporaryDirectory(prefix='dwindy-release-') as folder:
        root=Path(folder);host=root/'host';host.mkdir();(host/'docs').mkdir()
        (host/'README.md').write_text('# Cedar Desk\nCedar Desk loans last nine days.\n',encoding='utf-8')
        (host/'docs'/'returns.md').write_text('Cedar Desk returns are accepted at the north counter.\n',encoding='utf-8')
        (root/'ordinary.txt').write_text('The Vale store locker identifier is V-19.\n',encoding='utf-8')
        (root/'documents.toml').write_text('[[documents]]\nid="vale"\npath="ordinary.txt"\nname="Vale locker"\n',encoding='utf-8')
        project=root/'project.toml';project.write_text('project_id="cedar"\nname="Cedar Desk"\nroot="host"\nindex_path="index.sqlite3"\ndocuments_manifest="documents.toml"\n',encoding='utf-8')
        dry=synchronize(project,dry_run=True);assert not (root/'index.sqlite3').exists()
        snapshot=synchronize(project);index=root/'index.sqlite3';database=root/'conversation.db';audit=root/'packets.jsonl'
        token=secrets.token_urlsafe(32);rss=[];stop=threading.Event()
        def monitor(process):
            parent=psutil.Process(process.pid)
            while not stop.wait(.05):
                try:rss.append(max(p.memory_info().rss for p in (parent,*parent.children(recursive=True))))
                except psutil.Error:pass
        with server(args,root,database,index,audit,token) as (client,process,startup):
            results['startup_s']=startup;thread=threading.Thread(target=monitor,args=(process,),daemon=True);thread.start()
            health=client.get('/v1/health').json();assert health['persistence_enabled'] and health['project_snapshot']['snapshot_id']==snapshot['snapshot_id']
            assert str(host).casefold() not in json.dumps(health).casefold()
            assert 'reach_enabled' not in health
            plain=ask(client,'Remember CEDAR as my code word. Reply briefly.',retrieval=False,reach=False)
            key=plain['started']['conversation_id'];results['turns'].append(plain)
            docs=ask(client,'What is the Vale store locker identifier? Reply briefly.',retrieval=True,reach=False)
            project_turn=ask(client,'How long are Cedar Desk loans? Reply briefly.',retrieval=True,reach=False)
            for observation in (docs,project_turn):
                meta=observation['started']['retrieval'];assert meta['status']=='supplied'
                packet=json.loads(audit.read_text().splitlines()[-1 if observation is project_turn else -2])
                with closing(RetrievalIndex(index)) as search:
                    sources={p.source.chunk_id:p for p in search.search(observation is docs and 'Vale store locker identifier' or 'Cedar Desk loans',12)}
                for source in meta['sources']:
                    p=sources[source['chunk_id']];assert source==p.source.mapping()
                    assert any(quoted(p.text) in m['content'] for m in packet)
                results['turns'].append(observation)
            before=stored(database,key);event=None;cancelled=False
            with client.stream('POST','/v1/chat',json=dict(message='Write a long story about a forest.',conversation_id=key,retrieval=False,reach=False,stream=True)) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith('event: '):event=line[7:]
                    if event=='delta' and line.startswith('data: '):cancelled=True;break
            assert cancelled
            deadline=time.monotonic()+30
            while client.get('/v1/health').json()['busy'] and time.monotonic()<deadline:time.sleep(.05)
            assert not client.get('/v1/health').json()['busy'];assert stored(database,key)==before
            results['checks']['cancellation_rollback']=True
            with launch_browser(args.browser) as browser:
                browser.navigate(str(client.base_url).rstrip('/')+'/chat/')
                browser.wait("!!document.querySelector('dwindy-chat')?.shadowRoot?.querySelector('link')?.sheet")
                browser.evaluate('globalThis.chat=document.querySelector("dwindy-chat");chat.bearerToken='+json.dumps(token))
                browser.wait("!chat.$('.persistence').hidden")
                assert browser.evaluate("chat.$('.reach-setting').hidden")
                browser.evaluate("chat.$('.use-retrieval').checked=false")
                submit(browser,'Reply briefly with a greeting.');assert completed(browser).strip()
                browser.evaluate('chat.resetConversation()')
                browser.wait("chat.$('.messages').children.length===0")
            results['checks']['authenticated_frontend_reset']=True
            stop.set();thread.join();assert len(audit.read_text().splitlines())==5
        assert stored(database,key)==before
        with server(args,root,database,index,audit,token) as (client,process,startup):
            resumed=ask(client,'What code word did I ask you to remember? Reply briefly.',conversation_id=key,retrieval=False,reach=False)
            packet=json.loads(audit.read_text().splitlines()[-1])
            native=[m for m in packet if m['role']!='system']
            assert native[:2]==[dict(role='user',content=before[0][0]),dict(role='assistant',content=before[0][1])]
            assert len(stored(database,key))==2
            results['turns'].append(resumed);results['restart_startup_s']=startup
            assert client.delete('/v1/conversations/'+key).status_code==204;assert not stored(database,key)
            missing=client.post('/v1/chat',json=dict(message='hello',conversation_id=key));assert missing.status_code==404
            results['checks']['restart_restore_delete']=True
        assert len(audit.read_text().splitlines())==6
        (host/'docs'/'returns.md').unlink();(host/'README.md').write_text('# Cedar Desk\nCedar Desk loans last ten days.\n',encoding='utf-8')
        changed=synchronize(project);assert changed['snapshot_id']!=snapshot['snapshot_id']
        with closing(RetrievalIndex(index)) as search:
            assert any('ten days' in p.text for p in search.search('Cedar loans',12))
            assert not search.search('north counter',12)
        results['checks'].update(project_dry_run_sync_update_delete=True,exact_source_packet_identity=True,
                                one_generation_per_turn=True,offline_operation=True,persistence_transience=True)
        with closing(sqlite3.connect(database)) as db:
            for user,answer in db.execute('SELECT user_text,assistant_text FROM turns'):
                assert 'Local entries:' not in user and 'WEB/text' not in user
        results['peak_model_process_rss_bytes']=max(rss)
        results['available_machine_ram_bytes']=psutil.virtual_memory().total
    print(json.dumps(results,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--browser',type=Path)
    p.add_argument('--serve',action='store_true');p.add_argument('--port',type=int);p.add_argument('--database');p.add_argument('--index');p.add_argument('--audit')
    args=p.parse_args();serve(args) if args.serve else run(args)
