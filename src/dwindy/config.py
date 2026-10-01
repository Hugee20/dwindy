"""Explicit TOML configuration; no discovery, downloads, or writes."""

from dataclasses import dataclass, field
import math
from pathlib import Path
import tomllib

from .backend import GenerationOptions


class ConfigError(ValueError):
    pass


# Owned by Jinja2ChatFormatter, rather than model-specific template options.
RESERVED_TEMPLATE_ARGUMENTS = frozenset({
    "self", "messages", "functions", "function_call", "tools", "tool_choice",
    "bos_token", "eos_token", "add_generation_prompt", "raise_exception",
    "strftime_now",
})


def validate_template_kwargs(value) -> dict[str, str | bool | int | float]:
    if not isinstance(value, dict):
        raise ConfigError("chat_template_kwargs must be a TOML table.")
    for key, item in value.items():
        if (not isinstance(key, str) or not key.isidentifier() or key.startswith("_")
                or key in RESERVED_TEMPLATE_ARGUMENTS):
            raise ConfigError(f"Invalid or reserved chat-template argument: {key!r}.")
        if (type(item) not in (str, bool, int, float)
                or (type(item) is float and not math.isfinite(item))):
            raise ConfigError(f"chat_template_kwargs.{key} must be a string, boolean, "
                              "integer, or finite float.")
    return dict(value)


@dataclass(frozen=True)
class Config:
    model_path: Path
    context_size: int = 4096
    max_tokens: int = 256
    temperature: float = 0.7
    seed: int = 42
    threads: int | None = None
    system_prompt: str = ""
    chat_template_kwargs: dict[str, str | bool | int | float] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "chat_template_kwargs",
                           validate_template_kwargs(self.chat_template_kwargs))

    def options(self) -> GenerationOptions:
        return GenerationOptions(self.max_tokens, self.temperature, self.seed)


def load_config(path: str | Path | None = None,
                model_path: str | Path | None = None) -> Config:
    values = {}
    base = Path.cwd()
    if path is not None:
        config_path = Path(path).expanduser().resolve()
        base = config_path.parent
        try:
            with config_path.open("rb") as handle:
                values = tomllib.load(handle)
        except (OSError, ValueError) as exc:
            raise ConfigError(f"Cannot read TOML configuration: {exc}") from exc
    unknown = values.keys() - Config.__dataclass_fields__.keys()
    if unknown:
        raise ConfigError(f"Unknown configuration keys: {', '.join(sorted(unknown))}")
    if model_path is not None:
        values["model_path"] = str(model_path)
        base = Path.cwd()  # CLI paths are relative to the working directory.
    raw_path = values.get("model_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ConfigError("Supply a local GGUF using --model or model_path in TOML.")
    if "://" in raw_path or raw_path.startswith(("\\\\", "//")):
        raise ConfigError("Model paths must be local files, not URLs or UNC shares.")
    local_path = Path(raw_path).expanduser()
    if not local_path.is_absolute():
        local_path = base / local_path
    local_path = local_path.resolve()
    if local_path.suffix.lower() != ".gguf" or not local_path.is_file():
        raise ConfigError("model_path must point to an existing local .gguf file.")
    values["model_path"] = local_path
    cfg = Config(**values)
    for key in ("context_size", "max_tokens", "seed", "threads"):
        value = getattr(cfg, key)
        if key == "threads" and value is None:
            continue
        minimum = 0 if key == "seed" else 1
        if type(value) is not int or value < minimum:
            raise ConfigError(f"{key} must be an integer >= {minimum}.")
    if cfg.seed > 2**32 - 1:
        raise ConfigError("seed must fit an unsigned 32-bit integer.")
    if cfg.max_tokens >= cfg.context_size:
        raise ConfigError("max_tokens must be smaller than context_size.")
    if (type(cfg.temperature) not in (int, float)
            or not math.isfinite(cfg.temperature) or not 0 <= cfg.temperature <= 2):
        raise ConfigError("temperature must be a finite number between 0 and 2.")
    if not isinstance(cfg.system_prompt, str):
        raise ConfigError("system_prompt must be a string.")
    return cfg
