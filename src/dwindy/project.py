"""Explicit, bounded project snapshot builder over the existing M6 index writer."""
import argparse
from dataclasses import dataclass, field, fields
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tomllib

from .ingest import Document, chunks, manifest_entries, normalize, write_documents
from .project_policy import Policy, checked_path, hard_excluded, safe_read
from .retrieval import RetrievalIndex, RetrievalError

POLICY_VERSION = 1
DOC_TYPES = {'.md','.txt'}
SOURCE_TYPES = {'.py','.js','.jsx','.ts','.tsx'}
CONFIG_TYPES = {'.toml','.json'}
MAX_DOCUMENTS, MAX_BYTES = 500,10*1024*1024


@dataclass(frozen=True)
class ProjectConfig:
    project_id: str
    name: str
    root: Path
    index_path: Path
    documentation_dirs: tuple = ('docs',)
    source_files: tuple = ()
    config_files: tuple = ()
    exclude: tuple = ()
    documents_manifest: Path | None = None


def load_config(path):
    path=Path(os.path.abspath(path))
    raw,_=safe_read(path,65536)
    data=tomllib.loads(raw.decode('utf-8-sig'))
    if set(data)-{f.name for f in fields(ProjectConfig)}:
        raise ValueError('Unknown project configuration field')
    if not {'project_id','name','root','index_path'} <= data.keys():
        raise ValueError('Project configuration requires identity, name, root and index_path')
    if not isinstance(data['project_id'],str) or not re.fullmatch('[A-Za-z0-9_-]{1,64}',data['project_id']):
        raise ValueError('Invalid project ID')
    if not isinstance(data['name'],str) or not data['name'].strip() or len(data['name'])>128:
        raise ValueError('Invalid project name')
    for key in ('root','index_path','documents_manifest'):
        if key in data:
            value=data[key]
            if (not isinstance(value,str) or not value.strip() or value.startswith(('\\\\','//')) or
                '://' in value or value.lower().startswith('file:') or '\x00' in value):
                raise ValueError('Expected a physical local path')
            data[key]=Path(os.path.abspath(path.parent/value))
    for key,maximum in (('documentation_dirs',16),('source_files',32),('config_files',16),('exclude',2000)):
        value=data.get(key,('docs',) if key=='documentation_dirs' else ())
        if not isinstance(value,(tuple,list)) or len(value)>maximum or any(not isinstance(v,str) for v in value):
            raise ValueError('Invalid project selection list')
        data[key]=tuple(value)
    cfg=ProjectConfig(**data)
    checked_path(cfg.root,directory=True)
    # Keep generated state outside the host tree, including during directory rechecks.
    if cfg.index_path.is_relative_to(cfg.root) or cfg.index_path == path:
        raise ValueError('Project index must be outside the host tree and configuration file')
    parent=cfg.index_path.parent
    while not parent.exists(): parent=parent.parent
    checked_path(parent,directory=True)
    if cfg.index_path.exists(): checked_path(cfg.index_path)
    return cfg,raw


def source_chunks(text):
    """Line/declaration boundaries only; no AST, imports or execution."""
    boundaries=[0]
    offset=0
    decorator=None
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith('@'):
            if decorator is None: decorator=offset
        elif re.match(r'^\s*(?:(?:export|default|async)\s+)*(?:def|class|function|interface|type)\s+\w+',line):
            start=decorator if decorator is not None else offset
            if start>boundaries[-1]: boundaries.append(start)
            decorator=None
        elif line.strip(): decorator=None
        offset+=len(line)
    boundaries.append(len(text))
    for begin,end in zip(boundaries,boundaries[1:]):
        for heading,start,stop in chunks(text[begin:end]):
            yield heading,begin+start,begin+stop


