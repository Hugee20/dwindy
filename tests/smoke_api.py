"""Explicit real-GGUF HTTP smoke test, separate from the frozen M1 evaluation.

Run from the repository root: python tests/smoke_api.py --config <model TOML>
Prints synthetic responses and checks; does not write transcripts or change config.
"""
import argparse
import json
import time

from dwindy.api import create_app
from dwindy.config import load_config
from dwindy.server import ApiConfig
from test_api_http import live_server, wait_for


def first_delta(response):
    response.raise_for_status()
    for line in response.iter_lines():
        if line.startswith("data: "):
            data = json.loads(line[6:])
            if "text" in data:
                return data["text"]
    raise AssertionError("No streamed text received")


def run(path):
    config = load_config(path)
    api_config = ApiConfig()
    token = api_config.validate()
    app = create_app(config, api_config)
    results = {"model": config.model_path.name, "context_size": config.context_size,
               "max_tokens": config.max_tokens, "temperature": config.temperature,
               "seed": config.seed, "chat_template_kwargs": config.chat_template_kwargs}
    with live_server(app, startup_timeout=120) as (client, server, thread):
        client.timeout = 180
        if token:
            client.headers["Authorization"] = "Bearer " + token
        assert client.get("/v1/health").json() == {"status": "ready", "busy": False}
        first = client.post("/v1/chat", json={"message":
            "Remember the code word CEDAR for this conversation. Reply only OK."})
        first.raise_for_status()
        key = first.json()["conversation_id"]
        second = client.post("/v1/chat", json={"conversation_id": key,
            "message": "What is the code word? Reply with just that word."})
        second.raise_for_status()
        results["first_answer"] = first.json()["text"]
        results["recall_answer"] = second.json()["text"]
        assert "CEDAR" in second.json()["text"]
        core = app.state.dwindy.conversations[key].core
        assert len(core._history) == 4
        streamed = client.post("/v1/chat", json={"conversation_id": key, "stream": True,
            "message": "Repeat the code word only."})
        streamed.raise_for_status()
        names = [line[7:] for line in streamed.text.splitlines() if line.startswith("event: ")]
        assert names[0] == "started" and names[-1] == "completed" and "delta" in names and "error" not in names
        results["stream_event_counts"] = {name: names.count(name) for name in set(names)}
        history_before = list(core._history)
        with client.stream("POST", "/v1/chat", json={"conversation_id": key, "stream": True,
                "message": "List the integers from 1 to 100, one per line."}) as response:
            results["cancelled_first_delta"] = first_delta(response)
        stopped = time.monotonic()
        wait_for(lambda: not client.get("/v1/health").json()["busy"], timeout=120)
        results["disconnect_recovery_seconds"] = round(time.monotonic() - stopped, 3)
        assert core._history == history_before
        results["cancelled_turn_rolled_back"] = True
        recovered = client.post("/v1/chat", json={"conversation_id": key,
            "message": "What code word did I give you? Reply with just that word."})
        recovered.raise_for_status()
        results["recovery_answer"] = recovered.json()["text"]
        assert "CEDAR" in recovered.json()["text"]
        assert client.delete("/v1/conversations/" + key).status_code == 204
        assert client.post("/v1/chat", json={"conversation_id": key, "message": "hello"}).status_code == 404
        fresh = client.post("/v1/chat", json={"message": "Reply only FRESH."})
        fresh.raise_for_status()
        fresh_key = fresh.json()["conversation_id"]
        assert fresh_key != key
        assert len(app.state.dwindy.conversations[fresh_key].core._history) == 2
        results["fresh_answer"] = fresh.json()["text"]
        results["deleted_and_new_conversation"] = True
        with client.stream("POST", "/v1/chat", json={"conversation_id": fresh_key, "stream": True,
                "message": "List the integers from 1 to 100, one per line."}) as response:
            first_delta(response)
            server.should_exit = True
            thread.join(timeout=120)
            assert not thread.is_alive(), "Server did not drain active generation"
    assert not app.state.dwindy.busy and not app.state.dwindy.conversations
    assert app.state.dwindy.backend._model is None
    results["shutdown_during_generation_and_model_cleanup"] = True
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    run(parser.parse_args().config)
