"""Shared test doubles: a fake OpenAI client and helpers for SDK errors. No key, no network."""

import inspect
import json
from types import SimpleNamespace
from typing import Any

import pytest
from openai.resources.responses import AsyncResponses

REQUEST = SimpleNamespace(method="POST", url="https://api.openai.com/v1/responses")


def status_error(cls: type, status: int, message: str = "boom") -> Exception:
    """Build an OpenAI status error for a test: status_error(RateLimitError, 429)."""
    return cls(message, response=SimpleNamespace(request=REQUEST, status_code=status, headers={}), body=None)


def _usage(usage: tuple[int, int] | None) -> SimpleNamespace | None:
    return SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1]) if usage else None


class FakeOpenAI:
    """Stands in for AsyncOpenAI. Queue the replies in order, then assert on `requests`."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.replies: list[Any] = []
        self.responses = self  # so that client.responses.create(...) works
        self._calls = 0

    def will_say(self, text: str, status: str = "completed", usage: tuple[int, int] | None = None) -> None:
        """The next reply is a final text answer. status="incomplete" imitates a reply that was cut off.
        usage=(input_tokens, output_tokens) adds token counts; without it the reply has usage None."""
        part = SimpleNamespace(type="output_text", text=text)
        message = SimpleNamespace(type="message", role="assistant", content=[part])
        self.replies.append(
            SimpleNamespace(output=[message], output_text=text, status=status, usage=_usage(usage))
        )

    def will_call(self, *calls: tuple[str, dict[str, Any]], usage: tuple[int, int] | None = None) -> None:
        """The next reply asks for tools: will_call(("get_weather", {"city": "Haifa"}), ...)."""
        output = []
        for name, args in calls:
            self._calls += 1
            call_id = f"call_{self._calls}"
            output.append(
                SimpleNamespace(type="function_call", name=name, arguments=json.dumps(args), call_id=call_id)
            )
        self.replies.append(
            SimpleNamespace(output=output, output_text="", status="completed", usage=_usage(usage))
        )

    def will_raise(self, error: Exception) -> None:
        """The next call raises error."""
        self.replies.append(error)

    async def create(self, **request: Any) -> Any:
        # the same keywords as the real SDK: a Chat Completions parameter such as `messages` fails here
        inspect.signature(AsyncResponses.create).bind(None, **request)
        if isinstance(request.get("input"), list):
            request["input"] = list(request["input"])  # a snapshot: the caller keeps appending to its list
        self.requests.append(request)
        if not self.replies:
            raise AssertionError("unexpected model call: the test queued no reply for it")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def fake_openai() -> FakeOpenAI:
    """A fresh FakeOpenAI with no queued replies."""
    return FakeOpenAI()
