import asyncio
import logging

import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError

from tests.conftest import REQUEST, FakeOpenAI, status_error


def test_healthz_does_not_touch_the_model(client: TestClient, fake_openai: FakeOpenAI) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200 and response.json() == {"status": "ok"}
    assert fake_openai.requests == []


def test_ask_returns_the_answer_and_sends_the_configured_model(
    client: TestClient, fake_openai: FakeOpenAI
) -> None:
    fake_openai.will_say("pong")
    response = client.post("/v1/ask", json={"question": "  ping  "})
    assert response.status_code == 200
    assert response.json() == {"answer": "pong", "model": "test-model"}
    sent = fake_openai.requests[0]
    assert sent["model"] == "test-model" and sent["input"] == "ping"  # whitespace was stripped
    assert sent["instructions"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": ""},
        {"question": "   "},
        {"question": "x" * 4001},
        {"question": "hi", "admin": True},
        {"question": 5},
    ],
)
def test_bad_input_is_rejected_before_the_model_is_called(
    client: TestClient, fake_openai: FakeOpenAI, body: dict
) -> None:
    response = client.post("/v1/ask", json=body)
    assert response.status_code == 422
    assert fake_openai.requests == []


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (APITimeoutError(REQUEST), 504, "upstream_timeout"),  # type: ignore[arg-type]
        (APIConnectionError(request=REQUEST), 502, "upstream_unreachable"),  # type: ignore[arg-type]
        (status_error(RateLimitError, 429), 503, "upstream_rate_limited"),
        (
            status_error(AuthenticationError, 401, "Incorrect API key provided: sk-secret"),
            502,
            "upstream_error",
        ),
    ],
)
def test_model_failures_become_clean_errors(
    client: TestClient, fake_openai: FakeOpenAI, error: Exception, status: int, code: str
) -> None:
    fake_openai.will_raise(error)
    response = client.post("/v1/ask", json={"question": "hi"})
    assert response.status_code == status
    body = response.json()
    assert body["error"]["code"] == code
    assert body["request_id"] == response.headers["x-request-id"]
    assert "sk-secret" not in response.text  # upstream messages never reach the client


def test_invalid_request_uses_the_same_error_shape_and_does_not_echo_the_value(client: TestClient) -> None:
    response = client.post("/v1/ask", json={"question": "hi", "password": "hunter2"})
    body = response.json()
    assert response.status_code == 422 and body["error"]["code"] == "invalid_request"
    assert body["error"]["fields"][0]["field"] == "body.password"
    assert body["request_id"] == response.headers["x-request-id"]
    assert "hunter2" not in response.text


def test_unknown_path_and_wrong_method_use_the_same_error_shape(client: TestClient) -> None:
    assert client.get("/nope").json()["error"]["code"] == "http_404"
    response = client.get("/v1/ask")
    assert response.status_code == 405 and response.json()["error"]["code"] == "http_405"


def test_a_bug_in_our_code_is_a_clean_500(client: TestClient, fake_openai: FakeOpenAI) -> None:
    fake_openai.will_raise(RuntimeError("boom sk-secret"))
    response = client.post("/v1/ask", json={"question": "hi"})
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal error."},
        "request_id": response.headers["x-request-id"],
    }


def test_request_id_is_generated_or_taken_from_a_safe_header(client: TestClient) -> None:
    generated = client.get("/healthz").headers["x-request-id"]
    assert len(generated) == 12
    assert client.get("/healthz", headers={"x-request-id": "abc-123"}).headers["x-request-id"] == "abc-123"
    unsafe = client.get("/healthz", headers={"x-request-id": "a b\tc"}).headers["x-request-id"]
    assert unsafe != "a b\tc" and len(unsafe) == 12


def test_openapi_documents_the_contract(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/v1/ask" in schema["paths"] and "/healthz" in schema["paths"]


def test_the_fake_rejects_parameters_the_real_sdk_does_not_have(fake_openai: FakeOpenAI) -> None:
    fake_openai.will_say("x")
    with pytest.raises(TypeError):
        asyncio.run(fake_openai.create(model="m", messages=[]))  # Chat Completions shape
    with pytest.raises(AssertionError, match="unexpected model call"):
        asyncio.run(FakeOpenAI().create(model="m", input="hi"))


def test_log_lines_are_visible_to_caplog_and_carry_no_question(
    client: TestClient, fake_openai: FakeOpenAI, caplog: pytest.LogCaptureFixture
) -> None:
    fake_openai.will_say("pong")
    with caplog.at_level(logging.INFO, logger="app"):
        client.post("/v1/ask", json={"question": "my secret question"})
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "POST /v1/ask status=200" in text
    assert "my secret question" not in text
