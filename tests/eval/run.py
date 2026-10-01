"""Explicit synthetic baseline runner. Does not read terminal conversations."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import threading
import time

from dwindy.backend import BackendError, Completion, Message, TextDelta
from dwindy.config import ConfigError, load_config


CATEGORIES = {"casual", "instruction", "reasoning", "transformation", "unknown", "context"}


def load_cases(path):
    cases = []
    ids = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        if (not isinstance(case, dict) or not isinstance(case.get("id"), str)
                or case["id"] in ids or case.get("category") not in CATEGORIES
                or not isinstance(case.get("rubric"), str) or not case["rubric"].strip()
                or not isinstance(case.get("messages"), list) or not case["messages"]):
            raise ValueError("Invalid or duplicate evaluation case.")
        for index, message in enumerate(case["messages"]):
            if (not isinstance(message, dict) or set(message) != {"role", "content"}
                    or message["role"] != ("user" if index % 2 == 0 else "assistant")
                    or not isinstance(message["content"], str) or not message["content"].strip()):
                raise ValueError(f"Invalid conversation in {case['id']}.")
        if case["messages"][-1]["role"] != "user":
            raise ValueError("Evaluation conversations must end with a user message.")
        ids.add(case["id"])
        cases.append(case)
    if not cases:
        raise ValueError("Empty evaluation dataset.")
    return cases


class MemorySampler:
    """Sample RSS, including native allocations, every 50 ms if psutil exists."""
    def __init__(self):
        self.peak = None
        self.total_ram = None
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        try:
            import psutil
        except ImportError:
            return
        process = psutil.Process()
        self.total_ram = psutil.virtual_memory().total
        def sample():
            while not self._stop.is_set():
                self.peak = max(self.peak or 0, process.memory_info().rss)
                self._stop.wait(0.05)
        self._thread = threading.Thread(target=sample, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join()


def evaluate_case(backend, case, config):
    messages = [Message(**m) for m in case["messages"]]
    if config.system_prompt:
        messages.insert(0, Message("system", config.system_prompt))
    result = {"type": "case", "id": case["id"], "category": case["category"],
              "rubric": case["rubric"], "response": "", "error": None,
              "human_score": None, "unsupported_claims": None,
              "first_text_seconds": None, "prompt_tokens": None,
              "text_tokens": None, "finish_reason": None}
    started = time.perf_counter()
    stream = None
    try:
        count = backend.count_tokens(messages)
        result["prompt_tokens"] = count
        if count + config.max_tokens > backend.context_size():
            raise BackendError("Evaluation prompt exceeds context; no truncation applied.")
        stream = backend.generate(messages, config.options())
        for event in stream:
            if isinstance(event, TextDelta):
                if event.text and result["first_text_seconds"] is None:
                    result["first_text_seconds"] = time.perf_counter() - started
                result["response"] += event.text
            elif isinstance(event, Completion):
                result.update(asdict(event))
        if result["finish_reason"] is None:
            raise BackendError("Missing completion result.")
        if not result["response"].strip():
            raise BackendError("No visible answer.")
    except BackendError as exc:
        result["error"] = str(exc)
    finally:
        if stream is not None and hasattr(stream, "close"):
            stream.close()
    result["elapsed_seconds"] = time.perf_counter() - started
    # Honest throughput proxy: includes prefill, and counts retokenized visible text.
    result["visible_text_tokens_per_second"] = (
        result["text_tokens"] / result["elapsed_seconds"]
        if result["text_tokens"] is not None and not result["error"] else None
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--model")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("core_v0.jsonl"))
    parser.add_argument("--output", required=True, type=Path,
                        help="Explicit local JSONL output; must not already exist")
    args = parser.parse_args(argv)
    backend = None
    memory = MemorySampler()
    try:
        config = load_config(args.config, args.model)
        cases = load_cases(args.dataset)
        with config.model_path.open("rb") as handle:
            model_hash = hashlib.file_digest(handle, "sha256").hexdigest()
        settings = asdict(config)
        settings.pop("model_path")  # No personal absolute path in results.
        dataset_hash = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
        # Exclusive creation prevents accidental replacement of previous results.
        with args.output.open("x", encoding="utf-8") as output:
            def emit(value):
                output.write(json.dumps(value, ensure_ascii=False) + "\n")
                output.flush()
            memory.start()
            from dwindy.llama_backend import LlamaBackend
            started = time.perf_counter()
            backend = LlamaBackend(config)
            load_seconds = time.perf_counter() - started
            emit({"type": "run", "started_utc": datetime.now(timezone.utc).isoformat(),
                  "dwindy_version": importlib.metadata.version("dwindy"),
                  "runtime_version": importlib.metadata.version("llama-cpp-python"),
                  "model_sha256": model_hash, "model_bytes": config.model_path.stat().st_size,
                  "dataset_sha256": dataset_hash, "settings": settings,
                  "effective_context_size": backend.context_size(),
                  "machine": {"os": platform.system(), "release": platform.release(),
                              "architecture": platform.machine(), "cpu": platform.processor(),
                              "logical_cpus": os.cpu_count(), "python": platform.python_version(),
                              "total_ram_bytes": memory.total_ram},
                  "model_load_seconds": load_seconds,
                  "measurement_note": "Actual machine only; not validation of the 8 GB target. "
                                      "Hashing before loading warms the file cache; not cold startup."})
            failures = 0
            for case in cases:
                result = evaluate_case(backend, case, config)
                failures += result["error"] is not None
                emit(result)
                print(f"{case['id']}: {'ERROR' if result['error'] else 'recorded'}")
            memory.stop()
            emit({"type": "summary", "cases": len(cases), "execution_errors": failures,
                  "sampled_peak_process_rss_bytes": memory.peak,
                  "quality_status": "Unscored; apply per-case human rubric."})
            return 1 if failures else 0
    except (ConfigError, BackendError, OSError, ValueError) as exc:
        print(f"Evaluation error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Evaluation interrupted; output may be partial.", file=sys.stderr)
        return 130
    finally:
        memory.stop()
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    raise SystemExit(main())
