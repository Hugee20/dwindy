"""Historical quoted-history decoder; never used by production assertions."""
from dwindy.backend import Message
def conversation_messages(messages):
    """Observe the model transcript as native messages for legacy state assertions.

    This decoder is test-only: generation never parses or verifies historical text.
    Focused v3 tests separately assert the actual backend roles and byte representation.
    """
    import json
    from policy_experiments.v3.evidence import history_block
    values = list(messages)
    content = values[-1].content
    header = "Conversation history (quoted):\n"
    separator = "\nEnd quoted history.\nCurrent turn:\n"
    if content.startswith(header):
        transcript, current = content[len(header):].split(separator, 1)
        history = []
        for line in transcript.splitlines():
            speaker, text = line.split(" text=", 1)
            history.append(Message(speaker.lower(), json.loads(text)))
        assert history_block(history) + current == content
        return values[:-1] + history + [Message("user", current)]
    return values
