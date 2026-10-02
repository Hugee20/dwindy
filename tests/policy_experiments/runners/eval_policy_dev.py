"""Development-only M10/M11 comparison. No holdout execution option, network or verifier."""
import argparse
from contextlib import closing
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import random
import secrets
import sys
import time

sys.path.insert(0,str(Path(__file__).parent))
from dwindy.backend import Completion, TextDelta, Message
from dwindy.config import load_config
from dwindy.core import DwindyCore, TurnStarted
from dwindy.llama_backend import LlamaBackend
import dwindy.evidence as candidate_evidence
from policy.evaluate import core_inputs,evaluate_contract,load,p95,verify_freeze
from policy_probes import observe
from policy_support import baseline_core,baseline_inputs,RecordingBackend
from reach_support import no_network


ABLATION_IDS = ("history_1", "history_3", "history_5", "model_only_13")
CONTINUITY_PROMPTS = ("Write a two-line poem about a kite.",
                      "Replace the kite with a boat in the poem above. Keep two lines.")


class NativeHistoryAblation(DwindyCore):
    """Test-only one-factor control. No production toggle or public contract."""
    def _render_messages(self, system, history, content, web=False):
        return ([Message("system", system)] if system else []) + list(history) + [Message("user", content)]


def core_class(condition):
    if condition == "M10": return baseline_core()
    if condition == "V3_native_history": return NativeHistoryAblation
    return DwindyCore


class TokenizerRecorder(RecordingBackend):
    def __init__(self,tokenizer):super().__init__();self.tokenizer=tokenizer
    def count_tokens(self,messages):return self.tokenizer.count_tokens(messages)
    def context_size(self):return self.tokenizer.context_size()


class MeasuredBackend:
    def __init__(self,backend):self.backend=backend;self.calls=0;self.requests=[]
    def count_tokens(self,messages):return self.backend.count_tokens(messages)
    def context_size(self):return self.backend.context_size()
    def generate(self,messages,options):
        self.calls+=1;self.requests.append(list(messages))
        yield from self.backend.generate(messages,options)


def parameters(case,condition):
    inputs=core_inputs(case)
    kwargs={k:inputs[k] for k in ('evidence','facts','notice')}
    if condition=='M10':kwargs=baseline_inputs(inputs)
    return inputs,kwargs


def construction_ms(case,condition,admitted):
    inputs,kwargs=parameters(case,condition)
    module=sys.modules['dwindy._m10_evidence'] if condition=='M10' else candidate_evidence
    evidence,facts=kwargs['evidence'],kwargs['facts']
    selected=tuple(p for p in evidence.passages if p.source.chunk_id in admitted) if evidence else ()
    samples=[]
    for _ in range(100):
        start=time.perf_counter()
        if facts:module.facts_block(facts)
        if condition == 'M10':
            if facts:module.facts_guidance(facts)
        else:
            module.policy_guidance(facts, selected, bool(inputs['history']))
            if condition != 'V3_native_history': module.history_block(inputs['history'])
        if evidence:module.evidence_question(inputs['user_text'],selected,evidence.framing,evidence.origin)
        samples.append((time.perf_counter()-start)*1000)
    return p95(samples)