@dataclass
class Capture:
    config: ProjectConfig
    policy: Policy
    documents: list = field(default_factory=list)
    selected: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    source_bytes: int = 0
    project: dict = field(default_factory=dict)

    def add(self, logical, raw, source_type, name=None):
        self.source_bytes+=len(raw)
        if self.source_bytes>MAX_BYTES: raise ValueError('Aggregate project byte limit exceeded')
        text=normalize(raw)
        source=source_type in ('project_source','project_configuration')
        # Code-only checks: prose often has long soft-wrapped lines and "do not edit" wording;
        # the M6 chunker already hard-splits oversized documentation blocks.
        if source and any(len(line)>1000 for line in text.splitlines()):
            raise ValueError('Oversized line / potentially minified input')
        if source and re.search(r'(?im)^.{0,40}(?:@generated|auto-generated|automatically generated|do not edit)\b',text):
            raise ValueError('Generated file marker is not permitted')
        if len(self.documents)>=MAX_DOCUMENTS: raise ValueError('Selected document limit exceeded')
        suffix=Path(logical).suffix.lower()
        doc_id='p_'+hashlib.sha256((self.config.project_id+':'+logical).encode()).hexdigest()[:60]
        display=name or (source_type.removeprefix('project_')+' '+self.config.name+' '+logical)
        self.documents.append(Document(doc_id,logical,display[:128],suffix or '.txt',text,
            hashlib.sha256(raw).hexdigest(),source_type,2 if source else 1,
            tuple(source_chunks(text)) if source else None))


def capture(cfg):
    policy=Policy(cfg.root,cfg.exclude)
    result=Capture(cfg,policy)
    selected=set()
    visited_dirs=set()

    def select(logical,kind,explicit=False):
        logical=policy.relative(logical)
        if logical in selected: return
        if not policy.permitted(logical):
            if explicit: raise ValueError('Explicit project file is excluded')
            result.skipped.append((logical,'excluded')); return
        allowed=DOC_TYPES if kind=='project_documentation' else SOURCE_TYPES if kind=='project_source' else CONFIG_TYPES
        if Path(logical).suffix.lower() not in allowed:
            if explicit: raise ValueError('Unsupported explicitly selected format')
            result.skipped.append((logical,'unsupported')); return
        raw=policy.read(logical,256*1024 if kind=='project_documentation' else 128*1024)
        result.add(logical,raw,kind)
        selected.add(logical); result.selected.append(logical)

    def walk(relative):
        relative=policy.relative(relative)
        if relative in visited_dirs: return
        if not policy.permitted(relative,directory=True):
            result.skipped.append((relative,'excluded directory')); return
        visited_dirs.add(relative)
        for entry in policy.entries(relative):
            logical=relative+'/'+entry.name
            if hard_excluded(logical):
                result.skipped.append((logical,'hard exclusion')); continue
            if not policy.permitted(logical,directory=entry.is_dir(follow_symlinks=False)):
                result.skipped.append((logical,'ignored')); continue
            if entry.is_dir(follow_symlinks=False): walk(logical)
            else: select(logical,'project_documentation')

    top=[]
    for entry in policy.entries():
        logical=entry.name
        if hard_excluded(logical): continue
        if not policy.permitted(logical,directory=entry.is_dir(follow_symlinks=False)): continue
        # Reject encountered approved links without following them, even in the overview.
        checked_path(policy.root/logical,directory=entry.is_dir(follow_symlinks=False))
        if entry.is_dir(follow_symlinks=False): top.append(logical+'/')
        elif logical.casefold() in ('dwindy.md','readme.md','readme.txt'):
            select(logical,'project_documentation')
    for directory in cfg.documentation_dirs:
        relative=policy.relative(directory)
        # Missing conventional docs/ is fine; any supplied nondefault path must exist.
        if not (policy.root/relative).exists() and relative=='docs': continue
        walk(relative)
    for logical in cfg.source_files: select(logical,'project_source',True)
    for logical in cfg.config_files: select(logical,'project_configuration',True)

    metadata=[]
    for logical in ('package.json','pyproject.toml'):
        path=policy.root/logical
        if not path.exists() or not policy.permitted(logical): continue
        raw=policy.read(logical,128*1024)
        data=json.loads(raw) if logical.endswith('.json') else tomllib.loads(raw.decode('utf-8-sig')).get('project',{})
        if not isinstance(data,dict): raise ValueError('Invalid project metadata')
        metadata.append('Declared metadata from '+logical+' (not proof of active components):')
        for key in ('name','description','version','requires-python'):
            if key in data:
                value=data[key]
                if not isinstance(value,str) or len(value)>512: raise ValueError('Invalid metadata scalar')
                metadata.append(key+' = '+json.dumps(value,ensure_ascii=True))
    if metadata: result.add('@project/metadata','\n'.join(metadata).encode(),'project_metadata')

    # A plain M6 collection is an explicit additional input, never an exclusion bypass.
    if cfg.documents_manifest:
        raw,sig=safe_read(cfg.documents_manifest,1024*1024)
        policy.reads[cfg.documents_manifest]=sig
        external=tomllib.loads(raw.decode('utf-8-sig'))
        for item in external.get('documents',[]):
            if not isinstance(item,dict) or not isinstance(item.get('path'),str): raise ValueError('Invalid manifest')
            original=Path(os.path.abspath(cfg.documents_manifest.parent/item['path']))
            checked_path(original)
        for key,path,logical,name in manifest_entries(cfg.documents_manifest):
            if path.is_relative_to(policy.root):
                relative=path.relative_to(policy.root).as_posix()
                if not policy.permitted(relative): raise ValueError('Manifest cannot bypass project exclusions')
                select(relative,'project_documentation',True)
            else:
                raw,sig=safe_read(path,256*1024)
                policy.reads[path]=sig
                result.source_bytes+=len(raw)
                if result.source_bytes>MAX_BYTES or len(result.documents)>=MAX_DOCUMENTS:
                    raise ValueError('Combined collection limit exceeded')
                result.documents.append(Document('m_'+key,logical,name,path.suffix.lower(),normalize(raw),hashlib.sha256(raw).hexdigest()))

    listed=sorted(selected)
    if len(top)+len(listed)>100: raise ValueError('Overview entry limit exceeded; narrow project selection')
    overview=['# '+cfg.name,'Project ID: '+cfg.project_id,
        'This is a selected snapshot, not a complete repository or proof of runtime behavior.',
        '## Permitted top-level directories',*top,'## Selected original files',*listed]
    overview_text='\n'.join(overview)+'\n'
    if len(overview_text.encode())>32768: raise ValueError('Overview byte limit exceeded')
    result.add('@project/overview',overview_text.encode(),'project_structure')
    # Root location is deliberately omitted: relocating the same approved project is explicit configuration.
    policy_data=dict(project_id=cfg.project_id,name=cfg.name,documentation_dirs=cfg.documentation_dirs,
        source_files=cfg.source_files,config_files=cfg.config_files,exclude=cfg.exclude,
        policy_version=POLICY_VERSION,ignores=policy.policy_hashes)
    digest=hashlib.sha256(json.dumps([policy_data,[(d.id,d.content_hash,d.source_type) for d in result.documents]],sort_keys=True).encode()).hexdigest()
    result.project=dict(project_id=cfg.project_id,name=cfg.name,snapshot_id=digest,policy_version=POLICY_VERSION)
    policy.recheck()
    return result


