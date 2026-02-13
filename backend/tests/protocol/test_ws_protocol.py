import pytest

from app.gateway.protocol import (
    ProtocolError,
    make_challenge,
    make_event,
    make_response,
    parse_connect,
    parse_request,
)


def test_make_challenge():
    msg = make_challenge("abc")
    assert msg.type == "connect.challenge"
    assert msg.nonce == "abc"
    assert msg.protocol == "ws.v1"


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


def test_parse_connect_invalid():
    with pytest.raises(ProtocolError):
        parse_connect({"type": "connect", "nonce": "n"})


def test_parse_request_ok():
    req = parse_request({"type": "req", "id": "1", "method": "health.get", "params": {}})
    assert req.method == "health.get"


def test_make_response_and_event():
    res = make_response(req_id="1", result={"ok": True})
    ev = make_event(event="heartbeat", data={"ok": True})
    assert res.type == "res"
    assert ev.type == "event"
