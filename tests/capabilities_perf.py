"""M9 deterministic-capability overhead in a fresh process; no model."""
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from dwindy.capabilities import calculate, select
from tools.evaluate import load


def percentile(durations, fraction):
    return sorted(durations)[max(0, int(len(durations) * fraction) - 1)] * 1000


def run():
    import psutil  # Existing optional eval extra; measurement only.
    process = psutil.Process()
    cases = load('cases.jsonl')
    arithmetic = [c['message'] for c in cases if c['expected']['calculator'] == 'result']
    adversarial = [c['message'] for c in cases if c['category'] == 'adversarial_expression']
    everything = [c['message'] for c in cases]
    for message in everything:
        select(message)  # Warm imports and regex caches.
    before = process.memory_info().rss

    def timed(messages, fn, rounds):
        durations = []
        for _ in range(rounds):
            for message in messages:
                start = time.perf_counter(); fn(message); durations.append(time.perf_counter() - start)
        return durations

    calculator = timed(arithmetic, calculate, 200)
    adversarial_worst = max(timed(adversarial, calculate, 50)) * 1000
    selection = timed(everything, select, 100)
    print(json.dumps(dict(
        calculator_p50_ms=statistics.median(calculator) * 1000, calculator_p95_ms=percentile(calculator, .95),
        adversarial_worst_ms=adversarial_worst,
        select_all_cases_p95_ms=percentile(selection, .95),
        rss_increase_bytes=process.memory_info().rss - before,
        note='Fresh process after imports and one warm-up pass; 12,000+ timed calls.'), indent=2))


if __name__ == '__main__':
    run()
