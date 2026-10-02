"""Terminal client and application wiring for Dwindy Core."""

import argparse
import sys
from .backend import BackendError, Completion, TextDelta
from .config import ConfigError, load_config
from .capabilities import select as select_capabilities
from .core import DwindyCore, TurnStarted
from .evidence import Facts
from .reach import decide as reach_decide, local_relevant as reach_local_relevant
from .retrieval import RetrievalError


def terminal(core: DwindyCore, read=input, output=None, *, index=None, mode="off") -> None:
    """An optional RetrievalIndex selects local context through the same policy as the API."""
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
        stream = decision = evidence = None
        try:
            if index is not None:
                from .context_policy import decide
                snapshot = index.project_snapshot
                decision, evidence = decide(user, mode, search=index.search,
                                            project_name=snapshot["name"] if snapshot else None)
            # Clock and calculator facts are computed per turn; host context does not apply here.
            computed = select_capabilities(user)
            # The terminal has no Reach provider: only the offline-honesty notice can apply.
            snapshot = index.project_snapshot if index is not None else None
            _, _, notice = reach_decide(user, "off", project_name=snapshot["name"] if snapshot else None,
                                        local_relevant=reach_local_relevant(decision, evidence))
            stream = core.chat(user, evidence=evidence, facts=Facts(tuple((f.name, f.text) for f in computed)),
                               notice=notice)
            for event in stream:
                if isinstance(event, TurnStarted):
                    retrieval = decision.metadata(event.retrieval) if decision else None
                    if retrieval and retrieval["status"] == "supplied":
                        print(f"[Local context: {len(retrieval['sources'])} passage(s).]", file=output)
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
        except RetrievalError as exc:
            print(f"Error: {exc}", file=output)
        finally:
            if stream is not None and hasattr(stream, "close"):
                stream.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Dwindy offline CPU terminal chat")
    parser.add_argument("--config", help="Explicit TOML configuration file")
    parser.add_argument("--model", help="Existing local GGUF; overrides TOML model_path")
    parser.add_argument("--retrieval-index", help="Optional local retrieval or project index")
    parser.add_argument("--retrieval", choices=["auto", "on", "off"],
                        help="Local context mode; default auto when an index is given")
    args = parser.parse_args(argv)
    if args.retrieval and not args.retrieval_index:
        parser.error("--retrieval requires --retrieval-index")
    backend = index = None
    try:
        config = load_config(args.config, args.model)
        if args.retrieval_index:
            from .retrieval import RetrievalIndex
            index = RetrievalIndex(args.retrieval_index)
        from .llama_backend import LlamaBackend
        backend = LlamaBackend(config)
        core = DwindyCore(backend, options=config.options(), system_prompt=config.system_prompt)
        terminal(core, index=index, mode=args.retrieval or "auto")
        return 0
    except (ConfigError, BackendError, RetrievalError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    finally:
        if index is not None:
            index.close()
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    raise SystemExit(main())
