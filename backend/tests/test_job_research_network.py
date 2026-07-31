from __future__ import annotations

import socket
import ssl

import pytest

from app.services import job_research


PUBLIC_IP = "93.184.216.34"


class _FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        body: bytes = b"",
        reason: str = "OK",
    ) -> None:
        self.status = status
        self.headers = headers or {}
        self.reason = reason
        self.body = body
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]

    def close(self) -> None:
        self.closed = True


class _FakeConnection:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.closed = False

    def request(self, method: str, target: str, *, headers: dict[str, str]) -> None:
        self.requests.append((method, target, headers))

    def getresponse(self) -> _FakeResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


def _address_record(host: str, port: int):
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            (host, port),
        )
    ]


def test_fetch_pins_validated_ip_against_public_first_private_second_dns(monkeypatch):
    dns_calls: list[tuple[str, int]] = []

    def rebinding_getaddrinfo(host, port, **kwargs):
        dns_calls.append((host, port))
        if len(dns_calls) == 1:
            return _address_record(PUBLIC_IP, port)
        return _address_record("127.0.0.1", port)

    response = _FakeResponse(
        headers={"content-type": "text/html; charset=utf-8"},
        body=b"<html>public job</html>",
    )
    connections: list[tuple[job_research._PublicUrlTarget, _FakeConnection]] = []

    def connection_for_target(target):
        connection = _FakeConnection(response)
        connections.append((target, connection))
        return connection

    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8888")
    monkeypatch.setattr(job_research.socket, "getaddrinfo", rebinding_getaddrinfo)
    monkeypatch.setattr(job_research, "_connection_for_target", connection_for_target)

    body = job_research._fetch("https://jobs.example/roles/backend?id=42")

    assert body == "<html>public job</html>"
    assert dns_calls == [("jobs.example", 443)]
    target, connection = connections[0]
    assert [address.ip for address in target.addresses] == [PUBLIC_IP]
    assert connection.requests == [
        (
            "GET",
            "/roles/backend?id=42",
            {
                "Host": "jobs.example",
                "User-Agent": job_research.USER_AGENT,
            },
        )
    ]
    assert connection.closed is True


def test_redirect_is_resolved_again_and_private_destination_is_blocked(monkeypatch):
    dns_hosts: list[str] = []

    def redirecting_getaddrinfo(host, port, **kwargs):
        dns_hosts.append(host)
        if host == "jobs.example":
            return _address_record(PUBLIC_IP, port)
        return _address_record("10.0.0.8", port)

    first_response = _FakeResponse(
        status=302,
        reason="Found",
        headers={"location": "http://internal.example/admin"},
    )
    connections: list[_FakeConnection] = []

    def connection_for_target(target):
        connection = _FakeConnection(first_response)
        connections.append(connection)
        return connection

    monkeypatch.setattr(job_research.socket, "getaddrinfo", redirecting_getaddrinfo)
    monkeypatch.setattr(job_research, "_connection_for_target", connection_for_target)

    with pytest.raises(ValueError, match="private or local"):
        job_research._fetch("https://jobs.example/redirect")

    assert dns_hosts == ["jobs.example", "internal.example"]
    assert len(connections) == 1
    assert connections[0].closed is True


def test_public_redirect_uses_a_new_validated_pinned_target(monkeypatch):
    dns_hosts: list[str] = []

    def public_getaddrinfo(host, port, **kwargs):
        dns_hosts.append(host)
        address = PUBLIC_IP if host == "jobs.example" else "142.250.74.14"
        return _address_record(address, port)

    responses = iter(
        [
            _FakeResponse(status=302, headers={"location": "https://careers.example/openings/7"}),
            _FakeResponse(
                headers={"content-type": "text/html"},
                body=b"<html>redirected job</html>",
            ),
        ]
    )
    targets: list[job_research._PublicUrlTarget] = []

    def connection_for_target(target):
        targets.append(target)
        return _FakeConnection(next(responses))

    monkeypatch.setattr(job_research.socket, "getaddrinfo", public_getaddrinfo)
    monkeypatch.setattr(job_research, "_connection_for_target", connection_for_target)

    body = job_research._fetch("https://jobs.example/start")

    assert body == "<html>redirected job</html>"
    assert dns_hosts == ["jobs.example", "careers.example"]
    assert [target.hostname for target in targets] == ["jobs.example", "careers.example"]
    assert [target.addresses[0].ip for target in targets] == [PUBLIC_IP, "142.250.74.14"]


