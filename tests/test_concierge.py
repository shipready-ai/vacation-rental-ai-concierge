import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import concierge  # noqa: E402


def text(t):
    return SimpleNamespace(type="text", text=t)


def ask_host(summary):
    return SimpleNamespace(type="tool_use", id="tu_1", name="ask_host", input={"summary": summary, "urgency": "normal"})


class FakeClient:
    """Replays scripted responses, one per request."""

    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    @contextmanager
    def _stream(self, **kwargs):
        self.requests.append(kwargs)
        content = self.responses.pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        yield SimpleNamespace(
            text_stream=[b.text for b in content if b.type == "text"],
            get_final_message=lambda: SimpleNamespace(content=content, stop_reason=stop),
        )


def test_answers_from_facts_with_cached_system():
    client = FakeClient([text("Check-in is from 14:00.")])
    out, messages = [], [{"role": "user", "content": "When can I check in?"}]
    concierge.reply(client, "Check-in from 14:00.", messages, on_text=out.append)
    assert "".join(out) == "Check-in is from 14:00."
    system = client.requests[0]["system"][0]
    assert "Check-in from 14:00." in system["text"] and system["cache_control"] == {"type": "ephemeral"}


def test_ask_host_then_answer():
    client = FakeClient([ask_host("Guest wants late check-out")], [text("I asked the host.")])
    alerts, messages = [], [{"role": "user", "content": "Can I leave at 2pm?"}]
    concierge.reply(client, "facts", messages, on_ask_host=lambda s, u: alerts.append(s))
    assert alerts == ["Guest wants late check-out"]
    assert messages[2]["content"][0]["tool_use_id"] == "tu_1"
    assert len(client.requests) == 2
