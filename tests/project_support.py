"""Materialize the frozen Project Awareness fixture into a temporary directory."""
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / 'project'


def load(name):
    return json.loads((FIXTURES/name).read_text(encoding='utf-8'))


def materialize(folder, **overrides):
    """Write host files and project.toml beneath folder; return the configuration path."""
    folder = Path(folder)
    for logical, text in load('files.json').items():
        path = folder/'host'/logical
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode('utf-8'))
    return write_config(folder, **overrides)


def write_config(folder, **overrides):
    settings = dict(load('policy.json'), **overrides)
    config = Path(folder)/'project.toml'
    config.write_text('\n'.join(f'{key} = {json.dumps(value)}' for key, value in settings.items()
                                if value is not None), encoding='utf-8')
    return config


def apply_lifecycle(folder):
    """Turn snapshot A into snapshot B exactly as lifecycle.json defines."""
    host, change = Path(folder)/'host', load('lifecycle.json')
    for logical, text in {**change['replace'], **change['add']}.items():
        (host/logical).write_bytes(text.encode('utf-8'))
    for logical in change['delete']:
        (host/logical).unlink()
    with (host/'.gitignore').open('ab') as handle:
        handle.write(change['new_ignore'].encode('utf-8'))