def test_pinned_https_connects_to_ip_but_uses_original_hostname_for_tls(monkeypatch):
    address = job_research._ResolvedAddress(
        family=socket.AF_INET,
        socktype=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
        sockaddr=(PUBLIC_IP, 443),
        ip=PUBLIC_IP,
    )

    class FakeSocket:
        def __init__(self) -> None:
            self.timeout = None
            self.connected_to = None
            self.closed = False

        def settimeout(self, timeout) -> None:
            self.timeout = timeout

        def connect(self, sockaddr) -> None:
            self.connected_to = sockaddr

        def close(self) -> None:
            self.closed = True

    class FakeTlsSocket:
        def close(self) -> None:
            pass

    class FakeContext:
        check_hostname = True
        verify_mode = ssl.CERT_REQUIRED

        def __init__(self) -> None:
            self.raw_socket = None
            self.server_hostname = None

        def wrap_socket(self, raw_socket, *, server_hostname):
            self.raw_socket = raw_socket
            self.server_hostname = server_hostname
            return FakeTlsSocket()

    raw_socket = FakeSocket()
    context = FakeContext()
    monkeypatch.setattr(job_research.socket, "socket", lambda *args: raw_socket)
    monkeypatch.setattr(
        job_research.socket,
        "getaddrinfo",
        lambda *args, **kwargs: pytest.fail("Pinned connection attempted a second DNS lookup."),
    )
    connection = job_research._PinnedHTTPSConnection(
        "jobs.example",
        443,
        (address,),
        timeout=15,
        context=context,
    )

    connection.connect()

    assert raw_socket.connected_to == (PUBLIC_IP, 443)
    assert context.server_hostname == "jobs.example"
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


def test_pinned_https_default_context_verifies_certificates():
    address = job_research._ResolvedAddress(
        family=socket.AF_INET,
        socktype=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
        sockaddr=(PUBLIC_IP, 443),
        ip=PUBLIC_IP,
    )

    connection = job_research._PinnedHTTPSConnection(
        "jobs.example",
        443,
        (address,),
        timeout=15,
    )

    assert connection._context.check_hostname is True
    assert connection._context.verify_mode == ssl.CERT_REQUIRED


@pytest.mark.parametrize(
    ("value", "base_url", "expected"),
    [
        (
            "/apply?source=job#application",
            "https://Jobs.Example:443/openings/7",
            "https://jobs.example/apply?source=job",
        ),
        (
            "HTTPS://CAREERS.EXAMPLE:443/jobs/42#application",
            "",
            "https://careers.example/jobs/42",
        ),
        ("http://careers.example:80", "", "http://careers.example/"),
    ],
)
def test_application_link_is_canonical_absolute_url_without_dns(
    monkeypatch,
    value,
    base_url,
    expected,
):
    monkeypatch.setattr(
        job_research.socket,
        "getaddrinfo",
        lambda *args, **kwargs: pytest.fail("Application-link normalization must not resolve DNS."),
    )

    assert job_research.normalize_application_link(value, base_url=base_url) == expected


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "mailto:jobs@example.com",
        "https://user:secret@careers.example/apply",
        "https://localhost/apply",
        "http://127.0.0.1/apply",
        "https://[::1]/apply",
        "https://careers.example:8443/apply",
        "https://exa mple.com/apply",
        "https://-careers.example/apply",
        "https://internal/apply",
        "https://127.1/apply",
    ],
)
def test_application_link_rejects_unsafe_or_malformed_urls(value):
    assert job_research.normalize_application_link(value) == ""


@pytest.mark.parametrize(
    ("headers", "body", "message"),
    [
        ({"content-type": "application/octet-stream"}, b"binary", "Unsupported content type"),
        (
            {
                "content-type": "text/html",
                "content-length": str(job_research.MAX_FETCH_BYTES + 1),
            },
            b"",
            "too large",
        ),
        (
            {"content-type": "text/html"},
            b"x" * (job_research.MAX_FETCH_BYTES + 1),
            "too large",
        ),
    ],
    ids=["content-type", "declared-size", "streamed-size"],
)
def test_fetch_enforces_content_type_and_size_limits(monkeypatch, headers, body, message):
    response = _FakeResponse(headers=headers, body=body)
    target = job_research._PublicUrlTarget(
        url="https://jobs.example/role",
        parsed=job_research.urllib.parse.urlparse("https://jobs.example/role"),
        hostname="jobs.example",
        port=443,
        addresses=(
            job_research._ResolvedAddress(
                family=socket.AF_INET,
                socktype=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
                sockaddr=(PUBLIC_IP, 443),
                ip=PUBLIC_IP,
            ),
        ),
    )
    monkeypatch.setattr(job_research, "_public_url_target", lambda url: target)
    monkeypatch.setattr(
        job_research,
        "_connection_for_target",
        lambda resolved_target: _FakeConnection(response),
    )

    with pytest.raises(ValueError, match=message):
        job_research._fetch(target.url)

    assert response.closed is True
