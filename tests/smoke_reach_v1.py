"""Five approved live infrastructure checks. No model-output or H2 scoring.

Uses a recording model-free backend so actual Core preparation is the supply oracle.
Run the assembled-runtime smoke separately with the reference GGUF.
"""
import json
from pathlib import Path
import time
import argparse

from dwindy.api import create_app
from dwindy.config import Config
from dwindy.server import ApiConfig
from test_api_http import live_server
from test_terminal import FakeBackend


def run(config=None):
    model = Config(Path('unused.gguf'), max_tokens=256)
    backend = FakeBackend(limit=4096)
    if config:
        from dwindy.config import load_config
        from dwindy.llama_backend import LlamaBackend
        model = load_config(config)
        class Recorded(LlamaBackend):
            def __init__(self, config):
                super().__init__(config); self.requests=[]
            def generate(self, messages, options):
                self.requests.append(list(messages))
                yield from super().generate(messages, options)
        backend = Recorded(model)
    app = create_app(model,
                     ApiConfig(reach_provider='wikipedia', reach_default='auto'), backend=backend)
    observations = []
    checks = [('python','What is the latest stable version of Python?', 'auto'),
              ('president','Who is the current president of the Philippines?', 'auto'),
              ('android','What is the latest version of Android?', 'auto'),
              ('ordinary','What is photosynthesis?', 'auto'),
              ('off','What is the latest stable version of Python?', False)]
    with live_server(app, startup_timeout=120) as (client, _, __):
        client.timeout=180
        for i,(name,message,mode) in enumerate(checks):
            if 0 < i < 3:
                time.sleep(6)  # Deliberate lookups, no retries or burst traffic.
            start=time.perf_counter()
            reply=client.post('/v1/chat',json=dict(message=message, reach=mode))
            reply.raise_for_status();data=reply.json();meta=data['reach']
            packet=backend.requests[-1]
            record=dict(check=name,message=message,reach=meta,elapsed_ms=(time.perf_counter()-start)*1000,
                        prompt_tokens=data['usage']['prompt_tokens'],model_packet=[dict(role=m.role,content=m.content) for m in packet])
            assert len(backend.requests)==i+1
            assert meta['supplied']==bool(meta['supplied_entry_ids'])
            assert not meta['sources'] or meta['state']=='supplied'
            if name in ('ordinary','off'):assert not meta['attempted'] and not meta['sources']
            elif config: assert meta['state']=='supplied', meta
            observations.append(record);print(json.dumps(record,ensure_ascii=False),flush=True)
    return observations


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config')
    run(p.parse_args().config)
