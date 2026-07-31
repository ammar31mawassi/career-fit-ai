from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.services import storage


USER_ID = UUID("00000000-0000-0000-0000-000000000803")
OTHER_ID = UUID("00000000-0000-0000-0000-000000000804")


def _supabase_settings():
    return SimpleNamespace(
        supabase_url="https://project.supabase.co",
        supabase_secret_key="sb_secret_test",
        supabase_storage_bucket="profile-documents",
    )


class Response:
    def __init__(self, payload=b"[]"):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit=-1):
        return self.payload if limit < 0 else self.payload[:limit]


def test_supabase_prefix_cleanup_lists_nested_and_unreferenced_objects(monkeypatch):
    requests = []
    deleted = False

    def urlopen(request, timeout):
        nonlocal deleted
        assert timeout == 20
        requests.append(request)
        if request.method == "POST":
            body = json.loads(request.data)
            if deleted:
                return Response()
            if body["prefix"] == str(USER_ID):
                return Response(
                    json.dumps(
                        [
                            {"id": "object-1", "name": "cv.pdf", "metadata": {}},
                            {"id": None, "name": "nested", "metadata": None},
                        ]
                    ).encode()
                )
            assert body["prefix"] == f"{USER_ID}/nested"
            return Response(
                json.dumps(
                    [{"id": "object-2", "name": "unreferenced.pdf", "metadata": {}}]
                ).encode()
            )
        assert request.method == "DELETE"
        deleted = True
        return Response()

    monkeypatch.setattr(storage, "get_settings", _supabase_settings)
    monkeypatch.setattr(storage.urllib.request, "urlopen", urlopen)

    storage.delete_private_user_files(USER_ID)

    delete_requests = [request for request in requests if request.method == "DELETE"]
    assert len(delete_requests) == 1
    assert json.loads(delete_requests[0].data) == {
        "prefixes": [
            f"{USER_ID}/cv.pdf",
            f"{USER_ID}/nested/unreferenced.pdf",
        ]
    }
    assert all(
        path.startswith(f"{USER_ID}/")
        for path in json.loads(delete_requests[0].data)["prefixes"]
    )
    assert [request.method for request in requests] == ["POST", "POST", "DELETE", "POST"]


def test_supabase_prefix_cleanup_rejects_silent_partial_deletion(monkeypatch):
    requests = []

    def urlopen(request, timeout):
        del timeout
        requests.append(request)
        if request.method == "DELETE":
            return Response()
        return Response(
            json.dumps([{"id": "still-present", "name": "orphan.pdf", "metadata": {}}]).encode()
        )

    monkeypatch.setattr(storage, "get_settings", _supabase_settings)
    monkeypatch.setattr(storage.urllib.request, "urlopen", urlopen)

    with pytest.raises(RuntimeError, match="prefix is not empty"):
        storage.delete_private_user_files(USER_ID)

    assert [request.method for request in requests] == ["POST", "DELETE", "POST"]


def test_supabase_prefix_cleanup_rejects_unsafe_listing_before_delete(monkeypatch):
    requests = []

    def urlopen(request, timeout):
        del timeout
        requests.append(request)
        return Response(json.dumps([{"id": "bad", "name": "../other-user.pdf", "metadata": {}}]).encode())

    monkeypatch.setattr(storage, "get_settings", _supabase_settings)
    monkeypatch.setattr(storage.urllib.request, "urlopen", urlopen)

    with pytest.raises(RuntimeError, match="unsafe object name"):
        storage.delete_private_user_files(USER_ID)

    assert [request.method for request in requests] == ["POST"]


def test_single_object_operations_enforce_expected_owner_before_network(monkeypatch):
    monkeypatch.setattr(storage, "get_settings", _supabase_settings)
    monkeypatch.setattr(
        storage.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("cross-user path reached storage network"),
    )

    with pytest.raises(RuntimeError, match="another user's"):
        storage.delete_private_file(
            f"{OTHER_ID}/cv.pdf",
            expected_user_id=USER_ID,
        )
    with pytest.raises(RuntimeError, match="another user's"):
        storage.load_private_file(
            f"{OTHER_ID}/cv.pdf",
            expected_user_id=USER_ID,
        )
