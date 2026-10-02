"""Explicit local API launcher and API-only configuration (no model policy)."""

import argparse
from dataclasses import dataclass, fields
import ipaddress
import os
from pathlib import Path
import re
import ssl
import sys
import tomllib
from urllib.parse import urlsplit

from .config import ConfigError, load_config


@dataclass(frozen=True)
class ApiConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    allow_non_loopback: bool = False
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost", "::1")
    allowed_origins: tuple[str, ...] = ()
    token_env: str = "DWINDY_API_TOKEN"
    max_conversations: int = 16
    conversation_idle_seconds: int = 1800
    max_request_bytes: int = 65536
    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None
    database_path: str | None = None
    database_max_mib: int = 128
    retrieval_index_path: str | None = None
    retrieval_context_tokens: int = 768
    retrieval_default: str | None = None  # "auto" | "off"; unset means auto when an index is configured

    def validate(self) -> str | None:
        if not isinstance(self.host, str):
            raise ConfigError("API host must be a literal IP address string.")
        try:
            address = ipaddress.ip_address(self.host)
        except ValueError as exc:
            raise ConfigError("API host must be a literal IP address.") from exc
        if type(self.allow_non_loopback) is not bool:
            raise ConfigError("allow_non_loopback must be a boolean.")
        for name in ("port", "max_conversations", "conversation_idle_seconds", "max_request_bytes", "database_max_mib", "retrieval_context_tokens"):
            value = getattr(self, name)
            if type(value) is not int or value < 1 or (name == "port" and value > 65535):
                raise ConfigError(f"Invalid API {name}.")
        if self.database_path is not None:
            validate_database_path(self.database_path)
        if self.retrieval_index_path is not None:
            validate_database_path(self.retrieval_index_path)
            if self.database_path and Path(self.database_path).resolve() == Path(self.retrieval_index_path).resolve():
                raise ConfigError("Conversation database and retrieval index must be separate files.")
        if self.retrieval_default is not None:
            if self.retrieval_default not in ("auto", "off"):
                raise ConfigError('retrieval_default must be "auto" or "off"; forced retrieval is per request only.')
            if self.retrieval_index_path is None:
                raise ConfigError("retrieval_default requires retrieval_index_path.")
        for name in ("allowed_hosts", "allowed_origins"):
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)) or any(not isinstance(v, str) for v in values):
                raise ConfigError(f"{name} must be a list of strings.")
        if not self.allowed_hosts:
            raise ConfigError("allowed_hosts must not be empty.")
        for host in self.allowed_hosts:
            try:
                ipaddress.ip_address(host)
            except ValueError:
                if not re.fullmatch(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*", host):
                    raise ConfigError("allowed_hosts must contain exact hostnames or IPs, no wildcards.")
        for origin in self.allowed_origins:
            try:
                parsed = urlsplit(origin)
                port = parsed.port
            except ValueError as exc:
                raise ConfigError("Invalid allowed origin.") from exc
            if (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username or parsed.password or parsed.path or parsed.query
                    or parsed.fragment or "*" in origin or origin.endswith(":")):
                raise ConfigError("Origins must be exact http(s) scheme/host/port values.")
        if not isinstance(self.token_env, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.token_env):
            raise ConfigError("token_env must name an environment variable.")
        token = os.environ.get(self.token_env)
        if token is not None and (len(token) < 32 or not token.isascii() or any(c.isspace() for c in token)):
            raise ConfigError("Configured API token must be at least 32 non-whitespace ASCII characters.")
        if bool(self.ssl_certfile) != bool(self.ssl_keyfile):
            raise ConfigError("Configure both ssl_certfile and ssl_keyfile.")
        if not address.is_loopback and not (self.allow_non_loopback and token and self.ssl_certfile):
            raise ConfigError("Non-loopback requires explicit opt-in, bearer token, and TLS certificate/key.")
        if self.ssl_certfile:
            try:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(self.ssl_certfile, self.ssl_keyfile, password=lambda: "")
            except (OSError, ValueError, TypeError) as exc:
                raise ConfigError("Cannot load API TLS certificate/key.") from exc
        return token


def validate_database_path(value):
    if (not isinstance(value, str) or not value.strip() or value == ":memory:"
            or value.startswith(("\\\\", "//")) or "://" in value
            or value.lower().startswith("file:") or "?" in value or "\x00" in value):
        raise ConfigError("database_path must be a physical local file path, not a URL, URI or UNC path.")


def load_api_config(path=None) -> ApiConfig:
    data = {}
    if path is not None:
        source = Path(path).expanduser().resolve()
        try:
            with source.open("rb") as handle:
                data = tomllib.load(handle)
        except (OSError, ValueError) as exc:
            raise ConfigError("Cannot read API TOML configuration.") from exc
        unknown = data.keys() - {f.name for f in fields(ApiConfig)}
        if unknown:
            raise ConfigError(f"Unknown API configuration keys: {', '.join(sorted(unknown))}")
        if "database_path" in data:
            validate_database_path(data["database_path"])
        if "retrieval_index_path" in data:
            validate_database_path(data["retrieval_index_path"])
        for key in ("ssl_certfile", "ssl_keyfile", "database_path", "retrieval_index_path"):
            if key in data:
                if not isinstance(data[key], str) or not data[key]:
                    raise ConfigError(f"{key} must be a nonempty local path.")
                data[key] = str((source.parent / Path(data[key]).expanduser()).resolve())
    cfg = ApiConfig(**data)
    cfg.validate()
    return cfg


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Dwindy local HTTP API (one process, one model)")
    parser.add_argument("--config", help="Existing model TOML configuration")
    parser.add_argument("--model", help="Explicit local GGUF override")
    parser.add_argument("--api-config", help="Optional API-only TOML configuration")
    parser.add_argument("--chat-root", help="Opt in to frontend hosting from a bundle containing web/ and assets/")
    args = parser.parse_args(argv)
    try:
        api_config = load_api_config(args.api_config)
        model_config = load_config(args.config, args.model)
        try:
            import uvicorn
            from .api import create_app
        except ImportError:
            print('Install the optional API dependencies: pip install -e ".[api]"', file=sys.stderr)
            return 1
        app = create_app(model_config, api_config, chat_root=args.chat_root)
        if api_config.retrieval_index_path is not None:
            mode = api_config.retrieval_default or "auto"
            print(f"Local context: {mode} by default. Clients may send retrieval=false; "
                  f'set retrieval_default = "{"auto" if mode == "off" else "off"}" in the API configuration to change it.',
                  file=sys.stderr)
        server = uvicorn.Server(uvicorn.Config(app, host=api_config.host, port=api_config.port,
                    workers=1, reload=False, loop="asyncio", http="h11", ws="none",
                    proxy_headers=False, access_log=False, server_header=False,
                    timeout_graceful_shutdown=1,
                    ssl_certfile=api_config.ssl_certfile, ssl_keyfile=api_config.ssl_keyfile))
        server.run()
        return 0 if server.started else 1
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
