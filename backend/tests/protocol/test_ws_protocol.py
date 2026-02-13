import pytest

from app.gateway.protocol import (
    ProtocolError,
    make_challenge,
    make_event,
    make_response,
    parse_connect,
    parse_connect_request,
    parse_request,
)


def test_make_challenge():
    msg = make_challenge("abc")
    assert msg.type == "event"
    assert msg.event == "connect.challenge"
    assert msg.payload["nonce"] == "abc"
    assert msg.payload["protocol"] == 3


def test_parse_connect_ok():
    msg = parse_connect(
        {
            "type": "connect",
            "token": "t",
            "nonce": "n",
            "client": {"name": "tests", "version": "1.0"},
        }
    )
    assert msg.type == "connect"
    assert msg.client.name == "tests"


def test_parse_connect_request_ok():
    req = parse_connect_request(
        {
            "type": "req",
            "id": "c1",
            "method": "connect",
            "params": {
                "token": "t",
                "nonce": "n",
                "client": {"name": "tests", "version": "1.0"},
            },
        }
    )
    assert req.token == "t"


def test_parse_connect_invalid():
    with pytest.raises(ProtocolError):
        parse_connect({"type": "connect", "nonce": "n"})


def test_parse_request_ok():
    req = parse_request({"type": "req", "id": "1", "method": "health.get", "params": {}})
    assert req.method == "health.get"


def test_make_response_and_event():
    res = make_response(req_id="1", payload={"ok": True})
    ev = make_event(event="heartbeat", payload={"ok": True})
    assert res.type == "res"
    assert ev.type == "event"
