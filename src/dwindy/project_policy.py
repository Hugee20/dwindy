"""Bounded local project policy. No model, Git process, or content-driven permissions."""
import os
from pathlib import Path, PurePosixPath
import stat

DENIED_DIRS = frozenset('''.git .hg .svn venv .venv env node_modules vendor bower_components
build dist target out bin obj coverage __pycache__ .cache .pytest_cache .mypy_cache
.next .nuxt .svelte-kit .dwindy secrets credentials models data cache'''.split())
DENIED_SUFFIXES = frozenset('''.key .pem .p12 .pfx .crt .cer .db .sqlite .sqlite3 .gguf
.ggml .safetensors .pt .pth .onnx .exe .dll .so .zip .tar .gz .7z .map .pyc .log'''.split())
MAX_ENTRIES, MAX_DEPTH, MAX_PATTERNS = 10000, 12, 2000


def signature(value):
    # Windows lstat reports creation time as st_ctime but fstat reports change time, so
    # ctime is not comparable across the two there; identity, size and mtime still are.
    return (value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns,
            None if os.name == 'nt' else value.st_ctime_ns)


def checked_path(path, *, directory=False):
    """Reject links/reparse points on every component, including the approved root."""
    path = Path(os.path.abspath(path))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0) & 0x400:
            raise ValueError('Links and reparse points are not permitted')
    info = path.lstat()
    if directory:
        if not stat.S_ISDIR(info.st_mode): raise ValueError('Expected a directory')
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Expected an unlinked regular file')
    return path,info


def safe_read(path, limit):
    path,before = checked_path(path)
    if before.st_size > limit: raise ValueError('File size limit exceeded')
    descriptor = os.open(path,os.O_RDONLY | getattr(os,'O_BINARY',0) | getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(descriptor,'rb') as handle:
        opened = os.fstat(handle.fileno())
        if signature(opened) != signature(before): raise ValueError('File changed during open')
        if os.name == 'nt':
            import ctypes
            import msvcrt
            buffer = ctypes.create_unicode_buffer(32768)
            function = ctypes.windll.kernel32.GetFinalPathNameByHandleW
            function.argtypes = [ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_ulong,ctypes.c_ulong]
            size = function(msvcrt.get_osfhandle(handle.fileno()),buffer,len(buffer),0)
            actual = buffer.value.removeprefix('\\\\?\\')
            if not size or size >= len(buffer) or os.path.normcase(actual) != os.path.normcase(str(path)):
                raise ValueError('Opened file escaped its approved path')
        checked_path(path)
        raw = handle.read(limit+1)
        if len(raw)>limit or signature(os.fstat(handle.fileno())) != signature(before):
            raise ValueError('File changed during read')
    if signature(checked_path(path)[1]) != signature(before): raise ValueError('File replaced during read')
    return raw,signature(before)


def hard_excluded(relative):
    parts = PurePosixPath(relative).parts
    for part in parts:
        name=part.casefold()
        if (name in DENIED_DIRS or name.startswith('.') or
            name.startswith(('credentials','secrets','id_rsa','id_ed25519')) or
            name.endswith(('.local.toml','.local.json','.local.yaml','.local.yml','-journal','-wal','-shm')) or
            '.min.' in name or name.endswith(('.generated.ts','.generated.js','.g.py')) or
            PurePosixPath(name).suffix in DENIED_SUFFIXES):
            return True
    return False


class Policy:
    def __init__(self, root, excludes=()):
        try:
            from pathspec import GitIgnoreSpec
        except ImportError as exc:
            raise ValueError('Project ingestion requires the optional dwindy[project] dependency') from exc
        self.spec_type = GitIgnoreSpec
        self.root,self.root_stat = checked_path(root,directory=True)
        if self.root == Path(self.root.anchor): raise ValueError('Filesystem roots are not project roots')
        if len(excludes)>MAX_PATTERNS or any(not isinstance(p,str) or not p or p.startswith('!') or len(p)>512 for p in excludes):
            raise ValueError('Invalid deny-only project exclusions')
        self.extra = GitIgnoreSpec.from_lines(excludes,backend='simple')
        self.rules = {}
        self.reads = {}
        self.directories = {}
        self.policy_hashes = {}
        self.pattern_count = len(excludes)
        self.visited = 0

    def relative(self, value):
        if (not isinstance(value,str) or not value or '\\' in value or ':' in value or
            len(value)>512 or PurePosixPath(value).is_absolute() or
            any(p in ('..','.') for p in value.split('/'))):
            raise ValueError('Use a contained relative forward-slash project path')
        return PurePosixPath(value).as_posix()

    def ignore_rules(self, directory):
        if directory in self.rules: return self.rules[directory]
        parent = self.root / directory
        checked_path(parent,directory=True)
        path = parent / '.gitignore'
        spec = None
        if path.exists() or path.is_symlink():
            raw,sig = safe_read(path,65536)
            self.reads[path]=sig
            import hashlib
            self.policy_hashes[path.relative_to(self.root).as_posix()] = hashlib.sha256(raw).hexdigest()
            lines=raw.decode('utf-8-sig').splitlines()
            self.pattern_count += len(lines)
            if self.pattern_count>MAX_PATTERNS: raise ValueError('Ignore pattern limit exceeded')
            spec = self.spec_type.from_lines(lines,backend='simple')
        self.rules[directory] = spec
        return spec

    def permitted(self, relative, directory=False):
        relative=self.relative(relative)
        if hard_excluded(relative): return False
        parts=PurePosixPath(relative).parts
        if len(parts)>MAX_DEPTH: raise ValueError('Project depth limit exceeded')
        # Check each parent first: excluded directories are never traversed.
        for end in range(1,len(parts)+1):
            prefix='/'.join(parts[:end])
            is_dir=end<len(parts) or directory
            candidate=prefix+('/' if is_dir else '')
            ignored=False
            for depth in range(end):
                base='/'.join(parts[:depth])
                spec=self.ignore_rules(base)
                if spec is not None:
                    match=spec.check_file('/'.join(parts[depth:end])+('/' if is_dir else ''))
                    if match.include is not None: ignored=match.include
            if ignored or self.extra.match_file(candidate): return False
        return True

    def read(self, relative, limit):
        if not self.permitted(relative): raise ValueError('Selected file is excluded')
        path=self.root/relative
        raw,sig=safe_read(path,limit)
        self.reads[path]=sig
        return raw

    def entries(self, relative=''):
        path=self.root/relative
        path,info=checked_path(path,directory=True)
        self.directories[path]=signature(info)
        entries=[]
        with os.scandir(path) as iterator:
            for entry in iterator:
                self.visited+=1
                if self.visited>MAX_ENTRIES: raise ValueError('Visited entry limit exceeded')
                entries.append(entry)
        return sorted(entries,key=lambda e:(e.name.casefold(),e.name))

    def recheck(self):
        for path,sig in self.reads.items():
            if signature(checked_path(path)[1]) != sig: raise ValueError('Input changed before commit')
        for path,sig in self.directories.items():
            if signature(checked_path(path,directory=True)[1]) != sig:
                raise ValueError('Directory changed before commit')
