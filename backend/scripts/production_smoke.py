from __future__ import annotations

import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[2]
LOCAL_ENV = dotenv_values(ROOT / ".env")
FRONTEND = os.getenv("SMOKE_FRONTEND_URL", "https://career-fit-ai-sigma.vercel.app").rstrip("/")
BACKEND = os.getenv("SMOKE_BACKEND_URL", "https://career-fit-ai-api.vercel.app").rstrip("/")
SUPABASE = str(LOCAL_ENV.get("SUPABASE_URL") or LOCAL_ENV.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
ANON_KEY = str(LOCAL_ENV.get("SUPABASE_ANON_KEY") or LOCAL_ENV.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or "")
SECRET_KEY = str(LOCAL_ENV.get("SUPABASE_SECRET_KEY") or LOCAL_ENV.get("SUPABASE_SERVICE_ROLE_KEY") or "")
INTERNAL_KEY = os.getenv("SMOKE_INTERNAL_KEY", "")
BUCKET = str(LOCAL_ENV.get("SUPABASE_STORAGE_BUCKET") or "profile-documents")


def request(url: str, method: str = "GET", headers: dict[str, str] | None = None, data: bytes | None = None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode()) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:800]
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
    headers = {"apikey": SECRET_KEY}
    if SECRET_KEY.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + SECRET_KEY
    return headers


def main() -> None:
    if not all((SUPABASE, ANON_KEY, SECRET_KEY, INTERNAL_KEY)):
        raise SystemExit("Smoke configuration is incomplete.")
    email = f"smoke-{int(time.time())}-{secrets.token_hex(3)}@example.com"
    password = "Smoke-" + secrets.token_urlsafe(18)
    user_id = ""
    try:
        form = urllib.parse.urlencode({"email": email, "password": password}).encode()
        status, _ = request(FRONTEND + "/auth/signup", "POST", {"Content-Type": "application/x-www-form-urlencoded"}, form)
        print(f"Public signup: {status}")

        status, auth = json_request(
            SUPABASE + "/auth/v1/token?grant_type=password",
            "POST",
            {"email": email, "password": password},
            {"apikey": ANON_KEY},
        )
        user_id = auth["user"]["id"]
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

        status, completed = json_request(BACKEND + "/api/profile/onboarding/complete", "POST", {}, api_headers)
        assert completed["status"] == "ready" and completed["onboarding_completed"] is True
        print(f"Onboarding completion: {status}")

        python_fact = next(
            fact for fact in analysis["profile"]["facts"]
            if fact["fact_type"] == "skill" and fact["value"] == "python"
        )
        status, reviewed = json_request(
            BACKEND + f'/api/profile/facts/{python_fact["id"]}',
            "PATCH",
            {"value": "python", "review_status": "rejected"},
            api_headers,
        )
        assert next(f for f in reviewed["facts"] if f["id"] == python_fact["id"])["review_status"] == "rejected"
        _, reviewed = json_request(
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
            },
            api_headers,
        )
        match = job["match"]
        assert match["model_version"] == "fit-v2.1.0" and match["resume_advice"]["template_id"]
        print(f'Job match: {status}; score={match["score"]}; template={match["resume_advice"]["template_id"]}')

        status, updated = json_request(BACKEND + f'/api/jobs/{job["id"]}/status', "PATCH", {"status": "Applied"}, api_headers)
        assert updated["match"]["status"] == "Applied" and len(updated["match"]["status_history"]) >= 2
        print(f"Application status/history: {status}")
        status, jobs = request(BACKEND + "/api/jobs?query=Smoke", headers=api_headers)
        assert len(jobs) == 1 and jobs[0]["id"] == job["id"]
        print(f"Saved-job search: {status}")
    finally:
        if user_id:
            storage_path = f"{user_id}/cv-smoke-cv.pdf"
            try:
                request(
                    SUPABASE + "/storage/v1/object/" + urllib.parse.quote(BUCKET, safe="") + "/" + urllib.parse.quote(storage_path, safe="/"),
                    "DELETE",
                    admin_headers(),
                )
            except Exception:
                pass
            status, _ = request(SUPABASE + "/auth/v1/admin/users/" + urllib.parse.quote(user_id, safe=""), "DELETE", admin_headers())
            print(f"Test-account cleanup: {status}")


if __name__ == "__main__":
    main()
