"""Terminal client and application wiring for Dwindy Core."""

import argparse
import sys
from .backend import BackendError, Completion, TextDelta
from .config import ConfigError, load_config
from .core import DwindyCore, TurnStarted


def terminal(core: DwindyCore, read=input, output=None) -> None:
    output = output or sys.stdout
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
            core.reset()
            print("History cleared.", file=output)
            continue
        if not user:
            continue
        stream = None
        try:
            stream = core.chat(user)
            for event in stream:
                if isinstance(event, TurnStarted):
                    if event.dropped_turns:
                        print(f"[Dropped {event.dropped_turns} oldest turn(s) to fit context.]",
                              file=output)
                    print("Dwindy> ", end="", file=output, flush=True)
                elif isinstance(event, TextDelta):
                    print(event.text, end="", file=output, flush=True)
                elif isinstance(event, Completion):
                    print(file=output)
                    if event.finish_reason == "length":
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
        core = DwindyCore(backend, options=config.options(), system_prompt=config.system_prompt)
        terminal(core)
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
