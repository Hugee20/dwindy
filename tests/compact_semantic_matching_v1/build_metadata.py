"""Construction metadata only; never install, acquire encoders or evaluate arms."""
import hashlib
import json
from pathlib import Path
from . import evaluate, probes, workload

ROOT = Path(__file__).parent
REPO = ROOT.parent.parent


def save(name,value):
    (ROOT/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))


def build():
    if (ROOT/'FREEZE.json').exists(): raise FileExistsError('Do not rebuild frozen metadata')
    save('contract_probes.json',[dict(id=name,kind='concept_contract' if n<27 else 'existing_core_packet',generation_calls=0,network_calls=0)
                                for n,name in enumerate(probes.IDS)])
    save('gates.json',dict(quality=dict(semantic_candidates=33,semantic_final=30,semantic_each_language=9,
         semantic_answers=27,semantic_net_gain=9,exact_retention=16,morphology=7,short_local=3,false_supply=0),
         resources=dict(dependency_compressed_bytes=50*1024**2,dependency_installed_bytes=150*1024**2,
         model_artifact_bytes=160*1024**2,steady_incremental_rss_bytes=384*1024**2,peak_incremental_rss_bytes=512*1024**2,
         startup_ms=4000,first_query_ms=250,encoding_p95_ms=100,selection_p95_ms=150,
         build_ms=300000,additional_index_bytes=32*1024**2),
         additional=dict(selection_delta_ms=125,mechanical_passes=32,historical_new_false_supply=0),
         interpretation='All gates conjunctive, separately for each frozen model/arm; no weighted average, no holdout without review.'))
    baseline = evaluate.read('../morphology_retrieval_v1/baseline.json')
    save('baseline.json',dict(commit='54f4483a324a34053cf57660fb1ae4ed57fa5d7d',files=baseline['files'],
                             note='Current production infrastructure; no Porter, semantic pipeline or generation-policy adoption.'))
    old = evaluate.read('../morphology_retrieval_v1/historical.json')['files']
    pinned = dict(old)
    for folder in ('morphology_retrieval_v1','morphology_retrieval_v1_results'):
        for p in (REPO/'tests'/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                pinned[p.relative_to(REPO).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    for path in ('tests/test_morphology_retrieval_fixtures.py','docs/morphology_retrieval_v1.md'):
        p = REPO/path
        if p.exists(): pinned[path]=hashlib.sha256(p.read_bytes()).hexdigest()
    save('historical.json',dict(files=pinned,note='Hash integrity only, not sealed-output inspection; M11 and morphology holdouts unspent; H2 partial capture untouched.'))
    diagnostics = evaluate.read('../morphology_retrieval_v1/diagnostics.json')
    diagnostics['scope'] = 'M6-M8 plus rejected morphology development only; historical observations never provide fresh semantic acceptance credit.'
    diagnostics['morphology_dev'] = 'tests/morphology_retrieval_v1_results/dev_01'
    diagnostics['reach'] = 'No execution or modification. The revised infrastructure-oriented Reach concept requires a separately versioned future evaluation; existing H2 stays deferred.'
    save('diagnostics.json',diagnostics)
    save('performance.json',dict(identity=workload.identity(),reference=dict(cpu='Intel Core i3-1215U',ram_gib=8,os='Windows',python='3.13',device='CPU'),
         isolated_trials=5,warm_queries_per_trial=200,query_order_seeds=[8164,8165,8166,8167,8168],arm_order_seed=8169,
         ort_intra_op_threads=2,ort_inter_op_threads=1,blas_threads=1,tokenizer_parallelism=False,
         startup='Fresh process: import, load local pinned model/tokenizer, validate hashes, create session; time before first encoding. Warm OS cache; not cold disk.',
         first_query='First query encoding and complete selection after initialization, separately reported.',
         warm='20 untimed fixed workload queries; 200 timed queries per trial, no outlier removal; report all 1000 samples. Query-embedding caches disabled. Bypassed ordinary turns have no encoding and are identified separately; also report encoding-only distribution for actually encoded queries.',
         p95='Nearest rank over pooled 1000 samples; construction probes are not performance samples.',
         trial_gate='Startup/first-query/build/steady RSS median of five trials; peak RSS maximum observed across five; compressed/installed/index/artifact bytes exact.',
         timing_components=['query_tokenization','query_encoding','lexical_search','dense_search','candidate_fusion','admission','core_packet','complete_selection'],
         timing='Exclusive component timings; full selection includes query encoding, search, fusion, admission and unchanged Core preparation. Post-hoc gold/audit serialization excluded.',
         build='Current chunking plus all corpus encoding and vector writing/validation; acquisition and fixture generation excluded and separately reported.',
         baseline='Same sources, current FTS writer/search/usefulness, packet oracle, query order and settings. RSS delta against same interpreter/dependency-import baseline before encoder/vector load; additionally report total fresh-process RSS so imports are not hidden.',
         rss_sample_interval_ms=10,scale='10,000 current chunks; raw float32 vectors, stable identity table; report disk and resident copies.',
         footprint='Complete incremental dependency closure relative to clean Dwindy base, not only currently installed wheels. Downloads and encoder acquisition forbidden in this construction phase.',
         offline='Acquisition separate and explicit; evaluation blocks all network calls, uses an explicit local model directory, rejects missing/corrupt artifacts without auto-download. No private corpus or query leaves process.',
         missing_model='unavailable, never no_match; baseline behavior remains usable and no silent semantic adoption.',
         generation_calls=0,network_calls=0))
    save('protocol.json',dict(hypothesis='A small local encoder improves Dwindy’s discovery and admission of relevant information while preserving source identity, compact evidence, offline operation and bounded resource use.',
         arms=dict(A='Current unicode61 FTS + existing usefulness unchanged.',R='Semantic ordering/admission of FTS candidates only; cannot repair missing lexical candidates.',
                   S='Exact cosine retrieval across permitted split-local chunks + semantic admission.',H='FTS top12 + dense top12 union, RRF k=60, reduce to12 + semantic admission.'),
         candidate_limit=12,supplied_limit=3,evidence_budget=768,output_reserve=256,context_size=8192,budget_oracle='utf8_quarters_v1',
         core='Existing production Core prepares packet; stop/close at TurnStarted before generate. Audit real packet IDs and trimming; no generation. Model-free accounting is not Qwen tokenizer accuracy. Any later real-token validation must be separately authorized and reported.',
         lexical='Unchanged unicode61, BM25 weights2/2/1, first32 original unique non-stopword query terms, existing OR query, duplicate/overlap suppression and context_policy classifications. No Porter.',
         bypass='Existing mode/classification/history query rules retained for all arms; model-only and self-contained turns do not execute encoders. Candidate availability probes, if separately collected, flagged diagnostic only.',
         semantic='No conflict, intent or answerability classifier. Cosine is a selection heuristic; similarity does not establish relevance, truth, support or action capability.',
         admission='R/S/H: for non-directed queries, independently admit selected original passages with cosine >= the one global development threshold. Never let one high-scoring passage authorize other passages. Directed queries retain existing explicit opt-in behavior, reported separately. Ordering remains arm order after admission.',
         hybrid='RRF sum(1/(60+rank)) over source-anchored entry IDs. Ties break by document ID then original chunk ordinal. Dense similarities retained for individual admission; no score-scale mixing or tuned weights.',
         ties='Dense ties: document ID, original chunk ordinal. R reranks only original FTS12. Dedup/overlap policy unchanged; dense/union final candidate packet bound12.',
         vector_store='Evaluation-owned flat float32 vectors + JSON identity table, exact dot products; no vector database or orchestration framework.',
         encoding='Name then current heading then original chunk body. No query, gold labels, source category or split label in encoded document text. Full text remains original supply. Audit tokenizer input length, retained body codepoint span, truncation and gold beyond that span; all misses remain in denominators.',
         thresholds=[.35,.45,.55,.65,.75,.85,.95],threshold_rule='Single threshold per model/arm, same across categories/languages. Evaluate only this predeclared grid, no corpus repair. Choose highest threshold that passes every quality/control gate; resources also mandatory.',
         candidate_selection='If none passes all development gates, stop. Otherwise prefer smallest total model/dependency/RSS footprint among eligible candidates; break ties by selection p95 then semantic final-answer count. No holdout run/freeze automatically.',
         runs='One paired A/R/S/H record per dev case at each declared model/threshold profile; preserve raw candidate/admission/supply and pairwise changes. No library/model substitutions or additional tuning after outputs without a separately versioned evaluation.',
         result_contract='contract.py is evaluation-only concept machinery, not a production abstraction. Public source indicators represent supplied material, not an assertion that Qwen used it or verified facts.'))


if __name__=='__main__': build()
