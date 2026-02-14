"""Tests for the webhook API endpoints."""
import pytest


def test_health_endpoint(api_client):
    resp = api_client.get("/api/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


def test_settings_requires_auth(api_client):
    resp = api_client.get("/api/settings")
    assert resp.status_code in (401, 403)


def test_providers_requires_auth(api_client):
    resp = api_client.get("/api/providers")
    assert resp.status_code in (401, 403)


def test_sessions_requires_auth(api_client):
    resp = api_client.get("/api/sessions")
    assert resp.status_code in (401, 403)


def test_tasks_requires_auth(api_client):
    resp = api_client.get("/api/tasks")
    assert resp.status_code in (401, 403)


def test_plugins_requires_auth(api_client):
    resp = api_client.get("/api/plugins")
    assert resp.status_code in (401, 403)


def test_webhooks_requires_auth(api_client):
    resp = api_client.get("/api/webhooks")
    assert resp.status_code in (401, 403)
