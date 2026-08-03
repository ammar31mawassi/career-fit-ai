from __future__ import annotations

import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.matcher import MODEL_VERSION  # noqa: E402


TARGET_ENV = os.getenv("SMOKE_TARGET_ENV", "")
FRONTEND = os.getenv("SMOKE_FRONTEND_URL", "").rstrip("/")
BACKEND = os.getenv("SMOKE_BACKEND_URL", "").rstrip("/")
SUPABASE = os.getenv("SMOKE_SUPABASE_URL", "").rstrip("/")
ANON_KEY = os.getenv("SMOKE_SUPABASE_ANON_KEY", "")
SECRET_KEY = os.getenv("SMOKE_SUPABASE_SECRET_KEY", "")
INTERNAL_KEY = os.getenv("SMOKE_INTERNAL_KEY", "")
BUCKET = os.getenv("SMOKE_STORAGE_BUCKET") or "profile-documents"
EMAIL_DOMAIN = os.getenv("SMOKE_EMAIL_DOMAIN") or "example.com"


def response_payload(raw: bytes, content_type: str | None):
    if not raw:
        return {}
    media_type = (content_type or "").partition(";")[0].strip().lower()
    if media_type == "application/json" or media_type.endswith("+json"):
        return json.loads(raw.decode())
    return {}


