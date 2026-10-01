"""M1 terminal client; conversations exist only in process memory."""

import argparse
import sys
from typing import Sequence

from .backend import BackendError, Completion, Message, ModelBackend, TextDelta
from .config import Config, ConfigError, load_config


def bounded_messages(backend: ModelBackend, history: Sequence[Message],
                     user: str, config: Config) -> list[Message]:
    prefix = [Message("system", config.system_prompt)] if config.system_prompt else []
    recent = list(history)
    while True:
        messages = prefix + recent + [Message("user", user)]
        if backend.count_tokens(messages) + config.max_tokens <= backend.context_size():
            return messages
        if not recent:
            raise BackendError("Current message cannot fit with the generation allowance. "
                               "Shorten it or adjust the context/output settings.")
        del recent[:2]  # Drop oldest complete user/assistant turn.


def terminal(backend: ModelBackend, config: Config, read=input, output=None) -> None:
    output = output or sys.stdout
    history = []
    print("Dwindy: local CPU chat. /reset clears history; /exit quits.", file=output)
    while True:
        try:
            user = read("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.", file=output)
            return
        if user == "/exit":
            return
        if user == "/reset":
            history.clear()
            print("History cleared.", file=output)
            continue
        if not user:
            continue
        stream = None
        try:
            messages = bounded_messages(backend, history, user, config)
            removed = len(history) - sum(m.role != "system" for m in messages[:-1])
            if removed:
                print(f"[Dropped {removed // 2} oldest turn(s) to fit context.]", file=output)
            print("Dwindy> ", end="", file=output, flush=True)
            pieces = []
            completion = None
            stream = backend.generate(messages, config.options())
            for event in stream:
                if isinstance(event, TextDelta):
                    pieces.append(event.text)
                    print(event.text, end="", file=output, flush=True)
                elif isinstance(event, Completion):
                    completion = event
            if completion is None:
                raise BackendError("Backend ended without a completion result.")
            response = "".join(pieces)
            if not response.strip():
                raise BackendError("Model produced no visible answer; turn not retained.")
            history = [m for m in messages if m.role != "system"]
            history.append(Message("assistant", response))
            print(file=output)
            if completion.finish_reason == "length":
                print("[Output limit reached.]", file=output)
        except KeyboardInterrupt:
            print("\n[Generation interrupted; turn not retained.]", file=output)
        except BackendError as exc:
            print(f"\nError: {exc}", file=output)
        finally:
            if stream is not None and hasattr(stream, "close"):
                stream.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Dwindy offline CPU terminal chat")
    parser.add_argument("--config", help="Explicit TOML configuration file")
    parser.add_argument("--model", help="Existing local GGUF; overrides TOML model_path")
    args = parser.parse_args(argv)
    backend = None
    try:
        config = load_config(args.config, args.model)
        from .llama_backend import LlamaBackend
        backend = LlamaBackend(config)
        terminal(backend, config)
        return 0
    except (ConfigError, BackendError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    finally:
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    raise SystemExit(main())