def prepare(case,condition,config,tokenizer):
    inputs,kwargs=parameters(case,condition)
    recorder=TokenizerRecorder(tokenizer)
    cls=core_class(condition)
    core=cls(recorder,options=config.options(),system_prompt=config.system_prompt)
    core.restore(inputs['history'])
    events=list(core.chat(inputs['user_text'],**kwargs))
    started=events[0]
    messages=recorder.requests[-1]
    return dict(admitted_ids=[s['chunk_id'] for s in (started.retrieval or {}).get('sources',[])],
                history_turns=(len(inputs['history'])//2)-started.dropped_turns,
                dropped_turns=started.dropped_turns,prompt_tokens=tokenizer.count_tokens(messages),
                messages=[asdict(m) for m in messages],retrieval=started.retrieval)


def run_one(case,condition,config,prepared):
    # Fresh backend per generation establishes matched llama context/KV/seed state.
    loading=time.perf_counter();backend=LlamaBackend(config);load_seconds=time.perf_counter()-loading
    measured=MeasuredBackend(backend);inputs,kwargs=parameters(case,condition)
    cls=core_class(condition)
    core=cls(measured,options=config.options(),system_prompt=config.system_prompt)
    core.restore(inputs['history']);text=[];first=None;completion=None;error=None;started=None
    clock=time.perf_counter()
    try:
        with closing(core.chat(inputs['user_text'],**kwargs)) as stream:
            for event in stream:
                if isinstance(event,(TurnStarted,sys.modules['dwindy._m10_core'].TurnStarted)):started=event
                elif isinstance(event,TextDelta):
                    if first is None and event.text:first=time.perf_counter()-clock
                    text.append(event.text)
                elif isinstance(event,Completion):completion=event
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    elapsed=time.perf_counter()-clock
    actual=[asdict(m) for m in measured.requests[-1]] if measured.requests else []
    backend.close()
    if actual!=prepared['messages']:raise AssertionError('Prepared/actual rendered input differs')
    return dict(id=case['id'],condition=condition,text=''.join(text),load_seconds=load_seconds,
                model_calls=measured.calls,verifier_calls=0,network_calls=0,ttft_s=first,
                end_to_end_s=elapsed,execution_error=error,finish_reason=completion.finish_reason if completion else 'error',
                text_tokens=completion.text_tokens if completion else None,prompt_tokens=completion.prompt_tokens if completion else prepared['prompt_tokens'],
                matched_input_tokens=prepared['prompt_tokens'],admitted_ids=prepared['admitted_ids'],
                history_turns=prepared['history_turns'],dropped_turns=prepared['dropped_turns'],
                policy_build_ms=construction_ms(case,condition,prepared['admitted_ids']),
                messages=actual,retrieval=started.retrieval if started else None)


def run(args):
    root=Path(args.output_dir);root.mkdir(parents=True,exist_ok=False)
    config=load_config(args.config)
    if (config.context_size,config.max_tokens,config.temperature,config.seed)!=(4096,256,0.7,42) or config.chat_template_kwargs!={'enable_thinking':False} or config.system_prompt or config.threads is not None:
        raise ValueError('Configuration does not match frozen evaluation settings')
    freeze=verify_freeze();baseline_core()
    contracts=evaluate_contract(observe,None)
    (root/'contracts.json').write_text(json.dumps(contracts,indent=2)+'\n',encoding='utf-8')
    if not all(row['pass'] for row in contracts):raise RuntimeError('Plumbing failed; no model run')
    cases=load('cases.jsonl','dev')
    if len(cases)!=40:raise AssertionError('Development composition changed')
    prep={}
    with no_network():
        tokenizer=LlamaBackend(config)
        try:
            for case in cases:
                for condition in ('M10','M11_candidate'):prep[(case['id'],condition)]=prepare(case,condition,config,tokenizer)
                if case['id'] in ABLATION_IDS: prep[(case['id'],'V3_native_history')]=prepare(case,'V3_native_history',config,tokenizer)
        finally:tokenizer.close()
    for case in cases:
        old,new=(prep[(case['id'],c)] for c in ('M10','M11_candidate'))
        if old['admitted_ids']!=new['admitted_ids'] or old['history_turns']!=new['history_turns']:
            raise RuntimeError('Admission/history divergence before inference: '+case['id'])
    from test_terminal import conversation_messages
    for case in cases:
        if case['id'] not in ABLATION_IDS: continue
        quoted = prep[(case['id'],'M11_candidate')]
        native = prep[(case['id'],'V3_native_history')]
        decoded = conversation_messages([Message(**m) for m in quoted['messages']])
        if [asdict(m) for m in decoded] != native['messages']:
            raise AssertionError('Ablation changed more than history representation: '+case['id'])
        if (quoted['admitted_ids'],quoted['history_turns']) != (native['admitted_ids'],native['history_turns']):
            raise AssertionError('Ablation admission/history divergence: '+case['id'])
    model_hash=hashlib.sha256()
    with config.model_path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):model_hash.update(block)
    if model_hash.hexdigest() != 'd2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5':
        raise ValueError('Model differs from frozen reference configuration')
    code_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                 (Path('src/dwindy/evidence.py'),Path('src/dwindy/core.py'),Path(__file__),Path('tests/policy_probes.py'))}
    manifest=dict(freeze=freeze,baseline_commit='25ea503202ba9b8030a78c2ac59df117aac7d0b9',
                  split='dev',candidate_label='v3',planned_generations=80,
                  supplementary_generations=8,total_generations=88,ablation_ids=ABLATION_IDS,
                  continuity_prompts=CONTINUITY_PROMPTS,post_output_tuning=False,model_sha256=model_hash.hexdigest(),
                  model_filename=config.model_path.name,context_size=config.context_size,
                  options=asdict(config.options()),chat_template_kwargs=config.chat_template_kwargs,
                  system_prompt=config.system_prompt,threads=config.threads,python=platform.python_version(),
                  platform=platform.platform(),code_hashes=code_hashes,
                  fresh_backend_per_generation=True,holdout_executed=False)
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    rows=[]
    with (root/'results.jsonl').open('x',encoding='utf-8',newline='\n') as stream,no_network() as attempts:
        for ordinal,case in enumerate(cases,1):
            order=('M10','M11_candidate') if ordinal%2 else ('M11_candidate','M10')
            for condition in order:
                row=run_one(case,condition,config,prep[(case['id'],condition)])
                rows.append(row);stream.write(json.dumps(row,ensure_ascii=True)+'\n');stream.flush()
                print(json.dumps({k:row[k] for k in ('id','condition','ttft_s','finish_reason','execution_error')}),flush=True)
    sheet=[];key={}
    for row in rows:
        token=secrets.token_hex(8);key[token]={'id':row['id'],'condition':row['condition']}
        case=next(c for c in cases if c['id']==row['id'])
        sheet.append((token,case,row))
    random.Random(1111).shuffle(sheet)
    with (root/'sheet.md').open('x',encoding='utf-8',newline='\n') as output:
        output.write('# M11 development blind sheet\n\nScore with the frozen rubric before opening key.json. Canonical data, not rendered policy.\n')
        for token,case,row in sheet:
            output.write('\n## '+token+'\n\nQuestion: '+case['input']['message']+'\n\nHistory/material:\n```json\n'+json.dumps(case['input'],ensure_ascii=False,indent=2)+'\n```\n\nAnswer:\n'+row['text']+'\n')
    (root/'key.json').write_text(json.dumps(key,indent=2)+'\n',encoding='utf-8')
    with (root/'ablation-results.jsonl').open('x',encoding='utf-8',newline='\n') as stream,no_network():
        for case in cases:
            if case['id'] not in ABLATION_IDS: continue
            row=run_one(case,'V3_native_history',config,prep[(case['id'],'V3_native_history')])
            stream.write(json.dumps(row,ensure_ascii=True)+'\n');stream.flush()
            print(json.dumps({k:row[k] for k in ('id','condition','ttft_s','finish_reason','execution_error')}),flush=True)
    with (root/'continuity.jsonl').open('x',encoding='utf-8',newline='\n') as stream,no_network():
        for condition in ('M10','M11_candidate'):
            backend=LlamaBackend(config);measured=MeasuredBackend(backend)
            core=core_class(condition)(measured,options=config.options(),system_prompt=config.system_prompt)
            try:
                for turn,question in enumerate(CONTINUITY_PROMPTS,1):
                    pieces=[];completion=None;error=None;before=measured.calls
                    try:
                        with closing(core.chat(question)) as answer:
                            for event in answer:
                                if isinstance(event,TextDelta): pieces.append(event.text)
                                elif isinstance(event,Completion):completion=event
                    except Exception as exc: error=type(exc).__name__+': '+str(exc)
                    row=dict(condition=condition,turn=turn,message=question,text=''.join(pieces),
                        execution_error=error,model_calls=measured.calls-before,verifier_calls=0,network_calls=0,
                        finish_reason=completion.finish_reason if completion else 'error',
                        messages=[asdict(m) for m in measured.requests[-1]],snapshot=[asdict(m) for m in core.snapshot()])
                    stream.write(json.dumps(row,ensure_ascii=True)+'\n');stream.flush()
                    print(json.dumps({k:row[k] for k in ('condition','turn','finish_reason','execution_error')}),flush=True)
            finally: backend.close()
    assert verify_freeze()==freeze
    print('Development complete: 80 primary + 4 history ablation + 4 continuity generations; holdout not run.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--output-dir',required=True)
    run(parser.parse_args())
