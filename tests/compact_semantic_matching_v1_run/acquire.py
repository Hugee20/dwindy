"""Explicit public-artifact acquisition, separate from offline evaluation.

Uses the frozen publisher revision and hashes. Never sends private sources/queries,
installs packages, imports an encoder or changes production/evaluation fixtures.
"""
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

REPO=Path(__file__).resolve().parents[2]
ROOT=REPO/'tests/compact_semantic_matching_v1'
CACHE=REPO/'.cache/compact_semantic_matching_v1'


def acquire():
    model=next(m for m in json.loads((ROOT/'models.json').read_text())['encoders'] if m['id']=='potion')
    folder=CACHE/'models/potion'; folder.mkdir(parents=True,exist_ok=True)
    metadata=json.load(urlopen(model['metadata_url'],timeout=30))
    assert metadata['sha']==model['revision']
    siblings={s['rfilename']:s for s in metadata['siblings']}
    pins={model['graph']['path']:model['graph'],model['tokenizer']['path']:model['tokenizer']}
    pins.update({p:dict(git_blob_sha1=h) for p,h in model['configuration_git_blobs'].items()})
    # Publisher model card contains the model license; preserve its exact bytes too.
    pins['README.md']=dict(git_blob_sha1=siblings['README.md']['blobId'])
    records=[]
    for name,pin in pins.items():
        target=folder/name
        raw=target.read_bytes() if target.exists() else urlopen(
            f'https://huggingface.co/{model["repository"]}/resolve/{model["revision"]}/{quote(name,safe="/")}',timeout=60).read()
        digest=hashlib.sha256(raw).hexdigest()
        if 'sha256' in pin: assert digest==pin['sha256'],name
        if 'git_blob_sha1' in pin:
            assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==pin['git_blob_sha1'],name
        if 'bytes' in pin: assert len(raw)==pin['bytes'],name
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists(): target.write_bytes(raw)
        records.append(dict(path=name,bytes=len(raw),sha256=digest))
        print(json.dumps(records[-1]),flush=True)
    manifest=dict(repository=model['repository'],revision=model['revision'],license=model['license'],files=records)
    (CACHE/'acquisition.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(total_model_bytes=sum(r['bytes'] for r in records),local_directory=str(folder))),flush=True)


if __name__=='__main__': acquire()
