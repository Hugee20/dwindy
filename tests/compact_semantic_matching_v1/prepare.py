"""Finalize construction hashes; explicit freeze refuses pending human review.

No encoder acquisition, retrieval, timing or inference. Authoring and validation
must precede review; review must precede --freeze. Never overwrites a freeze.
"""
import argparse
import hashlib
import json
from pathlib import Path
from . import evaluate, probes, workload

ROOT = Path(__file__).parent


def manifest(root=ROOT):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
            and p.name not in ('FREEZE.json','DRAFT_MANIFEST.json')}


def freeze(root=ROOT):
    if (root/'FREEZE.json').exists(): raise FileExistsError('Do not replace a freeze')
    evaluate.validate_review(root)
    # Construction validation/probes always run before sealing. No quality output.
    if root==ROOT:
        evaluate.validate_fixtures(); evaluate.verify_bindings(); probes.run_all()
        if workload.identity()!=evaluate.read('performance.json')['identity']:
            raise AssertionError('Performance inputs changed')
    path = root/'FREEZE.json'
    path.write_bytes((json.dumps(manifest(root),indent=2)+'\n').encode('utf-8'))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def draft():
    if (ROOT/'FREEZE.json').exists(): raise FileExistsError('Frozen construction cannot change')
    evaluate.validate_fixtures(); evaluate.verify_bindings(); probes.run_all()
    if workload.identity()!=evaluate.read('performance.json')['identity']:
        raise AssertionError('Performance inputs changed')
    (ROOT/'DRAFT_MANIFEST.json').write_bytes((json.dumps(manifest(),indent=2)+'\n').encode('utf-8'))
    return evaluate.verify_manifest('DRAFT_MANIFEST.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--freeze',action='store_true')
    args=parser.parse_args()
    print(json.dumps(dict(state='frozen' if args.freeze else 'draft_pending_human_review',sha256=freeze() if args.freeze else draft())))