def request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
    *,
    accepted_statuses: set[int] | None = None,
):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read()
            if accepted_statuses is not None and response.status not in accepted_statuses:
                path = urllib.parse.urlparse(url).path
                raise RuntimeError(
                    f"Unexpected HTTP {response.status} for {method} {path}."
                )
            return response.status, response_payload(
                raw,
                response.headers.get("Content-Type"),
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        if accepted_statuses is not None and exc.code in accepted_statuses:
            try:
                payload = response_payload(raw, exc.headers.get("Content-Type"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = {}
            return exc.code, payload
        detail = raw.decode("utf-8", errors="ignore")[:800]
        path = urllib.parse.urlparse(url).path
        raise RuntimeError(f"HTTP {exc.code} for {method} {path}: {detail}") from exc


def json_request(url: str, method: str = "GET", payload=None, headers: dict[str, str] | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    return request(url, method, {"Content-Type": "application/json", **(headers or {})}, body)


def pdf_bytes(text: str) -> bytes:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = f"BT /F1 10 Tf 45 760 Td ({safe}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


def multipart_pdf(data: bytes) -> tuple[str, bytes]:
    boundary = "----CareerFitSmoke" + secrets.token_hex(8)
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="smoke-cv.pdf"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return boundary, body


def admin_headers() -> dict[str, str]:
    headers = {"apikey": SECRET_KEY, "User-Agent": "careerfit-staging-smoke/1.0"}
    if SECRET_KEY.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + SECRET_KEY
    return headers


def validate_configuration() -> None:
    if TARGET_ENV != "staging":
        raise SystemExit(
            "Set SMOKE_TARGET_ENV=staging. This destructive synthetic journey "
            "must not run against production."
        )
    if not all((FRONTEND, BACKEND, SUPABASE, ANON_KEY, SECRET_KEY, INTERNAL_KEY)):
        raise SystemExit("Smoke configuration is incomplete.")
    for name, value in (
        ("SMOKE_FRONTEND_URL", FRONTEND),
        ("SMOKE_BACKEND_URL", BACKEND),
        ("SMOKE_SUPABASE_URL", SUPABASE),
    ):
        parsed = urllib.parse.urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise SystemExit(f"{name} must be an absolute HTTPS origin without credentials.")
    if (
        not EMAIL_DOMAIN
        or len(EMAIL_DOMAIN) > 253
        or "/" in EMAIL_DOMAIN
        or "@" in EMAIL_DOMAIN
    ):
        raise SystemExit("SMOKE_EMAIL_DOMAIN is invalid.")


def storage_prefix_is_empty(user_id: str) -> bool:
    quoted_bucket = urllib.parse.quote(BUCKET, safe="")
    _, items = json_request(
        f"{SUPABASE}/storage/v1/object/list/{quoted_bucket}",
        "POST",
        {
            "prefix": user_id,
            "limit": 1,
            "offset": 0,
            "sortBy": {"column": "name", "order": "asc"},
        },
        admin_headers(),
    )
    if not isinstance(items, list):
        raise RuntimeError("Supabase Storage returned an invalid verification listing.")
    return not items


def main() -> None:
    validate_configuration()
    email = f"careerfit-smoke-{int(time.time())}-{secrets.token_hex(3)}@{EMAIL_DOMAIN}"
    password = "Smoke-" + secrets.token_urlsafe(18)
    user_id = ""
    api_headers: dict[str, str] = {}
    try:
        status, _ = request(
            FRONTEND + "/privacy",
            accepted_statuses={200},
        )
        print(f"Public privacy page: {status}")

        status, created = json_request(
            SUPABASE + "/auth/v1/admin/users",
            "POST",
            {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"careerfit_synthetic_smoke": True},
            },
            admin_headers(),
        )
        user_id = str(created["id"])
        print(f"Synthetic staging account creation: {status}")

        status, auth = json_request(
            SUPABASE + "/auth/v1/token?grant_type=password",
            "POST",
            {"email": email, "password": password},
            {"apikey": ANON_KEY},
        )
        api_headers = {
            "Authorization": "Bearer " + auth["access_token"],
            "X-Internal-Api-Key": INTERNAL_KEY,
        }
        print(f"Supabase login: {status}")

        cv = pdf_bytes(
            "B.Sc. in Computer Science student with 2 semesters remaining. Built a Career Fit project using Python FastAPI PostgreSQL React TypeScript. Developed an embedded systems project using C++ Linux. Available full-time in Israel."
        )
        boundary, body = multipart_pdf(cv)
        status, profile = request(
            BACKEND + "/api/profile/cv",
            "POST",
            {**api_headers, "Content-Type": f"multipart/form-data; boundary={boundary}"},
            body,
        )
        assert profile["status"] == "needs_analysis"
        print(f"CV upload: {status}")

        json_request(
            BACKEND + "/api/profile/sources",
            "PUT",
            {"github_url": "", "linkedin_text": "", "manual_info": "Available full-time in Israel with 2 semesters remaining."},
            api_headers,
        )
        json_request(
            BACKEND + "/api/profile/preferences",
            "PUT",
            {"career_interests": ["Software Engineering"]},
            api_headers,
        )
        status, analysis = json_request(BACKEND + "/api/profile/analyze", "POST", {}, api_headers)
        assert analysis["profile"]["status"] == "ready" and analysis["generated_facts"] > 0
        print(f'Profile analysis: {status}; facts={analysis["generated_facts"]}')

        open_questions = [
            question
            for question in analysis["profile"]["questions"]
            if question["status"] == "open"
        ]
        completion_payload = {
            "facts_decision": "skipped",
            "approved_fact_ids": [],
            "rejected_fact_ids": [],
            "question_decision": "skipped" if open_questions else "no_question",
            "question_id": open_questions[0]["id"] if open_questions else None,
            "question_answer": "",
        }
        status, completed = json_request(
            BACKEND + "/api/profile/onboarding/complete",
            "POST",
            completion_payload,
            api_headers,
        )
        assert completed["status"] == "ready" and completed["onboarding_completed"] is True
        print(f"Onboarding completion: {status}")

        python_fact = next(
            fact for fact in analysis["profile"]["facts"]
            if fact["fact_type"] == "skill" and fact["value"].casefold() == "python"
        )
        status, reviewed = json_request(
            BACKEND + f'/api/profile/facts/{python_fact["id"]}',
            "PATCH",
            {"value": "python", "review_status": "rejected"},
            api_headers,
        )
        assert next(f for f in reviewed["facts"] if f["id"] == python_fact["id"])["review_status"] == "rejected"
        status, reviewed = json_request(
            BACKEND + f'/api/profile/facts/{python_fact["id"]}',
            "PATCH",
            {"value": "python", "review_status": "approved"},
            api_headers,
        )
        assert next(f for f in reviewed["facts"] if f["id"] == python_fact["id"])["review_status"] == "approved"
        print(f"Fact reject/confirm feedback: {status}")

        status, job = json_request(
            BACKEND + "/api/jobs",
            "POST",
            {
                "source_url": "",
                "company": "Smoke Co",
                "role": "Backend Student Developer",
                "description_text": "Student role. Requirements: Python, FastAPI, PostgreSQL and React. Preferred: Docker. Location: Israel. Full-time.",
                "contribute_public_posting": False,
            },
            api_headers,
        )
        match = job["match"]
        assert match["model_version"].startswith(MODEL_VERSION)
        assert match["resume_advice"]["template_id"]
        print(f'Job match: {status}; score={match["score"]}; template={match["resume_advice"]["template_id"]}')

        status, updated = json_request(BACKEND + f'/api/jobs/{job["id"]}/status', "PATCH", {"status": "Applied"}, api_headers)
        assert updated["match"]["status"] == "Applied" and len(updated["match"]["status_history"]) >= 2
        print(f"Application status/history: {status}")
        status, jobs = request(BACKEND + "/api/jobs?query=Smoke", headers=api_headers)
        assert len(jobs) == 1 and jobs[0]["id"] == job["id"]
        print(f"Saved-job search: {status}")
    finally:
        if user_id:
            try:
                if not api_headers:
                    if not storage_prefix_is_empty(user_id):
                        raise RuntimeError(
                            "Storage objects exist before an authenticated cleanup path was established."
                        )
                    status, _ = request(
                        SUPABASE
                        + "/auth/v1/admin/users/"
                        + urllib.parse.quote(user_id, safe=""),
                        "DELETE",
                        admin_headers(),
                        accepted_statuses={200, 204, 404},
                    )
                    print(
                        "Synthetic pre-login account cleanup verified: "
                        f"auth-delete={status}; storage=empty"
                    )
                else:
                    status, _ = json_request(
                        BACKEND + "/api/account",
                        "DELETE",
                        {"confirmation": "DELETE"},
                        api_headers,
                    )
                    if status != 204:
                        raise RuntimeError(f"Unexpected account-deletion status {status}.")
                    if not storage_prefix_is_empty(user_id):
                        raise RuntimeError("Synthetic account Storage prefix is not empty.")
                    auth_status, _ = request(
                        SUPABASE
                        + "/auth/v1/admin/users/"
                        + urllib.parse.quote(user_id, safe=""),
                        headers=admin_headers(),
                        accepted_statuses={404},
                    )
                    print(
                        "Synthetic account cleanup verified: "
                        f"backend={status}; auth={auth_status}; storage=empty"
                    )
            except Exception as cleanup_error:
                raise RuntimeError(
                    "Synthetic staging account cleanup failed. Stop promotion and "
                    f"retry deletion for user_id={user_id}."
                ) from cleanup_error


if __name__ == "__main__":
    main()
