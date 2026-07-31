from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import health, readiness


class _ReadySession:
    def exec(self, _statement):
        return SimpleNamespace(one=lambda: 1)


class _UnavailableSession:
    def exec(self, _statement):
        raise RuntimeError("database hostname and credentials must not leak")


def test_liveness_does_not_depend_on_external_services():
    assert health() == {"status": "ok"}


def test_readiness_checks_database_with_stable_failure_message():
    assert readiness(_ReadySession()) == {"status": "ready"}

    with pytest.raises(HTTPException) as caught:
        readiness(_UnavailableSession())

    assert caught.value.status_code == 503
    assert caught.value.detail == "Database readiness check failed."
