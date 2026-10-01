# M7 project awareness

Project Awareness builds a **controlled local knowledge snapshot** of one explicitly
configured project and stores it in an M6 retrieval index. Three things stay distinct:

- **Project Awareness** decides which permitted project material enters the snapshot;
- **retrieval** (unchanged M6 lexical search) selects passages from that snapshot;
- **model interpretation** is the model answering from those supplied passages.

Dwindy does not "understand the codebase". It sees only the selected files, as text. It
does not run, import or analyze code, read Git history, detect frameworks, or follow
references written in project files. Nothing is scanned at server startup or during chat.
When Project Awareness is not configured, M1–M6 behave exactly as before.

## Install and synchronize

The optional `project` extra adds one pure-Python dependency, `pathspec==1.1.1`, used only
to match `.gitignore`-style patterns. Base Dwindy does not need it.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[api,project]'
Copy-Item project.example.toml project.local.toml
notepad project.local.toml
.\.venv\Scripts\python.exe -m dwindy.project sync --config project.local.toml --dry-run
.\.venv\Scripts\python.exe -m dwindy.project sync --config project.local.toml
```

The dry run reports what would be selected, skipped, added, changed and deleted, and writes
nothing. Then point the server at the index with the existing M6 setting in `api.local.toml`:

```toml
retrieval_index_path = 'data/my-project.sqlite3'
```

Synchronization is manual, as in M6: stop the server, sync, then restart. There is no
watcher, automatic resync or project-management screen.

## Configuration

| Field | Rule |
| --- | --- |
| `project_id` | Required. 1–64 of `A–Z a–z 0–9 _ -`. Stable identity; an index belongs to one project. |
| `name` | Required, 1–128 characters. |
| `root` | Required. A local directory; URLs, UNC paths and filesystem roots are refused. |
| `index_path` | Required. Must be **outside** `root`. |
| `documentation_dirs` | Default `["docs"]`; up to 16 root-relative directories. A missing `docs` is ignored; any other listed directory must exist. |
| `source_files` | Default empty; up to 32 individually named files. |
| `config_files` | Default empty; up to 16 individually named files. |
| `exclude` | Default empty; up to 2,000 deny-only gitignore-style patterns (no `!`). |
| `documents_manifest` | Optional. One ordinary M6 manifest combined into the same index. |

Unknown fields fail. Paths in lists are relative, forward-slash and contained: no `..`,
`.`, drive letters or backslashes. The configuration file is at most 64 KiB, and the index
path is never written into the snapshot.

## What is selected

1. Root `DWINDY.md`, `README.md` and `README.txt` (case-insensitive), if present.
2. `.md` and `.txt` files found by walking each documentation directory.
3. Each listed source file (`.py .js .jsx .ts .tsx`) and configuration file (`.toml .json`).
4. Four fields from the root `pyproject.toml` `[project]` table and the root `package.json`:
   `name`, `description`, `version` and `requires-python`. Nothing else is read from them, so
   scripts and dependency lists are never stored. The entry is labeled "Declared metadata …
   (not proof of active components)".
5. A generated overview (below).

Source code is never discovered automatically. An explicitly listed file that is excluded,
missing or of an unsupported type fails the sync rather than being silently skipped.

### Exclusions

Exclusions are checked **before any content is read**. The order of authority is:

1. **Hard exclusions** override everything, including explicit selection, `.gitignore`
   negation (`!path`) and M6 manifest entries beneath the project root. A path is
   hard-excluded when any component:
   - starts with `.` (so `.env`, `.git` and `.github` are all excluded);
   - is one of `venv env node_modules vendor bower_components build dist target out bin obj
     coverage __pycache__ secrets credentials models data cache` or a common tool cache;
   - starts with `credentials`, `secrets`, `id_rsa` or `id_ed25519`;
   - ends in `.local.toml/.json/.yaml/.yml`, `-journal`, `-wal` or `-shm`;
   - contains `.min.`, ends in `.generated.ts/.js` or `.g.py`; or
   - has a key/certificate, database, model-weight, binary, archive, source-map, `.pyc` or
     `.log` suffix.
2. **`.gitignore` files** in the root and in every traversed directory, with Git's
   precedence: deeper files override shallower ones, and an ignored directory is never
   entered. Each `.gitignore` is read only as policy; its SHA-256 is part of the snapshot
   identity. `.git/info/exclude` and global Git excludes are **not** consulted.
3. **`exclude` patterns** from the configuration.

Symbolic links, junctions and other reparse points are refused on every path component,
including the root. So are hard-linked files (link count above one) and non-regular files.
Each one **fails the sync** with a message instead of being skipped. To proceed, exclude
the path. Each file is opened without following links, and on Windows the opened handle's
final path must equal the approved path. Every file and directory read is checked again for
changes before commit.

These rules are a boundary, not a secret scanner. They do **not** guarantee that a permitted
document or a selected source file contains no secrets.

### Limits

| Limit | Value |
| --- | ---: |
| Documentation file | 256 KiB |
| Source, configuration or metadata file | 128 KiB |
| Combined source bytes | 10 MiB |
| Indexed documents | 500 |
| Overview entries (top-level directories plus selected files) | 100 |
| Overview size | 32 KiB |
| Directory entries visited | 10,000 |
| Path depth | 12 components |
| Ignore and exclude patterns, combined | 2,000 |

The overview cap means that in practice a snapshot holds about 100 original files.
Source and configuration files are also refused if any line exceeds 1,000 characters
(likely minified) or if an early-line marker such as `@generated` or `do not edit` appears.
Documentation is exempt from both checks: long soft-wrapped paragraphs and editing advice
are ordinary prose, and the M6 chunker already splits oversized blocks. Any limit breach
fails the whole sync and leaves the previous snapshot untouched.

## DWINDY.md semantics

`DWINDY.md` is optional project-written documentation. It is indexed exactly like
`README.md`, as **untrusted project knowledge**. It cannot change inclusion policy, authorize
paths, trigger ingestion, alter system behavior, run commands or grant capabilities. Paths and
links inside it are ordinary text and are never opened. Like any passage, its content reaches
the model only when retrieved, inside the existing "Untrusted local passages" framing. A
model can still be persuaded by text; that M6 limitation remains.

## Generated overview

One deterministic document, `@project/overview`, lists only observed structure:

```text
# Lantern Desk
Project ID: lantern
This is a selected snapshot, not a complete repository or proof of runtime behavior.
## Permitted top-level directories
config/
docs/
src/
web/
## Selected original files
DWINDY.md
README.md
config/reference.toml
...
```

It contains no recursive directory listing, unselected files or excluded directories, and
no claims about purpose or framework.

## Source chunking and provenance

Source and configuration files use chunker version 2. Boundaries are placed before lines
that begin a declaration (`def`, `class`, `function`, `interface`, `type`, optionally
preceded by `export`, `default` or `async`). Decorators stay attached to the declaration
they precede. Each region is then split by the unchanged M6 text chunker. There is no
parsing, symbol table, import resolution or call graph. Documentation keeps chunker
version 1. Every passage carries the project-relative path, half-open Unicode offsets, 1-based
lines and content hash, so it is an exact substring of the normalized original.

Document IDs are `p_` plus a hash of the project ID and path. Documents from a combined M6
manifest keep their manifest ID behind an `m_` prefix and their `local_text` source type.
Project passages have the source types `project_documentation`, `project_source`,
`project_configuration`, `project_metadata` or `project_structure`.

## Index schema and M6 compatibility

A project index is an M6 index with `user_version` 2 and one extra table:

| Table | Columns |
| --- | --- |
| project_snapshot | singleton (=1), project_id, name, snapshot_id, policy_version, indexed_at |

`snapshot_id` is a SHA-256 over the selection policy, the `.gitignore` hashes and every
document's ID, content hash and type. It excludes the project root, so moving a project
does not change its identity. The M6 search, ranking, tokenizer, BM25 weights, candidate
limits, duplicate suppression, three-passage maximum and evidence budget are unchanged.

There is no silent repurposing or migration. A project sync into an M6 (version 1) index,
an M6 manifest sync into a project index, and a sync into another project's index all fail
with an ownership error, and no data is changed. Build a new index instead. The server
opens either version read-only.

## Synchronization lifecycle

- **Atomic.** Every file is captured and rechecked, then one SQLite transaction writes the
  changes. Inputs are rechecked once more immediately before commit. Any failure, including
  a file changed during sync, rolls back and leaves the previous snapshot byte-for-byte intact.
- **Incremental.** Unchanged documents keep their chunk IDs. Changed documents are replaced.
  Documents that are no longer selected (deleted, newly ignored or newly excluded) are removed.
- **Freshness is manual.** Health reports `"freshness": "not_checked"`, meaning Dwindy never
  compares the snapshot with the live project. Run `--dry-run` to see pending changes. Answers
  always reflect the last successful sync, so they can be stale.

## API and browser

Endpoints, request bodies, SSE events and the `retrieval` opt-in are unchanged. With a
project index:

- `GET /v1/health` adds `project_snapshot`: `project_id`, `name`, `snapshot_id`,
  `indexed_at` and `freshness`. It never includes the project root or index path. For an M6
  index or no index, the field is omitted and the response is identical to M6.
- Retrieve matches and chat `retrieval.sources` add `project_id` and `snapshot_id` for project
  passages. Those keys are omitted for ordinary M6 passages.
- When any supplied passage comes from a project, the evidence framing first states that
  observations are limited to selected files, that documentation describes intended behavior,
  that source excerpts do not prove runtime behavior, that rationale is known only when a
  passage states it, and that file references grant no permissions.
- The chat component labels its existing checkbox **Use local project context** when health
  reports a project snapshot, and **Use local documents** otherwise.

Evidence is never stored in conversation history, whether persistence is on or off.

## Privacy and security limitations

The index stores selected project text unencrypted on local disk. Any authorized API client
can retrieve it. The exclusion rules reduce exposure but are not secret detection. Hidden
directories are always excluded, even when they hold documentation. Rename or move such
documentation to include it. Sync reads files sequentially and verifies them before commit,
but it is not an OS-level atomic snapshot of a tree being edited. A changed input fails the
sync rather than producing a mixed snapshot. Deleted SQLite pages are not securely erased.

See the [M7 validation report](M7_VALIDATION.md) for benchmark results and measurements.