def synchronize(config_path, *, dry_run=False):
    cfg,config_raw=load_config(config_path)
    old={}
    if cfg.index_path.exists():
        index=RetrievalIndex(cfg.index_path)
        try:
            if not index.project_snapshot or index.project_snapshot['project_id'] != cfg.project_id:
                raise ValueError('Index ownership differs; explicitly build a new project index')
            old={r['id']:r['content_hash'] for r in index.connection.execute('SELECT id,content_hash FROM documents')}
        finally: index.close()
    captured=capture(cfg)
    desired={d.id:d.content_hash for d in captured.documents}
    report=dict(project_id=cfg.project_id,snapshot_id=captured.project['snapshot_id'],
        selected=captured.selected,skipped=captured.skipped,source_bytes=captured.source_bytes,
        added=sum(k not in old for k in desired),changed=sum(k in old and old[k]!=v for k,v in desired.items()),
        deleted=len(old.keys()-desired.keys()),unchanged=sum(old.get(k)==v for k,v in desired.items()),dry_run=dry_run)
    def recheck():
        if safe_read(config_path,65536)[0]!=config_raw: raise ValueError('Configuration changed during capture')
        captured.policy.recheck()
    recheck()
    if not dry_run:
        report['write']=write_documents(captured.documents,cfg.index_path,project=captured.project,precommit=recheck)
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['sync'])
    parser.add_argument('--config',required=True)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args(argv)
    try:
        print(json.dumps(synchronize(args.config,dry_run=args.dry_run),indent=2))
        return 0
    except (OSError,ValueError,sqlite3.Error,RetrievalError) as exc:
        print('Project sync failed: '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__': raise SystemExit(main())
