"""Ollama client tests with a fake session (no network)."""

from __future__ import annotations

import json

import pytest

from src.pipeline.ollama_client import MAX_ATTEMPTS, DEFAULT_BACKOFF, OllamaClient, OllamaError


class FakeResponse:
    def __init__(self, payload: dict = None, status: int = 200, raise_exc=None):
        self._payload = {} if payload is None else payload
        self.status_code = status
        self._raise_exc = raise_exc

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self._raise_exc is not None:
            raise self._raise_exc


class FakeSession:
    def __init__(self):
        self.posts: list[tuple[str, dict]] = []
        self.gets: list[tuple[str, dict]] = []
        self.responses: list = []
        self.get_responses: list = []

    def post(self, url, json=None, timeout=None):
        self.posts.append((url, json))
        if self.responses:
            return self.responses.pop(0)
        return FakeResponse({})

    def get(self, url, timeout=None):
        self.gets.append((url, timeout))
        info = {"models": [{"name": "padauk-gemma:q8_0"}]}
        return FakeResponse(info)


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def client(session):
    return OllamaClient(host="http://fake:1", model="padauk-gemma:q8_0", session=session)


def test_generate_payload_shape(client, session):
    session.responses.append(FakeResponse({"response": "အဖြေ"}))
    out = client.generate("translate this")
    assert out == "အဖြေ"
    url, payload = session.posts[0]
    assert url.endswith("/api/generate")
    assert payload["model"] == "padauk-gemma:q8_0"
    assert payload["think"] is False
    assert payload["keep_alive"] == -1
    assert payload["options"]["temperature"] == 0.2
    assert "stream" in payload


def test_generate_system_and_num_predict(client, session):
    session.responses.append(FakeResponse({"response": "x"}))
    client.generate("p", system="sys", num_predict=100)
    _, payload = session.posts[0]
    assert payload.get("system") == "sys"
    assert payload["options"]["num_predict"] == 100


def test_generate_retries_on_timeout_then_raises(client, session):
    from requests import Timeout

    session.responses = [FakeResponse(raise_exc=Timeout())] * MAX_ATTEMPTS
    with pytest.raises(OllamaError) as ei:
        client.generate("p")
    assert ei.value.code == "E_TIMEOUT"
    assert len(session.posts) == MAX_ATTEMPTS


def test_generate_connection_error_raises_e_conn(client, session):
    from requests import ConnectionError

    session.responses = [FakeResponse(raise_exc=ConnectionError())] * MAX_ATTEMPTS
    with pytest.raises(OllamaError) as ei:
        client.generate("p")
    assert ei.value.code == "E_CONN"


def test_generate_empty_output_retries_once_at_higher_temp(client, session):
    session.responses = [
        FakeResponse({"response": ""}),  # first empty -> retry at 0.5
        FakeResponse({"response": "ok"}),  # retry succeeds
    ]
    out = client.generate("p")
    assert out == "ok"
    assert len(session.posts) == 2
    # second attempt used temperature 0.5
    assert session.posts[1][1]["options"]["temperature"] == 0.5


def test_generate_empty_twice_raises_e_empty(client, session):
    session.responses = [
        FakeResponse({"response": ""}),
        FakeResponse({"response": ""}),
    ]
    with pytest.raises(OllamaError) as ei:
        client.generate("p")
    assert ei.value.code == "E_EMPTY"


def test_generate_ping_and_models(client, session):
    assert client.ping() is True
    assert "padauk-gemma:q8_0" in client.models()


def test_generate_http_error_raises(client, session):
    from requests import HTTPError

    session.responses = [FakeResponse(raise_exc=HTTPError("boom"))] * MAX_ATTEMPTS
    with pytest.raises(OllamaError) as ei:
        client.generate("p")
    assert ei.value.code == "E_HTTP"


def test_generate_http_status_error(client, session):
    session.responses = [FakeResponse(status=500, payload={"error": "x"})] * MAX_ATTEMPTS
    with pytest.raises(OllamaError):
        client.generate("p")


def test_parse_passthrough(client):
    assert client.parse_translations('{"translations":["a"]}') == ["a"]
    assert client.parse_results('{"results":[{"k":1}]}') == [{"k": 1}]


def _unload_posts(session):
    return [p for _, p in session.posts if p.get("keep_alive") == 0]


def test_generate_unloads_previous_model_on_switch(client, session):
    # 3 posts expected: generate(a), unload(a), generate(b)
    session.responses = [
        FakeResponse({"response": "a"}),
        FakeResponse({}),  # consumed by the unload POST
        FakeResponse({"response": "b"}),
    ]
    assert client.generate("p1", model="model-a") == "a"
    assert client.generate("p2", model="model-b") == "b"

    unloads = _unload_posts(session)
    assert len(unloads) == 1
    assert unloads[0]["model"] == "model-a"
    assert unloads[0]["prompt"] == ""
    assert unloads[0]["keep_alive"] == 0
    assert client.loaded_model == "model-b"  # now on the new model


def test_generate_no_unload_on_same_model(client, session):
    session.responses = [
        FakeResponse({"response": "a"}),
        FakeResponse({"response": "b"}),
    ]
    client.generate("p1", model="model-a")
    client.generate("p2", model="model-a")
    assert _unload_posts(session) == []


def test_generate_unload_clears_loaded_model(client, session):
    # 3 posts expected: generate(a), unload(a), generate(b)
    session.responses = [
        FakeResponse({"response": "a"}),
        FakeResponse({}),
        FakeResponse({"response": "b"}),
    ]
    client.generate("p1", model="model-a")
    assert client.loaded_model == "model-a"
    client.generate("p2", model="model-b")
    assert client.loaded_model == "model-b"


def test_generate_unload_clears_loaded_model_after_switch(client, session):
    session.responses = [
        FakeResponse({"response": "a"}),  # generate(a)
        FakeResponse({}),                 # unload(a)
        FakeResponse({"response": "b"}),  # generate(b)
    ]
    client.generate("p1", model="model-a")
    client.generate("p2", model="model-b")
    assert client.loaded_model == "model-b"
    assert _unload_posts(session)[0]["model"] == "model-a"


def test_unload_explicit_leaves_other_model_loaded(client, session):
    session.responses = [FakeResponse({"response": "a"}), FakeResponse({"response": "b"})]
    client.generate("p1", model="model-a")
    client.unload("model-a")
    assert client.loaded_model is None
    assert _unload_posts(session)[-1]["model"] == "model-a"