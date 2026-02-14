"""Tests for the in-memory event bus."""
import asyncio
import pytest
from app.services.event_bus import InMemoryEventBus


@pytest.fixture()
def bus():
    return InMemoryEventBus()


@pytest.mark.asyncio
async def test_subscribe_and_receive(bus):
    sub_id, queue = await bus.subscribe()
    await bus.publish("test.event", {"key": "value"})
    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert msg["event"] == "test.event"
    assert msg["data"]["key"] == "value"
    await bus.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_multiple_subscribers(bus):
    sub1, q1 = await bus.subscribe()
    sub2, q2 = await bus.subscribe()
    await bus.publish("multi.event", {"n": 1})
    m1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    m2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert m1["event"] == "multi.event"
    assert m2["event"] == "multi.event"
    await bus.unsubscribe(sub1)
    await bus.unsubscribe(sub2)


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery(bus):
    sub_id, queue = await bus.subscribe()
    await bus.unsubscribe(sub_id)
    await bus.publish("after.unsub", {"ignored": True})
    assert queue.empty()


@pytest.mark.asyncio
async def test_full_queue_drops_oldest(bus):
    sub_id, queue = await bus.subscribe()
    # Fill the queue (max 256)
    for i in range(256):
        await bus.publish("fill", {"i": i})
    # One more should succeed (drops oldest)
    await bus.publish("overflow", {"extra": True})
    # Queue should still have 256 items (oldest dropped, new one added)
    assert queue.qsize() == 256
    await bus.unsubscribe(sub_id)


@pytest.mark.asyncio
async def test_publish_nowait_no_error_outside_loop(bus):
    # publish_nowait should not raise even when event loop handling is odd
    # In a running loop, it should schedule the publish
    sub_id, queue = await bus.subscribe()
    bus.publish_nowait("nowait.event", {"data": 1})
    await asyncio.sleep(0.1)
    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert msg["event"] == "nowait.event"
    await bus.unsubscribe(sub_id)
